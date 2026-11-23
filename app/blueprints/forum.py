"""Forum: thread, balasan, suara (upvote), dan laporan. Hanya untuk pengguna yang masuk."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import attachments
from ..db import execute, query
from ..i18n import _
from ..notifications import notify
from ..forms import validate_thread
from ..queries import approved_companies
from ..security import is_admin, login_required
from ..utils import Page, delete_upload

bp = Blueprint("forum", __name__, url_prefix="/forum")

THREAD_SELECT = """
    SELECT t.*, u.full_name, u.photo, u.status AS user_status, u.angkatan,
           cat.name AS category_name, cat.slug AS category_slug,
           c.name AS company_name, c.slug AS company_slug,
           (SELECT COUNT(*) FROM replies r WHERE r.thread_id = t.id AND r.is_hidden = 0) AS n_replies,
           (SELECT COUNT(*) FROM votes v WHERE v.thread_id = t.id) AS n_votes
      FROM threads t
      JOIN users u ON u.id = t.author_id
      JOIN categories cat ON cat.id = t.category_id
      LEFT JOIN companies c ON c.id = t.company_id
"""


def _categories():
    """Kategori beserta jumlah thread yang tampil di tiap kategori."""
    return query(
        """SELECT cat.*,
                  (SELECT COUNT(*) FROM threads t WHERE t.category_id = cat.id AND t.is_hidden = 0) AS n_threads
             FROM categories cat ORDER BY cat.position"""
    )


def _get_thread(thread_id):
    thread = query(f"{THREAD_SELECT} WHERE t.id = ?", (thread_id,), one=True)
    if thread is None or (thread["is_hidden"] and not is_admin()):
        abort(404)
    return thread


@bp.route("/")
@login_required
def index():
    args = request.args
    where, params = ["t.is_hidden = 0"], []
    if args.get("kategori"):
        where.append("cat.slug = ?")
        params.append(args["kategori"])
    if args.get("q", "").strip():
        where.append("(t.title LIKE ? OR t.body LIKE ?)")
        like = f"%{args['q'].strip()}%"
        params += [like, like]
    where_sql = " AND ".join(where)
    order = "n_votes DESC, t.created_at DESC" if args.get("urut") == "populer" else "t.created_at DESC"

    total = query(
        f"SELECT COUNT(*) AS n FROM threads t JOIN categories cat ON cat.id = t.category_id WHERE {where_sql}",
        params,
        one=True,
    )["n"]
    page = Page(total, per_page=15)
    threads = query(
        f"{THREAD_SELECT} WHERE {where_sql} ORDER BY t.is_pinned DESC, {order}, t.id DESC LIMIT ? OFFSET ?",
        params + [page.per_page, page.offset],
    )
    categories = _categories()
    return render_template(
        "forum/index.html",
        threads=threads,
        page=page,
        categories=categories,
        total_threads=sum(cat["n_threads"] for cat in categories),
    )


@bp.route("/buat", methods=("GET", "POST"))
@login_required
def create():
    categories, companies = _categories(), approved_companies()
    errors = {}
    if request.method == "POST":
        data, errors = validate_thread(
            request.form, {row["id"] for row in categories}, {row["id"] for row in companies}
        )
        uploads, upload_error = attachments.read_uploads(request.files.getlist("files"))
        if upload_error:
            errors["files"] = upload_error
        if not errors:
            thread_id = execute(
                "INSERT INTO threads (author_id, category_id, company_id, title, body, is_anonymous)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (g.user["id"], data["category_id"], data["company_id"], data["title"], data["body"],
                 data["is_anonymous"]),
            )
            attachments.store(uploads, "forum", g.user["id"], thread_id=thread_id)
            flash("Thread diterbitkan.", "success")
            return redirect(url_for("forum.thread", thread_id=thread_id))
        form = request.form
    else:
        # Tautan "Mulai diskusi" di halaman perusahaan mengisi tag perusahaan lebih dulu.
        form = {"company_id": request.args.get("perusahaan", ""), "category_id": request.args.get("kategori_id", "")}
    return render_template(
        "forum/form.html", form=form, errors=errors, categories=categories, companies=companies, thread=None,
        current_files=[],
    )


@bp.route("/t/<int:thread_id>")
@login_required
def thread(thread_id):
    thread = _get_thread(thread_id)
    replies = query(
        """SELECT r.*, u.full_name, u.photo, u.status AS user_status, u.angkatan
             FROM replies r JOIN users u ON u.id = r.author_id
            WHERE r.thread_id = ? ORDER BY r.created_at, r.id""",
        (thread_id,),
    )
    # Susun balasan menjadi dua tingkat: balasan utama dan anak-anaknya.
    top_level = [reply for reply in replies if reply["parent_id"] is None]
    children = {}
    for reply in replies:
        if reply["parent_id"] is not None:
            children.setdefault(reply["parent_id"], []).append(reply)
    voted = query(
        "SELECT 1 FROM votes WHERE user_id = ? AND thread_id = ?", (g.user["id"], thread_id), one=True
    )
    return render_template(
        "forum/thread.html",
        thread=thread,
        top_level=top_level,
        children=children,
        voted=bool(voted),
        thread_files=attachments.for_owners("thread_id", [thread_id]).get(thread_id, []),
        reply_files=attachments.for_owners("reply_id", [reply["id"] for reply in replies]),
    )


@bp.route("/t/<int:thread_id>/edit", methods=("GET", "POST"))
@login_required
def edit(thread_id):
    thread = _get_thread(thread_id)
    if thread["author_id"] != g.user["id"]:
        abort(403)
    categories, companies = _categories(), approved_companies()
    current_files = attachments.for_owners("thread_id", [thread_id]).get(thread_id, [])
    errors = {}
    if request.method == "POST":
        data, errors = validate_thread(
            request.form, {row["id"] for row in categories}, {row["id"] for row in companies}
        )
        uploads, upload_error = attachments.read_uploads(request.files.getlist("files"))
        removed = {int(x) for x in request.form.getlist("remove_file") if x.isdigit()}
        kept = [row for row in current_files if row["id"] not in removed]
        if upload_error:
            errors["files"] = upload_error
        elif len(kept) + len(uploads) > attachments.MAX_FILES:
            errors["files"] = _("Lampiran maksimal {n} file.", n=attachments.MAX_FILES)
        if not errors:
            execute(
                """UPDATE threads SET category_id = ?, company_id = ?, title = ?, body = ?, is_anonymous = ?,
                          updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (data["category_id"], data["company_id"], data["title"], data["body"], data["is_anonymous"],
                 thread_id),
            )
            for row in current_files:
                if row["id"] in removed:
                    delete_upload("forum", row["stored_name"])
                    execute("DELETE FROM attachments WHERE id = ?", (row["id"],))
            attachments.store(uploads, "forum", g.user["id"], thread_id=thread_id)
            flash("Thread disimpan.", "success")
            return redirect(url_for("forum.thread", thread_id=thread_id))
        form = request.form
    else:
        form = dict(thread)
    return render_template(
        "forum/form.html", form=form, errors=errors, categories=categories, companies=companies, thread=thread,
        current_files=current_files,
    )


