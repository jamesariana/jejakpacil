"""Direktori perusahaan tempat mahasiswa Fasilkom pernah magang atau bekerja."""

from flask import Blueprint, abort, g, render_template, request

from ..constants import INDUSTRIES
from ..db import query
from ..queries import EXP_SELECT, visibility_sql
from ..security import is_admin
from ..utils import Page

bp = Blueprint("companies", __name__)


@bp.route("/perusahaan")
def index():
    """Daftar perusahaan beserta jumlah orang yang pernah magang dan bekerja di sana.

    Jumlah dihitung dari pengalaman yang tidak privat. Yang ditampilkan hanya
    angka gabungan, jadi tidak membuka data siapa pun.
    """
    args = request.args
    where, params = ["c.is_approved = 1"], []
    if args.get("q", "").strip():
        where.append("c.name LIKE ?")
        params.append(f"%{args['q'].strip()}%")
    if args.get("industri") in INDUSTRIES:
        where.append("c.industry = ?")
        params.append(args["industri"])
    having = {"magang": "n_magang > 0", "kerja": "n_kerja > 0"}.get(args.get("jenis"), "n_orang > 0")
    order = "c.name COLLATE NOCASE" if args.get("urut") == "az" else "n_orang DESC, c.name COLLATE NOCASE"

    rows = query(
        f"""SELECT c.*,
                   COUNT(DISTINCT e.user_id) AS n_orang,
                   COUNT(DISTINCT CASE WHEN e.type = 'magang' THEN e.user_id END) AS n_magang,
                   COUNT(DISTINCT CASE WHEN e.type != 'magang' THEN e.user_id END) AS n_kerja,
                   GROUP_CONCAT(DISTINCT e.position) AS positions
              FROM companies c
              LEFT JOIN experiences e ON e.company_id = c.id AND e.visibility != 'privat'
             WHERE {' AND '.join(where)}
             GROUP BY c.id HAVING {having} ORDER BY {order}""",
        params,
    )
    page = Page(len(rows), per_page=20)
    companies = []
    for row in rows[page.offset:page.offset + page.per_page]:
        company = dict(row)
        # GROUP_CONCAT memisahkan dengan koma; ubah jadi daftar posisi.
        company["position_list"] = sorted(set((row["positions"] or "").split(","))) if row["positions"] else []
        companies.append(company)
    return render_template("companies/index.html", companies=companies, page=page)


@bp.route("/perusahaan/<slug>")
def detail(slug):
    company = query("SELECT * FROM companies WHERE slug = ?", (slug,), one=True)
    if company is None or (not company["is_approved"] and not is_admin()):
        abort(404)

    vis_sql, vis_params = visibility_sql("e")
    experiences = query(
        f"{EXP_SELECT} WHERE e.company_id = ? AND {vis_sql}"
        " ORDER BY (e.end_date IS NULL) DESC, e.start_date DESC, e.id DESC",
        [company["id"]] + vis_params,
    )
    counts = query(
        """SELECT COUNT(*) AS total,
                  COUNT(DISTINCT user_id) AS n_orang,
                  COUNT(DISTINCT CASE WHEN type = 'magang' THEN user_id END) AS n_magang,
                  COUNT(DISTINCT CASE WHEN type != 'magang' THEN user_id END) AS n_kerja
             FROM experiences WHERE company_id = ? AND visibility != 'privat'""",
        (company["id"],),
        one=True,
    )
    positions = query(
        """SELECT position, COUNT(*) AS n FROM experiences
            WHERE company_id = ? AND visibility != 'privat'
            GROUP BY position COLLATE NOCASE ORDER BY n DESC, position LIMIT 6""",
        (company["id"],),
    )
    skills = query(
        """SELECT s.name, COUNT(*) AS n
             FROM experiences e
             JOIN experience_skills es ON es.experience_id = e.id
             JOIN skills s ON s.id = es.skill_id
            WHERE e.company_id = ? AND e.visibility != 'privat'
            GROUP BY s.id ORDER BY n DESC, s.name COLLATE NOCASE LIMIT 10""",
        (company["id"],),
    )
    threads = []
    if g.user is not None:
        threads = query(
            """SELECT t.id, t.title, t.created_at,
                      (SELECT COUNT(*) FROM replies r WHERE r.thread_id = t.id) AS n_replies
                 FROM threads t WHERE t.company_id = ? AND t.is_hidden = 0
                ORDER BY t.created_at DESC, t.id DESC LIMIT 8""",
            (company["id"],),
        )
    return render_template(
        "companies/detail.html",
        company=company,
        experiences=experiences,
        counts=counts,
        # Pengalaman "sivitas" yang belum terlihat karena pengunjung belum masuk.
        hidden_count=counts["total"] - sum(1 for e in experiences if e["visibility"] != "privat"),
        positions=positions,
        skills=skills,
        threads=threads,
    )
