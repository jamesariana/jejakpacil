// JavaScript kecil untuk kenyamanan form. Situs tetap berfungsi tanpa file ini,
// karena semua validasi yang sebenarnya dilakukan di server (Python).

// 1. Tampilkan isian hanya saat pilihan tertentu dipilih.
//    Contoh: isian "Tahun lulus" hanya muncul jika Status = alumni.
//    Bisa dipasang di <select> atau di pembungkus sekelompok radio (fieldset).
document.querySelectorAll("[data-toggle-target]").forEach((control) => {
  const target = document.getElementById(control.dataset.toggleTarget);
  if (!target) return;
  const currentValue = () => {
    if (control.tagName === "SELECT") return control.value;
    const checked = control.querySelector("input:checked");
    return checked ? checked.value : "";
  };
  const update = () => {
    target.hidden = currentValue() !== control.dataset.toggleValue;
  };
  control.addEventListener("change", update);
  update();
});

// 2. Kotak centang yang mematikan isian lain.
//    Contoh: "Masih berjalan" mematikan isian "Bulan selesai".
document.querySelectorAll("[data-disables]").forEach((checkbox) => {
  const target = document.getElementById(checkbox.dataset.disables);
  if (!target) return;
  const update = () => {
    target.disabled = checkbox.checked;
  };
  checkbox.addEventListener("change", update);
  update();
});

// 3. Minta konfirmasi sebelum tindakan yang tidak bisa dibatalkan (hapus, gabung).
//    Dipasang di document (fase capture) supaya juga berlaku untuk form yang baru
//    muncul belakangan, misalnya tombol Hapus di pesan chat yang baru masuk.
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-confirm]");
  if (form && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

// 4. Tutup menu akun saat pengguna mengklik di luar menu.
document.addEventListener("click", (event) => {
  document.querySelectorAll("details.menu[open]").forEach((menu) => {
    if (!menu.contains(event.target)) menu.removeAttribute("open");
  });
});

// 5. Menu utama dengan "pil" yang bergeser.
//    - Pil terang mengikuti menu yang sedang ditunjuk kursor.
//    - Pil berwarna menandai menu aktif. Saat menu diklik, pil ini bergeser dulu
//      ke menu yang dipilih, baru halamannya berpindah.
const sliderNav = document.querySelector("[data-slider]");
if (sliderNav) {
  const links = Array.from(sliderNav.querySelectorAll("a"));
  const activePill = sliderNav.querySelector(".nav-pill-active");
  const hoverPill = sliderNav.querySelector(".nav-pill-hover");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SLIDE_MS = 320;
  let current = links.find((link) => link.hasAttribute("aria-current")) || null;

  // Letakkan pil tepat di belakang sebuah menu.
  const place = (pill, link) => {
    if (!link) {
      pill.style.opacity = "0";
      return;
    }
    pill.style.width = `${link.offsetWidth}px`;
    pill.style.height = `${link.offsetHeight}px`;
    pill.style.transform = `translate(${link.offsetLeft}px, ${link.offsetTop}px)`;
    pill.style.opacity = "1";
  };

  const markActive = (link) => {
    links.forEach((a) => a.classList.toggle("is-active", a === link));
  };

  // Posisi awal tanpa animasi, supaya pil tidak "terbang" saat halaman dibuka.
  const placeWithoutAnimation = () => {
    sliderNav.classList.add("no-anim");
    markActive(current);
    place(activePill, current);
    requestAnimationFrame(() => requestAnimationFrame(() => sliderNav.classList.remove("no-anim")));
  };
  sliderNav.classList.add("js-slider");
  placeWithoutAnimation();

  // Pil kursor selalu berangkat dari menu yang sedang aktif, lalu bergeser ke menu
  // yang ditunjuk. Kalau belum ada menu aktif, pil tumbuh dari tengah menu yang ditunjuk.
  let hoverVisible = false;
  const showHover = (link) => {
    if (!hoverVisible) {
      hoverPill.classList.add("no-anim");
      if (current) {
        place(hoverPill, current);
      } else {
        hoverPill.style.width = "0px";
        hoverPill.style.height = `${link.offsetHeight}px`;
        hoverPill.style.transform = `translate(${link.offsetLeft + link.offsetWidth / 2}px, ${link.offsetTop}px)`;
        hoverPill.style.opacity = "1";
      }
      hoverPill.getBoundingClientRect(); // paksa browser menerapkan posisi awal dulu
      hoverPill.classList.remove("no-anim");
      hoverVisible = true;
    }
    place(hoverPill, link);
  };
  const hideHover = () => {
    hoverPill.style.opacity = "0";
    hoverVisible = false;
  };

  links.forEach((link) => {
    link.addEventListener("mouseenter", () => showHover(link));
    link.addEventListener("focus", () => showHover(link));
    link.addEventListener("blur", hideHover);

    link.addEventListener("click", (event) => {
      // Biarkan klik dengan Cmd/Ctrl/Shift (buka tab baru) dan klik menu yang sudah aktif.
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0 || link === current) return;
      if (reduceMotion) return;
      event.preventDefault();
      if (!current) {
        // Belum ada menu aktif: munculkan pil langsung di menu yang dipilih.
        sliderNav.classList.add("no-anim");
        place(activePill, link);
        activePill.style.opacity = "0";
        requestAnimationFrame(() => {
          sliderNav.classList.remove("no-anim");
          activePill.style.opacity = "1";
        });
      } else {
        place(activePill, link);
      }
      current = link;
      markActive(link);
      hideHover();
      setTimeout(() => { window.location.href = link.href; }, SLIDE_MS);
    });
  });

  sliderNav.addEventListener("mouseleave", hideHover);
  window.addEventListener("resize", () => place(activePill, current));
  // Saat kembali dengan tombol Back, kembalikan pil ke menu halaman ini.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      current = links.find((link) => link.hasAttribute("aria-current")) || null;
      placeWithoutAnimation();
    }
  });
  // Ukuran huruf bisa berubah setelah font selesai dimuat.
  if (document.fonts) document.fonts.ready.then(() => place(activePill, current));
}

