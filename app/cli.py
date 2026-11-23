"""Perintah terminal: membuat admin dan mengisi data demo.

Contoh pemakaian (dari folder proyek):
    flask --app app create-admin
    flask --app app seed-demo --with-logos
"""

import io

import click
from werkzeug.security import generate_password_hash

from .db import get_db, query
from .forms import is_allowed_email
from .logos import fetch_logo
from .utils import save_image_bytes, slugify

DEMO_PASSWORD = "pacil12345"

# (nama, domain, industri, deskripsi singkat)
DEMO_COMPANIES = [
    ("Tokopedia", "tokopedia.com", "E-commerce", "Marketplace dan platform belanja daring asal Indonesia."),
    ("Gojek", "gojek.com", "Teknologi", "Aplikasi transportasi, pesan-antar makanan, dan pembayaran."),
    ("Traveloka", "traveloka.com", "Teknologi", "Platform pemesanan tiket perjalanan dan penginapan."),
    ("Shopee", "shopee.co.id", "E-commerce", "Marketplace belanja daring."),
    ("Bank Central Asia", "bca.co.id", "Perbankan & Keuangan", "Bank swasta nasional."),
    ("Bank Mandiri", "bankmandiri.co.id", "Perbankan & Keuangan", "Bank milik negara."),
    ("Telkom Indonesia", "telkom.co.id", "Telekomunikasi", "Perusahaan telekomunikasi milik negara."),
    ("Bukalapak", "bukalapak.com", "E-commerce", "Marketplace dan layanan untuk warung."),
    ("Blibli", "blibli.com", "E-commerce", "Platform belanja daring."),
    ("DANA", "dana.id", "Fintech", "Dompet digital untuk pembayaran dan transfer."),
    ("Ruangguru", "ruangguru.com", "Pendidikan", "Platform belajar daring untuk pelajar."),
    ("Grab", "grab.com", "Teknologi", "Aplikasi transportasi dan pesan-antar di Asia Tenggara."),
    ("Fasilkom UI", "cs.ui.ac.id", "Pendidikan", "Fakultas Ilmu Komputer Universitas Indonesia."),
]

# (kunci, nama, prodi, angkatan, status, tahun lulus, skill)
DEMO_USERS = [
    ("raka", "Raka Pradipta", "Ilmu Komputer", 2019, "alumni", 2023, "Go, Kubernetes, PostgreSQL"),
    ("nadia", "Nadia Wardani", "Sistem Informasi", 2020, "alumni", 2024, "SQL, Figma, Product Management"),
    ("bagas", "Bagas Wicaksono", "Ilmu Komputer", 2021, "alumni", 2025, "Java, Spring Boot, MySQL"),
    ("salsa", "Salsa Hartono", "Sistem Informasi", 2022, "aktif", None, "Python, SQL, Tableau"),
    ("farhan", "Farhan Maulana", "Ilmu Komputer", 2022, "aktif", None, "Kotlin, Android"),
    ("putri", "Putri Anindya", "Ilmu Komputer KKI", 2021, "alumni", 2025, "Python, scikit-learn, SQL"),
    ("yoga", "Yoga Saputra", "Sistem Informasi", 2023, "aktif", None, "Figma, UX Research"),
    ("citra", "Citra Maharani", "Ilmu Komputer", 2023, "aktif", None, "React, TypeScript"),
    ("rizky", "Rizky Firmansyah", "Ilmu Komputer", 2020, "alumni", 2024, "Go, React"),
    ("tiara", "Tiara Nugraha", "Sistem Informasi", 2021, "alumni", 2025, "SQL, Python"),
    ("fikri", "Fikri Ramadhan", "Ilmu Komputer", 2024, "aktif", None, "Python, PyTorch"),
    ("anisa", "Anisa Rahmawati", "Sistem Informasi", 2019, "alumni", 2023, "SQL, Product Management"),
]

