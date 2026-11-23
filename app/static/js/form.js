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
