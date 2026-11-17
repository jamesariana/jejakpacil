"""Query dan operasi database yang dipakai oleh lebih dari satu blueprint."""

import re

from flask import g, url_for

from .db import execute, get_db, query
from .logos import fetch_logo
from .security import is_admin
from .utils import clean_domain, slugify

# SELECT dasar untuk pengalaman, lengkap dengan nama perusahaan, pemilik, dan daftar skill.
EXP_SELECT = """
    SELECT e.*,
           c.name AS company_name, c.slug AS company_slug, c.logo AS company_logo,
           c.is_approved AS company_approved,
           u.full_name, u.prodi, u.angkatan, u.status AS user_status, u.photo AS user_photo,
           (SELECT GROUP_CONCAT(s.name, ', ')
              FROM experience_skills es JOIN skills s ON s.id = es.skill_id
             WHERE es.experience_id = e.id) AS skills
      FROM experiences e
      JOIN companies c ON c.id = e.company_id
      JOIN users u ON u.id = e.user_id
"""


def visibility_sql(alias="e"):
    """Potongan WHERE yang menyaring pengalaman sesuai hak lihat pengunjung.

    - belum masuk  : hanya yang publik
    - sudah masuk  : publik + sivitas + milik sendiri
    - admin        : semuanya
    Mengembalikan (teks_sql, daftar_parameter).
    """
    if g.user is None:
        return f"{alias}.visibility = 'publik'", []
    if is_admin():
        return "1 = 1", []
    return f"({alias}.visibility IN ('publik', 'sivitas') OR {alias}.user_id = ?)", [g.user["id"]]


# ---------- Skill ----------

def parse_skills(text):
    """ "Python,  django , python" -> ["Python", "django"] (rapikan spasi, buang duplikat)."""
    names, seen = [], set()
    for part in (text or "").split(","):
        name = re.sub(r"\s+", " ", part).strip()[:40]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names[:15]


def _set_skills(table, owner_column, owner_id, names):
    """Ganti seluruh skill milik satu pengguna/pengalaman dengan daftar baru."""
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE {owner_column} = ?", (owner_id,))
    for name in names:
        db.execute("INSERT OR IGNORE INTO skills (name) VALUES (?)", (name,))
        skill_id = db.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()["id"]
        db.execute(
            f"INSERT OR IGNORE INTO {table} ({owner_column}, skill_id) VALUES (?, ?)",
            (owner_id, skill_id),
        )
    db.commit()


def set_user_skills(user_id, names):
    _set_skills("user_skills", "user_id", user_id, names)


def set_experience_skills(experience_id, names):
    _set_skills("experience_skills", "experience_id", experience_id, names)


def user_skills(user_id):
    rows = query(
        "SELECT s.name FROM user_skills us JOIN skills s ON s.id = us.skill_id"
        " WHERE us.user_id = ? ORDER BY s.name COLLATE NOCASE",
        (user_id,),
    )
    return [row["name"] for row in rows]


# ---------- Perusahaan ----------

def unique_company_slug(name):
    base = slugify(name)
    slug, counter = base, 2
    while query("SELECT 1 FROM companies WHERE slug = ?", (slug,), one=True):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def get_or_create_company(name, website=""):
    """Cari perusahaan berdasarkan nama (huruf besar/kecil diabaikan); buat baru jika belum ada.

    Perusahaan baru dari pengguna biasa berstatus "menunggu persetujuan admin"
    supaya nama ganda atau salah ketik tidak langsung masuk direktori.
    """
    existing = query("SELECT id FROM companies WHERE name = ?", (name,), one=True)
    if existing:
        return existing["id"]
    domain = clean_domain(website)
    company_id = execute(
        "INSERT INTO companies (name, slug, domain, website, is_approved, created_by)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            name,
            unique_company_slug(name),
            domain,
            f"https://{domain}" if domain else "",
            1 if is_admin() else 0,
            g.user["id"] if g.user else None,
        ),
    )
    logo = fetch_logo(domain)
    if logo:
        execute("UPDATE companies SET logo = ? WHERE id = ?", (logo, company_id))
    return company_id


def approved_companies():
    return query("SELECT id, name FROM companies WHERE is_approved = 1 ORDER BY name COLLATE NOCASE")


# ---------- Kelengkapan profil ----------

def profile_checklist(user):
    """Daftar cek kelengkapan profil untuk beranda dan halaman profil pemiliknya."""
    n_exp = query("SELECT COUNT(*) AS n FROM experiences WHERE user_id = ?", (user["id"],), one=True)["n"]
    edit_url = url_for("profiles.edit")
    items = [
        {"label": "Tentang kamu (bio singkat)", "short": "bio", "done": bool(user["bio"]),
         "action": "Tulis bio", "url": edit_url},
        {"label": "Skill", "short": "skill", "done": bool(user_skills(user["id"])),
         "action": "Tambah skill", "url": edit_url},
        {"label": "Pengalaman pertama", "short": "pengalaman pertama", "done": n_exp > 0,
         "action": "Tambah pengalaman", "url": url_for("experiences.create")},
        {"label": "Foto profil", "short": "foto profil", "done": bool(user["photo"]),
         "action": "Tambah foto", "url": edit_url},
        {"label": "CV dalam PDF", "short": "CV", "done": bool(user["cv"]),
         "action": "Unggah CV", "url": edit_url},
    ]
    done = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "done": done,
        "total": len(items),
        "percent": round(done / len(items) * 100),
        "missing": [item["short"] for item in items if not item["done"]],
    }
