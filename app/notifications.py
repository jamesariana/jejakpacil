"""Notifikasi di dalam website.

Dipanggil dari blueprint lain saat sesuatu terjadi yang perlu diketahui pengguna:
thread-nya dibalas, komentarnya dibalas, thread-nya diberi suara, pengalamannya
diverifikasi atau ditolak, perusahaan yang ia tambahkan disetujui, atau kontennya
disembunyikan moderator.

Yang disimpan hanya jenis dan datanya; kalimatnya disusun di template
(notifications/_item.html) supaya ikut bahasa yang dipilih pengguna.
"""

from flask import Blueprint, abort, g, jsonify, redirect, render_template, request, url_for

from .db import execute, query
from .security import login_required
from .utils import Page, is_safe_next

bp = Blueprint("notifications", __name__, url_prefix="/notifikasi")

KINDS = {
    "balasan_thread",       # seseorang membalas thread-mu
    "balasan_komentar",     # seseorang membalas komentarmu
    "suara",                # thread-mu diberi suara (digabung per thread)
    "verifikasi_diterima",  # admin memverifikasi pengalamanmu
    "verifikasi_ditolak",   # admin menolak bukti pengalamanmu
    "perusahaan_disetujui",  # perusahaan yang kamu tambahkan disetujui admin
    "konten_disembunyikan",  # thread atau balasanmu disembunyikan moderator
}
PER_PAGE = 30


def notify(user_id, kind, link, subject="", detail="", actor_id=None, is_anonymous=False, group_key=None):
    """Buat notifikasi untuk `user_id`.

    - Tidak ada notifikasi untuk tindakan sendiri (misalnya membalas thread sendiri).
    - Kalau `group_key` diisi dan masih ada notifikasi dengan kunci sama yang belum
      dibaca, notifikasi itu diperbarui (hitungannya bertambah) alih-alih membuat baru,
      supaya 10 suara tidak menjadi 10 notifikasi.
    """
    if kind not in KINDS:
        raise ValueError(kind)
    if user_id is None or (actor_id is not None and actor_id == user_id):
        return
    if is_anonymous:
        actor_id = None  # jangan simpan siapa penulis anonimnya, bahkan di database
    if group_key:
        existing = query(
            "SELECT id, actor_id FROM notifications WHERE user_id = ? AND group_key = ? AND is_read = 0",
            (user_id, group_key),
            one=True,
        )
        if existing and actor_id is not None and existing["actor_id"] == actor_id:
            return  # orang yang sama (misalnya mencabut lalu memberi suara lagi): jangan dihitung dua kali
        if existing:
            execute(
                """UPDATE notifications SET count = count + 1, actor_id = ?, is_anonymous = ?,
                          subject = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (actor_id, int(is_anonymous), subject, existing["id"]),
            )
            return
    execute(
        """INSERT INTO notifications (user_id, kind, actor_id, is_anonymous, subject, detail, link, group_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, kind, actor_id, int(is_anonymous), subject, detail, link, group_key),
    )


def unread_count(user_id):
    return query(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,), one=True
    )["n"]


def prune(user_id):
    """Simpan paling banyak 200 notifikasi terbaru per pengguna."""
    execute(
        """DELETE FROM notifications WHERE user_id = ? AND id NOT IN (
               SELECT id FROM notifications WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 200)""",
        (user_id, user_id),
    )


# ---------- Halaman ----------

@bp.route("/")
@login_required
def index():
    unread_only = request.args.get("filter") == "belum"
    where = "n.user_id = ?" + (" AND n.is_read = 0" if unread_only else "")
    total = query(f"SELECT COUNT(*) AS n FROM notifications n WHERE {where}", (g.user["id"],), one=True)["n"]
    page = Page(total, per_page=PER_PAGE)
    items = query(
        f"""SELECT n.*, u.full_name AS actor_name, u.photo AS actor_photo
              FROM notifications n LEFT JOIN users u ON u.id = n.actor_id
             WHERE {where} ORDER BY n.updated_at DESC, n.id DESC LIMIT ? OFFSET ?""",
        (g.user["id"], page.per_page, page.offset),
    )
    prune(g.user["id"])
    return render_template("notifications/index.html", items=items, page=page, unread_only=unread_only)


@bp.route("/<int:notification_id>/buka")
@login_required
def open_one(notification_id):
    """Tandai satu notifikasi sudah dibaca, lalu buka halaman yang dituju."""
    item = query(
        "SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notification_id, g.user["id"]), one=True
    )
    if item is None:
        abort(404)
    execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    return redirect(item["link"] if is_safe_next(item["link"]) else url_for("notifications.index"))


@bp.route("/tandai-dibaca", methods=("POST",))
@login_required
def mark_all_read():
    execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (g.user["id"],))
    return redirect(url_for("notifications.index"))


@bp.route("/jumlah")
@login_required
def counts():
    """Dipanggil app.js berkala supaya angka di ikon lonceng dan pesan tetap terbaru."""
    from .blueprints.messages import unread_count as unread_messages

    return jsonify(notifications=unread_count(g.user["id"]), messages=unread_messages(g.user["id"]))
