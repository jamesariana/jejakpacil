"""Membuat CV PDF dari profil dan pengalaman di JejakPacil (library ReportLab).

Alurnya:
1. blueprints/cv.py mengumpulkan data dan pilihan pengguna (bahasa, pengalaman mana saja, dsb.).
2. build_cv_pdf() menyusun dokumen dengan "flowable" ReportLab: Paragraph, Table, Spacer.
   ReportLab yang memotong ke halaman berikutnya bila isinya panjang.
3. Foto profil (kalau ada dan dipilih) dipotong bulat dengan Pillow lalu ditaruh di kanan atas.
"""

import io
import os
from datetime import date
from xml.sax.saxutils import escape

from flask import g
from PIL import Image as PILImage, ImageDraw, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .constants import CV_SECTIONS, EXP_TYPES, WORK_MODES
from .i18n import _
from .utils import _month_name, format_month, format_period

# Pengalaman kerja dipisah dari pengalaman akademik (asisten dosen, riset).
ACADEMIC_TYPES = {"asdos", "riset"}

INK = colors.HexColor("#1b2a3a")
MUTED = colors.HexColor("#5b6b7c")
ACCENT = colors.HexColor("#2c4f7a")
RULE = colors.HexColor("#b9d7ea")
GREEN = colors.HexColor("#2f7a4f")

FONT, FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"


def _register_fonts():
    """DejaVu Sans dipakai karena mendukung huruf beraksen dan tanda ✓ (font bawaan PDF tidak)."""
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    folder = os.path.join(os.path.dirname(__file__), "fonts")
    pdfmetrics.registerFont(TTFont(FONT, os.path.join(folder, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(folder, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)


def _styles():
    base = dict(fontName=FONT, textColor=INK, fontSize=9.5, leading=13.5)
    return {
        "name": ParagraphStyle("name", **{**base, "fontName": FONT_BOLD, "fontSize": 20, "leading": 24, "textColor": ACCENT}),
        "sub": ParagraphStyle("sub", **{**base, "textColor": MUTED, "fontSize": 9.5}),
        "contact": ParagraphStyle("contact", **{**base, "fontSize": 8.5, "leading": 12, "textColor": INK}),
        "section": ParagraphStyle("section", **{**base, "fontName": FONT_BOLD, "fontSize": 11, "leading": 14,
                                                "textColor": ACCENT, "spaceBefore": 12, "spaceAfter": 2}),
        "body": ParagraphStyle("body", **base),
        "title": ParagraphStyle("title", **{**base, "fontName": FONT_BOLD, "fontSize": 10.5, "leading": 14}),
        "date": ParagraphStyle("date", **{**base, "textColor": MUTED, "alignment": TA_RIGHT, "fontSize": 9}),
        "meta": ParagraphStyle("meta", **{**base, "textColor": MUTED, "fontSize": 9}),
        "bullet": ParagraphStyle("bullet", **{**base, "leftIndent": 10, "bulletIndent": 1}),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.5, "leading": 10, "textColor": MUTED}),
    }


# ---------- Penyusun dokumen ----------

def _text(value):
    """Teks dari pengguna harus di-escape: Paragraph membaca tanda <b>, <a>, dst. sebagai format."""
    return escape(value or "")


def _link_label(url):
    return url.split("://", 1)[-1].rstrip("/")


def _description(text, styles):
    """Baris yang diawali - atau • menjadi poin; baris lain menjadi paragraf biasa."""
    items = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0] in "-•*":
            items.append(Paragraph(_text(line[1:].strip()), styles["bullet"], bulletText="•"))
        else:
            items.append(Paragraph(_text(line), styles["body"]))
    return items


def _experience_block(e, styles, width):
    head = Table(
        [[Paragraph(f"{_text(e['position'])}", styles["title"]),
          Paragraph(_text(format_period(e["start_date"], e["end_date"])), styles["date"])]],
        colWidths=[width * 0.68, width * 0.32],
    )
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    meta = [f"<font name='{FONT_BOLD}' color='#1b2a3a'>{_text(e['company_name'])}</font>"]
    place = ", ".join(x for x in (e["location"], _(WORK_MODES.get(e["work_mode"], ""))) if x)
    if place:
        meta.append(_text(place))
    meta.append(_text(_(EXP_TYPES.get(e["type"], e["type"]))))
    parts = [head, Paragraph(" | ".join(meta), styles["meta"]), Spacer(1, 2)]
    parts += _description(e["description"], styles)
    tail = []
    if e["skills"]:
        tail.append(f"<font name='{FONT_BOLD}'>{_('Keterampilan')}:</font> {_text(e['skills'])}")
    if e["verification"] == "terverifikasi":
        tail.append(f"<font color='#2f7a4f'>✓ {_('Terverifikasi JejakPacil')}</font>")
    if tail:
        parts.append(Paragraph("&nbsp;&nbsp;&nbsp;".join(tail), styles["meta"]))
    parts.append(Spacer(1, 8))
    return KeepTogether(parts)


def _item_date(item):
    if item["start_date"]:
        return format_period(item["start_date"], item["end_date"])
    return format_month(item["end_date"]) if item["end_date"] else ""


def _item_block(item, config, styles, width):
    """Proyek, organisasi, prestasi, atau sertifikasi: bentuknya sama dengan pengalaman."""
    head = Table(
        [[Paragraph(_text(item["title"]), styles["title"]), Paragraph(_text(_item_date(item)), styles["date"])]],
        colWidths=[width * 0.68, width * 0.32],
    )
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    parts = [head]
    meta = []
    if item["subtitle"]:
        meta.append(_text(item["subtitle"]))
    if item["url"]:
        meta.append(f"<a href='{_text(item['url'])}' color='#2c4f7a'>{_text(_link_label(item['url']))}</a>")
    if meta:
        parts.append(Paragraph(" | ".join(meta), styles["meta"]))
    parts.append(Spacer(1, 2))
    parts += _description(item["description"], styles)
    if config["tools"] and item["tools"]:
        parts.append(Paragraph(f"<font name='{FONT_BOLD}'>{_('Teknologi')}:</font> {_text(item['tools'])}", styles["meta"]))
    parts.append(Spacer(1, 8))
    return KeepTogether(parts)


