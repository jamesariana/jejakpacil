// 11. Angka di ikon lonceng dan pesan tetap terbaru di semua halaman.
//     Ditanyakan ke server setiap 30 detik selama tab terlihat. Judul tab juga
//     diberi angka, misalnya "(3) JejakPacil", supaya terlihat dari tab lain.
const countsUrl = document.body.dataset.countsUrl;
if (countsUrl) {
  const bellBadge = document.querySelector("[data-notification-count]");
  const messageBadge = document.querySelector("[data-unread-count]");
  const baseTitle = document.title.replace(/^\(\d+\+?\)\s*/, "");
  const setBadge = (badge, n) => {
    if (!badge) return;
    badge.textContent = n > 99 ? "99+" : n;
    badge.hidden = n === 0;
  };
  const refresh = async () => {
    if (document.hidden) return;
    try {
      const response = await fetch(countsUrl, { headers: { "X-Requested-With": "fetch" } });
      if (!response.ok) return;
      const data = await response.json();
      setBadge(bellBadge, data.notifications);
      setBadge(messageBadge, data.messages);
      const total = data.notifications + data.messages;
      document.title = total ? `(${total > 99 ? "99+" : total}) ${baseTitle}` : baseTitle;
    } catch (e) { /* coba lagi di putaran berikutnya */ }
  };
  refresh();
  setInterval(refresh, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
}
