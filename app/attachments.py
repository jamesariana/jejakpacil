"""Lampiran foto dan PDF untuk forum dan chat.

Satu tabel `attachments` dipakai bersama. Tiap lampiran menempel ke tepat satu
pemilik: thread, balasan, atau pesan (kolom thread_id, reply_id, atau message_id).
File disimpan di folder unggahan dengan nama acak; nama asli hanya untuk ditampilkan.
"""

import os
import uuid

from .db import execute, query
from .i18n import _
from .utils import MAX_FILE_BYTES, _upload_dir, delete_upload, save_image_bytes

MAX_FILES = 4
OWNER_COLUMNS = ("thread_id", "reply_id", "message_id")


def read_uploads(files):
    """Periksa file dari form sebelum ada yang disimpan.

    Mengembalikan (daftar file, pesan error). Kalau ada satu saja yang salah,
    tidak ada file yang disimpan, supaya pengguna bisa memperbaikinya dulu.
    """
    picked = [file for file in files if file and file.filename]
    if len(picked) > MAX_FILES:
        return [], _("Lampiran maksimal {n} file.", n=MAX_FILES)
    uploads = []
    for file in picked:
        data = file.read()
        name = os.path.basename(file.filename).strip()[:100] or "file"
        if len(data) > MAX_FILE_BYTES:
            return [], _("{name} lebih dari 5 MB.", name=name)
        if not data.startswith(b"%PDF") and not _looks_like_image(data):
            return [], _("{name} bukan foto (PNG, JPG, WEBP) atau PDF.", name=name)
        uploads.append((name, data))
    return uploads, None


def _looks_like_image(data):
    """Tanda awal file (magic number) PNG, JPEG, WEBP, atau GIF."""
    return (
        data.startswith(b"\x89PNG")
        or data.startswith(b"\xff\xd8\xff")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
        or data.startswith(b"GIF8")
    )


def store(uploads, folder, uploader_id, **owner):
    """Simpan file yang sudah diperiksa `read_uploads`, lalu catat di database.

    `owner` berisi tepat satu dari thread_id, reply_id, atau message_id.
    Gambar ditulis ulang oleh Pillow (lebar maksimal 1600 px), PDF disimpan apa adanya.
    """
    (column, owner_id), = owner.items()
    if column not in OWNER_COLUMNS:
        raise ValueError(column)
    for name, data in uploads:
        if data.startswith(b"%PDF"):
            stored, kind = _save_pdf_bytes(data, folder), "pdf"
        else:
            try:
                stored, kind = save_image_bytes(data, folder, max_size=(1600, 1600), photo=True), "image"
            except ValueError:
                continue  # tanda awalnya mirip gambar tapi isinya rusak: lewati saja
        execute(
            f"""INSERT INTO attachments (uploader_id, {column}, stored_name, original_name, kind, size)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (uploader_id, owner_id, stored, name, kind, len(data)),
        )


def _save_pdf_bytes(data, folder):
    filename = f"{uuid.uuid4().hex}.pdf"
    with open(os.path.join(_upload_dir(folder), filename), "wb") as output:
        output.write(data)
    return filename


def for_owners(column, ids):
    """Lampiran untuk banyak pemilik sekaligus: {id pemilik: [lampiran, ...]}."""
    if column not in OWNER_COLUMNS or not ids:
        return {}
    ids = list(ids)
    marks = ", ".join("?" for _id in ids)
    grouped = {}
    for row in query(f"SELECT * FROM attachments WHERE {column} IN ({marks}) ORDER BY id", ids):
        grouped.setdefault(row[column], []).append(row)
    return grouped


def remove(column, owner_id, folder):
    """Hapus file lampiran dari disk sebelum pemiliknya dihapus dari database."""
    for row in query(f"SELECT stored_name FROM attachments WHERE {column} = ?", (owner_id,)):
        delete_upload(folder, row["stored_name"])


def human_size(size):
    """1536 -> "1,5 KB" (koma desimal ala Indonesia, titik untuk bahasa Inggris)."""
    from .i18n import current_language

    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            text = f"{size:.0f}" if unit == "B" else f"{size:.1f}".rstrip("0").rstrip(".")
            if current_language() == "id":
                text = text.replace(".", ",")
            return f"{text} {unit}"
        size /= 1024
