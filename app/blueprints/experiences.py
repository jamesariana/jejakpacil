"""Riwayat pengalaman: jelajah, tambah, ubah, hapus."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..i18n import _
from ..constants import EXP_TYPES, PRODI, ROLE_CATEGORIES
from ..db import execute, query
from ..forms import validate_experience
from ..queries import EXP_SELECT, get_or_create_company, set_experience_skills, visibility_sql
from ..security import is_admin, login_required
from ..utils import Page, delete_upload, save_proof, url_with

bp = Blueprint("experiences", __name__)


@bp.route("/pengalaman")
def index():
    """Jelajah semua pengalaman yang boleh dilihat pengunjung, dengan pencarian dan filter."""
    args = request.args
    vis_sql, params = visibility_sql("e")
    where = [vis_sql, "c.is_approved = 1"]
    if args.get("q", "").strip():
        where.append("(e.position LIKE ? OR c.name LIKE ?)")
        like = f"%{args['q'].strip()}%"
        params += [like, like]
    if args.get("jenis") in EXP_TYPES:
        where.append("e.type = ?")
        params.append(args["jenis"])
    if args.get("prodi") in PRODI:
        where.append("u.prodi = ?")
        params.append(args["prodi"])
    if args.get("angkatan", "").isdigit():
        where.append("u.angkatan = ?")
        params.append(int(args["angkatan"]))
    if args.get("skill", "").strip():
        where.append(
            "EXISTS (SELECT 1 FROM experience_skills es JOIN skills s ON s.id = es.skill_id"
            " WHERE es.experience_id = e.id AND s.name LIKE ?)"
        )
        params.append(f"%{args['skill'].strip()}%")
    if args.get("terverifikasi"):
        where.append("e.verification = 'terverifikasi'")
    if args.get("bidang") in ROLE_CATEGORIES:
        where.append("e.role_category = ?")
        params.append(args["bidang"])
    if args.get("cerita"):
        where.append(
            "(e.selection_stages IS NOT NULL OR e.selection_weeks IS NOT NULL OR e.selection_difficulty IS NOT NULL"
            " OR e.selection_questions IS NOT NULL OR e.selection_tips IS NOT NULL)"
        )
    where_sql = " AND ".join(where)

    total = query(
        f"""SELECT COUNT(*) AS n FROM experiences e
              JOIN companies c ON c.id = e.company_id JOIN users u ON u.id = e.user_id
             WHERE {where_sql}""",
        params,
        one=True,
    )["n"]
    page = Page(total)
    experiences = query(
        f"{EXP_SELECT} WHERE {where_sql} ORDER BY e.start_date DESC, e.id DESC LIMIT ? OFFSET ?",
        params + [page.per_page, page.offset],
    )
    angkatan_list = query("SELECT DISTINCT angkatan FROM users WHERE is_verified = 1 ORDER BY angkatan DESC")

    # Skill yang paling sering muncul di pengalaman yang boleh dilihat, untuk pilihan cepat.
    vis_only, vis_params = visibility_sql("e")
    popular_skills = query(
        f"""SELECT s.name, COUNT(*) AS n FROM experience_skills es
              JOIN skills s ON s.id = es.skill_id JOIN experiences e ON e.id = es.experience_id
             WHERE {vis_only} GROUP BY s.id ORDER BY n DESC, s.name COLLATE NOCASE LIMIT 8""",
        vis_params,
    )

    # Filter yang sedang aktif, ditampilkan sebagai label yang bisa dihapus satu per satu.
    active_filters = []
    if args.get("jenis") in EXP_TYPES:
        active_filters.append((EXP_TYPES[args["jenis"]], "jenis"))
    if args.get("prodi") in PRODI:
        active_filters.append((args["prodi"], "prodi"))
    if args.get("angkatan", "").isdigit():
        active_filters.append((_("Angkatan {n}", n=args["angkatan"]), "angkatan"))
    if args.get("skill", "").strip():
        active_filters.append((_("Skill: {name}", name=args["skill"].strip()), "skill"))
    if args.get("bidang") in ROLE_CATEGORIES:
        active_filters.append((ROLE_CATEGORIES[args["bidang"]], "bidang"))
    if args.get("terverifikasi"):
        active_filters.append(("Terverifikasi", "terverifikasi"))
    if args.get("cerita"):
        active_filters.append(("Ada cerita seleksi", "cerita"))
    active_filters = [(label, url_with(**{key: None})) for label, key in active_filters]

    return render_template(
        "experiences/index.html",
        experiences=experiences,
        page=page,
        angkatan_list=angkatan_list,
        popular_skills=popular_skills,
        active_filters=active_filters,
    )


def _company_names():
    """Nama perusahaan yang sudah ada, untuk saran saat mengetik (mencegah nama ganda)."""
    return [row["name"] for row in query("SELECT name FROM companies ORDER BY name COLLATE NOCASE")]


def _get_own_experience(experience_id):
    """Ambil pengalaman dan pastikan yang mengakses adalah pemiliknya (atau admin)."""
    experience = query(f"{EXP_SELECT} WHERE e.id = ?", (experience_id,), one=True)
    if experience is None:
        abort(404)
    if experience["user_id"] != g.user["id"] and not is_admin():
        abort(403)
    return experience


@bp.route("/pengalaman/tambah", methods=("GET", "POST"))
@login_required
def create():
    errors = {}
    if request.method == "POST":
        data, errors = validate_experience(request.form)
        proof = None
        upload = request.files.get("proof")
        if not errors and upload and upload.filename:
            try:
                proof = save_proof(upload)
            except ValueError:
                errors["proof"] = "Bukti harus berupa PDF atau gambar (PNG, JPG, WEBP)."
        if not errors:
            company_id = get_or_create_company(data["company_name"], data["company_website"])
            experience_id = execute(
                """INSERT INTO experiences (user_id, company_id, position, type, start_date, end_date,
                          location, work_mode, description, how_obtained, proof, verification, visibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    g.user["id"], company_id, data["position"], data["type"], data["start_date"],
                    data["end_date"], data["location"], data["work_mode"], data["description"],
                    data["how_obtained"], proof, "menunggu" if proof else "belum", data["visibility"],
                ),
            )
            set_experience_skills(experience_id, data["skills"])
            _save_details(experience_id, data)
            flash("Pengalaman ditambahkan.", "success")
            return redirect(url_for("profiles.detail", user_id=g.user["id"]))
        form = request.form
    else:
        form = {"type": "magang", "work_mode": "onsite", "visibility": "sivitas", "how_obtained": "portal"}
    return render_template(
        "experiences/form.html", form=form, errors=errors, experience=None, company_names=_company_names(),
        selected_stages=_stages_in(form),
    )