# (pemilik, perusahaan, posisi, jenis, mulai, selesai, lokasi, cara kerja, cara dapat, skill, verifikasi, visibilitas)
DEMO_EXPERIENCES = [
    ("raka", "Tokopedia", "Software Engineer Intern", "magang", "2022-06", "2022-08", "Jakarta", "hybrid", "portal", "Go, PostgreSQL", "terverifikasi", "publik"),
    ("raka", "Gojek", "Software Engineer", "fulltime", "2023-09", None, "Jakarta", "hybrid", "referral", "Go, Kubernetes, gRPC", "terverifikasi", "publik"),
    ("nadia", "Bank Central Asia", "IT Business Analyst Intern", "magang", "2023-01", "2023-06", "Jakarta", "onsite", "kampus", "SQL, Excel", "belum", "sivitas"),
    ("nadia", "Traveloka", "Associate Product Manager", "fulltime", "2024-10", None, "Jakarta", "hybrid", "portal", "SQL, Figma", "terverifikasi", "publik"),
    ("bagas", "Shopee", "Backend Engineer Intern", "magang", "2024-02", "2024-07", "Jakarta", "onsite", "portal", "Java, Spring Boot, MySQL", "terverifikasi", "publik"),
    ("bagas", "Shopee", "Backend Engineer", "fulltime", "2025-09", None, "Jakarta", "onsite", "referral", "Java, Spring Boot, Kafka", "belum", "publik"),
    ("salsa", "DANA", "Data Analyst Intern", "magang", "2025-06", "2025-08", "Jakarta", "hybrid", "acara", "Python, SQL, Tableau", "terverifikasi", "publik"),
    ("salsa", "Fasilkom UI", "Asisten Dosen DDP1", "asdos", "2025-08", "2025-12", "Depok", "onsite", "kampus", "Python", "belum", "sivitas"),
    ("farhan", "Tokopedia", "Android Engineer Intern", "magang", "2025-06", "2025-09", "Jakarta", "remote", "portal", "Kotlin, Android", "belum", "publik"),
    ("farhan", "Ruangguru", "Content Reviewer", "parttime", "2024-03", "2024-08", "Jakarta", "remote", "web", "", "belum", "privat"),
    ("putri", "Grab", "Data Science Intern", "magang", "2024-06", "2024-08", "Jakarta", "hybrid", "web", "Python, scikit-learn", "terverifikasi", "publik"),
    ("putri", "Traveloka", "Data Scientist", "fulltime", "2025-10", None, "Jakarta", "hybrid", "portal", "Python, SQL, scikit-learn", "belum", "sivitas"),
    ("yoga", "Ruangguru", "UI/UX Design Intern", "magang", "2026-07", "2026-09", "Jakarta", "remote", "portal", "Figma, UX Research", "belum", "sivitas"),
    ("citra", "Telkom Indonesia", "Frontend Engineer Intern", "magang", "2026-06", "2026-08", "Bandung", "onsite", "jobfair", "React, TypeScript", "terverifikasi", "publik"),
    ("citra", "Fasilkom UI", "Asisten Dosen DDP1", "asdos", "2026-08", None, "Depok", "onsite", "kampus", "Python", "belum", "sivitas"),
    ("rizky", "Bukalapak", "Software Engineer Intern", "magang", "2022-07", "2022-12", "Jakarta", "hybrid", "acara", "Go, React", "belum", "publik"),
    ("rizky", "Tokopedia", "Software Engineer", "fulltime", "2024-08", None, "Jakarta", "hybrid", "referral", "Go, React, PostgreSQL", "terverifikasi", "publik"),
    ("tiara", "Bank Mandiri", "IT Intern", "magang", "2024-01", "2024-04", "Jakarta", "onsite", "kampus", "SQL", "belum", "sivitas"),
    ("tiara", "Blibli", "Product Analyst", "fulltime", "2025-08", None, "Jakarta", "hybrid", "portal", "SQL, Python", "belum", "publik"),
    ("fikri", "Fasilkom UI", "Asisten Riset", "riset", "2026-02", None, "Depok", "onsite", "kampus", "Python, PyTorch", "belum", "sivitas"),
    ("anisa", "Gojek", "Business Analyst Intern", "magang", "2022-02", "2022-06", "Jakarta", "hybrid", "jobfair", "SQL, Excel", "terverifikasi", "publik"),
    ("anisa", "Telkom Indonesia", "System Analyst", "fulltime", "2023-10", "2025-03", "Jakarta", "onsite", "portal", "SQL", "belum", "publik"),
    ("anisa", "DANA", "Product Manager", "fulltime", "2025-04", None, "Jakarta", "hybrid", "referral", "SQL, Product Management", "belum", "publik"),
]

# Bidang pekerjaan tiap posisi demo (lihat ROLE_CATEGORIES di constants.py).
DEMO_ROLES = {
    "Software Engineer Intern": "swe_backend", "Software Engineer": "swe_backend",
    "IT Business Analyst Intern": "business_analyst", "Associate Product Manager": "product_manager",
    "Backend Engineer Intern": "swe_backend", "Backend Engineer": "swe_backend",
    "Data Analyst Intern": "data_analyst", "Asisten Dosen DDP1": "researcher",
    "Android Engineer Intern": "mobile", "Content Reviewer": "lainnya",
    "Data Science Intern": "data_scientist", "Data Scientist": "data_scientist",
    "UI/UX Design Intern": "ui_ux", "Frontend Engineer Intern": "swe_frontend",
    "IT Intern": "lainnya", "Product Analyst": "data_analyst", "Asisten Riset": "researcher",
    "Business Analyst Intern": "business_analyst", "System Analyst": "business_analyst",
    "Product Manager": "product_manager", "Data Engineer Intern": "data_engineer",
}

# Cerita seleksi demo: (pemilik, perusahaan, posisi) -> (tahapan, minggu, kesulitan, pertanyaan, tips)
DEMO_STORIES = {
    ("raka", "Tokopedia", "Software Engineer Intern"): (
        "berkas,tes_online,wawancara_teknis,wawancara_hr", 5, 4,
        "Tes online 2 soal algoritma (graf dan dynamic programming) dalam 90 menit. "
        "Wawancara teknis: rancang sistem pemendek URL dan jelaskan proyek terbesarmu.",
        "Latihan soal medium di LeetCode minimal sebulan sebelumnya. Saat wawancara, pikirkan dengan suara keras.",
    ),
    ("farhan", "Tokopedia", "Android Engineer Intern"): (
        "berkas,tes_online,tes_teknis,wawancara_hr", 6, 4,
        "Take-home membuat aplikasi daftar produk dengan Kotlin dan MVVM, lalu dibahas saat live coding.",
        "Punya satu aplikasi yang benar-benar rilis di Play Store sangat membantu. Rapikan arsitektur kodenya.",
    ),
    ("rizky", "Tokopedia", "Software Engineer"): (
        "berkas,tes_online,wawancara_teknis,wawancara_teknis,wawancara_hr", 4, 3,
        "System design: layanan keranjang belanja yang tahan lonjakan saat promo.",
        "Pengalaman magang sebelumnya paling banyak ditanyakan. Siapkan angka dampak dari proyekmu.",
    ),
    ("salsa", "DANA", "Data Analyst Intern"): (
        "berkas,tes_online,studi_kasus,wawancara_hr", 3, 3,
        "Studi kasus: kenapa jumlah transaksi turun 15% minggu ini? Tes SQL berisi JOIN dan window function.",
        "Latihan SQL di HackerRank, lalu siapkan cerita proyek dengan format STAR. Ikut sesi DANA di COMPFEST.",
    ),
    ("bagas", "Shopee", "Backend Engineer Intern"): (
        "berkas,tes_online,wawancara_teknis,wawancara_teknis", 7, 5,
        "Dua wawancara teknis: struktur data (heap, trie) dan desain basis data untuk sistem voucher.",
        "Prosesnya panjang, jangan menunggu satu perusahaan saja. Pelajari dasar concurrency di Java.",
    ),
    ("putri", "Grab", "Data Science Intern"): (
        "berkas,tes_online,studi_kasus,wawancara_teknis,wawancara_hr", 6, 4,
        "Take-home membuat model prediksi waktu tiba dari data perjalanan, lalu dipresentasikan.",
        "Jelaskan alasan memilih fitur dan metrik evaluasi, bukan hanya angka akurasinya.",
    ),
    ("anisa", "Gojek", "Business Analyst Intern"): (
        "berkas,psikotes,studi_kasus,wawancara_hr", 4, 3,
        "Studi kasus menentukan kota berikutnya untuk layanan GoFood, lengkap dengan perhitungan kasar.",
        "Biasakan menyusun jawaban dengan kerangka. Datang ke job fair untuk kenalan dengan perekrutnya.",
    ),
    ("citra", "Telkom Indonesia", "Frontend Engineer Intern"): (
        "berkas,psikotes,tes_teknis,wawancara_hr", 3, 2,
        "Membuat halaman dari desain Figma dengan React dalam 2 jam.",
        "Psikotesnya cukup panjang, istirahat yang cukup sehari sebelumnya.",
    ),
}

