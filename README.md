# JejakPacil

Website untuk mencatat dan menelusuri riwayat magang dan kerja mahasiswa serta alumni Fasilkom UI.
Proyek kelompok Dasar-Dasar Pemrograman 1, Semester Gasal 2026/2027.

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
| Forum | Kategori, thread, balasan dua tingkat, suara, posting anonim, tag perusahaan, laporan |
| Statistik | Perusahaan terbanyak, jenis pengalaman, jalur mendapatkan, skill, per angkatan |
| Panel admin | Verifikasi, setujui dan gabungkan perusahaan, moderasi forum, kelola pengguna, ekspor CSV |

## Teknologi

- **Python 3.10+** dengan **Flask** sebagai kerangka web
- **SQLite** (modul bawaan `sqlite3`) sebagai database, dengan SQL yang ditulis sendiri
- **Jinja2** untuk template HTML, CSS dan sedikit JavaScript tanpa framework
- **Pillow** untuk memeriksa dan mengecilkan gambar unggahan
- **requests** untuk memanggil layanan logo
- **unittest** untuk tes otomatis

Hal yang tidak diajarkan di kelas DDP1 dan dipakai di sini: aplikasi web dengan routing dan blueprint,
database relasional dan SQL (JOIN, GROUP BY, subquery), template HTML, sesi login dan hashing kata
sandi, token bertanda tangan, perlindungan CSRF, unggah file, memanggil API luar, decorator, dan tes
otomatis dengan objek tiruan (mock).

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

Belum ada pengiriman email sungguhan. Tautan verifikasi ditampilkan di halaman setelah mendaftar dan
dicetak di terminal. Admin juga bisa memverifikasi email pengguna secara manual di panel admin.

## Tes

```bash
python -m unittest -v
```

Ada 45 tes yang mencakup pendaftaran, login, CSRF, pengalaman dan aturan privasinya, unggahan,
perusahaan dan panel admin, pengambilan logo (dengan balasan tiruan), serta forum.

## Ide pengembangan

- Cerita proses seleksi per perusahaan dengan format terstruktur
- Notifikasi saat thread dibalas atau pengalaman diverifikasi
- Isi profil otomatis dari CV dengan membaca PDF
- Rekomendasi perusahaan berdasarkan kemiripan skill

