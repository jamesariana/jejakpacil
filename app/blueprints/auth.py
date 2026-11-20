"""Akun: daftar, verifikasi email, masuk, dan keluar."""

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from ..i18n import _
from ..db import execute, query
from ..forms import is_allowed_email, validate_identity
from ..security import make_verify_token, read_verify_token
from ..utils import is_safe_next

bp = Blueprint("auth", __name__)


def send_verification(email):
    """"Kirim" tautan verifikasi.

    Proyek ini belum punya server email, jadi tautan dicetak di terminal dan
    (selama SHOW_VERIFY_LINK aktif) ditampilkan di halaman. Untuk produksi,
    ganti isi fungsi ini dengan pengiriman email sungguhan, misalnya lewat smtplib.
    """
    link = url_for("auth.verify", token=make_verify_token(email), _external=True)
    if not current_app.testing:
        print(f"\n[JejakPacil] Tautan verifikasi untuk {email}:\n{link}\n", flush=True)
    if current_app.config["SHOW_VERIFY_LINK"]:
        # Markup.format() meng-escape isinya, jadi aman dari sisipan HTML.
        flash(
            Markup(_('Mode pengembangan, belum ada pengiriman email. <a href="{}">Verifikasi akun ini</a>.')).format(link),
            "info",
        )


@bp.route("/daftar", methods=("GET", "POST"))
def register():
    if g.user is not None:
        return redirect(url_for("main.home"))
    errors = {}
    if request.method == "POST":
        data, errors = validate_identity(request.form)
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not is_allowed_email(email):
            errors["email"] = "Pakai email UI kamu, yang berakhiran @ui.ac.id."
        elif query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
            errors["email"] = "Email ini sudah terdaftar. Coba masuk."
        if len(password) < 8:
            errors["password"] = "Kata sandi minimal 8 karakter."
        elif password != request.form.get("password2", ""):
            errors["password2"] = "Ulangi kata sandi yang sama."
        if not errors:
            execute(
                "INSERT INTO users (email, password_hash, full_name, prodi, angkatan, status, grad_year)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email,
                    generate_password_hash(password),  # kata sandi tidak pernah disimpan apa adanya
                    data["full_name"],
                    data["prodi"],
                    data["angkatan"],
                    data["status"],
                    data["grad_year"],
                ),
            )
            flash("Akun dibuat. Verifikasi emailmu dulu, lalu masuk.", "success")
            send_verification(email)
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", errors=errors, form=request.form)


@bp.route("/verifikasi/<token>")
def verify(token):
    email = read_verify_token(token)
    if email is None:
        flash("Tautan verifikasi salah atau sudah kedaluwarsa. Minta tautan baru.", "error")
        return redirect(url_for("auth.resend"))
    execute("UPDATE users SET is_verified = 1 WHERE email = ?", (email,))
    flash("Email terverifikasi. Silakan masuk.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/verifikasi/kirim-ulang", methods=("GET", "POST"))
def resend():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query("SELECT is_verified FROM users WHERE email = ?", (email,), one=True)
        if user is not None and not user["is_verified"]:
            send_verification(email)
        # Pesan sama untuk semua kasus supaya orang lain tidak bisa menebak email siapa yang terdaftar.
        flash("Jika email itu terdaftar dan belum terverifikasi, tautan baru sudah dikirim.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/resend.html")


@bp.route("/masuk", methods=("GET", "POST"))
def login():
    if g.user is not None:
        return redirect(url_for("main.home"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user is None or not check_password_hash(user["password_hash"], request.form.get("password", "")):
            error = "Email atau kata sandi salah."
        elif not user["is_verified"]:
            error = "Emailmu belum diverifikasi. Buka tautan verifikasi, atau minta tautan baru di bawah."
        else:
            lang = session.get("lang")
            session.clear()  # sesi baru setiap kali masuk (mencegah session fixation)
            session["user_id"] = user["id"]
            if lang:
                session["lang"] = lang  # pilihan bahasa tetap dipakai setelah masuk
            target = request.args.get("next", "")
            return redirect(target if is_safe_next(target) else url_for("main.home"))
    return render_template("auth/login.html", error=error, form=request.form)


@bp.route("/keluar", methods=("POST",))
def logout():
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    flash("Kamu sudah keluar.", "success")
    return redirect(url_for("main.home"))
