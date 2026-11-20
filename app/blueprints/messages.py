"""Chat pribadi antara dua pengguna.

- Satu percakapan untuk tiap pasangan pengguna (tabel conversations, user_low < user_high).
- Pesan bisa berisi teks, foto, dan PDF (lampiran disimpan di folder "chat").
- Pesan baru muncul tanpa memuat ulang halaman: app.js menanyakan ke server setiap
  beberapa detik (polling) lewat /pesan/<id>/baru. Cara ini cukup untuk skala kampus
  dan tidak perlu server WebSocket terpisah.
- Hanya dua orang di percakapan yang bisa membaca pesannya. Admin hanya melihat
  pesan yang dilaporkan.
"""

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .. import attachments
from ..db import execute, query
from ..i18n import _
from ..security import is_admin, login_required
from ..utils import day_label

bp = Blueprint("messages", __name__, url_prefix="/pesan")

MAX_BODY = 4000
PAGE_SIZE = 200  # pesan terakhir yang dimuat saat percakapan dibuka


# ---------- Bantuan ----------

def _pair(a, b):
    return (a, b) if a < b else (b, a)


def _other_id(conversation):
    me = g.user["id"]
    return conversation["user_high"] if conversation["user_low"] == me else conversation["user_low"]


def _get_conversation(conversation_id):
    """Ambil percakapan dan pastikan pengguna yang masuk adalah salah satu pesertanya."""
    conversation = query("SELECT * FROM conversations WHERE id = ?", (conversation_id,), one=True)
    if conversation is None or g.user["id"] not in (conversation["user_low"], conversation["user_high"]):
        abort(404)  # 404, bukan 403, supaya orang lain tidak tahu percakapan itu ada
    return conversation


def is_blocked(user_a, user_b):
    """True kalau salah satu memblokir yang lain. Pesan tidak bisa dikirim ke dua arah."""
    return bool(
        query(
            """SELECT 1 FROM blocks WHERE (blocker_id = ? AND blocked_id = ?)
                                        OR (blocker_id = ? AND blocked_id = ?)""",
            (user_a, user_b, user_b, user_a),
            one=True,
        )
    )


def unread_count(user_id):
    """Jumlah pesan yang belum dibaca, untuk angka di ikon pesan di navbar."""
    row = query(
        """SELECT COUNT(*) AS n FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE (c.user_low = ? OR c.user_high = ?) AND m.sender_id != ?
              AND m.read_at IS NULL AND m.is_hidden = 0""",
        (user_id, user_id, user_id),
        one=True,
    )
    return row["n"]


def can_see_message_file(message_id):
    """Dipakai saat menyajikan lampiran chat: peserta percakapan, atau admin bila dilaporkan."""
    if message_id is None or g.user is None:
        return False
    row = query(
        """SELECT c.user_low, c.user_high FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = ?""",
        (message_id,),
        one=True,
    )
    if row is None:
        return False
    if g.user["id"] in (row["user_low"], row["user_high"]):
        return True
    return is_admin() and bool(
        query("SELECT 1 FROM message_reports WHERE message_id = ?", (message_id,), one=True)
    )


def _conversation_list(keyword="", unread_only=False):
    """Daftar percakapan pengguna, terbaru di atas, beserta cuplikan pesan terakhir."""
    me = g.user["id"]
    rows = query(
        """SELECT c.*, u.id AS other_id, u.full_name, u.photo, u.prodi, u.angkatan,
                  last.body AS last_body, last.sender_id AS last_sender, last.is_hidden AS last_hidden,
                  (SELECT kind FROM attachments a WHERE a.message_id = last.id ORDER BY a.id LIMIT 1) AS last_kind,
                  (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.sender_id != ?
                      AND m.read_at IS NULL AND m.is_hidden = 0) AS n_unread
             FROM conversations c
             JOIN users u ON u.id = CASE WHEN c.user_low = ? THEN c.user_high ELSE c.user_low END
             LEFT JOIN messages last ON last.id = (SELECT MAX(id) FROM messages WHERE conversation_id = c.id)
            WHERE (c.user_low = ? OR c.user_high = ?) AND c.last_message_at IS NOT NULL
            ORDER BY c.last_message_at DESC, c.id DESC""",
        (me, me, me, me),
    )
    if keyword:
        rows = [row for row in rows if keyword.lower() in row["full_name"].lower()]
    if unread_only:
        rows = [row for row in rows if row["n_unread"]]
    return rows


