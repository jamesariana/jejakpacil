"""Fungsi bantu umum: teks, tanggal, URL, unggahan file, dan paginasi."""

import io
import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import current_app, request, url_for
from PIL import Image

WIB = timezone(timedelta(hours=7))
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_name(number):
    """Nama bulan singkat sesuai bahasa yang dipilih (1 = Januari)."""
    from .i18n import pick  # impor di dalam fungsi untuk menghindari impor melingkar

    return pick(BULAN, MONTHS)[number - 1]

# Warna latar untuk avatar/logo pengganti. Dipilih dari nama supaya selalu sama.
# Diselaraskan dengan palet utama (biru batu, koral) dan turunannya. Arang #222831 tidak
# dipakai karena sama dengan latar mode gelap.
TILE_COLORS = ["#3f6a9e", "#7a4f5a", "#c2413f", "#4f6d8a", "#2f6b62", "#6d5a8e", "#8a5a44"]

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DOMAIN_RE = re.compile(r"^(?=.{4,100}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


# ---------- Teks ----------

def slugify(text):
    """Ubah teks menjadi bentuk aman untuk URL: "Bank Central Asia" -> "bank-central-asia"."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def initials(name):
    """Dua huruf awal untuk avatar pengganti: "Bank Central Asia" -> "BC"."""
    words = [word for word in re.split(r"\s+", (name or "").strip()) if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def color_for(name):
    """Pilih warna yang konsisten untuk sebuah nama."""
    total = sum(ord(char) for char in (name or ""))
    return TILE_COLORS[total % len(TILE_COLORS)]


# ---------- Tanggal ----------

def valid_month(value):
    return bool(MONTH_RE.match(value or ""))


def current_month():
    return datetime.now(WIB).strftime("%Y-%m")


def format_month(value):
    """ "2025-06" -> "Jun 2025" """
    if not valid_month(value):
        return ""
    year, month = value.split("-")
    return f"{_month_name(int(month))} {year}"


def format_period(start, end):
    from .i18n import _

    return f"{format_month(start)} – {format_month(end) if end else _('sekarang')}"


def format_duration(start, end):
    """Lama pengalaman, dihitung inklusif: Jun–Agu = 3 bulan."""
    if not valid_month(start):
        return ""
    end = end if valid_month(end) else current_month()
    start_year, start_month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    months = (end_year - start_year) * 12 + (end_month - start_month) + 1
    if months < 1:
        return ""
    from .i18n import _

    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(_("{n} thn", n=years))
    if rest:
        parts.append(_("{n} bln", n=rest))
    return " ".join(parts)


def _parse_timestamp(value):
    """SQLite menyimpan CURRENT_TIMESTAMP dalam UTC dengan format 'YYYY-MM-DD HH:MM:SS'."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def format_date(value):
    moment = _parse_timestamp(value)
    if moment is None:
        return ""
    local = moment.astimezone(WIB)
    return f"{local.day} {_month_name(local.month)} {local.year}"


def format_clock(value):
    """Jam kirim pesan dalam WIB: "10.42" (bahasa Inggris: "10:42")."""
    from .i18n import pick

    moment = _parse_timestamp(value)
    if moment is None:
        return ""
    local = moment.astimezone(WIB)
    return f"{local.hour:02d}{pick('.', ':')}{local.minute:02d}"


def day_label(value):
    """Pemisah hari di chat: "Hari ini", "Kemarin", atau tanggal lengkap."""
    from .i18n import _

    moment = _parse_timestamp(value)
    if moment is None:
        return ""
    day = moment.astimezone(WIB).date()
    today = datetime.now(WIB).date()
    if day == today:
        return _("Hari ini")
    if day == today - timedelta(days=1):
        return _("Kemarin")
    return format_date(value)


def short_when(value):
    """Waktu singkat di daftar percakapan: jam untuk hari ini, "Kemarin", atau tanggal."""
    moment = _parse_timestamp(value)
    if moment is None:
        return ""
    if moment.astimezone(WIB).date() == datetime.now(WIB).date():
        return format_clock(value)
    label = day_label(value)
    return label.rsplit(" ", 1)[0] if label[:1].isdigit() else label  # "12 Nov 2026" -> "12 Nov"


def time_ago(value):
    """Waktu relatif: "5 menit lalu", "kemarin", atau tanggal untuk yang sudah lama."""
    from .i18n import _

    moment = _parse_timestamp(value)
    if moment is None:
        return ""
    seconds = int((datetime.now(timezone.utc) - moment).total_seconds())
    if seconds < 60:
        return _("baru saja")
    if seconds < 3600:
        return _("{n} menit lalu", n=seconds // 60)
    if seconds < 86400:
        return _("{n} jam lalu", n=seconds // 3600)
    days = seconds // 86400
    if days == 1:
        return _("kemarin")
    if days < 30:
        return _("{n} hari lalu", n=days)
    return format_date(value)


# ---------- URL ----------

def valid_url(value):
    """Hanya terima tautan http/https supaya tidak bisa disisipi skema berbahaya (mis. javascript:)."""
    try:
        parts = urlparse(value)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def clean_domain(value):
    """Ambil nama domain dari masukan bebas: "https://www.Tokopedia.com/karier" -> "tokopedia.com".

    Mengembalikan string kosong kalau masukan bukan domain yang valid.
    """
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "http://" + value
    try:
        host = urlparse(value).hostname or ""
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host if DOMAIN_RE.match(host) else ""


def is_safe_next(target):
    """Parameter ?next= hanya boleh mengarah ke halaman di situs ini (mencegah open redirect)."""
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target


# ---------- Unggahan file ----------

def _upload_dir(kind):
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], kind)
    os.makedirs(path, exist_ok=True)
    return path


MAX_FILE_BYTES = 5 * 1024 * 1024  # batas ukuran per file unggahan


def save_image_bytes(data, kind, max_size=(512, 512), photo=False):
    """Periksa bahwa `data` benar-benar gambar, perkecil, dan simpan ulang.

    Gambar selalu ditulis ulang oleh Pillow, jadi file berbahaya yang menyamar
    dengan ekstensi .png tidak akan tersimpan. Mengembalikan nama file baru.
    `photo=True` menyimpan sebagai JPEG (lebih kecil untuk foto lampiran);
    selain itu PNG supaya latar transparan logo tetap terjaga.
    """
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Ukuran file maksimal 5 MB.")
    try:
        image = Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP", "GIF"])
        image.load()
    except Exception as error:  # Pillow melempar banyak jenis error untuk file rusak
        raise ValueError("File bukan gambar PNG, JPG, WEBP, atau GIF yang valid.") from error
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    image.thumbnail(max_size)
    if photo:
        if image.mode == "RGBA":  # JPEG tidak punya transparansi: tempel di atas latar putih
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.split()[3])
            image = background
        filename = f"{uuid.uuid4().hex}.jpg"
        image.save(os.path.join(_upload_dir(kind), filename), format="JPEG", quality=85, optimize=True)
        return filename
    filename = f"{uuid.uuid4().hex}.png"
    image.save(os.path.join(_upload_dir(kind), filename), format="PNG")
    return filename


