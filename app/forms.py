"""Validasi masukan form.

Setiap fungsi menerima isi form dan mengembalikan (data_bersih, errors).
`errors` adalah dict {nama_field: pesan}; kosong berarti semua masukan valid.
"""

import re
from datetime import datetime

from .i18n import _
from .constants import EXP_TYPES, HOW_OBTAINED, PRODI, STATUS, VISIBILITY, WORK_MODES
from .queries import parse_skills
from .utils import current_month, valid_month, valid_url

FIRST_ANGKATAN = 1986  # batas bawah tahun angkatan yang diterima form; ubah bila perlu
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+\.)*ui\.ac\.id$")


def is_allowed_email(email):
    """Hanya email UI (…@ui.ac.id atau subdomainnya, mis. …@cs.ui.ac.id)."""
    return bool(EMAIL_RE.match(email or ""))


# Kata sandi yang terlalu mudah ditebak, ditolak walaupun panjangnya cukup.
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1", "qwerty123", "qwertyuiop",
    "katasandi", "11111111", "00000000", "abcd1234", "iloveyou", "fasilkom", "fasilkomui", "pacil123",
}


def validate_new_password(password, password2, email=""):
    """Aturan kata sandi baru, dipakai saat daftar, lupa sandi, dan ganti sandi."""
    errors = {}
    local_part = email.split("@")[0].lower() if email else ""
    if len(password) < 8:
        errors["password"] = "Kata sandi minimal 8 karakter."
    elif len(password) > 128:
        errors["password"] = "Kata sandi maksimal 128 karakter."
    elif password.lower() in COMMON_PASSWORDS or (local_part and local_part in password.lower()):
        errors["password"] = "Kata sandi ini terlalu mudah ditebak. Jangan pakai nama emailmu atau angka berurutan."
    elif password != password2:
        errors["password2"] = "Ulangi kata sandi yang sama."
    return errors


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_identity(form):
    """Data diri yang dipakai di pendaftaran dan edit profil."""
    this_year = datetime.now().year
    data = {
        "full_name": re.sub(r"\s+", " ", form.get("full_name", "")).strip()[:80],
        "prodi": form.get("prodi", ""),
        "angkatan": _to_int(form.get("angkatan")),
        "status": form.get("status", ""),
        "grad_year": None,
    }
    errors = {}
    if len(data["full_name"]) < 3:
        errors["full_name"] = "Isi nama lengkap, minimal 3 huruf."
    if data["prodi"] not in PRODI:
        errors["prodi"] = "Pilih program studi."
    if data["angkatan"] is None or not FIRST_ANGKATAN <= data["angkatan"] <= this_year:
        errors["angkatan"] = _("Isi tahun angkatan antara {a} dan {b}.", a=FIRST_ANGKATAN, b=this_year)
    if data["status"] not in STATUS:
        errors["status"] = "Pilih status."
    elif data["status"] == "alumni":
        data["grad_year"] = _to_int(form.get("grad_year"))
        earliest = data["angkatan"] or FIRST_ANGKATAN
        if data["grad_year"] is None or not earliest <= data["grad_year"] <= this_year:
            errors["grad_year"] = "Isi tahun lulus, tidak boleh sebelum tahun angkatan."
    return data, errors


def validate_links(form):
    """Tautan profil boleh kosong, tetapi jika diisi harus berupa URL http/https."""
    labels = {"github_url": "GitHub", "linkedin_url": "LinkedIn", "portfolio_url": "portofolio"}
    data, errors = {}, {}
    for field, label in labels.items():
        value = form.get(field, "").strip()[:200]
        data[field] = value
        if value and not valid_url(value):
            errors[field] = _("Tautan {label} harus diawali http:// atau https://.", label=label)
    return data, errors


def validate_experience(form):
    is_current = bool(form.get("is_current"))
    data = {
        "company_name": re.sub(r"\s+", " ", form.get("company_name", "")).strip()[:80],
        "company_website": form.get("company_website", "").strip()[:200],
        "position": re.sub(r"\s+", " ", form.get("position", "")).strip()[:100],
        "type": form.get("type", ""),
        "start_date": form.get("start_date", "").strip(),
        "end_date": None if is_current else form.get("end_date", "").strip(),
        "location": form.get("location", "").strip()[:80],
        "work_mode": form.get("work_mode", ""),
        "description": form.get("description", "").strip()[:2000],
        "how_obtained": form.get("how_obtained", ""),
        "visibility": form.get("visibility", ""),
        "skills": parse_skills(form.get("skills", "")),
    }
    errors = {}
    if len(data["company_name"]) < 2:
        errors["company_name"] = "Isi nama perusahaan atau instansi."
    if len(data["position"]) < 2:
        errors["position"] = "Isi posisi, misalnya Software Engineer Intern."
    if data["type"] not in EXP_TYPES:
        errors["type"] = "Pilih jenis pengalaman."
    if not valid_month(data["start_date"]):
        errors["start_date"] = "Isi bulan mulai dengan format TTTT-BB, misalnya 2025-06."
    elif data["start_date"] > current_month():
        errors["start_date"] = "Bulan mulai belum terjadi. Isi pengalaman yang sudah dimulai."
    if not is_current:
        if not valid_month(data["end_date"]):
            errors["end_date"] = "Isi bulan selesai, atau centang “Masih berjalan”."
        elif "start_date" not in errors and data["end_date"] < data["start_date"]:
            errors["end_date"] = "Bulan selesai tidak boleh sebelum bulan mulai."
    if data["work_mode"] not in WORK_MODES:
        errors["work_mode"] = "Pilih cara kerja."
    if data["how_obtained"] not in HOW_OBTAINED:
        errors["how_obtained"] = "Pilih cara kamu mendapatkannya."
    if data["visibility"] not in VISIBILITY:
        errors["visibility"] = "Pilih siapa yang boleh melihat."
    return data, errors


def validate_thread(form, category_ids, company_ids):
    data = {
        "title": re.sub(r"\s+", " ", form.get("title", "")).strip()[:140],
        "body": form.get("body", "").strip()[:8000],
        "category_id": _to_int(form.get("category_id")),
        "company_id": _to_int(form.get("company_id")),
        "is_anonymous": 1 if form.get("is_anonymous") else 0,
    }
    errors = {}
    if len(data["title"]) < 8:
        errors["title"] = "Tulis judul yang jelas, minimal 8 huruf."
    if len(data["body"]) < 10:
        errors["body"] = "Tulis isi diskusi, minimal 10 huruf."
    if data["category_id"] not in category_ids:
        errors["category_id"] = "Pilih kategori."
    if data["company_id"] is not None and data["company_id"] not in company_ids:
        data["company_id"] = None  # tag perusahaan tidak dikenal: abaikan
    return data, errors
