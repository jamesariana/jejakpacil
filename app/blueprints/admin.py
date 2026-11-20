"""Panel admin: verifikasi pengalaman, kelola perusahaan, moderasi forum, pengguna, ekspor."""

import csv
import io

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from ..i18n import _
from ..constants import INDUSTRIES
from .. import attachments
from ..db import execute, get_db, query
from ..logos import fetch_logo
from ..queries import EXP_SELECT
from ..security import admin_required
from ..utils import clean_domain, delete_upload, save_image, valid_url

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    counts = query(
        """SELECT (SELECT COUNT(*) FROM experiences WHERE verification = 'menunggu') AS experiences,
                  (SELECT COUNT(*) FROM companies WHERE is_approved = 0) AS companies,
                  (SELECT COUNT(*) FROM reports WHERE status = 'baru')
                  + (SELECT COUNT(*) FROM message_reports WHERE status = 'baru') AS reports,
                  (SELECT COUNT(*) FROM users) AS users""",
        one=True,
    )
    return render_template("admin/dashboard.html", counts=counts)


# ---------- Verifikasi pengalaman ----------

@bp.route("/pengalaman")
@admin_required
def experiences():
    pending = query(f"{EXP_SELECT} WHERE e.verification = 'menunggu' ORDER BY e.created_at, e.id")
    return render_template("admin/experiences.html", pending=pending)


@bp.route("/pengalaman/<int:experience_id>/putuskan", methods=("POST",))
@admin_required
def decide_experience(experience_id):
    decision = request.form.get("decision")
    if decision not in ("terverifikasi", "ditolak"):
        abort(400, description="Keputusan tidak dikenal.")
    execute("UPDATE experiences SET verification = ? WHERE id = ?", (decision, experience_id))
    flash("Pengalaman diverifikasi." if decision == "terverifikasi" else "Bukti ditolak.", "success")
    return redirect(url_for("admin.experiences"))


# ---------- Perusahaan ----------

@bp.route("/perusahaan")
@admin_required
def companies():
    rows = query(
        """SELECT c.*, (SELECT COUNT(*) FROM experiences e WHERE e.company_id = c.id) AS n_exp,
                  u.full_name AS creator
             FROM companies c LEFT JOIN users u ON u.id = c.created_by
            ORDER BY c.is_approved, c.name COLLATE NOCASE"""
    )
    return render_template("admin/companies.html", companies=rows)


@bp.route("/perusahaan/<int:company_id>/setujui", methods=("POST",))
@admin_required
def approve_company(company_id):
    execute("UPDATE companies SET is_approved = 1 WHERE id = ?", (company_id,))
    flash("Perusahaan disetujui dan sekarang tampil di direktori.", "success")
    return redirect(url_for("admin.companies"))


@bp.route("/perusahaan/<int:company_id>/edit", methods=("GET", "POST"))
@admin_required
def edit_company(company_id):
    company = query("SELECT * FROM companies WHERE id = ?", (company_id,), one=True)
    if company is None:
        abort(404)
    errors = {}
    if request.method == "POST":
        form = request.form
        name = " ".join(form.get("name", "").split())[:80]
        website = form.get("website", "").strip()[:200]
        domain = clean_domain(form.get("domain", ""))
        industry = form.get("industry", "")
        description = form.get("description", "").strip()[:1000]
        if len(name) < 2:
            errors["name"] = "Isi nama perusahaan."
        elif query("SELECT 1 FROM companies WHERE name = ? AND id != ?", (name, company_id), one=True):
            errors["name"] = "Nama ini sudah dipakai perusahaan lain. Gabungkan saja keduanya."
        if website and not valid_url(website):
            errors["website"] = "Website harus diawali http:// atau https://."
        if form.get("domain", "").strip() and not domain:
            errors["domain"] = "Isi domain saja, misalnya tokopedia.com."
        if industry not in INDUSTRIES:
            errors["industry"] = "Pilih industri."

        logo = company["logo"]
        upload = request.files.get("logo")
        if not errors and upload and upload.filename:
            try:
                logo = save_image(upload, "logos", max_size=(256, 256))
            except ValueError as error:
                errors["logo"] = str(error)
        if not errors and form.get("remove_logo"):
            logo = None
        if not errors:
            execute(
                """UPDATE companies SET name = ?, website = ?, domain = ?, industry = ?, description = ?,
                          logo = ?, is_approved = ? WHERE id = ?""",
                (name, website, domain, industry, description, logo, 1 if form.get("is_approved") else 0,
                 company_id),
            )
            if logo != company["logo"]:
                delete_upload("logos", company["logo"])
            flash("Perusahaan disimpan.", "success")
            return redirect(url_for("admin.companies"))
    else:
        form = dict(company)
    return render_template(
        "admin/company_form.html", company=company, form=form, errors=errors
    )


