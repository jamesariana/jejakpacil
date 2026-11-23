"""Koneksi dan fungsi bantu database SQLite.

Satu request memakai satu koneksi yang disimpan di `g` (objek milik Flask yang
hidup selama satu request), lalu ditutup otomatis saat request selesai.
"""

import sqlite3

from flask import current_app, g

from .constants import DEFAULT_CATEGORIES


def get_db():
    """Ambil koneksi database untuk request ini (dibuat sekali, lalu dipakai ulang)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # baris bisa diakses dengan nama kolom: row["email"]
        g.db.execute("PRAGMA foreign_keys = ON")  # SQLite tidak mengaktifkannya secara bawaan
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    """Jalankan SELECT. Dengan one=True mengembalikan satu baris atau None."""
    rows = get_db().execute(sql, params).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    """Jalankan INSERT/UPDATE/DELETE, simpan (commit), dan kembalikan id baris baru."""
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor.lastrowid


# Kolom yang ditambahkan setelah tabelnya pertama kali dibuat.
# CREATE TABLE IF NOT EXISTS tidak menambah kolom ke tabel lama, jadi database yang
# sudah ada di laptop anggota kelompok diperbarui di sini tanpa menghapus datanya.
NEW_COLUMNS = {
    "users": {
        "open_to_questions": "INTEGER NOT NULL DEFAULT 0",
        "open_note": "TEXT NOT NULL DEFAULT ''",
    },
    "experiences": {
        "role_category": "TEXT",
        "selection_stages": "TEXT",
        "selection_weeks": "INTEGER",
        "selection_difficulty": "INTEGER",
        "selection_questions": "TEXT",
        "selection_tips": "TEXT",
    },
    "messages": {
        "reply_to_id": "INTEGER REFERENCES messages (id) ON DELETE SET NULL",
        "edited_at": "TEXT",
        "deleted_at": "TEXT",
        "updated_at": "TEXT",
    },
}


def _add_missing_columns(db):
    for table, columns in NEW_COLUMNS.items():
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db():
    """Buat tabel yang belum ada, tambah kolom baru, dan isi kategori forum bawaan."""
    db = get_db()
    with current_app.open_resource("schema.sql") as file:
        db.executescript(file.read().decode("utf-8"))
    _add_missing_columns(db)
    for position, (slug, name, description) in enumerate(DEFAULT_CATEGORIES):
        db.execute(
            "INSERT OR IGNORE INTO categories (slug, name, description, position) VALUES (?, ?, ?, ?)",
            (slug, name, description, position),
        )
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
