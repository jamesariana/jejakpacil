# Menaruh JejakPacil online di PythonAnywhere

Panduan ini memakai akun **gratis** PythonAnywhere (Beginner). Hasilnya website di
`https://USERNAME.pythonanywhere.com` yang bisa dibuka siapa saja, termasuk dosen dan asisten.
Cukup satu orang di kelompok yang mengerjakan ini. Waktu yang dibutuhkan sekitar 20 menit.

Di bawah ini, ganti `USERNAME` dengan username PythonAnywhere kalian dan `jamesariana/jejakpacil`
dengan alamat repo GitHub kalian.

## 1. Buat akun dan ambil kode

1. Daftar di pythonanywhere.com dan pilih paket **Beginner** (gratis).
2. Di Dashboard, buka **Consoles → Bash**, lalu jalankan:

```bash
git clone https://github.com/jamesariana/jejakpacil.git
cd jejakpacil
mkvirtualenv --python=/usr/bin/python3.13 jejakpacil
pip install -r requirements.txt
```

Setelah `mkvirtualenv`, awal baris terminal berubah menjadi `(jejakpacil)`. Itu tanda virtualenv aktif.

## 2. Isi pengaturan server

```bash
mkdir -p instance
cp config.example.py instance/config.py
nano instance/config.py
```

Di `nano`, cek isinya:

- `SHOW_DEV_LINKS = False` **harus** tetap False. Kalau True, tautan atur ulang kata sandi muncul
  di layar dan siapa pun bisa mengambil alih akun orang lain.
- Bagian `MAIL_*` untuk mengirim email verifikasi dan lupa kata sandi. PythonAnywhere gratis
  hanya mengizinkan Gmail. Caranya:
  1. Buat akun Gmail khusus kelompok, misalnya `jejakpacil.kelompok@gmail.com`.
  2. Aktifkan **Verifikasi 2 Langkah** di akun Google itu.
  3. Buka myaccount.google.com/apppasswords, buat sandi aplikasi bernama "JejakPacil", lalu salin
     16 hurufnya ke `MAIL_PASSWORD`.
  4. Isi `MAIL_USERNAME` dan `MAIL_SENDER` dengan alamat Gmail itu.

  Kalau belum sempat, biarkan dulu. Website tetap jalan dan akun demo tetap bisa dipakai. Akun
  baru bisa diverifikasi manual oleh admin lewat panel admin.

Simpan dengan **Ctrl+O**, Enter, lalu keluar dengan **Ctrl+X**.

Kalau email sudah diisi, coba kirim email percobaan ke dirimu sendiri:

```bash
flask --app run.py test-email emailmu@gmail.com
```

## 3. Isi data demo

```bash
flask --app run.py seed-demo
```

Perintah ini membuat database di `instance/` beserta akun demo (lihat README). Ganti kata sandi
admin setelah online lewat menu akun → **Ganti kata sandi**, karena `admin12345` tertulis di README
yang publik.

## 4. Buat web app

1. Buka tab **Web → Add a new web app → Next**.
2. Pilih **Manual configuration** (bukan "Flask"), lalu **Python 3.13**.
3. Di halaman web app, bagian **Virtualenv**, isi `/home/USERNAME/.virtualenvs/jejakpacil`.
4. Bagian **Code**: isi *Source code* dan *Working directory* dengan `/home/USERNAME/jejakpacil`.
5. Klik tautan **WSGI configuration file** (`/var/www/USERNAME_pythonanywhere_com_wsgi.py`),
   hapus **semua** isinya, lalu ganti dengan:

```python
import sys

path = "/home/USERNAME/jejakpacil"
if path not in sys.path:
    sys.path.insert(0, path)

from run import app as application  # noqa: E402
```

   Klik **Save**.
6. (Opsional, membuat halaman lebih cepat) Bagian **Static files**: URL `/static/`,
   Directory `/home/USERNAME/jejakpacil/app/static`.
7. Bagian **Security**: nyalakan **Force HTTPS**.
8. Klik tombol hijau **Reload USERNAME.pythonanywhere.com** di atas, lalu buka alamatnya.

## Memperbarui website setelah ada commit baru

Setiap kali ada perubahan yang sudah di-push ke GitHub:

```bash
cd ~/jejakpacil
git pull
workon jejakpacil
pip install -r requirements.txt   # hanya perlu kalau requirements.txt berubah
```

Lalu klik **Reload** di tab Web. Kolom database baru ditambahkan otomatis, jadi data yang sudah ada
tidak hilang.

## Kalau ada masalah

- **"Something went wrong" atau halaman error.** Buka tab Web, klik **Error log**, dan baca baris
  paling bawah. Biasanya penyebabnya salah path di WSGI atau virtualenv.
- **Tampilan tanpa warna.** Periksa isian **Static files** (langkah 4.6), atau hapus saja isian itu.
- **Email tidak sampai.** Jalankan `flask --app run.py test-email ...` dan baca pesannya.
  Penyebab paling umum: `MAIL_PASSWORD` diisi kata sandi Gmail biasa, bukan sandi aplikasi.
- **Website mati setelah beberapa minggu.** Web app gratis harus diperpanjang. Masuk ke tab Web dan
  klik **Run until 3 months from today** sebelum tanggal yang tertera, apalagi menjelang penilaian.
