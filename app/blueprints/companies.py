"""Direktori perusahaan tempat mahasiswa Fasilkom pernah magang atau bekerja."""

from flask import Blueprint, abort, g, render_template, request

from ..constants import INDUSTRIES
from ..db import query
from ..constants import ROLE_CATEGORIES
from ..queries import EXP_SELECT, selection_summary, visibility_sql
from ..security import is_admin
from ..utils import Page

bp = Blueprint("companies", __name__)


# Pilihan urutan daftar perusahaan. Kuncinya dipakai di URL (?urut=...).
SORTS = {
    "populer": ("Paling banyak anak Fasilkom", "n_orang DESC, c.name COLLATE NOCASE"),
    "terbaru": ("Baru saja ada yang masuk", "last_start DESC, n_orang DESC, c.name COLLATE NOCASE"),
    "az": ("Nama A sampai Z", "c.name COLLATE NOCASE"),
}
JENIS = {"magang": "Magang", "kerja": "Bekerja"}


@bp.route("/perusahaan")
def index():
    """Daftar perusahaan beserta jumlah orang yang pernah magang dan bekerja di sana.

    Jumlah dihitung dari pengalaman yang tidak privat. Yang ditampilkan hanya
    angka gabungan, jadi tidak membuka data siapa pun.

    Filter industri diterapkan di Python setelah query supaya jumlah per industri
    (angka di samping tiap pilihan industri) tetap bisa dihitung dari hasil yang sama.
    """
    args = request.args
    keyword = args.get("q", "").strip()
    jenis = args.get("jenis") if args.get("jenis") in JENIS else ""
    urut = args.get("urut") if args.get("urut") in SORTS else "populer"
    industri = args.get("industri") if args.get("industri") in INDUSTRIES else ""

    where, params = ["c.is_approved = 1"], []
    if keyword:
        where.append("c.name LIKE ?")
        params.append(f"%{keyword}%")
    having = {"magang": "n_magang > 0", "kerja": "n_kerja > 0"}.get(jenis, "n_orang > 0")

    rows = query(
        f"""SELECT c.*,
                   COUNT(DISTINCT e.user_id) AS n_orang,
                   COUNT(DISTINCT CASE WHEN e.type = 'magang' THEN e.user_id END) AS n_magang,
                   COUNT(DISTINCT CASE WHEN e.type != 'magang' THEN e.user_id END) AS n_kerja,
                   MAX(e.start_date) AS last_start,
                   GROUP_CONCAT(DISTINCT e.position) AS positions
              FROM companies c
              LEFT JOIN experiences e ON e.company_id = c.id AND e.visibility != 'privat'
             WHERE {' AND '.join(where)}
             GROUP BY c.id HAVING {having} ORDER BY {SORTS[urut][1]}""",
        params,
    )
    industry_counts = {name: 0 for name in INDUSTRIES}
    for row in rows:
        if row["industry"] in industry_counts:
            industry_counts[row["industry"]] += 1
    all_count = len(rows)
    if industri:
        rows = [row for row in rows if row["industry"] == industri]

    page = Page(len(rows), per_page=20)
    companies = []
    for row in rows[page.offset:page.offset + page.per_page]:
        company = dict(row)
        # GROUP_CONCAT memisahkan dengan koma; ubah jadi daftar posisi.
        company["position_list"] = sorted(set((row["positions"] or "").split(","))) if row["positions"] else []
        companies.append(company)
    return render_template(
        "companies/index.html",
        companies=companies,
        page=page,
        sorts=SORTS,
        jenis_choices={"": "Semua", **JENIS},
        current={"q": keyword, "jenis": jenis, "urut": urut, "industri": industri},
        industry_counts=industry_counts,
        all_count=all_count,
        filtered=bool(keyword or jenis or industri),
    )


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
    roles = query(
        """SELECT role_category, COUNT(*) AS n FROM experiences
            WHERE company_id = ? AND visibility != 'privat' AND role_category IS NOT NULL
            GROUP BY role_category ORDER BY n DESC LIMIT 8""",
        (company["id"],),
    )
    roles = [{"label": ROLE_CATEGORIES[r["role_category"]], "n": r["n"]} for r in roles if r["role_category"] in ROLE_CATEGORIES]
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
        roles=roles,
        selection=selection_summary(experiences),
        threads=threads,
    )
