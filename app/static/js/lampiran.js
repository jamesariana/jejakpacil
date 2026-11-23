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
