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
