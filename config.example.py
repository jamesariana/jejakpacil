# Contoh pengaturan untuk website yang online (misalnya di PythonAnywhere).
#
# Salin file ini ke instance/config.py lalu isi. instance/ tidak masuk Git, jadi
# kata sandi di sini tidak ikut ter-upload ke GitHub.

# Wajib di website online: tautan verifikasi dan atur ulang kata sandi TIDAK boleh tampil di layar.
SHOW_DEV_LINKS = False

# PythonAnywhere meneruskan pengunjung lewat proxy dan memakai https.
BEHIND_PROXY = True
SESSION_COOKIE_SECURE = True

# Akun Gmail khusus untuk mengirim email JejakPacil.
# MAIL_PASSWORD adalah "sandi aplikasi" 16 huruf dari myaccount.google.com/apppasswords
# (perlu verifikasi 2 langkah aktif), bukan kata sandi Gmail biasa.
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USERNAME = "jejakpacil.kelompok@gmail.com"
MAIL_PASSWORD = "isi sandi aplikasi di sini"
MAIL_SENDER = "JejakPacil <jejakpacil.kelompok@gmail.com>"

# Akun gratis PythonAnywhere hanya boleh mengakses situs tertentu, jadi pengambilan logo
# perusahaan otomatis kemungkinan gagal. Matikan supaya halaman tidak menunggu.
LOGO_FETCH_ENABLED = False