# (penulis, kategori, perusahaan atau None, judul, isi, anonim, disematkan, [balasan], [pemberi suara])
# balasan: (penulis, isi, anonim, [balasan anak: (penulis, isi)])
DEMO_THREADS = [
    (
        "admin", "umum", None, "Aturan main forum JejakPacil",
        "Forum ini untuk saling bantu soal magang dan karier.\n\n"
        "1. Ceritakan pengalaman sendiri, bukan kabar dari orang ketiga.\n"
        "2. Jangan bagikan soal tes yang masih dipakai perusahaan atau dokumen rahasia.\n"
        "3. Mau cerita hal sensitif? Centang opsi anonim.\n"
        "4. Lihat konten yang melanggar? Pakai tombol Laporkan.",
        0, 1, [], ["raka", "nadia", "salsa", "yoga"],
    ),
    (
        "yoga", "tanya-alumni", None, "Magang pertama: lebih baik di startup atau korporat?",
        "Aku angkatan 2023 dan lagi cari magang pertama. Ada yang bilang startup lebih banyak "
        "belajar karena langsung pegang fitur, ada juga yang bilang korporat lebih rapi "
        "bimbingannya. Menurut kakak-kakak yang sudah pernah, mana yang lebih cocok untuk pemula?",
        0, 0,
        [
            ("raka", "Menurutku yang paling menentukan itu mentornya, bukan jenis perusahaannya. "
                     "Waktu wawancara, tanya langsung siapa yang akan membimbing dan seberapa sering review-nya.", 0,
             [("yoga", "Oh iya, belum kepikiran buat tanya itu. Makasih, Kak!")]),
            ("anisa", "Aku mulai di korporat. Prosesnya lebih lambat, tapi aku jadi paham cara kerja "
                      "tim besar dan dokumentasi. Dua-duanya bagus asal kamu aktif bertanya.", 0, []),
        ],
        ["salsa", "citra", "fikri", "farhan"],
    ),
    (
        "farhan", "magang", "Tokopedia", "Cerita persiapan magang Android",
        "Banyak yang tanya cara aku siap-siap, jadi kutulis di sini. Dua bulan sebelum daftar aku "
        "bikin satu aplikasi kecil sampai rilis, lalu latihan soal struktur data tiap malam. "
        "Yang paling membantu ternyata proyek pribadi, karena hampir semua pertanyaan wawancara "
        "berangkat dari situ.",
        0, 0,
        [("citra", "Aplikasinya tentang apa, Kak? Aku lagi bingung pilih topik proyek pribadi.", 0,
          [("farhan", "Pencatat jadwal kuliah sederhana. Pilih masalah yang kamu sendiri alami, biar semangat nyelesainnya.")])],
        ["yoga", "citra", "fikri"],
    ),
    (
        "tiara", "karier", None, "Gagal di tahap akhir tiga kali, gimana cara bangkit?",
        "Tiga lamaran terakhirku semuanya berhenti di wawancara akhir. Rasanya capek dan mulai "
        "ragu sama kemampuan sendiri. Ada yang pernah di posisi ini? Apa yang kalian ubah?",
        1, 0,
        [
            ("rizky", "Pernah. Yang kuubah: selesai wawancara aku langsung catat pertanyaan yang "
                      "jawabanku lemah, lalu latihan ulang bareng teman. Lolos tahap akhir itu sudah "
                      "bukti kemampuanmu cukup.", 0, []),
            ("putri", "Coba minta umpan balik ke rekruternya. Tidak semua membalas, tapi sekali dibalas "
                      "isinya sangat membantu.", 0, []),
        ],
        ["nadia", "anisa", "bagas", "salsa", "raka"],
    ),
    (
        "salsa", "magang", "DANA", "Tips latihan SQL untuk posisi data analyst intern",
        "Yang kupakai latihan: JOIN beberapa tabel, GROUP BY dengan HAVING, dan window function "
        "seperti ROW_NUMBER. Biasakan juga menjelaskan alur berpikir sambil menulis query, "
        "karena itu yang dinilai.",
        0, 0, [("tiara", "Setuju. Window function sering banget keluar.", 0, [])], ["yoga", "tiara"],
    ),
    (
        "raka", "lowongan", "Gojek", "Mau direferensikan? Kirim CV lewat thread ini",
        "Kalau ada yang tertarik melamar magang backend, balas thread ini dan pastikan CV di "
        "profil JejakPacil-mu sudah yang terbaru. Aku bantu teruskan kalau profilnya cocok.",
        0, 0, [("fikri", "Tertarik, Kak. CV sudah kuperbarui di profil.", 0, [])], ["fikri", "farhan", "citra"],
    ),
]


