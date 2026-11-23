"""Ekspor CV: halaman pilihan, file PDF, dan isian tambahan (proyek, organisasi, prestasi, sertifikasi)."""

import os
import re

from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, url_for

from ..cv import build_cv_pdf
from ..constants import CV_ITEMS_MAX, CV_SECTIONS
from ..db import execute, query
from ..forms import validate_cv_item
from ..i18n import _
from ..i18n import LANGUAGES, current_language
from ..queries import EXP_SELECT, user_skills
from ..security import login_required

bp = Blueprint("cv", __name__)

SUMMARY_MAX = 600
ORDER = " ORDER BY (e.end_date IS NULL) DESC, COALESCE(e.end_date, '9999') DESC, e.start_date DESC, e.id DESC"


def _own_experiences(user_id):
    return query(f"{EXP_SELECT} WHERE e.user_id = ?{ORDER}", (user_id,))


def _own_items(user_id):
    """Isian tambahan milik sendiri, dikelompokkan per bagian: {"proyek": [...], ...}."""
    rows = query(
        "SELECT * FROM cv_items WHERE user_id = ?"
        " ORDER BY (end_date IS NULL AND start_date IS NOT NULL) DESC,"
        " COALESCE(end_date, start_date, '') DESC, id DESC",
        (user_id,),
    )
    grouped = {key: [] for key in CV_SECTIONS}
    for row in rows:
        if row["section"] in grouped:
            grouped[row["section"]].append(row)
    return grouped


def _options(form):
    """Baca pilihan dari formulir. Kotak centang yang tidak dicentang memang tidak terkirim."""
    lang = form.get("bahasa")
    return {
        "lang": lang if lang in LANGUAGES else current_language(),
        "summary": (form.get("ringkasan") or "")[:SUMMARY_MAX],
        "show_email": form.get("email") == "1",
        "show_links": form.get("tautan") == "1",
        "show_skills": form.get("skill") == "1",
        "show_photo": form.get("foto") == "1",
    }


@bp.route("/akun/cv")
@login_required
def options():
    experiences = _own_experiences(g.user["id"])
    items = _own_items(g.user["id"])
    return render_template(
        "cv/options.html",
        experiences=experiences,
        items=items,
        item_ids=[i["id"] for group in items.values() for i in group],
        # Bawaan: semua pengalaman yang tidak privat ikut masuk CV.
        checked={e["id"] for e in experiences if e["visibility"] != "privat"},
        summary=g.user["bio"][:SUMMARY_MAX],
        has_links=any(g.user[k] for k in ("linkedin_url", "github_url", "portfolio_url")),
        summary_max=SUMMARY_MAX,
    )


@bp.route("/akun/cv.pdf")
@login_required
def pdf():
    user = g.user
    chosen = {int(i) for i in request.args.getlist("pengalaman") if i.isdigit()}
    # Hanya pengalaman milik sendiri; id milik orang lain diabaikan.
    experiences = [e for e in _own_experiences(user["id"]) if e["id"] in chosen]
    options = _options(request.args)
    photo_path = None
    if options["show_photo"] and user["photo"]:
        photo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "photos", user["photo"])
    chosen_items = {int(i) for i in request.args.getlist("isian") if i.isdigit()}
    items = {key: [i for i in group if i["id"] in chosen_items] for key, group in _own_items(user["id"]).items()}
    data = build_cv_pdf(user, experiences, user_skills(user["id"]), options, photo_path, items=items)
    name = re.sub(r"[^A-Za-z0-9]+", "-", user["full_name"]).strip("-") or "JejakPacil"
    disposition = "inline" if request.args.get("pratinjau") else "attachment"
    response = Response(data, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'{disposition}; filename="CV-{name}.pdf"'
    response.headers["Cache-Control"] = "no-store"
    # Pratinjau ditampilkan di <iframe> halaman sendiri, jadi izinkan bingkai dari asal yang sama.
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


# ---------- Isian tambahan: tambah, ubah, hapus ----------

def _own_item_or_404(item_id):
    item = query("SELECT * FROM cv_items WHERE id = ? AND user_id = ?", (item_id, g.user["id"]), one=True)
    if item is None:
        abort(404)
    return item


def _back_to(section):
    return redirect(url_for("cv.options") + f"#bagian-{section}")


@bp.route("/akun/cv/tambah/<section>", methods=("GET", "POST"))
@login_required
def add_item(section):
    if section not in CV_SECTIONS:
        abort(404)
    count = query("SELECT COUNT(*) AS n FROM cv_items WHERE user_id = ?", (g.user["id"],), one=True)["n"]
    if count >= CV_ITEMS_MAX:
        flash(_("Isian tambahan CV sudah mencapai batas {n}. Hapus yang tidak dipakai dulu.", n=CV_ITEMS_MAX), "error")
        return _back_to(section)
    form, errors = {}, {}
    if request.method == "POST":
        form, errors = validate_cv_item(request.form, section)
        if not errors:
            execute(
                "INSERT INTO cv_items (user_id, section, title, subtitle, start_date, end_date, url, tools, description)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (g.user["id"], section, form["title"], form["subtitle"], form["start_date"], form["end_date"],
                 form["url"], form["tools"], form["description"]),
            )
            flash(_("{label} ditambahkan ke CV.", label=_(CV_SECTIONS[section]["label"])), "success")
            return _back_to(section)
    return render_template("cv/item_form.html", section=section, config=CV_SECTIONS[section], form=form,
                           errors=errors, item=None)


@bp.route("/akun/cv/isian/<int:item_id>/edit", methods=("GET", "POST"))
@login_required
def edit_item(item_id):
    item = _own_item_or_404(item_id)
    section = item["section"]
    form = dict(item)
    form["is_current"] = bool(item["start_date"] and not item["end_date"])
    errors = {}
    if request.method == "POST":
        form, errors = validate_cv_item(request.form, section)
        if not errors:
            execute(
                "UPDATE cv_items SET title = ?, subtitle = ?, start_date = ?, end_date = ?, url = ?, tools = ?,"
                " description = ? WHERE id = ? AND user_id = ?",
                (form["title"], form["subtitle"], form["start_date"], form["end_date"], form["url"],
                 form["tools"], form["description"], item_id, g.user["id"]),
            )
            flash(_("Perubahan disimpan."), "success")
            return _back_to(section)
    return render_template("cv/item_form.html", section=section, config=CV_SECTIONS[section], form=form,
                           errors=errors, item=item)


@bp.route("/akun/cv/isian/<int:item_id>/hapus", methods=("POST",))
@login_required
def delete_item(item_id):
    item = _own_item_or_404(item_id)
    execute("DELETE FROM cv_items WHERE id = ? AND user_id = ?", (item_id, g.user["id"]))
    flash(_("“{title}” dihapus dari CV.", title=item["title"]), "success")
    return _back_to(item["section"])

