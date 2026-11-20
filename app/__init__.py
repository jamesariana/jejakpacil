"""JejakPacil: pencatat riwayat magang dan kerja mahasiswa serta alumni Fasilkom UI.

File ini berisi "application factory": fungsi create_app() yang merakit aplikasi
Flask dari bagian-bagiannya (konfigurasi, database, blueprint, template).
"""

import os
import secrets

from flask import Flask, g, render_template

from . import constants, db, i18n, security, utils


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
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # batas ukuran unggahan: 5 MB
        PER_PAGE=12,
        CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Belum ada server email, jadi tautan verifikasi ditampilkan di layar dan terminal.
        # Ubah ke False saat pengiriman email sungguhan sudah dipasang.
        SHOW_VERIFY_LINK=True,
        # Penyedia logo dicoba berurutan; {domain} diganti domain perusahaan.
        LOGO_FETCH_ENABLED=True,
        LOGO_PROVIDERS=[
            "https://logo.hunter.io/{domain}",
            "https://logo.debounce.com/{domain}",
        ],
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or _load_secret_key(app.instance_path)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    app.before_request(security.load_logged_in_user)
    app.before_request(security.check_csrf)

    from .blueprints import admin, auth, companies, experiences, forum, main, profiles, stats
    from .cli import register_commands

    for module in (main, auth, profiles, experiences, companies, forum, stats, admin):
        app.register_blueprint(module.bp)
    app.register_blueprint(i18n.bp)
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
    )
    app.jinja_env.filters.update(
        bulan=utils.format_month,
        tanggal=utils.format_date,
        lalu=utils.time_ago,
        inisial=utils.initials,
        warna=utils.color_for,
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
                    + (SELECT COUNT(*) FROM reports WHERE status = 'baru') AS total""",
            one=True,
        )
        return {"admin_pending": row["total"]}

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
        return error_page(413, i18n._("File terlalu besar"), i18n._("Ukuran unggahan maksimal 5 MB. Perkecil file lalu coba lagi."))

    with app.app_context():
        db.init_db()

    return app