# ---------- Data demo tambahan: supaya statistik, direktori, dan ringkasan seleksi lebih terisi ----------
# Semua orang di bawah fiktif. Formatnya sama dengan daftar di atas.

DEMO_COMPANIES += [
    ("Xendit", "xendit.co", "Fintech", "Infrastruktur pembayaran untuk bisnis di Asia Tenggara."),
    ("Accenture", "accenture.com", "Konsultan", "Perusahaan konsultan teknologi dan bisnis."),
    ("Halodoc", "halodoc.com", "Kesehatan", "Aplikasi konsultasi dokter, apotek, dan janji temu rumah sakit."),
    ("Vidio", "vidio.com", "Media & Hiburan", "Platform streaming video dan siaran olahraga."),
    ("Pertamina", "pertamina.com", "Pemerintahan & BUMN", "BUMN energi."),
]

DEMO_USERS += [
    ("dimas", "Dimas Aryaguna", "Ilmu Komputer", 2018, "alumni", 2022, "Go, AWS, Terraform"),
    ("intan", "Intan Permatasari", "Sistem Informasi", 2018, "alumni", 2022, "SQL, Power BI, Excel"),
    ("kevin", "Kevin Hartanto", "Ilmu Komputer", 2019, "alumni", 2023, "Python, PyTorch, MLOps"),
    ("laras", "Laras Kusumawardhani", "Sistem Informasi", 2020, "alumni", 2024, "Figma, UX Research, HTML"),
    ("hendra", "Hendra Gunawan", "Ilmu Komputer", 2020, "alumni", 2024, "Linux, Python, Penetration Testing"),
    ("maya", "Maya Puspitasari", "Ilmu Komputer KKI", 2021, "alumni", 2025, "TypeScript, Node.js, React"),
    ("arief", "Arief Nugroho", "Sistem Informasi", 2021, "alumni", 2025, "SAP, SQL, Business Process"),
    ("gita", "Gita Lestari", "Kecerdasan Artifisial", 2023, "aktif", None, "Python, PyTorch, NLP"),
    ("bima", "Bima Prakoso", "Ilmu Komputer", 2022, "aktif", None, "Flutter, Dart, Firebase"),
    ("sekar", "Sekar Ayuningtyas", "Sistem Informasi", 2022, "aktif", None, "SQL, Python, Looker"),
    ("reza", "Reza Mahendra", "Ilmu Komputer", 2023, "aktif", None, "Java, Selenium, Postman"),
    ("wulan", "Wulan Safitri", "Sistem Informasi", 2024, "aktif", None, "Figma, Notion"),
    ("daffa", "Daffa Alghifari", "Ilmu Komputer", 2024, "aktif", None, "Python, C++"),
    ("nabila", "Nabila Zahra", "Kecerdasan Artifisial", 2024, "aktif", None, "Python, scikit-learn"),
]

DEMO_EXPERIENCES += [
    ("dimas", "Traveloka", "Site Reliability Engineer Intern", "magang", "2021-06", "2021-12", "Jakarta", "hybrid", "portal", "Kubernetes, Prometheus", "terverifikasi", "publik"),
    ("dimas", "Xendit", "Site Reliability Engineer", "fulltime", "2022-08", "2024-06", "Jakarta", "remote", "referral", "AWS, Terraform, Go", "terverifikasi", "publik"),
    ("dimas", "Gojek", "Senior Site Reliability Engineer", "fulltime", "2024-07", None, "Jakarta", "hybrid", "referral", "Kubernetes, AWS", "belum", "publik"),
    ("intan", "Bank Central Asia", "IT Business Analyst Intern", "magang", "2021-07", "2021-12", "Jakarta", "onsite", "kampus", "SQL, Excel", "terverifikasi", "publik"),
    ("intan", "Accenture", "Technology Analyst", "fulltime", "2022-09", "2024-08", "Jakarta", "hybrid", "jobfair", "SQL, SAP", "terverifikasi", "publik"),
    ("intan", "Bank Mandiri", "Data Analyst", "fulltime", "2024-09", None, "Jakarta", "onsite", "portal", "SQL, Power BI", "belum", "sivitas"),
    ("kevin", "Gojek", "Data Science Intern", "magang", "2022-01", "2022-06", "Jakarta", "hybrid", "acara", "Python, SQL", "terverifikasi", "publik"),
    ("kevin", "Halodoc", "Machine Learning Engineer", "fulltime", "2023-08", None, "Jakarta", "hybrid", "portal", "Python, PyTorch, MLOps", "terverifikasi", "publik"),
    ("laras", "Traveloka", "UI/UX Design Intern", "magang", "2023-02", "2023-07", "Jakarta", "hybrid", "portal", "Figma, UX Research", "terverifikasi", "publik"),
    ("laras", "Ruangguru", "Product Designer", "fulltime", "2024-08", None, "Jakarta", "hybrid", "referral", "Figma, UX Research", "belum", "publik"),
    ("hendra", "Telkom Indonesia", "Cyber Security Intern", "magang", "2023-01", "2023-06", "Bandung", "onsite", "kampus", "Linux, Wireshark", "terverifikasi", "publik"),
    ("hendra", "Bank Central Asia", "Security Engineer", "fulltime", "2024-09", None, "Jakarta", "onsite", "portal", "Penetration Testing, Python", "belum", "sivitas"),
    ("maya", "Vidio", "Fullstack Engineer Intern", "magang", "2024-01", "2024-06", "Jakarta", "hybrid", "portal", "React, Node.js", "terverifikasi", "publik"),
    ("maya", "Xendit", "Software Engineer", "fulltime", "2025-08", None, "Jakarta", "remote", "acara", "TypeScript, Node.js", "belum", "publik"),
    ("arief", "Pertamina", "IT Intern", "magang", "2024-02", "2024-06", "Jakarta", "onsite", "kampus", "SAP, SQL", "belum", "publik"),
    ("arief", "Accenture", "Technology Consultant", "fulltime", "2025-08", None, "Jakarta", "hybrid", "jobfair", "SAP, Business Process", "terverifikasi", "publik"),
    ("gita", "Fasilkom UI", "Asisten Riset", "riset", "2025-09", None, "Depok", "onsite", "kampus", "Python, NLP", "belum", "sivitas"),
    ("gita", "Gojek", "Machine Learning Intern", "magang", "2026-06", "2026-08", "Jakarta", "hybrid", "acara", "Python, PyTorch", "belum", "publik"),
    ("bima", "Bukalapak", "Mobile Engineer Intern", "magang", "2025-06", "2025-08", "Jakarta", "remote", "portal", "Flutter, Dart", "terverifikasi", "publik"),
    ("bima", "Halodoc", "Mobile Engineer Intern", "magang", "2026-06", "2026-09", "Jakarta", "hybrid", "referral", "Flutter, Firebase", "belum", "publik"),
    ("sekar", "Shopee", "Business Intelligence Intern", "magang", "2025-06", "2025-09", "Jakarta", "onsite", "portal", "SQL, Looker", "terverifikasi", "publik"),
    ("sekar", "Blibli", "Data Analyst Intern", "magang", "2026-06", "2026-08", "Jakarta", "hybrid", "jobfair", "SQL, Python", "belum", "publik"),
    ("reza", "Traveloka", "QA Engineer Intern", "magang", "2026-06", "2026-08", "Jakarta", "hybrid", "portal", "Selenium, Postman", "belum", "publik"),
    ("reza", "Fasilkom UI", "Asisten Dosen SDA", "asdos", "2025-08", "2025-12", "Depok", "onsite", "kampus", "Java", "belum", "sivitas"),
    ("wulan", "Fasilkom UI", "Asisten Dosen PSI", "asdos", "2025-08", "2025-12", "Depok", "onsite", "kampus", "Figma", "belum", "sivitas"),
    ("daffa", "Fasilkom UI", "Asisten Dosen DDP1", "asdos", "2025-08", "2025-12", "Depok", "onsite", "kampus", "Python", "belum", "sivitas"),
    ("nabila", "Fasilkom UI", "Asisten Riset", "riset", "2025-10", None, "Depok", "onsite", "kampus", "Python, scikit-learn", "belum", "sivitas"),
    ("salsa", "Xendit", "Data Analyst Intern", "magang", "2026-06", "2026-08", "Jakarta", "hybrid", "referral", "SQL, Python", "belum", "publik"),
    ("farhan", "Gojek", "Android Engineer Intern", "magang", "2026-06", "2026-09", "Jakarta", "hybrid", "acara", "Kotlin, Jetpack Compose", "belum", "publik"),
    ("tiara", "Halodoc", "Data Analyst Intern", "magang", "2024-06", "2024-08", "Jakarta", "hybrid", "web", "SQL, Python", "terverifikasi", "publik"),
    ("citra", "Vidio", "Frontend Engineer Intern", "magang", "2025-06", "2025-08", "Jakarta", "remote", "portal", "React, TypeScript", "belum", "publik"),
]

