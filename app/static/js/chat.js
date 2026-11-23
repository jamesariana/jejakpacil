// 9. Chat pribadi.
//    - Kirim tanpa memuat ulang halaman (fetch), Enter untuk kirim.
//    - Menu tiap pesan: Balas, Edit, dan Hapus (pesan sendiri) atau Laporkan.
//    - Setiap 4 detik selama tab terlihat, ambil pesan baru dan pesan yang diedit/dihapus
//      lawan bicara (polling).
//    Tanpa JavaScript semuanya tetap bisa dipakai lewat form biasa dan ?balas= / ?edit=.
const chat = document.querySelector("[data-chat]");
if (chat) {
  const list = chat.querySelector("[data-chat-list]");
  const form = document.querySelector("[data-chat-form]");
  const unreadBadge = document.querySelector("[data-unread-count]");
  let lastId = Number(chat.dataset.lastId || 0);
  let since = chat.dataset.now || "";
  let busy = false;

  const nearBottom = () => chat.scrollHeight - chat.scrollTop - chat.clientHeight < 120;
  const toBottom = () => { chat.scrollTop = chat.scrollHeight; };
  if (!location.hash || location.hash === "#akhir") toBottom();
  // Foto selesai dimuat setelah halaman tampil; gulir lagi supaya pesan terakhir terlihat.
  chat.querySelectorAll("img").forEach((img) => img.addEventListener("load", () => {
    if (!location.hash || location.hash === "#akhir") toBottom();
  }, { once: true }));

  const htmlToNodes = (html) => {
    const holder = document.createElement("div");
    holder.innerHTML = html;
    return holder;
  };

  // Ganti satu gelembung dengan versi terbaru dari server (setelah diedit atau dihapus).
  const replaceMessage = (id, html) => {
    const old = list.querySelector(`[data-message-id="${id}"]`);
    const fresh = htmlToNodes(html).querySelector("[data-message-id]");
    if (old && fresh) old.replaceWith(fresh);
  };

  const apply = (data) => {
    (data.changed || []).forEach((item) => replaceMessage(item.id, item.html));
    if (data.now) since = data.now;
    if (unreadBadge && typeof data.unread === "number") {
      unreadBadge.textContent = data.unread;
      unreadBadge.hidden = data.unread === 0;
    }
    if (!data.html || !data.html.trim()) return;
    const stick = nearBottom();
    const empty = chat.querySelector("[data-chat-empty]");
    if (empty) empty.remove();
    const holder = htmlToNodes(data.html);
    // Lewati pesan yang sudah ada (bisa terjadi bila kiriman dan polling datang bersamaan).
    holder.querySelectorAll("[data-message-id]").forEach((node) => {
      if (list.querySelector(`[data-message-id="${node.dataset.messageId}"]`)) node.remove();
    });
    holder.querySelectorAll("img").forEach((img) => img.addEventListener("load", () => stick && toBottom(), { once: true }));
    list.append(...holder.childNodes);
    lastId = Math.max(lastId, Number(data.last_id || 0));
    if (stick) toBottom();
  };

  const poll = async () => {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const url = `${chat.dataset.pollUrl}?setelah=${lastId}&ubah=${encodeURIComponent(since)}`;
      const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
      if (response.ok) apply(await response.json());
    } catch (e) { /* koneksi putus sebentar: coba lagi di putaran berikutnya */ }
    busy = false;
  };
  setInterval(poll, 4000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });

  // Menu ⋯ di pesan dekat bagian bawah dibuka ke atas supaya tidak terpotong,
  // dan hanya satu menu yang terbuka pada satu waktu.
  list.addEventListener("toggle", (event) => {
    const menu = event.target;
    if (!menu.classList || !menu.classList.contains("b-menu") || !menu.open) return;
    list.querySelectorAll(".b-menu[open]").forEach((other) => { if (other !== menu) other.open = false; });
    const room = chat.getBoundingClientRect().bottom - menu.getBoundingClientRect().bottom;
    menu.classList.toggle("opens-up", room < 200);
  }, true);

  // Klik kutipan balasan: gulir ke pesan aslinya dan beri sorotan sebentar.
  list.addEventListener("click", (event) => {
    const quote = event.target.closest("[data-jump]");
    if (!quote) return;
    event.preventDefault();
    const target = list.querySelector(`[data-message-id="${quote.dataset.jump}"]`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.remove("is-flash");
    void target.offsetWidth; // mulai ulang animasi
    target.classList.add("is-flash");
  });

  if (form) {
    const textarea = form.querySelector("[data-chat-input]");
    const errorBox = form.querySelector("[data-chat-error]");
    const context = form.querySelector("[data-chat-context]");
    const contextTitle = form.querySelector("[data-context-title]");
    const contextSummary = form.querySelector("[data-context-summary]");
    const contextIcon = form.querySelector("[data-context-icon]");
    const replyInput = form.querySelector("[data-reply-input]");
    const attachButton = form.querySelector("[data-attach-button]");
    const fileInput = form.querySelector("[data-attach-input]");
    const sendButton = form.querySelector("button[type=submit]");
    // Ikon untuk tiap mode disiapkan server di <template>, supaya tidak ditulis ulang di sini.
    const iconFrom = (name) => form.querySelector(`template[data-icon="${name}"]`).innerHTML;
    let editingId = form.classList.contains("is-editing") ? Number(form.action.match(/pesan\/(\d+)\/edit/)[1]) : null;

    const grow = () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
    };
    textarea.addEventListener("input", grow);
    grow();

    // Kembali ke mode pesan baru.
    const resetMode = () => {
      if (editingId) textarea.value = "";
      editingId = null;
      replyInput.value = "";
      context.hidden = true;
      form.classList.remove("is-editing");
      form.action = form.dataset.sendUrl;
      attachButton.hidden = false;
      fileInput.disabled = false;
      sendButton.innerHTML = iconFrom("send");
      grow();
    };

    const startReply = (bubble) => {
      if (editingId) resetMode();
      replyInput.value = bubble.dataset.messageId;
      contextTitle.textContent = contextTitle.dataset.replyLabel.replace("{name}", bubble.dataset.sender);
      contextSummary.textContent = bubble.dataset.summary;
      contextIcon.innerHTML = iconFrom("reply");
      context.hidden = false;
      textarea.focus();
    };

    const startEdit = (bubble) => {
      replyInput.value = "";
      editingId = Number(bubble.dataset.messageId);
      form.action = form.dataset.editUrl.replace(/\/0\/edit$/, `/${editingId}/edit`);
      form.classList.add("is-editing");
      contextTitle.textContent = contextTitle.dataset.editLabel;
      contextSummary.textContent = bubble.dataset.summary;
      contextIcon.innerHTML = iconFrom("edit");
      context.hidden = false;
      attachButton.hidden = true; // lampiran tidak bisa diganti saat mengedit
      fileInput.disabled = true;
      sendButton.innerHTML = iconFrom("check");
      textarea.value = bubble.dataset.body;
      grow();
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    };

    form.querySelector("[data-context-close]").addEventListener("click", (event) => {
      event.preventDefault();
      resetMode();
      textarea.focus();
    });

    // Menu tiap pesan (Balas, Edit, Hapus).
    list.addEventListener("click", (event) => {
      const action = event.target.closest("a[data-action]");
      if (!action) return;
      event.preventDefault();
      const bubble = action.closest("[data-message-id]");
      action.closest("details").open = false;
      if (action.dataset.action === "reply") startReply(bubble);
      if (action.dataset.action === "edit") startEdit(bubble);
    });

    list.addEventListener("submit", async (event) => {
      const deleteForm = event.target.closest("form[data-action=delete]");
      if (!deleteForm) return; // konfirmasi "Hapus?" sudah ditangani bagian 3
      event.preventDefault();
      try {
        const response = await fetch(deleteForm.action, {
          method: "POST", body: new FormData(deleteForm), headers: { "X-Requested-With": "fetch" },
        });
        const result = await response.json();
        if (response.ok) {
          replaceMessage(result.id, result.html);
          if (editingId === result.id || Number(replyInput.value) === result.id) resetMode();
        }
      } catch (e) {
        deleteForm.submit();
      }
    });

    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        form.requestSubmit();
      }
      if (event.key === "Escape" && !context.hidden) {
        event.preventDefault();
        resetMode();
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const hasFiles = fileInput && !fileInput.disabled && fileInput.files.length;
      if (!textarea.value.trim() && !hasFiles && !editingId) return;
      const data = new FormData(form);
      data.append("setelah", lastId);
      data.append("ubah", since);
      sendButton.disabled = true;
      errorBox.hidden = true;
      try {
        const response = await fetch(form.action, {
          method: "POST", body: data, headers: { "X-Requested-With": "fetch" },
        });
        const result = await response.json();
        if (!response.ok) {
          errorBox.textContent = result.error;
          errorBox.hidden = false;
        } else if (editingId) {
          replaceMessage(result.id, result.html);
          resetMode();
        } else {
          textarea.value = "";
          form.dispatchEvent(new Event("reset-attachments"));
          resetMode();
          apply(result);
          toBottom();
        }
      } catch (e) {
        form.submit(); // gagal lewat fetch: kirim cara biasa
      }
      sendButton.disabled = false;
      textarea.focus();
    });
  }
}