// 6. Tombol mode gelap / mode terang.
//    Pilihan disimpan di localStorage supaya tetap dipakai di halaman berikutnya.
//    Tema awal sudah dipasang oleh skrip kecil di <head> (base.html).
const themeButton = document.querySelector("[data-theme-toggle]");
if (themeButton) {
  const root = document.documentElement;
  const updateButton = () => {
    const dark = root.getAttribute("data-theme") === "dark";
    // Teks diambil dari atribut data-label-* supaya ikut bahasa yang dipilih.
    const label = dark ? themeButton.dataset.labelLight : themeButton.dataset.labelDark;
    themeButton.setAttribute("aria-label", label);
    themeButton.setAttribute("title", label);
  };
  updateButton();

  themeButton.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.classList.add("theme-switching");
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("jejakpacil-theme", next); } catch (e) { /* mode privat: abaikan */ }
    updateButton();
    setTimeout(() => root.classList.remove("theme-switching"), 350);
  });
}

// 7. Filter yang langsung diterapkan.
//    Form dengan atribut data-autosubmit dikirim begitu pilihan (radio atau
//    dropdown, atau sakelar) diganti, jadi tidak perlu tombol "Terapkan". Kolom pencarian
//    tetap dikirim lewat tombol Cari atau Enter.
document.querySelectorAll("form[data-autosubmit]").forEach((form) => {
  form.addEventListener("change", (event) => {
    if (event.target.matches("select, input[type=radio], input[type=checkbox]")) {
      form.requestSubmit ? form.requestSubmit() : form.submit();
    }
  });
  // Kolom yang kosong tidak ikut dikirim, supaya alamat halaman tetap pendek
  // (misalnya /pengalaman?prodi=Sistem+Informasi, bukan ?q=&angkatan=&skill=...).
  form.addEventListener("submit", () => {
    form.querySelectorAll("input[name], select[name]").forEach((field) => {
      if (field.value === "" && field.type !== "checkbox") field.disabled = true;
    });
  });
});

// 8. Pilih lampiran (forum dan chat).
//    Menampilkan pratinjau foto/PDF yang dipilih, dengan tombol × untuk membatalkan
//    satu file. Batas jumlah dan ukuran juga dicek di sini supaya pengguna langsung
//    tahu, tetapi server tetap memeriksa ulang semuanya.
const MAX_FILE_BYTES = 5 * 1024 * 1024;

function setupAttachments(box) {
  const input = box.querySelector("[data-attach-input]");
  const preview = box.querySelector("[data-attach-preview]");
  if (!input || !preview) return;
  const max = Number(input.dataset.max || 4);

  const render = () => {
    preview.replaceChildren();
    Array.from(input.files).forEach((file, index) => {
      const item = document.createElement("div");
      if (file.type.startsWith("image/")) {
        item.className = "pv";
        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        img.alt = file.name;
        img.onload = () => URL.revokeObjectURL(img.src);
        item.append(img);
      } else {
        item.className = "pvf";
        const ext = document.createElement("span");
        ext.className = "att-ext";
        ext.textContent = "PDF";
        const name = document.createElement("span");
        name.className = "pvf-name";
        name.textContent = file.name;
        item.append(ext, name);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "pv-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", file.name);
      remove.addEventListener("click", () => removeFile(index));
      item.append(remove);
      preview.append(item);
    });
    box.classList.toggle("has-files", input.files.length > 0);
  };

  // FileList tidak bisa diubah langsung, jadi disusun ulang lewat DataTransfer.
  const keepFiles = (files) => {
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    render();
  };
  const removeFile = (index) => keepFiles(Array.from(input.files).filter((_, i) => i !== index));

  input.addEventListener("change", () => {
    let files = Array.from(input.files);
    const tooBig = files.find((file) => file.size > MAX_FILE_BYTES);
    if (tooBig) {
      alertInline(box, input.dataset.sizeMessage.replace("{name}", tooBig.name));
      files = files.filter((file) => file.size <= MAX_FILE_BYTES);
    }
    if (files.length > max) {
      alertInline(box, input.dataset.maxMessage);
      files = files.slice(0, max);
    }
    keepFiles(files);
  });
  box.addEventListener("reset-attachments", () => keepFiles([]));
}

// Pesan singkat di dekat kolom lampiran (tanpa alert() yang memblokir halaman).
function alertInline(box, text) {
  let note = box.querySelector(".attach-error");
  if (!note) {
    note = document.createElement("p");
    note.className = "attach-error";
    note.setAttribute("role", "alert");
    box.append(note);
  }
  note.textContent = text;
  clearTimeout(note._timer);
  note._timer = setTimeout(() => note.remove(), 5000);
}

document.querySelectorAll("[data-attach]").forEach(setupAttachments);

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