DEMO_ROLES.update({
    "Site Reliability Engineer Intern": "devops", "Site Reliability Engineer": "devops",
    "Senior Site Reliability Engineer": "devops", "Technology Analyst": "it_consultant",
    "Data Analyst": "data_analyst", "Machine Learning Engineer": "ml_engineer",
    "Product Designer": "ui_ux", "Cyber Security Intern": "security", "Security Engineer": "security",
    "Fullstack Engineer Intern": "swe_fullstack", "Technology Consultant": "it_consultant",
    "Machine Learning Intern": "ml_engineer", "Mobile Engineer Intern": "mobile",
    "Business Intelligence Intern": "data_analyst", "QA Engineer Intern": "qa",
    "Asisten Dosen SDA": "researcher", "Asisten Dosen PSI": "researcher",
})

DEMO_STORIES.update({
    ("dimas", "Xendit", "Site Reliability Engineer"): (
        "berkas,wawancara_hr,tes_teknis,wawancara_teknis", 4, 4,
        "Debugging langsung: server yang lambat karena disk penuh, lalu jelaskan cara memantaunya. "
        "Ditanya juga beda readiness dan liveness probe di Kubernetes.",
        "Biasakan membaca log dan metrik. Satu proyek pribadi yang di-deploy sungguhan lebih meyakinkan "
        "daripada sertifikat.",
    ),
    ("intan", "Accenture", "Technology Analyst"): (
        "berkas,tes_online,psikotes,wawancara_hr,presentasi", 6, 3,
        "Studi kasus kelompok: merancang ulang proses klaim asuransi, dipresentasikan 10 menit.",
        "Latih presentasi dan cara menjawab pertanyaan klien. Tes logikanya mirip TPA, cukup latihan beberapa set.",
    ),
    ("kevin", "Halodoc", "Machine Learning Engineer"): (
        "berkas,studi_kasus,wawancara_teknis,wawancara_hr", 5, 4,
        "Take-home: model rekomendasi dokter dari data riwayat konsultasi, lalu jelaskan metrik evaluasinya.",
        "Tunjukkan cara berpikir soal data yang tidak seimbang dan cara memantau model setelah rilis.",
    ),
    ("laras", "Traveloka", "UI/UX Design Intern"): (
        "berkas,studi_kasus,presentasi,wawancara_hr", 5, 3,
        "Design challenge 3 hari: memperbaiki alur pemesanan hotel untuk pengguna pertama kali.",
        "Portofolio yang menjelaskan proses (riset, iterasi, alasan keputusan) lebih penting dari visual yang cantik.",
    ),
    ("hendra", "Telkom Indonesia", "Cyber Security Intern"): (
        "berkas,tes_teknis,wawancara_teknis", 3, 3,
        "Soal CTF sederhana: SQL injection, cari flag di file pcap, dan decode beberapa encoding.",
        "Ikut CTF (misalnya yang diadakan RISTEK atau COMPFEST) dan tulis write-up-nya. Itu yang ditanyakan.",
    ),
    ("maya", "Vidio", "Fullstack Engineer Intern"): (
        "berkas,tes_online,tes_teknis,wawancara_hr", 4, 3,
        "Live coding membuat halaman daftar video dengan pencarian dan paginasi di React, plus endpoint-nya.",
        "Kuasai dasar HTTP dan state management. Mereka lebih peduli kode rapi daripada fitur banyak.",
    ),
    ("bima", "Bukalapak", "Mobile Engineer Intern"): (
        "berkas,tes_online,wawancara_teknis,wawancara_hr", 4, 3,
        "Pertanyaan tentang siklus hidup widget Flutter dan cara menangani state saat koneksi putus.",
        "Siapkan satu aplikasi yang bisa didemokan langsung dari HP saat wawancara.",
    ),
    ("sekar", "Shopee", "Business Intelligence Intern"): (
        "berkas,tes_online,studi_kasus,wawancara_hr", 3, 4,
        "Tes SQL 60 menit (window function, join bertingkat) lalu studi kasus menurunnya konversi checkout.",
        "Latih window function dan cara menyusun jawaban studi kasus: masalah, hipotesis, data, rekomendasi.",
    ),
    ("arief", "Accenture", "Technology Consultant"): (
        "berkas,tes_online,psikotes,wawancara_hr,wawancara_teknis", 7, 3,
        "Ditanya pengalaman organisasi dan cara menghadapi klien yang mengubah kebutuhan di tengah proyek.",
        "Ceritakan pengalaman kepanitiaan atau organisasi dengan format STAR. Itu porsi besar penilaian.",
    ),
    ("reza", "Traveloka", "QA Engineer Intern"): (
        "berkas,tes_online,tes_teknis,wawancara_hr", 4, 2,
        "Menulis test case untuk form pemesanan tiket, lalu otomatisasi satu skenario dengan Selenium.",
        "Pahami beda unit, integration, dan end-to-end test. Contoh bug yang pernah kamu temukan jadi nilai plus.",
    ),
    ("salsa", "Xendit", "Data Analyst Intern"): (
        "berkas,tes_online,wawancara_teknis", 3, 3,
        "Analisis data transaksi: cari penyebab naiknya pembayaran gagal di satu bank.",
        "Referral dari alumni mempercepat proses. Jawaban yang rapi dan singkat lebih dihargai.",
    ),
})