@bp.route("/pengalaman/<int:experience_id>/edit", methods=("GET", "POST"))
@login_required
def edit(experience_id):
    experience = _get_own_experience(experience_id)
    errors = {}
    if request.method == "POST":
        data, errors = validate_experience(request.form)
        proof = experience["proof"]
        upload = request.files.get("proof")
        if not errors and upload and upload.filename:
            try:
                proof = save_proof(upload)
            except ValueError:
                errors["proof"] = "Bukti harus berupa PDF atau gambar (PNG, JPG, WEBP)."
        if not errors:
            company_id = get_or_create_company(data["company_name"], data["company_website"])
            # Jika fakta utamanya berubah atau bukti diganti, verifikasi lama tidak berlaku lagi.
            facts_changed = (
                company_id != experience["company_id"]
                or data["position"] != experience["position"]
                or data["type"] != experience["type"]
                or data["start_date"] != experience["start_date"]
                or data["end_date"] != experience["end_date"]
            )
            verification = experience["verification"]
            if proof != experience["proof"] or facts_changed:
                verification = "menunggu" if proof else "belum"
            execute(
                """UPDATE experiences SET company_id = ?, position = ?, type = ?, start_date = ?, end_date = ?,
                          location = ?, work_mode = ?, description = ?, how_obtained = ?, proof = ?,
                          verification = ?, visibility = ?
                    WHERE id = ?""",
                (
                    company_id, data["position"], data["type"], data["start_date"], data["end_date"],
                    data["location"], data["work_mode"], data["description"], data["how_obtained"], proof,
                    verification, data["visibility"], experience_id,
                ),
            )
            set_experience_skills(experience_id, data["skills"])
            _save_details(experience_id, data)
            if proof != experience["proof"]:
                delete_upload("proofs", experience["proof"])
            flash("Pengalaman disimpan.", "success")
            return redirect(url_for("profiles.detail", user_id=experience["user_id"]))
        form = request.form
    else:
        form = dict(experience)
        form["is_current"] = experience["end_date"] is None
        form["end_date"] = experience["end_date"] or ""
        form["skills"] = experience["skills"] or ""
    return render_template(
        "experiences/form.html", form=form, errors=errors, experience=experience, company_names=_company_names(),
        selected_stages=_stages_in(form),
    )


def _stages_in(form):
    """Tahapan seleksi yang sedang dipilih: dari form yang dikirim, atau dari data tersimpan."""
    if hasattr(form, "getlist"):
        return set(form.getlist("selection_stages"))
    return set((form.get("selection_stages") or "").split(","))


def _save_details(experience_id, data):
    """Simpan bidang pekerjaan dan cerita seleksi (terpisah supaya query utama tetap ringkas)."""
    execute(
        """UPDATE experiences SET role_category = ?, selection_stages = ?, selection_weeks = ?,
                  selection_difficulty = ?, selection_questions = ?, selection_tips = ?
            WHERE id = ?""",
        (data["role_category"], data["selection_stages"], data["selection_weeks"], data["selection_difficulty"],
         data["selection_questions"], data["selection_tips"], experience_id),
    )


@bp.route("/pengalaman/<int:experience_id>/hapus", methods=("POST",))
@login_required
def delete(experience_id):
    experience = _get_own_experience(experience_id)
    execute("DELETE FROM experiences WHERE id = ?", (experience_id,))
    delete_upload("proofs", experience["proof"])
    flash("Pengalaman dihapus.", "success")
    return redirect(url_for("profiles.detail", user_id=experience["user_id"]))
