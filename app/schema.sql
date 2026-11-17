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
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
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

-- Indeks mempercepat pencarian yang sering dipakai.
CREATE INDEX IF NOT EXISTS idx_experiences_user    ON experiences (user_id);
CREATE INDEX IF NOT EXISTS idx_experiences_company ON experiences (company_id);
CREATE INDEX IF NOT EXISTS idx_threads_category    ON threads (category_id);
CREATE INDEX IF NOT EXISTS idx_threads_company     ON threads (company_id);
CREATE INDEX IF NOT EXISTS idx_replies_thread      ON replies (thread_id);
