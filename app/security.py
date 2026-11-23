"""Keamanan: sesi login, pembatasan akses, token CSRF, token email, dan pembatas percobaan."""

import functools
import hashlib
import secrets

from flask import abort, current_app, flash, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .db import execute, query


def password_stamp(password_hash):
    """Sidik pendek dari hash kata sandi, disimpan di sesi saat masuk.

    Begitu kata sandi diganti, sidiknya berubah, sehingga sesi lama di perangkat
    lain (misalnya laptop yang lupa logout) otomatis tidak berlaku lagi.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def start_session(user):
    """Mulai sesi baru untuk pengguna yang berhasil masuk."""
    lang = session.get("lang")
    session.clear()  # sesi baru setiap kali masuk (mencegah session fixation)
    session["user_id"] = user["id"]
    session["stamp"] = password_stamp(user["password_hash"])
    if lang:
        session["lang"] = lang  # pilihan bahasa tetap dipakai setelah masuk


def load_logged_in_user():
    """Dijalankan sebelum setiap request: isi g.user dari id yang tersimpan di sesi."""
    user_id = session.get("user_id")
    g.user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True) if user_id else None
    stamp = session.get("stamp")
    if g.user is not None and stamp and stamp != password_stamp(g.user["password_hash"]):
        # Kata sandi sudah diganti di perangkat lain: sesi ini tidak berlaku lagi.
        session.pop("user_id", None)
        session.pop("stamp", None)
        g.user = None


def is_admin():
    return g.user is not None and g.user["role"] == "admin"


def login_required(view):
    """Decorator: halaman hanya bisa dibuka setelah masuk."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Masuk dulu untuk membuka halaman itu.", "info")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Decorator: halaman hanya untuk admin."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)

    return wrapped


# ---------- CSRF ----------
# Setiap form POST membawa token rahasia yang juga disimpan di sesi. Situs lain
# tidak tahu token ini, jadi tidak bisa mengirim form atas nama pengguna.

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def check_csrf():
    """Dijalankan sebelum setiap request: tolak POST tanpa token yang cocok."""
    if request.method != "POST" or not current_app.config["CSRF_ENABLED"]:
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    if not sent or not expected or not secrets.compare_digest(sent, expected):
        abort(400, description="Sesi form sudah kedaluwarsa. Muat ulang halaman lalu coba lagi.")


# ---------- Token verifikasi email ----------

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="verifikasi-email")


def make_verify_token(email):
    """Token bertanda tangan: isinya email, tidak bisa dipalsukan tanpa SECRET_KEY."""
    return _serializer().dumps(email)


def read_verify_token(token, max_age=60 * 60 * 24):
    """Kembalikan email di dalam token, atau None jika token salah/kedaluwarsa (24 jam)."""
    try:
        return _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


# ---------- Token atur ulang kata sandi ----------
# Isinya id pengguna dan sidik kata sandinya saat ini. Setelah kata sandi diganti,
# sidiknya berubah, jadi tautan yang sama tidak bisa dipakai dua kali.

RESET_MAX_AGE = 60 * 60  # 1 jam


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="atur-ulang-sandi")


def make_reset_token(user):
    return _reset_serializer().dumps([user["id"], password_stamp(user["password_hash"])])


def read_reset_token(token):
    """Kembalikan pengguna pemilik token, atau None jika token salah, kedaluwarsa, atau sudah dipakai."""
    try:
        user_id, stamp = _reset_serializer().loads(token, max_age=RESET_MAX_AGE)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
    user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user is None or password_stamp(user["password_hash"]) != stamp:
        return None
    return user


# ---------- Pembatas percobaan ----------
# Mencegah orang menebak kata sandi berkali-kali. Setiap percobaan gagal dicatat;
# kalau dalam jangka waktu tertentu sudah terlalu banyak, permintaan berikutnya ditolak.

LOGIN_LIMIT_PER_EMAIL = 5   # gagal per email dalam 15 menit
LOGIN_LIMIT_PER_IP = 20     # gagal per alamat IP dalam 15 menit
RESET_LIMIT_PER_IP = 5      # permintaan tautan lupa sandi per IP dalam 15 menit
WINDOW_MINUTES = 15


def client_ip():
    return request.remote_addr or "tidak-diketahui"


def record_attempt(kind, key):
    execute("INSERT INTO rate_limits (kind, key) VALUES (?, ?)", (kind, key))


def clear_attempts(kind, key):
    execute("DELETE FROM rate_limits WHERE kind = ? AND key = ?", (kind, key))


def minutes_until_allowed(kind, key, limit, window=WINDOW_MINUTES):
    """0 kalau masih boleh mencoba; selain itu berapa menit lagi sampai boleh."""
    rows = query(
        f"""SELECT created_at FROM rate_limits
             WHERE kind = ? AND key = ? AND created_at > datetime('now', '-{int(window)} minutes')
             ORDER BY created_at""",
        (kind, key),
    )
    if len(rows) < limit:
        return 0
    # Boleh lagi saat percobaan tertua (yang membuat batas terlampaui) keluar dari jendela waktu.
    oldest = rows[len(rows) - limit]["created_at"]
    row = query(
        f"SELECT CAST((julianday(?, '+{int(window)} minutes') - julianday('now')) * 1440 AS INTEGER) + 1 AS m",
        (oldest,),
        one=True,
    )
    return max(1, row["m"])


def prune_attempts():
    """Buang catatan lama supaya tabel tidak terus membesar."""
    execute("DELETE FROM rate_limits WHERE created_at < datetime('now', '-1 day')")

