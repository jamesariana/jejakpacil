"""Profil mahasiswa/alumni dan direktori orang."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..constants import PRODI, STATUS
from ..db import execute, query
from ..forms import validate_availability, validate_identity, validate_links
from ..queries import EXP_SELECT, parse_skills, profile_checklist, set_user_skills, user_skills, visibility_sql
from ..security import login_required
from ..utils import Page, delete_upload, save_image, save_pdf

bp = Blueprint("profiles", __name__)


@bp.route("/mahasiswa")
@login_required
def index():
    """Direktori orang dengan pencarian nama dan filter prodi, angkatan, status, skill."""
    args = request.args
    where, params = ["u.is_verified = 1"], []
    if args.get("q", "").strip():
        where.append("u.full_name LIKE ?")
        params.append(f"%{args['q'].strip()}%")
    if args.get("prodi") in PRODI:
        where.append("u.prodi = ?")
        params.append(args["prodi"])
    if args.get("status") in STATUS:
        where.append("u.status = ?")
        params.append(args["status"])
    if args.get("angkatan", "").isdigit():
        where.append("u.angkatan = ?")
        params.append(int(args["angkatan"]))
    if args.get("skill", "").strip():
        where.append(
            "EXISTS (SELECT 1 FROM user_skills us JOIN skills s ON s.id = us.skill_id"
            " WHERE us.user_id = u.id AND s.name LIKE ?)"
        )
        params.append(f"%{args['skill'].strip()}%")
    if args.get("terbuka") == "1":
        where.append("u.open_to_questions = 1")
    where_sql = " AND ".join(where)

    total = query(f"SELECT COUNT(*) AS n FROM users u WHERE {where_sql}", params, one=True)["n"]
    page = Page(total)
    people = query(
        f"""SELECT u.*,
                   (SELECT COUNT(*) FROM experiences e WHERE e.user_id = u.id AND e.visibility != 'privat') AS n_exp,
                   (SELECT GROUP_CONCAT(s.name, ', ') FROM user_skills us JOIN skills s ON s.id = us.skill_id
                     WHERE us.user_id = u.id) AS skills
              FROM users u WHERE {where_sql}
             ORDER BY u.full_name COLLATE NOCASE LIMIT ? OFFSET ?""",
        params + [page.per_page, page.offset],
    )
    angkatan_list = query("SELECT DISTINCT angkatan FROM users WHERE is_verified = 1 ORDER BY angkatan DESC")
    return render_template("profiles/index.html", people=people, page=page, angkatan_list=angkatan_list)


@bp.route("/mahasiswa/<int:user_id>")
@login_required
def detail(user_id):
    person = query("SELECT * FROM users WHERE id = ? AND is_verified = 1", (user_id,), one=True)
    if person is None:
        abort(404)
    vis_sql, vis_params = visibility_sql("e")
    experiences = query(
        f"{EXP_SELECT} WHERE e.user_id = ? AND {vis_sql}"
        " ORDER BY (e.end_date IS NULL) DESC, e.start_date DESC, e.id DESC",
        [user_id] + vis_params,
    )
    is_owner = g.user["id"] == user_id
    return render_template(
        "profiles/detail.html",
        person=person,
        skills=user_skills(user_id),
        experiences=experiences,
        is_owner=is_owner,
        checklist=profile_checklist(person) if is_owner else None,
    )


@bp.route("/profil/edit", methods=("GET", "POST"))
@login_required
def edit():
    user = g.user
    errors = {}
    if request.method == "POST":
        data, errors = validate_identity(request.form)
        links, link_errors = validate_links(request.form)
        errors.update(link_errors)
        bio = request.form.get("bio", "").strip()[:600]
        availability = validate_availability(request.form)

        # Unggahan baru disimpan dulu; file lama baru dihapus setelah semuanya valid.
        photo, cv = user["photo"], user["cv"]
        new_photo = request.files.get("photo")
        new_cv = request.files.get("cv")
        try:
            if new_photo and new_photo.filename:
                photo = save_image(new_photo, "photos")
        except ValueError as error:
            errors["photo"] = str(error)
        try:
            if new_cv and new_cv.filename:
                cv = save_pdf(new_cv, "cv")
        except ValueError as error:
            errors["cv"] = "CV harus berformat PDF."
        if request.form.get("remove_photo"):
            photo = None
        if request.form.get("remove_cv"):
            cv = None

        if not errors:
            execute(
                """UPDATE users SET full_name = ?, prodi = ?, angkatan = ?, status = ?, grad_year = ?,
                          bio = ?, photo = ?, cv = ?, github_url = ?, linkedin_url = ?, portfolio_url = ?,
                          open_to_questions = ?, open_note = ?
                    WHERE id = ?""",
                (
                    data["full_name"], data["prodi"], data["angkatan"], data["status"], data["grad_year"],
                    bio, photo, cv, links["github_url"], links["linkedin_url"], links["portfolio_url"],
                    availability["open_to_questions"], availability["open_note"],
                    user["id"],
                ),
            )
            set_user_skills(user["id"], parse_skills(request.form.get("skills", "")))
            if photo != user["photo"]:
                delete_upload("photos", user["photo"])
            if cv != user["cv"]:
                delete_upload("cv", user["cv"])
            flash("Profil disimpan.", "success")
            return redirect(url_for("profiles.detail", user_id=user["id"]))

        # Ada error: buang file yang baru saja diunggah supaya tidak menumpuk.
        if photo != user["photo"]:
            delete_upload("photos", photo)
        if cv != user["cv"]:
            delete_upload("cv", cv)
        form = request.form
    else:
        form = dict(user)
        form["skills"] = ", ".join(user_skills(user["id"]))
    return render_template("profiles/edit.html", form=form, errors=errors, user=user)
