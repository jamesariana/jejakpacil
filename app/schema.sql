-- Struktur database JejakPacil (SQLite).
-- Semua perintah memakai IF NOT EXISTS, jadi aman dijalankan setiap aplikasi menyala.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    is_verified   INTEGER NOT NULL DEFAULT 0,          -- 1 jika email sudah diverifikasi
    status        TEXT    NOT NULL DEFAULT 'aktif' CHECK (status IN ('aktif', 'alumni')),
    prodi         TEXT    NOT NULL,
    angkatan      INTEGER NOT NULL,
    grad_year     INTEGER,                              -- hanya untuk alumni
    bio           TEXT    NOT NULL DEFAULT '',
    photo         TEXT,                                 -- nama file di folder uploads/photos
    cv            TEXT,                                 -- nama file di folder uploads/cv
    github_url    TEXT    NOT NULL DEFAULT '',
    linkedin_url  TEXT    NOT NULL DEFAULT '',
    portfolio_url TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
    open_to_questions INTEGER NOT NULL DEFAULT 0,       -- 1 = bersedia ditanya adik tingkat
    open_note         TEXT    NOT NULL DEFAULT '',      -- topik yang bisa ditanyakan, maks. 120 karakter
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE            -- "python" dan "Python" dianggap sama
);

CREATE TABLE IF NOT EXISTS user_skills (
    user_id  INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    slug        TEXT    NOT NULL UNIQUE,                -- dipakai di URL, mis. /perusahaan/tokopedia
    domain      TEXT    NOT NULL DEFAULT '',            -- mis. tokopedia.com, dipakai untuk mengambil logo
    logo        TEXT,                                   -- nama file di folder uploads/logos
    industry    TEXT    NOT NULL DEFAULT 'Lainnya',
    description TEXT    NOT NULL DEFAULT '',
    website     TEXT    NOT NULL DEFAULT '',
    is_approved INTEGER NOT NULL DEFAULT 0,             -- 1 jika sudah disetujui admin
    created_by  INTEGER REFERENCES users (id) ON DELETE SET NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiences (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    company_id   INTEGER NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    position     TEXT    NOT NULL,
    type         TEXT    NOT NULL,                      -- lihat EXP_TYPES di constants.py
    start_date   TEXT    NOT NULL,                      -- format YYYY-MM
    end_date     TEXT,                                  -- NULL berarti masih berjalan
    location     TEXT    NOT NULL DEFAULT '',
    work_mode    TEXT    NOT NULL DEFAULT 'onsite',
    description  TEXT    NOT NULL DEFAULT '',
    how_obtained TEXT    NOT NULL DEFAULT 'lainnya',
    proof        TEXT,                                  -- nama file bukti di uploads/proofs
    verification TEXT    NOT NULL DEFAULT 'belum',      -- belum | menunggu | terverifikasi | ditolak
    visibility   TEXT    NOT NULL DEFAULT 'sivitas',    -- publik | sivitas | privat
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    role_category        TEXT,              -- bidang pekerjaan, lihat ROLE_CATEGORIES
    -- Cerita seleksi (semuanya opsional), ikut aturan visibilitas pengalamannya:
    selection_stages     TEXT,              -- kunci SELECTION_STAGES dipisah koma, mis. "berkas,tes_online,wawancara_hr"
    selection_weeks      INTEGER,           -- lama proses dari melamar sampai diterima, dalam minggu
    selection_difficulty INTEGER,           -- 1 (mudah) sampai 5 (sangat sulit)
    selection_questions  TEXT,              -- contoh pertanyaan atau soal yang ditanyakan
    selection_tips       TEXT               -- tips untuk adik tingkat
);

CREATE TABLE IF NOT EXISTS experience_skills (
    experience_id INTEGER NOT NULL REFERENCES experiences (id) ON DELETE CASCADE,
    skill_id      INTEGER NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    PRIMARY KEY (experience_id, skill_id)
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0              -- urutan tampil
);

CREATE TABLE IF NOT EXISTS threads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    category_id  INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    company_id   INTEGER REFERENCES companies (id) ON DELETE SET NULL,  -- tag perusahaan, boleh kosong
    title        TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    is_pinned    INTEGER NOT NULL DEFAULT 0,
    is_hidden    INTEGER NOT NULL DEFAULT 0,            -- disembunyikan moderator
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS replies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id    INTEGER NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
    author_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    parent_id    INTEGER REFERENCES replies (id) ON DELETE CASCADE,     -- NULL = balasan langsung ke thread
    body         TEXT    NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    is_hidden    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votes (
    user_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    thread_id INTEGER NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, thread_id)                    -- satu orang satu suara per thread
);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    thread_id   INTEGER REFERENCES threads (id) ON DELETE CASCADE,
    reply_id    INTEGER REFERENCES replies (id) ON DELETE CASCADE,
    reason      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'baru',        -- baru | selesai
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Lampiran forum: foto atau PDF yang menempel di thread atau balasan.
CREATE TABLE IF NOT EXISTS attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    uploader_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    thread_id     INTEGER REFERENCES threads (id) ON DELETE CASCADE,
    reply_id      INTEGER REFERENCES replies (id) ON DELETE CASCADE,
    message_id    INTEGER REFERENCES messages (id) ON DELETE CASCADE,
    stored_name   TEXT    NOT NULL UNIQUE,                 -- nama acak di server
    original_name TEXT    NOT NULL,                        -- nama asli, hanya untuk ditampilkan
    kind          TEXT    NOT NULL CHECK (kind IN ('image', 'pdf')),
    size          INTEGER NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Chat pribadi: satu percakapan untuk tiap pasangan pengguna.