@bp.route("/t/<int:thread_id>/hapus", methods=("POST",))
@login_required
def delete(thread_id):
    thread = _get_thread(thread_id)
    if thread["author_id"] != g.user["id"] and not is_admin():
        abort(403)
    # File lampiran dihapus dari disk dulu; barisnya ikut terhapus oleh CASCADE.
    attachments.remove("thread_id", thread_id, "forum")
    for row in query("SELECT id FROM replies WHERE thread_id = ?", (thread_id,)):
        attachments.remove("reply_id", row["id"], "forum")
    execute("DELETE FROM threads WHERE id = ?", (thread_id,))  # balasan dan suara ikut terhapus (CASCADE)
    flash("Thread dihapus.", "success")
    return redirect(url_for("forum.index"))


@bp.route("/t/<int:thread_id>/balas", methods=("POST",))
@login_required
def reply(thread_id):
    thread = _get_thread(thread_id)
    body = request.form.get("body", "").strip()[:4000]
    uploads, upload_error = attachments.read_uploads(request.files.getlist("files"))
    if upload_error:
        flash(upload_error, "error")
        return redirect(url_for("forum.thread", thread_id=thread_id) + "#tulis")
    if len(body) < 2 and not uploads:  # balasan boleh hanya berisi foto
        flash("Balasan masih kosong. Tulis sesuatu dulu.", "error")
        return redirect(url_for("forum.thread", thread_id=thread_id))

    parent_id = parent_author = None
    if request.form.get("parent_id", "").isdigit():
        parent = query(
            "SELECT id, parent_id, author_id FROM replies WHERE id = ? AND thread_id = ?",
            (int(request.form["parent_id"]), thread_id),
            one=True,
        )
        if parent is not None:
            # Hanya dua tingkat: membalas "anak" berarti menempel ke balasan utamanya.
            parent_id = parent["parent_id"] or parent["id"]
            parent_author = parent["author_id"]  # yang dibalas langsung, untuk notifikasi
    reply_id = execute(
        "INSERT INTO replies (thread_id, author_id, parent_id, body, is_anonymous) VALUES (?, ?, ?, ?, ?)",
        (thread["id"], g.user["id"], parent_id, body, 1 if request.form.get("is_anonymous") else 0),
    )
    attachments.store(uploads, "forum", g.user["id"], reply_id=reply_id)

    # Notifikasi: penulis komentar yang dibalas, lalu penulis thread (sekali saja per orang).
    anonymous = bool(request.form.get("is_anonymous"))
    link = url_for("forum.thread", thread_id=thread_id) + f"#balasan-{reply_id}"
    if parent_author:
        notify(parent_author, "balasan_komentar", link, subject=thread["title"],
               actor_id=g.user["id"], is_anonymous=anonymous)
    if thread["author_id"] != parent_author:
        notify(thread["author_id"], "balasan_thread", link, subject=thread["title"],
               actor_id=g.user["id"], is_anonymous=anonymous)
    flash("Balasan terkirim.", "success")
    return redirect(url_for("forum.thread", thread_id=thread_id) + f"#balasan-{reply_id}")


