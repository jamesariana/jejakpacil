"""Dua bahasa: Indonesia (bawaan) dan Inggris.

Cara kerjanya sederhana dan tanpa library tambahan:
- Semua teks ditulis dalam bahasa Indonesia, lalu dibungkus `_()`,
  misalnya `_("Perusahaan")` di Python atau `{{ _('Perusahaan') }}` di template.
- Kalau bahasa yang dipilih Inggris, `_()` mencari terjemahannya di kamus
  `translations_en.EN`. Kalau belum ada, teks Indonesianya yang dipakai,
  jadi halaman tidak pernah rusak karena terjemahan yang terlewat.
- Pilihan bahasa disimpan di sesi (cookie), diganti lewat /bahasa/en atau /bahasa/id.

Teks yang punya bagian berubah memakai tanda kurung kurawal:
`_("{n} perusahaan", n=12)` menjadi "12 perusahaan" atau "12 companies".
"""

from flask import Blueprint, g, has_request_context, redirect, request, session, url_for
from markupsafe import Markup

from .translations_en import EN
from .utils import is_safe_next

LANGUAGES = {"id": "Bahasa Indonesia", "en": "English"}
DEFAULT_LANGUAGE = "id"

bp = Blueprint("i18n", __name__)

# Teks yang diminta dalam mode Inggris tetapi belum ada di kamus.
# Dipakai oleh tes untuk memastikan tidak ada terjemahan yang terlewat.
MISSING = set()
_ENGLISH_VALUES = set(EN.values())


def current_language():
    if not has_request_context():
        return DEFAULT_LANGUAGE
    if "lang" not in g:
        lang = session.get("lang")
        g.lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return g.lang


def translate(text, **values):
    """Terjemahkan teks ke bahasa yang sedang dipakai, lalu isi bagian {nama}."""
    if text is None:
        return ""
    if isinstance(text, Markup):
        return text  # HTML yang sudah diterjemahkan dan ditandai aman (misalnya pesan berisi tautan)
    text = str(text)
    if current_language() == "en" and text.strip():
        translated = EN.get(text)
        if translated is None:
            if text not in _ENGLISH_VALUES:
                MISSING.add(text)
            translated = text
        text = translated
    return text.format(**values) if values else text


_ = translate


def pick(indonesian, english):
    """Untuk teks yang lebih mudah ditulis dua versi langsung (misalnya nama bulan)."""
    return english if current_language() == "en" else indonesian


# Bentuk tunggal bahasa Inggris untuk kata yang sering muncul setelah angka.
# Bahasa Indonesia tidak membedakan tunggal dan jamak, jadi cukup untuk Inggris.
SINGULAR_EN = {
    "orang": "person", "balasan": "reply", "suara": "vote", "pengalaman": "experience",
    "perusahaan": "company", "magang": "intern", "bekerja": "employed",
}


def count(number, word):
    """"3 orang" / "1 person" / "3 people": angka diikuti kata yang sudah diterjemahkan."""
    if current_language() == "en" and number == 1 and word in SINGULAR_EN:
        return f"{number} {SINGULAR_EN[word]}"
    return f"{number} {translate(word)}"


@bp.route("/bahasa/<code>")
def switch(code):
    """Ganti bahasa lalu kembali ke halaman sebelumnya."""
    if code in LANGUAGES:
        session["lang"] = code
    target = request.args.get("next")
    if not is_safe_next(target):
        target = url_for("main.home")
    return redirect(target)
