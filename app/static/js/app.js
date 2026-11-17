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
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

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
    const label = dark ? "Ganti ke mode terang" : "Ganti ke mode gelap";
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