@bp.route("/balasan/<int:reply_id>/hapus", methods=("POST",))
@login_required
def delete_reply(reply_id):
    reply = query("SELECT * FROM replies WHERE id = ?", (reply_id,), one=True)
    if reply is None:
        abort(404)
    if reply["author_id"] != g.user["id"] and not is_admin():
        abort(403)
    attachments.remove("reply_id", reply_id, "forum")
    for row in query("SELECT id FROM replies WHERE parent_id = ?", (reply_id,)):
        attachments.remove("reply_id", row["id"], "forum")
    execute("DELETE FROM replies WHERE id = ?", (reply_id,))
    flash("Balasan dihapus.", "success")
    return redirect(url_for("forum.thread", thread_id=reply["thread_id"]))


@bp.route("/t/<int:thread_id>/suara", methods=("POST",))
@login_required
def vote(thread_id):
    """Tombol suara bersifat bolak-balik: tekan sekali memberi suara, tekan lagi mencabutnya."""
    thread = _get_thread(thread_id)
    key = (g.user["id"], thread_id)
    if query("SELECT 1 FROM votes WHERE user_id = ? AND thread_id = ?", key, one=True):
        execute("DELETE FROM votes WHERE user_id = ? AND thread_id = ?", key)
    else:
        execute("INSERT INTO votes (user_id, thread_id) VALUES (?, ?)", key)
        # Digabung per thread: "3 orang memberi suara", bukan tiga notifikasi terpisah.
        notify(thread["author_id"], "suara", url_for("forum.thread", thread_id=thread_id),
               subject=thread["title"], actor_id=g.user["id"], group_key=f"suara-{thread_id}")
    return redirect(url_for("forum.thread", thread_id=thread_id))


@bp.route("/lapor", methods=("POST",))
@login_required
def report():
    """Laporkan thread atau balasan ke admin."""
    reason = request.form.get("reason", "").strip()[:300]
    thread_id = request.form.get("thread_id", "")
    reply_id = request.form.get("reply_id", "")
    target_thread = None
    if reply_id.isdigit():
        reply = query("SELECT id, thread_id FROM replies WHERE id = ?", (int(reply_id),), one=True)
        if reply is None:
            abort(404)
        target_thread = reply["thread_id"]
        values = (g.user["id"], None, reply["id"], reason)
    elif thread_id.isdigit():
        target_thread = _get_thread(int(thread_id))["id"]
        values = (g.user["id"], target_thread, None, reason)
    else:
        abort(400, description="Laporan tidak menyebut thread atau balasan mana yang dimaksud.")
    if len(reason) < 5:
        flash("Tulis alasan laporan supaya admin bisa menindaklanjuti.", "error")
    else:
        execute("INSERT INTO reports (reporter_id, thread_id, reply_id, reason) VALUES (?, ?, ?, ?)", values)
        flash("Laporan terkirim ke admin.", "success")
    return redirect(url_for("forum.thread", thread_id=target_thread))