def _section(title, styles, width):
    rule = Table([[""]], colWidths=[width], rowHeights=[0.6])
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.8, RULE)]))
    return [Paragraph(_text(title), styles["section"]), rule, Spacer(1, 6)]


def _round_photo(path, size=26 * mm):
    """Potong foto jadi lingkaran (latar transparan) supaya serasi dengan avatar di situs."""
    try:
        with PILImage.open(path) as source:
            square = ImageOps.fit(source.convert("RGB"), (480, 480))
    except OSError:
        return None  # file hilang atau rusak: CV tetap dibuat tanpa foto
    mask = PILImage.new("L", square.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, *square.size), fill=255)
    square.putalpha(mask)
    buffer = io.BytesIO()
    square.save(buffer, format="PNG")
    buffer.seek(0)
    return Image(buffer, width=size, height=size)


def _identity_line(person):
    school = _("{prodi}, Fakultas Ilmu Komputer, Universitas Indonesia", prodi=_(person["prodi"]))
    if person["status"] == "alumni" and person["grad_year"]:
        status = _("Alumni, angkatan {a}, lulus {y}", a=person["angkatan"], y=person["grad_year"])
    else:
        status = _("Mahasiswa aktif, angkatan {a}", a=person["angkatan"])
    return f"{_text(school)}<br/>{_text(status)}"


def build_cv_pdf(person, experiences, skills, options, photo_path=None, items=None):
    """Susun CV dan kembalikan isi file PDF (bytes).

    options: lang ("id"/"en"), summary (teks), show_email, show_links, show_skills (bool).
    photo_path: lokasi file foto profil, atau None kalau tanpa foto.
    items: isian tambahan per bagian, {"proyek": [...], "organisasi": [...], ...}.
    """
    _register_fonts()
    previous = g.get("lang")
    g.lang = options.get("lang", "id")  # _() dan nama bulan mengikuti bahasa CV, bukan bahasa situs
    try:
        return _build(person, experiences, skills, options, photo_path, items or {})
    finally:
        if previous is None:
            g.pop("lang", None)
        else:
            g.lang = previous


def _build(person, experiences, skills, options, photo_path, items):
    buffer = io.BytesIO()
    margin = 18 * mm
    # Bingkai halaman ReportLab punya padding 6 pt di tiap sisi; tabel harus selebar isi bingkai
    # supaya rata kiri dengan paragraf biasa.
    pad = 6
    width = A4[0] - 2 * margin
    styles = _styles()
    today = date.today()
    generated = f"{today.day} {_month_name(today.month)} {today.year}"

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 11 * mm, _("Dibuat dari JejakPacil pada {d}.", d=generated))
        canvas.drawRightString(A4[0] - margin, 11 * mm, _("Halaman {n}", n=doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=margin - pad, rightMargin=margin - pad,
        topMargin=16 * mm - pad, bottomMargin=18 * mm,
        title=f"CV {person['full_name']}", author=person["full_name"], creator="JejakPacil",
    )

    # Kepala: nama, prodi, kontak. Foto di kanan.
    left = [Paragraph(_text(person["full_name"]), styles["name"]), Spacer(1, 3),
            Paragraph(_identity_line(person), styles["sub"])]
    contacts = []
    if options.get("show_email"):
        contacts.append(_text(person["email"]))
    if options.get("show_links"):
        for key in ("linkedin_url", "github_url", "portfolio_url"):
            if person[key]:
                contacts.append(f"<a href='{_text(person[key])}' color='#2c4f7a'>{_text(_link_label(person[key]))}</a>")
    if contacts:
        left += [Spacer(1, 5), Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(contacts), styles["contact"])]
    photo = _round_photo(photo_path) if photo_path else None
    if photo is not None:
        header = Table([[left, photo]], colWidths=[width - 30 * mm, 30 * mm])
    else:
        header = Table([[left]], colWidths=[width])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story = [header, Spacer(1, 4)]

    summary = (options.get("summary") or "").strip()
    if summary:
        story += _section(_("Ringkasan"), styles, width)
        story += [Paragraph(_text(line), styles["body"]) for line in summary.splitlines() if line.strip()]

    work = [e for e in experiences if e["type"] not in ACADEMIC_TYPES]
    academic = [e for e in experiences if e["type"] in ACADEMIC_TYPES]
    if work:
        story += _section(_("Pengalaman kerja dan magang"), styles, width)
        story += [_experience_block(e, styles, width) for e in work]
    if academic:
        story += _section(_("Pengalaman akademik"), styles, width)
        story += [_experience_block(e, styles, width) for e in academic]
    for key, config in CV_SECTIONS.items():
        if items.get(key):
            story += _section(_(config["label"]), styles, width)
            story += [_item_block(item, config, styles, width) for item in items[key]]

    if options.get("show_skills") and skills:
        story += _section(_("Keterampilan"), styles, width)
        story.append(Paragraph(_text(", ".join(skills)), styles["body"]))

    if any(e["verification"] == "terverifikasi" for e in experiences):
        story += [Spacer(1, 14), Paragraph(
            _("Pengalaman bertanda ✓ sudah diperiksa admin JejakPacil berdasarkan bukti dokumen."),
            styles["small"])]

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
