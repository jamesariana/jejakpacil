"""Akun: daftar, verifikasi email, masuk, keluar, lupa kata sandi, dan ganti kata sandi."""

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from ..i18n import _
from ..db import execute, query
from ..forms import is_allowed_email, validate_identity, validate_new_password
from ..security import (
    LOGIN_LIMIT_PER_EMAIL, LOGIN_LIMIT_PER_IP, RESET_LIMIT_PER_IP, RESET_MAX_AGE,
    clear_attempts, client_ip, login_required, make_reset_token, make_verify_token, minutes_until_allowed,
    password_stamp, prune_attempts, read_reset_token, read_verify_token, record_attempt, start_session,
)
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
        errors.update(validate_new_password(password, request.form.get("password2", ""), email))
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
        ip = client_ip()
        # Batasi tebak-tebakan: 5 kali gagal per email atau 20 kali per IP dalam 15 menit.
        wait = max(
            minutes_until_allowed("login-gagal", email, LOGIN_LIMIT_PER_EMAIL),
            minutes_until_allowed("login-gagal-ip", ip, LOGIN_LIMIT_PER_IP),
        )
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True) if not wait else None
        if wait:
            error = _("Terlalu banyak percobaan masuk yang gagal. Coba lagi dalam {n} menit, atau atur ulang kata sandimu.", n=wait)
        elif user is None or not check_password_hash(user["password_hash"], request.form.get("password", "")):
            record_attempt("login-gagal", email)
            record_attempt("login-gagal-ip", ip)
            error = "Email atau kata sandi salah."
        elif not user["is_verified"]:
            error = "Emailmu belum diverifikasi. Buka tautan verifikasi, atau minta tautan baru di bawah."
        else:
            clear_attempts("login-gagal", email)
            prune_attempts()
            start_session(user)
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


# ---------- Lupa dan ganti kata sandi ----------

def send_reset_link(user):
    """"Kirim" tautan atur ulang kata sandi (berlaku 1 jam, sekali pakai).

    Sama seperti verifikasi: tanpa server email, tautan dicetak di terminal dan,
    selama SHOW_VERIFY_LINK aktif, ditampilkan di halaman.
    """
    link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
    if not current_app.testing:
        print(f"\n[JejakPacil] Tautan atur ulang kata sandi untuk {user['email']}:\n{link}\n", flush=True)
    if current_app.config["SHOW_VERIFY_LINK"]:
        flash(
            Markup(_('Mode pengembangan, belum ada pengiriman email. <a href="{}">Atur ulang kata sandi</a>.')).format(link),
            "info",
        )


@bp.route("/lupa-kata-sandi", methods=("GET", "POST"))
def forgot_password():
    if request.method == "POST":
        ip = client_ip()
        wait = minutes_until_allowed("lupa-sandi", ip, RESET_LIMIT_PER_IP)
        if wait:
            flash(_("Terlalu banyak permintaan. Coba lagi dalam {n} menit.", n=wait), "error")
            return redirect(url_for("auth.forgot_password"))
        record_attempt("lupa-sandi", ip)
        email = request.form.get("email", "").strip().lower()
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user is not None:
            send_reset_link(user)
        # Pesan sama untuk semua kasus supaya orang lain tidak bisa menebak email siapa yang terdaftar.
        flash("Jika email itu terdaftar, tautan untuk mengatur ulang kata sandi sudah dikirim. Tautan berlaku 1 jam.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", minutes=RESET_MAX_AGE // 60)


@bp.route("/atur-ulang-kata-sandi/<token>", methods=("GET", "POST"))
def reset_password(token):
    user = read_reset_token(token)
    if user is None:
        flash("Tautan atur ulang kata sandi salah, kedaluwarsa, atau sudah dipakai. Minta tautan baru.", "error")
        return redirect(url_for("auth.forgot_password"))
    errors = {}
    if request.method == "POST":
        password = request.form.get("password", "")
        errors = validate_new_password(password, request.form.get("password2", ""), user["email"])
        if not errors:
            # Membuka tautan dari email juga membuktikan pemilik email, jadi akun ikut terverifikasi.
            execute(
                "UPDATE users SET password_hash = ?, is_verified = 1 WHERE id = ?",
                (generate_password_hash(password), user["id"]),
            )
            clear_attempts("login-gagal", user["email"])
            flash("Kata sandi baru tersimpan. Silakan masuk dengan kata sandi itu.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", errors=errors, email=user["email"])


@bp.route("/akun/kata-sandi", methods=("GET", "POST"))
@login_required
def change_password():
    errors = {}
    if request.method == "POST":
        if not check_password_hash(g.user["password_hash"], request.form.get("current", "")):
            errors["current"] = "Kata sandi saat ini salah."
        password = request.form.get("password", "")
        errors.update(validate_new_password(password, request.form.get("password2", ""), g.user["email"]))
        if not errors and check_password_hash(g.user["password_hash"], password):
            errors["password"] = "Kata sandi baru harus berbeda dari yang sekarang."
        if not errors:
            new_hash = generate_password_hash(password)
            execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, g.user["id"]))
            # Perbarui sidik di sesi ini supaya tetap masuk; sesi di perangkat lain otomatis keluar.
            session["stamp"] = password_stamp(new_hash)
            flash("Kata sandi diganti. Kamu otomatis keluar dari perangkat lain.", "success")
            return redirect(url_for("profiles.edit"))
    return render_template("auth/password.html", errors=errors)