-- user_low selalu id yang lebih kecil, supaya pasangan yang sama tidak tercatat dua kali.
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_low        INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    user_high       INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    thread_id       INTEGER REFERENCES threads (id) ON DELETE SET NULL,  -- thread asal, kalau dimulai dari forum
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TEXT,
    UNIQUE (user_low, user_high),
    CHECK (user_low < user_high)
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    sender_id       INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body            TEXT    NOT NULL DEFAULT '',
    reply_to_id     INTEGER REFERENCES messages (id) ON DELETE SET NULL,  -- pesan yang dibalas
    is_hidden       INTEGER NOT NULL DEFAULT 0,             -- disembunyikan admin setelah dilaporkan
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at         TEXT,                                   -- NULL = belum dibaca penerima
    edited_at       TEXT,                                   -- terisi kalau pesan pernah diedit
    deleted_at      TEXT,                                   -- terisi kalau pengirim menghapusnya
    updated_at      TEXT                                    -- perubahan terakhir (edit/hapus), untuk polling
);

-- Blokir: pengguna yang diblokir tidak bisa mengirim pesan ke pemblokir.
CREATE TABLE IF NOT EXISTS blocks (
    blocker_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    blocked_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (blocker_id, blocked_id)
);

-- Laporan pesan. Admin hanya bisa membaca pesan yang dilaporkan, bukan seluruh chat.
CREATE TABLE IF NOT EXISTS message_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    message_id  INTEGER NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    reason      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'baru',        -- baru | selesai
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Catatan percobaan untuk membatasi tebak-tebakan kata sandi dan permintaan tautan.
-- kind: "login-gagal" atau "lupa-sandi"; key: email atau alamat IP.
CREATE TABLE IF NOT EXISTS rate_limits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    key        TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Notifikasi di dalam website: balasan forum, suara, keputusan admin, dan moderasi.
-- Teksnya tidak disimpan jadi; yang disimpan jenis dan datanya, lalu template
-- menyusun kalimatnya dalam bahasa yang sedang dipilih pengguna.
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,   -- penerima
    kind         TEXT    NOT NULL,          -- lihat KINDS di notifications.py
    actor_id     INTEGER REFERENCES users (id) ON DELETE SET NULL,           -- yang memicu, kalau ada
    is_anonymous INTEGER NOT NULL DEFAULT 0, -- pemicu menulis secara anonim: namanya tidak ditampilkan
    count        INTEGER NOT NULL DEFAULT 1, -- untuk notifikasi yang digabung, misalnya "3 orang memberi suara"
    subject      TEXT    NOT NULL DEFAULT '', -- judul thread, posisi, atau nama perusahaan (salinan saat itu)
    detail       TEXT    NOT NULL DEFAULT '', -- keterangan tambahan, misalnya nama perusahaan
    link         TEXT    NOT NULL,            -- halaman yang dibuka saat notifikasi diklik
    group_key    TEXT,                        -- notifikasi dengan kunci sama yang belum dibaca digabung
    is_read      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indeks mempercepat pencarian yang sering dipakai.
CREATE INDEX IF NOT EXISTS idx_experiences_user    ON experiences (user_id);
CREATE INDEX IF NOT EXISTS idx_experiences_company ON experiences (company_id);
CREATE INDEX IF NOT EXISTS idx_threads_category    ON threads (category_id);
CREATE INDEX IF NOT EXISTS idx_threads_company     ON threads (company_id);
CREATE INDEX IF NOT EXISTS idx_replies_thread      ON replies (thread_id);
CREATE INDEX IF NOT EXISTS idx_attachments_thread  ON attachments (thread_id);
CREATE INDEX IF NOT EXISTS idx_attachments_reply   ON attachments (reply_id);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments (message_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv       ON messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_rate_limits ON rate_limits (kind, key, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, is_read, updated_at);

-- Isian tambahan CV yang ditulis sendiri: proyek, organisasi, prestasi, sertifikasi.
CREATE TABLE IF NOT EXISTS cv_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    section     TEXT    NOT NULL,                        -- kunci CV_SECTIONS di constants.py
    title       TEXT    NOT NULL,
    subtitle    TEXT    NOT NULL DEFAULT '',             -- peran, jabatan, penyelenggara, atau penerbit
    start_date  TEXT,                                    -- YYYY-MM, boleh kosong
    end_date    TEXT,                                    -- YYYY-MM; kosong + start_date terisi = masih berjalan
    url         TEXT    NOT NULL DEFAULT '',
    tools       TEXT    NOT NULL DEFAULT '',             -- teknologi yang dipakai (khusus proyek)
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cv_items_user ON cv_items (user_id, section);