# Isian tambahan CV: (pemilik, bagian, judul, subjudul, mulai, selesai, tautan, teknologi, deskripsi)
DEMO_CV_ITEMS = [
    ("salsa", "proyek", "Dasbor penjualan UMKM batik", "Proyek mata kuliah Basis Data, tim 3 orang", "2024-09", "2024-12",
     "https://github.com/contoh/dasbor-umkm", "Python, SQL, Tableau",
     "- Merancang skema basis data penjualan dari catatan Excel milik pemilik usaha\n"
     "- Membuat dasbor stok dan omzet mingguan yang dipakai pemilik toko"),
    ("salsa", "proyek", "JejakPacil", "Proyek kelompok DDP1", "2026-10", None, "", "Python, Flask, SQLite",
     "- Membuat fitur statistik dan filter perusahaan"),
    ("salsa", "organisasi", "COMPFEST 16", "Staf divisi Data", "2024-03", "2024-10", "", "",
     "- Mengolah data pendaftar dan peserta untuk laporan panitia inti"),
    ("salsa", "prestasi", "Finalis GEMASTIK XVII, divisi Data Mining", "Pusat Prestasi Nasional", None, "2025-10", "", "", ""),
    ("salsa", "sertifikasi", "Google Data Analytics", "Coursera", None, "2024-06", "https://coursera.org/verify/contoh", "", ""),
    ("farhan", "proyek", "Aplikasi jadwal kuliah", "Proyek pribadi", "2024-01", "2024-04", "", "Kotlin, Android", ""),
    ("bima", "proyek", "Aplikasi donor darah", "Proyek PBP, tim 5 orang", "2024-09", "2024-12", "", "Flutter, Firebase", ""),
]


def _seed_cv_items(db, users):
    for owner, section, title, subtitle, start, end, url, tools, description in DEMO_CV_ITEMS:
        db.execute(
            "INSERT INTO cv_items (user_id, section, title, subtitle, start_date, end_date, url, tools, description)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (users[owner], section, title, subtitle, start, end, url, tools, description),
        )


