// 10. Tombol "Tampilkan" di kolom kata sandi, supaya pengguna bisa memeriksa ketikannya.
document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  const input = document.getElementById(button.getAttribute("aria-controls"));
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? button.dataset.hide : button.dataset.show;
    button.setAttribute("aria-pressed", String(show));
    input.focus();
  });
});
