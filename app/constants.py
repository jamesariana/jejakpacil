"""Pilihan tetap yang dipakai di form, validasi, dan tampilan.

Kunci (sebelah kiri) disimpan di database, label (sebelah kanan) ditampilkan ke pengguna.
"""

PRODI = [
    "Ilmu Komputer",
    "Sistem Informasi",
    "Kecerdasan Artifisial",
    "Ilmu Komputer KKI",
    "Pascasarjana",
]

STATUS = {"aktif": "Mahasiswa aktif", "alumni": "Alumni"}

EXP_TYPES = {
    "magang": "Magang",
    "fulltime": "Full-time",
    "parttime": "Part-time",
    "freelance": "Freelance",
    "riset": "Riset",
    "asdos": "Asisten dosen",
}

WORK_MODES = {"onsite": "On-site", "hybrid": "Hybrid", "remote": "Remote"}

ROLE_CATEGORIES = {
    "swe_backend": "Software Engineer (Backend)",
    "swe_frontend": "Software Engineer (Frontend)",
    "swe_fullstack": "Software Engineer (Fullstack)",
    "mobile": "Mobile Developer",
    "data_scientist": "Data Scientist",
    "data_analyst": "Data Analyst",
    "data_engineer": "Data Engineer",
    "ml_engineer": "ML / AI Engineer",
    "devops": "DevOps / SRE / Cloud",
    "qa": "QA / Test Engineer",
    "security": "Cybersecurity",
    "product_manager": "Product Manager",
    "ui_ux": "UI/UX Designer",
    "business_analyst": "Business Analyst / System Analyst",
    "it_consultant": "IT Consultant",
    "researcher": "Peneliti / Akademisi",
    "lainnya": "Lainnya",
}

HOW_OBTAINED = {
    "portal": "Portal lowongan",
    "web": "Website perusahaan",
    "referral": "Referral teman atau alumni",
    "jobfair": "Job fair",
    "acara": "Acara Fasilkom (mis. COMPFEST)",
    "kampus": "Info dari kampus atau dosen",
    "lainnya": "Lainnya",
}

VISIBILITY = {
    "publik": "Publik, siapa saja bisa melihat",
    "sivitas": "Sivitas, hanya pengguna yang masuk",
    "privat": "Privat, hanya saya",
}

VERIFICATION = {
    "belum": "Belum ada bukti",
    "menunggu": "Menunggu verifikasi",
    "terverifikasi": "Terverifikasi",
    "ditolak": "Bukti ditolak",
}

INDUSTRIES = [
    "Teknologi",
    "E-commerce",
    "Fintech",
    "Perbankan & Keuangan",
    "Konsultan",
    "Telekomunikasi",
    "Pendidikan",
    "Pemerintahan & BUMN",
    "Kesehatan",
    "Media & Hiburan",
    "Logistik & Transportasi",
    "Lainnya",
]

# Kategori forum bawaan: (slug, nama, deskripsi)
DEFAULT_CATEGORIES = [
    ("magang", "Magang", "Cari magang, proses seleksi, dan cerita selama magang."),
    ("karier", "Karier & full-time", "Kerja setelah lulus, pindah kerja, dan negosiasi."),
    ("tanya-alumni", "Tanya alumni", "Pertanyaan untuk kakak tingkat dan alumni."),
    ("lowongan", "Lowongan & referral", "Info lowongan dan tawaran referral."),
    ("umum", "Umum", "Obrolan lain seputar kuliah dan dunia kerja."),
]

# Tahapan seleksi yang bisa dipilih di "Cerita seleksi". Urutan di sini adalah urutan
# tampilnya (kira-kira urutan yang paling umum di proses rekrutmen).
SELECTION_STAGES = {
    "berkas": "Seleksi CV / berkas",
    "tes_online": "Tes online / assessment",
    "psikotes": "Psikotes",
    "tes_teknis": "Tes teknis / live coding",
    "studi_kasus": "Studi kasus / take-home",
    "wawancara_hr": "Wawancara HR",
    "wawancara_teknis": "Wawancara teknis / user",
    "presentasi": "Presentasi",
    "lainnya": "Tahap lain",
}

SELECTION_DIFFICULTY = {1: "Mudah", 2: "Agak mudah", 3: "Sedang", 4: "Sulit", 5: "Sangat sulit"}