def _load_messages(conversation_id, after_id=0):
    """Pesan dalam percakapan (paling lama di atas) beserta lampirannya."""
    rows = query(
        """SELECT * FROM (
               SELECT m.*, u.full_name FROM messages m JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = ? AND m.id > ? ORDER BY m.id DESC LIMIT ?
           ) ORDER BY id""",
        (conversation_id, after_id, PAGE_SIZE),
    )
    files = attachments.for_owners("message_id", [row["id"] for row in rows])
    return [dict(row, files=files.get(row["id"], [])) for row in rows]


def _with_day_labels(messages, previous_day=None):
    """Tandai pesan pertama di tiap hari, supaya template bisa memberi pemisah "Hari ini"."""
    for message in messages:
        label = day_label(message["created_at"])
        message["day"] = label if label != previous_day else None
        previous_day = label
    return messages


def _mark_read(conversation_id):
    execute(
        """UPDATE messages SET read_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ? AND sender_id != ? AND read_at IS NULL""",
        (conversation_id, g.user["id"]),
    )


def _wants_json():
    return request.headers.get("X-Requested-With") == "fetch"


# ---------- Halaman ----------

@bp.route("/")
@login_required
def inbox():
    keyword = request.args.get("q", "").strip()
    unread_only = request.args.get("filter") == "belum"
    return render_template(
        "messages/index.html",
        conversations=_conversation_list(keyword, unread_only),
        conversation=None,
        keyword=keyword,
        unread_only=unread_only,
    )


@bp.route("/<int:conversation_id>")
@login_required
def conversation(conversation_id):
    conversation = _get_conversation(conversation_id)
    other = query(
        "SELECT id, full_name, photo, prodi, angkatan, status FROM users WHERE id = ?",
        (_other_id(conversation),),
        one=True,
    )
    _mark_read(conversation_id)
    origin = None
    if conversation["thread_id"]:
        origin = query("SELECT id, title FROM threads WHERE id = ?", (conversation["thread_id"],), one=True)
    latest_role = query(
        """SELECT e.position, c.name AS company_name FROM experiences e JOIN companies c ON c.id = e.company_id
            WHERE e.user_id = ? AND e.visibility != 'privat' AND c.is_approved = 1
            ORDER BY e.start_date DESC LIMIT 1""",
        (other["id"],),
        one=True,
    )
    i_blocked = bool(
        query("SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?", (g.user["id"], other["id"]), one=True)
    )
    return render_template(
        "messages/index.html",
        conversations=_conversation_list(),
        conversation=conversation,
        other=other,
        origin=origin,
        latest_role=latest_role,
        messages=_with_day_labels(_load_messages(conversation_id)),
        blocked=is_blocked(g.user["id"], other["id"]),
        i_blocked=i_blocked,
        keyword="",
        unread_only=False,
    )


@bp.route("/mulai/<int:user_id>", methods=("POST",))
@login_required
def start(user_id):
    """Buka percakapan dengan seseorang (dibuat kalau belum ada), lalu pindah ke halamannya."""
    if user_id == g.user["id"]:
        abort(400, description=_("Kamu tidak bisa mengirim pesan ke diri sendiri."))
    other = query("SELECT id FROM users WHERE id = ? AND is_verified = 1", (user_id,), one=True)
    if other is None:
        abort(404)
    low, high = _pair(g.user["id"], user_id)
    existing = query(
        "SELECT id FROM conversations WHERE user_low = ? AND user_high = ?", (low, high), one=True
    )
    if existing:
        return redirect(url_for("messages.conversation", conversation_id=existing["id"]))
    thread_id = request.form.get("thread_id", "")
    thread_id = int(thread_id) if thread_id.isdigit() else None
    if thread_id and not query("SELECT 1 FROM threads WHERE id = ?", (thread_id,), one=True):
        thread_id = None
    conversation_id = execute(
        "INSERT INTO conversations (user_low, user_high, thread_id) VALUES (?, ?, ?)", (low, high, thread_id)
    )
    return redirect(url_for("messages.conversation", conversation_id=conversation_id))


