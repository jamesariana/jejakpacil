"""Keamanan: sesi login, pembatasan akses, token CSRF, dan token verifikasi email."""

import functools
import secrets

from flask import abort, current_app, flash, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .db import query


def load_logged_in_user():
    """Dijalankan sebelum setiap request: isi g.user dari id yang tersimpan di sesi."""
    user_id = session.get("user_id")
    g.user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True) if user_id else None


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
