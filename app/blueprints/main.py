"""Beranda dan penyajian file unggahan."""

import os

from flask import Blueprint, abort, current_app, g, render_template, send_from_directory

from ..db import query
from ..queries import EXP_SELECT, profile_checklist, visibility_sql
from ..security import is_admin

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    """Beranda punya dua tampilan.

    - Belum masuk: penjelasan fitur, cara kerja, dan contoh isi.
    - Sudah masuk: daftar cek kelengkapan profil dan jalan pintas ke fitur.
    """
    vis_sql, vis_params = visibility_sql("e")
    latest = query(
        f"{EXP_SELECT} WHERE {vis_sql} AND c.is_approved = 1 ORDER BY e.start_date DESC, e.id DESC LIMIT 4",
        vis_params,
    )
    top_companies = query(
        """SELECT c.name, c.slug, c.logo, COUNT(DISTINCT e.user_id) AS n_orang
             FROM companies c JOIN experiences e ON e.company_id = c.id AND e.visibility != 'privat'
            WHERE c.is_approved = 1
            GROUP BY c.id ORDER BY n_orang DESC, c.name COLLATE NOCASE LIMIT 8"""
    )

    if g.user is None:
        totals = query(
            """SELECT (SELECT COUNT(*) FROM experiences WHERE visibility != 'privat') AS experiences,
                      (SELECT COUNT(DISTINCT user_id) FROM experiences WHERE visibility != 'privat') AS people,
                      (SELECT COUNT(DISTINCT e.company_id) FROM experiences e
                         JOIN companies c ON c.id = e.company_id
                        WHERE e.visibility != 'privat' AND c.is_approved = 1) AS companies""",
            one=True,
        )
        return render_template("home.html", latest=latest, totals=totals, top_companies=top_companies)

    threads = query(
        """SELECT t.id, t.title, t.created_at, cat.name AS category_name,
                  (SELECT COUNT(*) FROM replies r WHERE r.thread_id = t.id AND r.is_hidden = 0) AS n_replies
             FROM threads t JOIN categories cat ON cat.id = t.category_id
            WHERE t.is_hidden = 0 ORDER BY t.created_at DESC, t.id DESC LIMIT 4"""
    )
    return render_template(
        "home_member.html",
        latest=latest,
        top_companies=top_companies[:5],
        threads=threads,
        checklist=profile_checklist(g.user),
    )


@bp.route("/media/<kind>/<filename>")
def media(kind, filename):
    """Sajikan file unggahan dengan aturan akses per jenis file.

    - logos, photos : terbuka
    - cv            : hanya pengguna yang masuk
    - proofs        : hanya pemilik pengalaman dan admin (bisa berisi dokumen pribadi)
    """
    if kind not in ("logos", "photos", "cv", "proofs"):
        abort(404)
    if kind == "cv" and g.user is None:
        abort(403)
    if kind == "proofs":
        owner = query("SELECT user_id FROM experiences WHERE proof = ?", (filename,), one=True)
        if owner is None:
            abort(404)
        if g.user is None or not (is_admin() or g.user["id"] == owner["user_id"]):
            abort(403)
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], kind)
    # send_from_directory menolak nama file yang mencoba keluar dari folder (mis. ../../rahasia).
    return send_from_directory(folder, filename)
