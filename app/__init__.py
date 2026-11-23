"""JejakPacil: pencatat riwayat magang dan kerja mahasiswa serta alumni Fasilkom UI.

File ini berisi "application factory": fungsi create_app() yang merakit aplikasi
Flask dari bagian-bagiannya (konfigurasi, database, blueprint, template).
"""

import os
import secrets

from flask import Flask, current_app, g, render_template, url_for

from . import attachments, constants, db, i18n, notifications, security, utils


# File CSS dan JavaScript, dimuat sesuai urutan daftar ini.
# Urutan CSS penting: aturan di file belakang menimpa aturan di file depan.
CSS_FILES = [
    "01-dasar.css",          # warna, tipografi, tata letak dasar
    "02-komponen.css",       # kartu, tombol, hover, layar kecil
    "03-form.css",           # isian form
    "04-forum.css",          # forum
    "05-tata-letak.css",     # daftar perusahaan, navbar melayang
    "06-mode-gelap.css",     # mode gelap
    "07-palet.css",          # palet biru (terang dan gelap)
    "08-filter.css",         # panel filter Perusahaan dan Jelajahi
    "09-lampiran.css",       # lampiran foto dan PDF
    "10-chat.css",           # chat pribadi
    "11-akun.css",           # kata sandi, notifikasi, menu akun
    "12-cerita-seleksi.css", # bidang pekerjaan dan cerita seleksi
    "13-cv.css",             # buat CV dan halaman cek keaslian
]
JS_FILES = [
    "form.js",        # isian bersyarat, konfirmasi hapus, menu akun
    "navigasi.js",    # pil menu dan mode gelap
    "filter.js",      # filter yang langsung diterapkan
    "lampiran.js",    # pilih lampiran
    "chat.js",        # chat pribadi
    "kata-sandi.js",  # tombol Tampilkan kata sandi
    "notifikasi.js",  # angka di ikon lonceng dan pesan
    "cv.js",          # pratinjau CV yang langsung diperbarui
]


def asset_url(filename):
    """URL file statis dengan ?v=<waktu ubah>, supaya browser langsung memakai versi terbaru."""
    path = os.path.join(current_app.static_folder, filename)
    try:
        version = int(os.path.getmtime(path))
    except OSError:
        version = 0
    return url_for("static", filename=filename, v=version)


def _load_secret_key(instance_path):
    """SECRET_KEY menandatangani sesi login. Dibuat acak sekali, disimpan di luar Git."""
    path = os.path.join(instance_path, "secret_key")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(secrets.token_hex(32))
    with open(path, encoding="utf-8") as file:
        return file.read().strip()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "jejakpacil.sqlite3"),
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MAX_CONTENT_LENGTH=21 * 1024 * 1024,  # batas satu kiriman: 4 lampiran x 5 MB (per file dicek terpisah)
        PER_PAGE=12,
        CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Tanpa server email, tautan verifikasi dan atur ulang kata sandi ditampilkan di layar.
        # Hanya untuk laptop sendiri: di website online set False (lihat config.example.py).
        SHOW_DEV_LINKS=True,
        # Pengiriman email (lihat mailer.py). Kosong berarti email tidak dikirim.
        MAIL_SERVER="",
        MAIL_PORT=587,
        MAIL_USERNAME="",
        MAIL_PASSWORD="",
        MAIL_SENDER="",
        # True kalau aplikasi berjalan di belakang proxy (misalnya PythonAnywhere), supaya
        # alamat IP pengunjung dan https terbaca benar.
        BEHIND_PROXY=False,
        # Penyedia logo dicoba berurutan; {domain} diganti domain perusahaan.
        LOGO_FETCH_ENABLED=True,
        LOGO_PROVIDERS=[
            "https://logo.hunter.io/{domain}",
            "https://logo.debounce.com/{domain}",
        ],
    )
    if test_config:
        app.config.update(test_config)
    else:
        # Pengaturan server (kata sandi email, dsb.) di instance/config.py, tidak masuk Git.
        app.config.from_pyfile("config.py", silent=True)
    if app.config["BEHIND_PROXY"]:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or _load_secret_key(app.instance_path)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    app.before_request(security.load_logged_in_user)
    app.before_request(security.check_csrf)

    from .blueprints import admin, auth, companies, cv, experiences, forum, main, messages, profiles, stats
    from .cli import register_commands

    for module in (main, auth, profiles, experiences, companies, forum, messages, stats, admin, cv):
        app.register_blueprint(module.bp)
    app.register_blueprint(i18n.bp)
    app.register_blueprint(notifications.bp)
    register_commands(app)

    # Fungsi dan data yang bisa dipakai langsung di semua template.
    app.jinja_env.globals.update(
        csrf_token=security.csrf_token,
        media_url=utils.media_url,
        page_url=utils.page_url,
        url_with=utils.url_with,
        periode=utils.format_period,
        durasi=utils.format_duration,
        C=constants,
        _=i18n.translate,
        current_language=i18n.current_language,
        jumlah=i18n.count,
        LANGUAGES=i18n.LANGUAGES,
        asset_url=asset_url,
        CSS_FILES=CSS_FILES,
        JS_FILES=JS_FILES,
    )
    app.jinja_env.filters.update(
        bulan=utils.format_month,
        tanggal=utils.format_date,
        lalu=utils.time_ago,
        inisial=utils.initials,
        warna=utils.color_for,
        jam=utils.format_clock,
        singkat=utils.short_when,
        ukuran=attachments.human_size,
        t=i18n.translate,  # untuk nilai dari data: {{ label|t }}
    )

    @app.context_processor
    def inject_admin_counts():
        """Jumlah pekerjaan admin yang menunggu, untuk penanda di menu."""
        if not security.is_admin():
            return {"admin_pending": 0}
        row = db.query(
            """SELECT (SELECT COUNT(*) FROM experiences WHERE verification = 'menunggu')
                    + (SELECT COUNT(*) FROM companies WHERE is_approved = 0)
                    + (SELECT COUNT(*) FROM reports WHERE status = 'baru')
                    + (SELECT COUNT(*) FROM message_reports WHERE status = 'baru') AS total""",
            one=True,
        )
        return {"admin_pending": row["total"]}

    @app.context_processor
    def inject_unread_messages():
        """Jumlah pesan belum dibaca, untuk angka di ikon pesan di navbar."""
        if g.user is None:
            return {"unread_messages": 0, "unread_notifications": 0}
        return {
            "unread_messages": messages.unread_count(g.user["id"]),
            "unread_notifications": notifications.unread_count(g.user["id"]),
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def error_page(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(error):
        return error_page(400, i18n._("Permintaan tidak bisa diproses"), i18n._(error.description))

    @app.errorhandler(403)
    def forbidden(error):
        return error_page(403, i18n._("Halaman ini bukan untukmu"), i18n._("Akunmu tidak punya akses ke halaman ini."))

    @app.errorhandler(404)
    def not_found(error):
        return error_page(404, i18n._("Halaman tidak ditemukan"), i18n._("Periksa alamatnya, atau kembali ke beranda."))

    @app.errorhandler(413)
    def too_large(error):
        return error_page(413, i18n._("File terlalu besar"), i18n._("Ukuran maksimal 5 MB per file dan 20 MB sekali kirim. Perkecil file lalu coba lagi."))

    @app.errorhandler(500)
    def server_error(error):
        # Detail galat tidak ditampilkan ke pengunjung; tercatat di log server.
        return error_page(500, i18n._("Ada yang salah di server"), i18n._("Bukan salahmu. Coba muat ulang halaman sebentar lagi."))

    with app.app_context():
        db.init_db()

    return app