def register_commands(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt="Email admin (@ui.ac.id)")
    @click.option("--name", prompt="Nama lengkap")
    @click.password_option("--password", prompt="Kata sandi (min. 8 karakter)")
    def create_admin(email, name, password):
        """Buat akun admin, atau jadikan akun yang sudah ada sebagai admin."""
        email = email.strip().lower()
        if not is_allowed_email(email):
            raise click.ClickException("Email harus berakhiran @ui.ac.id.")
        if len(password) < 8:
            raise click.ClickException("Kata sandi minimal 8 karakter.")
        db = get_db()
        if query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
            db.execute("UPDATE users SET role = 'admin', is_verified = 1 WHERE email = ?", (email,))
            click.echo(f"{email} sekarang admin.")
        else:
            db.execute(
                "INSERT INTO users (email, password_hash, full_name, role, is_verified, prodi, angkatan)"
                " VALUES (?, ?, ?, 'admin', 1, 'Ilmu Komputer', 2024)",
                (email, generate_password_hash(password), name.strip()),
            )
            click.echo(f"Admin {email} dibuat. Lengkapi profilnya setelah masuk.")
        db.commit()

    @app.cli.command("test-email")
    @click.argument("to")
    def test_email(to):
        """Kirim email percobaan untuk memeriksa pengaturan MAIL_* di instance/config.py."""
        from .mailer import mail_enabled, send_mail

        if not mail_enabled():
            raise click.ClickException("MAIL_SERVER belum diisi di instance/config.py.")
        if not send_mail(to, "Percobaan email JejakPacil", "Kalau email ini sampai, pengiriman email sudah berfungsi."):
            raise click.ClickException("Gagal mengirim. Periksa MAIL_USERNAME, MAIL_PASSWORD (sandi aplikasi), dan log di atas.")
        click.echo(f"Email percobaan terkirim ke {to}.")

    @app.cli.command("seed-demo")
    @click.option("--with-logos", is_flag=True, help="Ambil logo perusahaan dari internet.")
    def seed_demo(with_logos):
        """Isi database dengan data contoh (semua orang dan ceritanya fiktif)."""
        db = get_db()
        if query("SELECT 1 FROM users WHERE email = 'admin@ui.ac.id'", one=True):
            raise click.ClickException("Data demo sudah ada. Hapus folder instance/ jika ingin mengulang.")

        users = {}
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, full_name, role, is_verified, prodi, angkatan, bio)"
            " VALUES ('admin@ui.ac.id', ?, 'Admin JejakPacil', 'admin', 1, 'Ilmu Komputer', 2022, ?)",
            (generate_password_hash("admin12345"), "Akun admin untuk demo."),
        )
        users["admin"] = cursor.lastrowid
        password_hash = generate_password_hash(DEMO_PASSWORD)
        for key, name, prodi, angkatan, status, grad_year, skills in DEMO_USERS:
            cursor = db.execute(
                "INSERT INTO users (email, password_hash, full_name, is_verified, prodi, angkatan, status,"
                " grad_year, bio) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
                (f"{key}.demo@ui.ac.id", password_hash, name, prodi, angkatan, status, grad_year,
                 "Akun demo. Orang dan riwayat di profil ini fiktif."),
            )
            users[key] = cursor.lastrowid
            _add_skills(db, "user_skills", "user_id", users[key], skills)

        companies = {}
        for name, domain, industry, description in DEMO_COMPANIES:
            logo = None
            if with_logos:
                logo = fetch_logo(domain)
                click.echo(f"  logo {name}: {'ok' if logo else 'tidak ditemukan'}")
            cursor = db.execute(
                "INSERT INTO companies (name, slug, domain, website, industry, description, logo, is_approved,"
                " created_by) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (name, slugify(name), domain, f"https://{domain}", industry, description, logo, users["admin"]),
            )
            companies[name] = cursor.lastrowid
        # Satu perusahaan ganda yang belum disetujui, untuk mencoba fitur "gabungkan" di panel admin.
        cursor = db.execute(
            "INSERT INTO companies (name, slug, is_approved, created_by) VALUES (?, ?, 0, ?)",
            ("PT Gojek Indonesia", "pt-gojek-indonesia", users["bagas"]),
        )
        db.execute(
            "INSERT INTO experiences (user_id, company_id, position, type, start_date, end_date, location,"
            " work_mode, how_obtained, visibility) VALUES (?, ?, 'Data Engineer Intern', 'magang',"
            " '2023-06', '2023-08', 'Jakarta', 'hybrid', 'portal', 'sivitas')",
            (users["bagas"], cursor.lastrowid),
        )

        for (owner, company, position, kind, start, end, location, mode, channel, skills,
             verification, visibility) in DEMO_EXPERIENCES:
            cursor = db.execute(
                "INSERT INTO experiences (user_id, company_id, position, type, start_date, end_date,"
                " location, work_mode, how_obtained, verification, visibility)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (users[owner], companies[company], position, kind, start, end, location, mode, channel,
                 verification, visibility),
            )
            _add_skills(db, "experience_skills", "experience_id", cursor.lastrowid, skills)

        categories = {row["slug"]: row["id"] for row in query("SELECT id, slug FROM categories")}
        thread_ids = {}
        for author, category, company, title, body, anonymous, pinned, replies, voters in DEMO_THREADS:
            cursor = db.execute(
                "INSERT INTO threads (author_id, category_id, company_id, title, body, is_anonymous, is_pinned)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (users[author], categories[category], companies.get(company), title, body, anonymous, pinned),
            )
            thread_id = cursor.lastrowid
            thread_ids[title] = thread_id
            for reply_author, reply_body, reply_anonymous, children in replies:
                cursor = db.execute(
                    "INSERT INTO replies (thread_id, author_id, body, is_anonymous) VALUES (?, ?, ?, ?)",
                    (thread_id, users[reply_author], reply_body, reply_anonymous),
                )
                parent_id = cursor.lastrowid
                for child_author, child_body in children:
                    db.execute(
                        "INSERT INTO replies (thread_id, author_id, parent_id, body) VALUES (?, ?, ?, ?)",
                        (thread_id, users[child_author], parent_id, child_body),
                    )
            for voter in voters:
                db.execute("INSERT INTO votes (user_id, thread_id) VALUES (?, ?)", (users[voter], thread_id))

        _seed_roles_and_stories(db, users)
        _seed_cv_items(db, users)
        _seed_attachments_and_chats(db, users, thread_ids)
        _seed_notifications(db, users)
        db.commit()
        click.echo("Data demo siap.")
        click.echo("  Admin : admin@ui.ac.id / admin12345")
        click.echo(f"  Contoh: salsa.demo@ui.ac.id / {DEMO_PASSWORD} (semua akun demo memakai kata sandi ini)")


def _add_skills(db, table, owner_column, owner_id, skills_text):
    for name in [part.strip() for part in skills_text.split(",") if part.strip()]:
        db.execute("INSERT OR IGNORE INTO skills (name) VALUES (?)", (name,))
        skill_id = db.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()["id"]
        db.execute(
            f"INSERT OR IGNORE INTO {table} ({owner_column}, skill_id) VALUES (?, ?)", (owner_id, skill_id)
        )