def save_image(file, kind, max_size=(512, 512)):
    return save_image_bytes(file.read(), kind, max_size)


def save_pdf(file, kind):
    """Simpan unggahan PDF setelah memeriksa tanda awal file (%PDF)."""
    data = file.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("File harus berformat PDF.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Ukuran file maksimal 5 MB.")
    filename = f"{uuid.uuid4().hex}.pdf"
    with open(os.path.join(_upload_dir(kind), filename), "wb") as output:
        output.write(data)
    return filename


def save_proof(file):
    """Bukti pengalaman boleh berupa PDF atau gambar."""
    head = file.read(4)
    file.seek(0)
    if head == b"%PDF":
        return save_pdf(file, "proofs")
    return save_image(file, "proofs", max_size=(1600, 1600))


def delete_upload(kind, filename):
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], kind, os.path.basename(filename))
    if os.path.exists(path):
        os.remove(path)


def media_url(kind, filename):
    return url_for("main.media", kind=kind, filename=filename)


# ---------- Paginasi ----------

class Page:
    """Menghitung offset dan jumlah halaman untuk daftar yang panjang."""

    def __init__(self, total, per_page=None):
        self.per_page = per_page or current_app.config["PER_PAGE"]
        self.total = total
        self.pages = max(1, -(-total // self.per_page))  # pembagian dibulatkan ke atas
        try:
            number = int(request.args.get("page", 1))
        except ValueError:
            number = 1
        self.number = min(max(1, number), self.pages)
        self.offset = (self.number - 1) * self.per_page
        self.has_prev = self.number > 1
        self.has_next = self.number < self.pages


def url_with(**changes):
    """URL halaman yang sama dengan sebagian filter diganti.

    Contoh: url_with(jenis="magang") mempertahankan kata kunci pencarian yang sedang
    dipakai, lalu mengganti filter jenis. Nilai None atau "" menghapus filter itu.
    Nomor halaman selalu kembali ke 1 karena hasilnya berubah.
    """
    args = request.args.to_dict()
    args.update(request.view_args or {})
    args.pop("page", None)
    for key, value in changes.items():
        if value in (None, ""):
            args.pop(key, None)
        else:
            args[key] = value
    return url_for(request.endpoint, **args)


def page_url(number):
    """URL halaman yang sama dengan filter yang sama, hanya nomor halamannya berbeda."""
    args = request.args.to_dict()
    args.update(request.view_args or {})
    args["page"] = number
    return url_for(request.endpoint, **args)