@bp.route("/<int:conversation_id>/kirim", methods=("POST",))
@login_required
def send(conversation_id):
    conversation = _get_conversation(conversation_id)
    other_id = _other_id(conversation)
    error = None
    body = request.form.get("body", "").strip()[:MAX_BODY]
    uploads, upload_error = attachments.read_uploads(request.files.getlist("files"))
    if is_blocked(g.user["id"], other_id):
        error = _("Pesan tidak bisa dikirim karena salah satu dari kalian memblokir yang lain.")
    elif upload_error:
        error = upload_error
    elif not body and not uploads:
        error = _("Pesan masih kosong.")

    if error:
        if _wants_json():
            return jsonify(error=error), 400
        flash(error, "error")
        return redirect(url_for("messages.conversation", conversation_id=conversation_id))

    message_id = execute(
        "INSERT INTO messages (conversation_id, sender_id, body) VALUES (?, ?, ?)",
        (conversation_id, g.user["id"], body),
    )
    attachments.store(uploads, "chat", g.user["id"], message_id=message_id)
    execute("UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    if _wants_json():
        return _new_messages_json(conversation_id)
    return redirect(url_for("messages.conversation", conversation_id=conversation_id) + "#akhir")


@bp.route("/<int:conversation_id>/baru")
@login_required
def new_messages(conversation_id):
    """Dipanggil app.js setiap beberapa detik: kirim pesan setelah id tertentu dalam bentuk HTML."""
    _get_conversation(conversation_id)
    _mark_read(conversation_id)
    return _new_messages_json(conversation_id)


def _new_messages_json(conversation_id):
    after = request.args.get("setelah", request.form.get("setelah", "0"))
    after = int(after) if str(after).isdigit() else 0
    previous = query(
        "SELECT created_at FROM messages WHERE id = ? AND conversation_id = ?", (after, conversation_id), one=True
    )
    messages = _with_day_labels(
        _load_messages(conversation_id, after), day_label(previous["created_at"]) if previous else None
    )
    html = render_template("messages/_messages.html", messages=messages)
    return jsonify(html=html, last_id=messages[-1]["id"] if messages else after, unread=unread_count(g.user["id"]))


@bp.route("/<int:conversation_id>/blokir", methods=("POST",))
@login_required
def toggle_block(conversation_id):
    """Blokir atau buka blokir lawan bicara."""
    other_id = _other_id(_get_conversation(conversation_id))
    key = (g.user["id"], other_id)
    if query("SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?", key, one=True):
        execute("DELETE FROM blocks WHERE blocker_id = ? AND blocked_id = ?", key)
        flash(_("Blokir dibuka. Kalian bisa saling mengirim pesan lagi."), "success")
    else:
        execute("INSERT INTO blocks (blocker_id, blocked_id) VALUES (?, ?)", key)
        flash(_("Pengguna diblokir. Dia tidak bisa mengirim pesan kepadamu."), "success")
    return redirect(url_for("messages.conversation", conversation_id=conversation_id))


@bp.route("/lapor/<int:message_id>", methods=("POST",))
@login_required
def report(message_id):
    """Laporkan pesan yang diterima. Admin hanya bisa membaca pesan yang dilaporkan ini."""
    message = query("SELECT * FROM messages WHERE id = ?", (message_id,), one=True)
    if message is None:
        abort(404)
    _get_conversation(message["conversation_id"])  # pelapor harus peserta percakapan
    if message["sender_id"] == g.user["id"]:
        abort(400, description=_("Kamu tidak bisa melaporkan pesanmu sendiri."))
    reason = request.form.get("reason", "").strip()[:300]
    if len(reason) < 5:
        flash("Tulis alasan laporan supaya admin bisa menindaklanjuti.", "error")
    else:
        execute(
            "INSERT INTO message_reports (reporter_id, message_id, reason) VALUES (?, ?, ?)",
            (g.user["id"], message_id, reason),
        )
        flash("Laporan terkirim ke admin.", "success")
    return redirect(url_for("messages.conversation", conversation_id=message["conversation_id"]))
