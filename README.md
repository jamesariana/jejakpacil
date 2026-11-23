# JejakPacil

Website untuk mencatat dan menelusuri riwayat magang dan kerja mahasiswa serta alumni Fasilkom UI.
Proyek kelompok Dasar-Dasar Pemrograman 1, Semester Gasal 2026/2027.

![Tes](https://github.com/jamesariana/jejakpacil/actions/workflows/tes.yml/badge.svg)

## Masalah yang diangkat

Info "siapa pernah magang di mana, lewat jalur apa" tersebar di grup chat, cerita dari mulut ke mulut,
dan profil media sosial masing-masing orang. Mahasiswa baru sulit menemukan kakak tingkat yang bisa
ditanya, dan fakultas tidak punya gambaran menyeluruh tentang ke mana mahasiswanya berkarya.

JejakPacil mengumpulkan riwayat itu di satu tempat yang khusus untuk sivitas Fasilkom.

## Fitur

| Fitur | Keterangan |
| --- | --- |
| Akun | Daftar hanya dengan email `@ui.ac.id`, verifikasi email, peran anggota dan admin |
| Profil | Prodi, angkatan, status (aktif/alumni), bio, skill, tautan, foto, CV (PDF) |
| Riwayat pengalaman | Tambah, ubah, hapus. Jenis: magang, full-time, part-time, freelance, riset, asdos |
| Privasi | Tiap pengalaman bisa publik, sivitas (hanya yang masuk), atau privat |
| Verifikasi | Unggah bukti, admin memberi tanda "Terverifikasi" |
| Direktori perusahaan | Semua perusahaan yang pernah ditempati, lengkap dengan logo dan jumlah orang |
| Logo otomatis | Logo diambil dari layanan logo berdasarkan domain, lalu disimpan di server sendiri |
| Jelajahi | Satu menu untuk dua pencarian: tab Pengalaman (cari posisi/perusahaan, filter jenis, prodi, angkatan, skill) dan tab Mahasiswa dan alumni |
| Beranda pribadi | Setelah masuk: daftar cek kelengkapan profil, diskusi terbaru, dan jalan pintas ke fitur |
| Forum | Kategori, thread, balasan dua tingkat, suara, posting anonim, tag perusahaan, laporan, lampiran foto dan PDF |
| Notifikasi | Ikon lonceng dengan jumlah belum dibaca: balasan forum, suara (digabung), keputusan verifikasi, perusahaan disetujui, konten disembunyikan |
| Cerita seleksi | Tahapan yang dilalui, lama proses, tingkat kesulitan, contoh pertanyaan, dan tips untuk adik tingkat, dirangkum per perusahaan ("Proses seleksi di ...") |
| Bidang pekerjaan | Posisi dengan nama berbeda ("BE Intern", "Backend Engineer") dikelompokkan ke satu bidang; bisa difilter di Jelajahi dan muncul di Statistik |
| Buat CV | Riwayat di profil diunduh jadi CV PDF (Indonesia atau Inggris) dengan foto profil dan pratinjau langsung. Bisa ditambah proyek, organisasi dan kepanitiaan, prestasi, serta sertifikasi yang tersimpan di akun. Pengalaman yang sudah diverifikasi admin diberi tanda ✓ |
| Chat pribadi | Kirim pesan ke siapa saja dari profil atau thread; teks, foto, dan PDF; penanda belum dibaca; blokir dan laporkan |
| Statistik | Perusahaan terbanyak, jenis pengalaman, jalur mendapatkan, skill, per angkatan |
| Panel admin | Verifikasi, setujui dan gabungkan perusahaan, moderasi forum, kelola pengguna, ekspor CSV |
| Dua bahasa | Tombol ID / EN di navbar mengganti seluruh tampilan ke bahasa Inggris dan kembali, tanpa library tambahan |
| Mode gelap | Tombol di navbar, pilihan disimpan di browser |

## Teknologi

- **Python 3.10+** dengan **Flask** sebagai kerangka web
- **SQLite** (modul bawaan `sqlite3`) sebagai database, dengan SQL yang ditulis sendiri
- **Jinja2** untuk template HTML, CSS dan sedikit JavaScript tanpa framework
- **Pillow** untuk memeriksa dan mengecilkan gambar unggahan
- **requests** untuk memanggil layanan logo
- **ReportLab** untuk membuat CV PDF
- **unittest** untuk tes otomatis

Hal yang tidak diajarkan di kelas DDP1 dan dipakai di sini: aplikasi web dengan routing dan blueprint,
database relasional dan SQL (JOIN, GROUP BY, subquery), template HTML, sesi login dan hashing kata
sandi, token bertanda tangan, perlindungan CSRF, unggah file, memanggil API luar, membuat PDF,
mengirim email lewat SMTP, decorator, dan tes otomatis dengan objek tiruan (mock).

## Cara menjalankan

Butuh Python 3.10 atau lebih baru.

```bash
# 1. Buat dan aktifkan lingkungan virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2. Pasang pustaka
pip install -r requirements.txt

# 3. (Opsional) Isi data contoh. --with-logos mengambil logo dari internet.
flask --app app seed-demo --with-logos

# 4. Jalankan
python run.py
```

Buka http://127.0.0.1:5000

Database dibuat otomatis saat aplikasi pertama kali dijalankan, di folder `instance/`.
Untuk mengulang dari nol, hapus folder `instance/`.

### Akun demo (setelah `seed-demo`)

| Peran | Email | Kata sandi |
| --- | --- | --- |
| Admin | `admin@ui.ac.id` | `admin12345` |
| Anggota | `salsa.demo@ui.ac.id` (dan 11 akun `*.demo@ui.ac.id` lain) | `pacil12345` |

Semua orang, riwayat, dan isi forum di data demo adalah **fiktif**. Nama perusahaan asli dipakai
hanya supaya fitur logo bisa dicoba.

### Tanpa data demo

```bash
flask --app app create-admin     # buat akun admin pertama
```

Di laptop, email tidak dikirim: tautan verifikasi dan atur ulang kata sandi ditampilkan di halaman
dan dicetak di terminal. Admin juga bisa memverifikasi email pengguna secara manual di panel admin.

## Menaruh website online

Langkah lengkap untuk PythonAnywhere (gratis), termasuk pengiriman email lewat Gmail, ada di
[DEPLOY.md](DEPLOY.md). Pengaturan server disimpan di `instance/config.py` (contohnya di
`config.example.py`), jadi kata sandi email tidak ikut masuk ke GitHub.

## Tes

```bash
python -m unittest discover -s tests -v
```

Ada 100 tes yang mencakup pendaftaran, login, lupa dan ganti kata sandi, CSRF, pengalaman dan
aturan privasinya, cerita seleksi, unggahan, perusahaan dan panel admin, pengambilan logo (dengan
balasan tiruan), forum dan lampirannya, chat pribadi, notifikasi, terjemahan Inggris, serta file
CSS dan JavaScript.

### Tes otomatis di GitHub (GitHub Actions)

Setiap kali ada `git push` atau pull request, GitHub menjalankan `.github/workflows/tes.yml`:
memasang dependensi, memeriksa sintaks Python dan JavaScript, menjalankan semua tes di Python
3.11, 3.12, dan 3.13, lalu mencoba mengisi data demo. Hasilnya ada di tab **Actions**, dan setiap
commit diberi tanda centang hijau (lulus) atau silang merah (ada yang gagal). Kalau merah, buka
tab Actions untuk melihat tes mana yang gagal, perbaiki, lalu push lagi.

## Struktur folder

```
jejakpacil/
├── run.py                  titik masuk: python run.py
├── requirements.txt
├── app/
│   ├── __init__.py         create_app(): merakit aplikasi
│   ├── schema.sql          struktur tabel database
│   ├── db.py               koneksi SQLite, query(), execute()
│   ├── constants.py        pilihan tetap (prodi, jenis pengalaman, industri, ...)
│   ├── security.py         sesi login, login_required, CSRF, token verifikasi
│   ├── forms.py            validasi masukan form
│   ├── queries.py          query bersama: aturan privasi, skill, perusahaan
│   ├── logos.py            ambil logo dari layanan luar
│   ├── utils.py            slug, tanggal, unggahan file, paginasi
│   ├── attachments.py      lampiran foto/PDF untuk forum dan chat
│   ├── i18n.py             dua bahasa: fungsi _() dan tombol ID/EN
│   ├── translations_en.py  kamus terjemahan Inggris
│   ├── cli.py              perintah create-admin, seed-demo, dan test-email
│   ├── cv.py               menyusun CV PDF
│   ├── mailer.py           mengirim email lewat SMTP (Gmail)
│   ├── fonts/              font DejaVu Sans untuk CV PDF (beserta lisensinya)
│   ├── blueprints/         satu file per fitur
│   │   ├── main.py         beranda, penyajian file unggahan
│   │   ├── auth.py         daftar, verifikasi, masuk, keluar
│   │   ├── profiles.py     profil dan direktori orang
│   │   ├── experiences.py  riwayat pengalaman
│   │   ├── companies.py    direktori perusahaan
│   │   ├── forum.py        forum
│   │   ├── messages.py     chat pribadi (/pesan)
│   │   ├── cv.py           buat CV (/akun/cv), unduh PDF-nya, dan isian tambahan CV
│   │   ├── stats.py        statistik
│   │   └── admin.py        panel admin
│   ├── templates/          HTML (Jinja2), satu folder per fitur
│   │   ├── home.html          beranda sebelum masuk
│   │   ├── home_member.html   beranda setelah masuk
│   │   ├── _macros.html       potongan tampilan yang dipakai ulang (kartu, ikon, chip)
│   │   └── _jelajahi_head.html  judul dan tab halaman Jelajahi
│   └── static/
│       ├── css/            12 file CSS, dimuat berurutan (01-dasar.css ... 12-cerita-seleksi.css)
│       └── js/             satu file per fitur: form, navigasi, filter, lampiran, chat, kata sandi, notifikasi
├── .github/workflows/tes.yml  tes otomatis di GitHub setiap push
├── tests/test_app.py       tes otomatis
└── instance/               database, unggahan, kunci rahasia (tidak masuk Git)
```

## Cara kerja singkat

1. Browser meminta sebuah alamat, misalnya `/perusahaan/tokopedia`.
2. Sebelum masuk ke fungsi halaman, Flask menjalankan dua pemeriksaan di `security.py`:
   memuat pengguna dari sesi (`g.user`) dan mencocokkan token CSRF untuk setiap POST.
3. Flask mencocokkan alamat dengan fungsi di salah satu blueprint, di sini `companies.detail`.
4. Fungsi itu mengambil data lewat `query()` dengan SQL berparameter (`?`).
5. Hasilnya dikirim ke template di `templates/companies/detail.html`, yang menghasilkan HTML.

Aturan privasi pengalaman ada di satu tempat, `visibility_sql()` di `queries.py`, dan dipakai oleh
semua halaman yang menampilkan pengalaman.

### CSS dan JavaScript

Daftar file ada di `CSS_FILES` dan `JS_FILES` di `app/__init__.py`, dan `base.html` memuatnya sesuai
urutan itu. Urutan CSS penting karena aturan di file belakang menimpa file depan, jadi file baru
ditambahkan di akhir daftar. Setiap alamat file diberi `?v=<waktu ubah>`, sehingga browser langsung
memakai versi terbaru setelah file diubah tanpa perlu Cmd+Shift+R. Tes `StaticFilesTest` memastikan
tidak ada file yang lupa didaftarkan dan tidak ada komentar atau kurung kurawal yang tidak ditutup.

### CV PDF (`cv.py`)

`/akun/cv` menampilkan pilihan isi CV dan pratinjaunya. Setiap pilihan berubah, `cv.js` meminta
`/akun/cv.pdf?pratinjau=1&...` dan menampilkannya di `<iframe>`. PDF disusun dengan ReportLab dari
potongan-potongan (`Paragraph`, `Table`, `Spacer`, `Image`), dan ReportLab yang membaginya ke beberapa
halaman. Foto profil dipotong bulat dengan Pillow sebelum dimasukkan. CV hanya bisa memuat
pengalaman dan isian milik sendiri; id milik orang lain di alamat diabaikan.

Proyek, organisasi, prestasi, dan sertifikasi disimpan di tabel `cv_items` dengan kolom `section`.
Daftar bagian beserta label dan isiannya ada di `CV_SECTIONS` (`constants.py`), jadi menambah bagian
baru cukup dengan menambah satu entri di sana.

### Dua bahasa (`i18n.py`)

Semua teks ditulis dalam bahasa Indonesia dan dibungkus `_()`, misalnya `{{ _('Perusahaan') }}`
di template atau `_("Profil disimpan.")` di Python. Kalau pengguna memilih EN, `_()` mencari
terjemahannya di kamus `translations_en.py`. Bagian yang berubah ditulis `{nama}`, misalnya
`_("{n} perusahaan", n=12)`. Pilihan bahasa disimpan di sesi dan tetap dipakai setelah masuk.
Saat menambah teks baru, bungkus dengan `_()` lalu tambahkan terjemahannya di `translations_en.py`.
Tes `LanguageTest` gagal kalau ada teks di halaman utama yang belum punya terjemahan.

### Chat pribadi (`blueprints/messages.py`)

Setiap pasangan pengguna punya satu percakapan (tabel `conversations`). Pesan baru muncul tanpa
memuat ulang halaman: `chat.js` menanyakan ke `/pesan/<id>/baru?setelah=<id pesan terakhir>` setiap
4 detik (polling) dan menempelkan HTML pesan yang dikirim server. Cara ini sengaja dipilih supaya
tetap sederhana dan sepenuhnya Python, tanpa server WebSocket terpisah.

## Keamanan dan privasi

- Kata sandi disimpan sebagai hash (`werkzeug.security`), tidak pernah apa adanya.
- Semua query memakai parameter `?`, jadi masukan pengguna tidak bisa mengubah SQL.
- Jinja2 meng-escape semua teks dari pengguna, jadi HTML atau skrip sisipan tampil sebagai teks.
- Setiap form POST membawa token CSRF.
- Gambar unggahan dibuka dan ditulis ulang dengan Pillow; PDF diperiksa tanda awalnya; nama file
  diganti dengan nama acak.
- Lupa kata sandi: tautan atur ulang berlaku 1 jam dan hanya bisa dipakai sekali (token berisi
  sidik kata sandi lama, jadi otomatis tidak berlaku setelah kata sandi diganti). Pesan yang
  ditampilkan sama untuk email terdaftar maupun tidak, supaya daftar pengguna tidak bisa ditebak.
- Ganti kata sandi mengeluarkan semua perangkat lain secara otomatis.
- Percobaan masuk dibatasi: 5 kali gagal per email atau 20 kali per alamat IP dalam 15 menit.
  Permintaan tautan lupa sandi dibatasi 5 kali per IP dalam 15 menit.
- Kata sandi minimal 8 karakter dan tidak boleh mudah ditebak (angka berurutan, nama email).
- File bukti hanya bisa dibuka pemiliknya dan admin. CV hanya untuk pengguna yang masuk.
- Pesan pribadi dan lampirannya hanya bisa dibuka dua orang di percakapan itu. Admin hanya melihat
  pesan yang dilaporkan, bukan seluruh percakapan. Pengguna bisa memblokir lawan bicara.
- Lampiran forum dan chat dibatasi 4 file, 5 MB per file; foto ditulis ulang sebagai JPEG.
- Gaji sengaja tidak dikumpulkan.
- Statistik hanya menampilkan angka gabungan dan tidak menghitung pengalaman privat.

## Batasan saat ini

- Email baru terkirim kalau `MAIL_*` diisi di `instance/config.py`. Tanpa itu, tautan verifikasi
  hanya tampil di layar (mode pengembangan), dan di website online akun baru belum bisa diverifikasi.
- Belum ada fitur hapus akun.
- Di website online, `SHOW_DEV_LINKS` wajib `False` dan aplikasi dijalankan lewat server WSGI
  (lihat [DEPLOY.md](DEPLOY.md)), bukan `python run.py`.
- Logo adalah merek dagang pemiliknya. Di sini logo dipakai hanya sebagai penanda perusahaan.

## Ide pengembangan

- Isi profil otomatis dari CV dengan membaca PDF
- Rekomendasi perusahaan berdasarkan kemiripan skill

## Saran pembagian kerja

| Anggota | Bagian | File utama |
| --- | --- | --- |
| 1 | Akun, keamanan, profil | `auth.py`, `security.py`, `profiles.py` |
| 2 | Pengalaman dan perusahaan, logo | `experiences.py`, `companies.py`, `logos.py`, `queries.py` |
| 3 | Forum | `forum.py`, `templates/forum/` |
| 4 | Statistik, panel admin, tes | `stats.py`, `admin.py`, `tests/` |

## Penggunaan AI

Kerangka awal kode proyek ini dibuat dengan bantuan AI (Claude), sesuai aturan proyek yang
mengizinkannya. (Lengkapi bagian ini: bagian mana yang kalian ubah atau tulis sendiri, dan bagaimana
tiap anggota mempelajari kode yang dipegangnya.)