def _demo_image(lines, background, foreground):
    """Gambar contoh sederhana untuk lampiran demo (tanpa perlu file dari luar)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 1200), background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 60, 840, 1140), 48, outline=foreground, width=10)
    for index, line in enumerate(lines):
        try:
            draw.text((120, 160 + index * 120), line, fill=foreground, font_size=64 if index == 0 else 48)
        except TypeError:  # Pillow lama (< 10.1) belum mendukung font_size
            draw.text((120, 160 + index * 120), line, fill=foreground)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _seed_attachments_and_chats(db, users, thread_ids):
    """Lampiran foto di satu thread dan beberapa chat pribadi, supaya fiturnya langsung terlihat."""
    def add_image(lines, background, foreground, folder, **owner):
        (column, owner_id), = owner.items()
        data = _demo_image(lines, background, foreground)
        stored = save_image_bytes(data, folder, max_size=(1600, 1600), photo=True)
        db.execute(
            f"INSERT INTO attachments (uploader_id, {column}, stored_name, original_name, kind, size)"
            " VALUES (?, ?, ?, ?, 'image', ?)",
            (users["farhan"], owner_id, stored, f"{lines[0]}.jpg", len(data)),
        )

    android = thread_ids.get("Cerita persiapan magang Android")
    if android:
        add_image(["Rencana 8 minggu", "1. Kotlin dasar", "2. Proyek kecil sampai rilis",
                   "3. Struktur data tiap malam", "4. Latihan wawancara"], "#2f4a3a", "#f2f2e9", "forum",
                  thread_id=android)
        add_image(["Jadwal Kuliah", "DDP 1   08.00", "Kalkulus   10.00", "Manbis   13.00"],
                  "#d6e6f2", "#1e3350", "forum", thread_id=android)

    def conversation(a, b, thread_id, lines):
        low, high = sorted((users[a], users[b]))
        cursor = db.execute(
            "INSERT INTO conversations (user_low, user_high, thread_id, last_message_at)"
            " VALUES (?, ?, ?, datetime('now', ?))",
            (low, high, thread_id, f"-{lines[-1][2]} minutes"),
        )
        for sender, body, minutes_ago, read in lines:
            message = db.execute(
                "INSERT INTO messages (conversation_id, sender_id, body, created_at, read_at)"
                " VALUES (?, ?, ?, datetime('now', ?), CASE WHEN ? THEN datetime('now') END)",
                (cursor.lastrowid, users[sender], body, f"-{minutes_ago} minutes", read),
            )
            if body == "":
                add_image(["Jadwal Kuliah", "DDP 1   08.00", "Kalkulus   10.00", "Manbis   13.00"],
                          "#d6e6f2", "#1e3350", "chat", message_id=message.lastrowid)

    conversation("salsa", "farhan", android, [
        ("salsa", "Halo Kak Farhan! Aku baca thread persiapan magang Android-nya. Boleh tanya soal proyek pribadinya?", 40, 1),
        ("farhan", "Halo Salsa! Boleh banget. Ini tampilan aplikasinya waktu itu:", 35, 1),
        ("farhan", "", 35, 1),
        ("salsa", "Keren! Itu pakai Kotlin semua, Kak?", 30, 1),
        ("farhan", "Iya, Kotlin semua. Nanti aku kirim juga catatan belajarku.", 12, 0),
    ])
    conversation("salsa", "raka", None, [
        ("salsa", "Kak Raka, aku tertarik dengan referral backend yang di forum.", 1500, 1),
        ("raka", "Boleh. Pastikan CV di profilmu sudah yang terbaru ya.", 1440, 1),
        ("raka", "CV-mu sudah kuteruskan ke tim HR, tunggu kabar minggu depan.", 90, 0),
    ])


def _seed_notifications(db, users):
    """Beberapa notifikasi untuk Salsa, supaya halaman /notifikasi tidak kosong saat demo."""
    salsa = users["salsa"]
    thread = db.execute(
        "SELECT id, title FROM threads WHERE author_id = ? ORDER BY id LIMIT 1", (salsa,)
    ).fetchone() or db.execute("SELECT id, title FROM threads ORDER BY id DESC LIMIT 1").fetchone()
    experience = db.execute(
        """SELECT e.id, e.position, c.name FROM experiences e JOIN companies c ON c.id = e.company_id
            WHERE e.user_id = ? AND e.verification = 'terverifikasi' LIMIT 1""",
        (salsa,),
    ).fetchone()
    rows = []
    if thread:
        link = f"/forum/t/{thread['id']}"
        rows.append(("balasan_thread", users["farhan"], 1, thread["title"], "", link, 0, 25))
        rows.append(("suara", users["raka"], 3, thread["title"], "", link, 0, 120))
    if experience:
        rows.append(("verifikasi_diterima", None, 1, experience["position"], experience["name"],
                     f"/mahasiswa/{salsa}#pengalaman-{experience['id']}", 1, 60 * 26))
    for kind, actor, count, subject, detail, link, read, minutes in rows:
        db.execute(
            """INSERT INTO notifications (user_id, kind, actor_id, count, subject, detail, link, is_read,
                                          created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', ?), datetime('now', ?))""",
            (salsa, kind, actor, count, subject, detail, link, read, f"-{minutes} minutes", f"-{minutes} minutes"),
        )


def _seed_roles_and_stories(db, users):
    """Isi bidang pekerjaan semua pengalaman demo, dan cerita seleksi untuk sebagian."""
    for position, role in DEMO_ROLES.items():
        db.execute("UPDATE experiences SET role_category = ? WHERE position = ?", (role, position))
    for (owner, company, position), (stages, weeks, level, questions, tips) in DEMO_STORIES.items():
        db.execute(
            """UPDATE experiences SET selection_stages = ?, selection_weeks = ?, selection_difficulty = ?,
                      selection_questions = ?, selection_tips = ?
                WHERE user_id = ? AND position = ?
                  AND company_id = (SELECT id FROM companies WHERE name = ?)""",
            (",".join(dict.fromkeys(stages.split(","))), weeks, level, questions, tips,
             users[owner], position, company),
        )

