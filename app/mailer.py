"""Pengiriman email lewat SMTP (misalnya Gmail).

Diatur di instance/config.py (lihat config.example.py):

    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USERNAME = "akunmu@gmail.com"
    MAIL_PASSWORD = "sandi aplikasi 16 huruf"   # bukan kata sandi Gmail biasa
    MAIL_SENDER = "JejakPacil <akunmu@gmail.com>"

Kalau MAIL_SERVER kosong, email tidak dikirim. Selama SHOW_DEV_LINKS aktif, tautannya
ditampilkan di layar sebagai gantinya (lihat blueprints/auth.py).
"""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def mail_enabled():
    return bool(current_app.config.get("MAIL_SERVER"))


def send_mail(to, subject, body):
    """Kirim email teks biasa. Mengembalikan True kalau terkirim, False kalau gagal atau belum diatur."""
    config = current_app.config
    if not mail_enabled():
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.get("MAIL_SENDER") or config.get("MAIL_USERNAME")
    message["To"] = to
    message.set_content(body)
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config.get("MAIL_PORT", 587), timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as error:
        current_app.logger.error("Gagal mengirim email ke %s: %s", to, error)
        return False
