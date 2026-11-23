"""Statistik gabungan (gaya tracer study). Hanya angka agregat, tanpa nama orang."""

from flask import Blueprint, render_template

from ..constants import EXP_TYPES, HOW_OBTAINED, ROLE_CATEGORIES, SELECTION_STAGES
from ..db import query
from ..i18n import _

bp = Blueprint("stats", __name__)


def to_bars(rows, labels=None):
    """Ubah hasil query (label, n) menjadi data batang: tiap batang punya persen lebar.

    Lebar dihitung relatif terhadap nilai terbesar, jadi batang terpanjang = 100%.
    """
    biggest = max((row["n"] for row in rows), default=0)
    bars = []
    for row in rows:
        label = labels.get(row["label"], row["label"]) if labels else row["label"]
        bars.append({"label": label, "value": row["n"], "percent": round(row["n"] / biggest * 100, 1)})
    return bars


@bp.route("/statistik")
def index():
    totals = query(
        """SELECT (SELECT COUNT(*) FROM experiences WHERE visibility != 'privat') AS experiences,
                  (SELECT COUNT(DISTINCT user_id) FROM experiences WHERE visibility != 'privat') AS people,
                  (SELECT COUNT(DISTINCT e.company_id) FROM experiences e
                     JOIN companies c ON c.id = e.company_id
                    WHERE e.visibility != 'privat' AND c.is_approved = 1) AS companies,
                  (SELECT COUNT(*) FROM experiences
                    WHERE visibility != 'privat' AND verification = 'terverifikasi') AS verified""",
        one=True,
    )
    top_companies = query(
        """SELECT c.name AS label, COUNT(DISTINCT e.user_id) AS n
             FROM experiences e JOIN companies c ON c.id = e.company_id
            WHERE e.visibility != 'privat' AND c.is_approved = 1
            GROUP BY c.id ORDER BY n DESC, c.name COLLATE NOCASE LIMIT 10"""
    )
    by_type = query(
        """SELECT type AS label, COUNT(*) AS n FROM experiences
            WHERE visibility != 'privat' GROUP BY type ORDER BY n DESC"""
    )
    by_angkatan = query(
        """SELECT u.angkatan AS label, COUNT(DISTINCT u.id) AS n
             FROM experiences e JOIN users u ON u.id = e.user_id
            WHERE e.visibility != 'privat' GROUP BY u.angkatan ORDER BY u.angkatan DESC"""
    )
    by_channel = query(
        """SELECT how_obtained AS label, COUNT(*) AS n FROM experiences
            WHERE visibility != 'privat' GROUP BY how_obtained ORDER BY n DESC"""
    )
    top_skills = query(
        """SELECT s.name AS label, COUNT(*) AS n
             FROM experiences e
             JOIN experience_skills es ON es.experience_id = e.id
             JOIN skills s ON s.id = es.skill_id
            WHERE e.visibility != 'privat'
            GROUP BY s.id ORDER BY n DESC, s.name COLLATE NOCASE LIMIT 10"""
    )
    by_role = query(
        """SELECT role_category AS label, COUNT(*) AS n FROM experiences
            WHERE visibility != 'privat' AND role_category IS NOT NULL
            GROUP BY role_category ORDER BY n DESC LIMIT 10"""
    )
    # Tahapan seleksi disimpan sebagai teks "a,b,c"; dihitung di Python per tahap.
    stage_counts = {}
    for row in query(
        "SELECT selection_stages FROM experiences WHERE visibility != 'privat' AND selection_stages IS NOT NULL"
    ):
        for key in set(row["selection_stages"].split(",")):
            if key in SELECTION_STAGES:
                stage_counts[key] = stage_counts.get(key, 0) + 1
    by_stage = sorted(({"label": key, "n": n} for key, n in stage_counts.items()), key=lambda r: -r["n"])

    # Label angkatan dibuat di Python supaya ikut bahasa yang dipilih ("Angkatan 2023" / "Class of 2023").
    by_angkatan = [{"label": _("Angkatan {n}", n=row["label"]), "n": row["n"]} for row in by_angkatan]
    charts = [
        {
            "title": "Perusahaan dengan anak Fasilkom terbanyak",
            "icon": "building",
            "unit": "orang",
            "bars": to_bars(top_companies),
        },
        {
            "title": "Bidang yang paling banyak diambil",
            "icon": "briefcase",
            "unit": "pengalaman",
            "bars": to_bars(by_role, ROLE_CATEGORIES),
        },
        {"title": "Pengalaman menurut jenis", "icon": "briefcase", "unit": "pengalaman", "bars": to_bars(by_type, EXP_TYPES)},
        {
            "title": "Cara mendapatkan pengalaman",
            "icon": "megaphone",
            "unit": "pengalaman",
            "bars": to_bars(by_channel, HOW_OBTAINED),
        },
        {
            "title": "Tahapan seleksi yang paling sering dilalui",
            "icon": "route",
            "unit": "cerita seleksi",
            "bars": to_bars(by_stage, SELECTION_STAGES),
        },
        {"title": "Skill yang paling sering dipakai", "icon": "trending", "unit": "pengalaman", "bars": to_bars(top_skills)},
        {
            "title": "Mahasiswa dan alumni yang punya pengalaman, per angkatan",
            "icon": "users",
            "unit": "orang",
            "bars": to_bars(by_angkatan),
        },
    ]
    return render_template("stats/index.html", totals=totals, charts=charts)
