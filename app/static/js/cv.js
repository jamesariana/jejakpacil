// 12. Buat CV: pratinjau PDF diperbarui sendiri setiap pilihan berubah.
(function () {
  const form = document.querySelector("[data-cv-form]");
  const frame = document.querySelector("[data-cv-preview]");
  if (!form || !frame) return;

  // Tanpa JavaScript, tombol "Perbarui pratinjau" yang dipakai. Dengan JavaScript tidak perlu.
  const refresh = form.querySelector(".cv-refresh");
  if (refresh) refresh.remove();

  let timer = null;
  function update() {
    if (!frame.offsetParent) return; // pratinjau disembunyikan di layar kecil
    const params = new URLSearchParams(new FormData(form));
    params.set("pratinjau", "1");
    frame.src = form.action + "?" + params.toString() + "#toolbar=0&view=FitH";
  }
  function schedule(delay) {
    clearTimeout(timer);
    timer = setTimeout(update, delay);
  }
  // Kotak centang langsung; ketikan ringkasan ditunggu dulu supaya tidak membuat PDF tiap huruf.
  form.addEventListener("change", () => schedule(150));
  form.addEventListener("input", (event) => {
    if (event.target.tagName === "TEXTAREA") schedule(700);
  });
})();