@bp.route("/perusahaan/<int:company_id>/logo-otomatis", methods=("POST",))
@admin_required
def auto_logo(company_id):
    """Ambil logo dari layanan logo berdasarkan domain perusahaan."""
    company = query("SELECT * FROM companies WHERE id = ?", (company_id,), one=True)
    if company is None:
        abort(404)
    if not company["domain"]:
        flash("Isi domain perusahaan dulu, misalnya tokopedia.com.", "error")
        return redirect(url_for("admin.edit_company", company_id=company_id))
    logo = fetch_logo(company["domain"])
    if logo is None:
        flash("Logo tidak ditemukan untuk domain itu. Periksa koneksi internet, atau unggah logo sendiri.", "error")
    else:
        execute("UPDATE companies SET logo = ? WHERE id = ?", (logo, company_id))
        delete_upload("logos", company["logo"])
        flash("Logo diperbarui.", "success")
    return redirect(url_for("admin.edit_company", company_id=company_id))


@bp.route("/perusahaan/gabung", methods=("POST",))
@admin_required
def merge_companies():
    """Gabungkan perusahaan ganda: semua pengalaman dan thread pindah ke perusahaan tujuan."""
    source_id = request.form.get("source_id", "")
    target_id = request.form.get("target_id", "")
    if not (source_id.isdigit() and target_id.isdigit()) or source_id == target_id:
        flash("Pilih dua perusahaan yang berbeda.", "error")
        return redirect(url_for("admin.companies"))
    source = query("SELECT * FROM companies WHERE id = ?", (int(source_id),), one=True)
    target = query("SELECT * FROM companies WHERE id = ?", (int(target_id),), one=True)
    if source is None or target is None:
        abort(404)
    # Tiga perubahan ini harus berhasil semua atau gagal semua, jadi di-commit sekali di akhir.
    db = get_db()
    db.execute("UPDATE experiences SET company_id = ? WHERE company_id = ?", (target["id"], source["id"]))
    db.execute("UPDATE threads SET company_id = ? WHERE company_id = ?", (target["id"], source["id"]))
    db.execute("DELETE FROM companies WHERE id = ?", (source["id"],))
    db.commit()
    delete_upload("logos", source["logo"])
    flash(_("{a} digabung ke {b}.", a=source["name"], b=target["name"]), "success")
    return redirect(url_for("admin.companies"))


# ---------- Moderasi forum ----------

@bp.route("/laporan")
@admin_required
def reports():
    rows = query(
        """SELECT rp.*, reporter.full_name AS reporter_name,
                  COALESCE(rp.thread_id, r.thread_id) AS target_thread_id,
                  t.title AS thread_title, t.is_hidden AS thread_hidden, t.is_pinned AS thread_pinned,
                  r.body AS reply_body, r.is_hidden AS reply_hidden,
                  author.full_name AS author_name
             FROM reports rp
             JOIN users reporter ON reporter.id = rp.reporter_id
             LEFT JOIN replies r ON r.id = rp.reply_id
             LEFT JOIN threads t ON t.id = COALESCE(rp.thread_id, r.thread_id)
             LEFT JOIN users author ON author.id = COALESCE(r.author_id, t.author_id)
            WHERE rp.status = 'baru' ORDER BY rp.created_at, rp.id"""
    )
    # Laporan chat: admin hanya melihat pesan yang dilaporkan, bukan seluruh percakapan.
    message_rows = query(
        """SELECT mr.*, reporter.full_name AS reporter_name, sender.full_name AS sender_name,
                  m.body AS message_body, m.is_hidden AS message_hidden
             FROM message_reports mr
             JOIN users reporter ON reporter.id = mr.reporter_id
             JOIN messages m ON m.id = mr.message_id
             JOIN users sender ON sender.id = m.sender_id
            WHERE mr.status = 'baru' ORDER BY mr.created_at, mr.id"""
    )
    files = attachments.for_owners("message_id", [row["message_id"] for row in message_rows])
    message_reports = [dict(row, files=files.get(row["message_id"], [])) for row in message_rows]
    return render_template("admin/reports.html", reports=rows, message_reports=message_reports)


@bp.route("/laporan-pesan/<int:report_id>/tindak", methods=("POST",))
@admin_required
def resolve_message_report(report_id):
    report = query("SELECT * FROM message_reports WHERE id = ?", (report_id,), one=True)
    if report is None:
        abort(404)
    if request.form.get("action") == "sembunyikan":
        execute("UPDATE messages SET is_hidden = 1 WHERE id = ?", (report["message_id"],))
        flash("Konten disembunyikan dan laporan ditutup.", "success")
    else:
        flash("Laporan ditutup tanpa tindakan.", "success")
    execute("UPDATE message_reports SET status = 'selesai' WHERE id = ?", (report_id,))
    return redirect(url_for("admin.reports"))


@bp.route("/laporan/<int:report_id>/tindak", methods=("POST",))
@admin_required
def resolve_report(report_id):
    report = query("SELECT * FROM reports WHERE id = ?", (report_id,), one=True)
    if report is None:
        abort(404)
    if request.form.get("action") == "sembunyikan":
        if report["reply_id"]:
            execute("UPDATE replies SET is_hidden = 1 WHERE id = ?", (report["reply_id"],))
        else:
            execute("UPDATE threads SET is_hidden = 1 WHERE id = ?", (report["thread_id"],))
        flash("Konten disembunyikan dan laporan ditutup.", "success")
    else:
        flash("Laporan ditutup tanpa tindakan.", "success")
    execute("UPDATE reports SET status = 'selesai' WHERE id = ?", (report_id,))
    return redirect(url_for("admin.reports"))


@bp.route("/thread/<int:thread_id>/<action>", methods=("POST",))
@admin_required
def moderate_thread(thread_id, action):
    """Sematkan/lepas semat atau sembunyikan/tampilkan sebuah thread."""
    column = {"semat": "is_pinned", "sembunyi": "is_hidden"}.get(action)
    if column is None:
        abort(404)
    execute(f"UPDATE threads SET {column} = 1 - {column} WHERE id = ?", (thread_id,))
    flash("Thread diperbarui.", "success")
    return redirect(url_for("forum.thread", thread_id=thread_id))


# ---------- Pengguna ----------

@bp.route("/pengguna")
@admin_required
def users():
    rows = query("SELECT * FROM users ORDER BY created_at DESC, id DESC")
    return render_template("admin/users.html", users=rows)


@bp.route("/pengguna/<int:user_id>/<action>", methods=("POST",))
@admin_required
def update_user(user_id, action):
    user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user is None:
        abort(404)
    if action == "verifikasi":
        execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
        flash(_("Email {name} ditandai terverifikasi.", name=user["full_name"]), "success")
    elif action == "peran":
        if user_id == g.user["id"]:
            flash("Kamu tidak bisa mengubah peranmu sendiri.", "error")
        else:
            new_role = "member" if user["role"] == "admin" else "admin"
            execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
            flash(_("Peran {name} sekarang {role}.", name=user["full_name"], role=_(new_role)), "success")
    else:
        abort(404)
    return redirect(url_for("admin.users"))


# ---------- Ekspor ----------

def _csv_safe(value):
    """Cegah "CSV injection": sel yang diawali = + - @ bisa dijalankan Excel sebagai rumus."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@bp.route("/ekspor.csv")
@admin_required
def export_csv():
    rows = query(f"{EXP_SELECT} ORDER BY u.full_name COLLATE NOCASE, e.start_date DESC")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "nama", "prodi", "angkatan", "status", "perusahaan", "posisi", "jenis", "mulai", "selesai",
        "lokasi", "cara_kerja", "cara_mendapatkan", "skill", "verifikasi", "visibilitas",
    ])
    for row in rows:
        writer.writerow([_csv_safe(value) for value in (
            row["full_name"], row["prodi"], row["angkatan"], row["user_status"], row["company_name"],
            row["position"], row["type"], row["start_date"], row["end_date"] or "sekarang",
            row["location"], row["work_mode"], row["how_obtained"], row["skills"] or "",
            row["verification"], row["visibility"],
        )])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pengalaman-jejakpacil.csv"},
    )
