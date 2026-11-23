"""Tes otomatis. Jalankan dari folder proyek dengan:  python -m unittest -v

Setiap tes memakai database dan folder unggahan sementara, jadi data asli tidak tersentuh.
"""

import io
import re
import os
import shutil
import tempfile
import unittest
from unittest import mock

from PIL import Image

from app import create_app
from app.db import execute, query
from app.logos import fetch_logo
from app.security import make_verify_token
from app.utils import clean_domain, format_duration, format_period, is_safe_next, slugify


def png_bytes(color="blue"):
    """Gambar PNG kecil yang valid, untuk menguji unggahan."""
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


class BaseTest(unittest.TestCase):
    csrf_enabled = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "kunci-tes",
            "DATABASE": os.path.join(self.tmp, "tes.sqlite3"),
            "UPLOAD_FOLDER": os.path.join(self.tmp, "uploads"),
            "CSRF_ENABLED": self.csrf_enabled,
            "LOGO_FETCH_ENABLED": False,  # tes tidak boleh bergantung pada internet
        })
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # ----- pembantu -----

    def register(self, email="budi@ui.ac.id", name="Budi Santoso", verify=True, **extra):
        data = {
            "full_name": name, "email": email, "password": "rahasia123", "password2": "rahasia123",
            "prodi": "Sistem Informasi", "angkatan": "2024", "status": "aktif",
        }
        data.update(extra)
        response = self.client.post("/daftar", data=data)
        if verify:
            with self.app.test_request_context():
                token = make_verify_token(email)
            self.client.get(f"/verifikasi/{token}")
        return response

    def login(self, email="budi@ui.ac.id", password="rahasia123"):
        return self.client.post("/masuk", data={"email": email, "password": password})

    def logout(self):
        return self.client.post("/keluar")

    def make_admin(self, email):
        with self.app.app_context():
            execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))

    def add_experience(self, **extra):
        data = {
            "company_name": "Tokopedia", "company_website": "tokopedia.com",
            "position": "Software Engineer Intern", "type": "magang",
            "start_date": "2025-06", "end_date": "2025-08", "location": "Jakarta",
            "work_mode": "hybrid", "how_obtained": "portal", "visibility": "publik",
            "skills": "Python, python, SQL",
        }
        data.update(extra)
        return self.client.post("/pengalaman/tambah", data=data, content_type="multipart/form-data")

    def db(self, sql, params=(), one=False):
        with self.app.app_context():
            return query(sql, params, one=one)


class UtilsTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Bank Central Asia"), "bank-central-asia")
        self.assertEqual(slugify("  !!  "), "item")

    def test_clean_domain(self):
        self.assertEqual(clean_domain("https://www.Tokopedia.com/karier"), "tokopedia.com")
        self.assertEqual(clean_domain("gojek.com"), "gojek.com")
        self.assertEqual(clean_domain("bukan domain"), "")
        self.assertEqual(clean_domain("localhost"), "")

    def test_periode_dan_durasi(self):
        self.assertEqual(format_period("2025-06", "2025-08"), "Jun 2025 – Agu 2025")
        self.assertEqual(format_period("2025-06", None), "Jun 2025 – sekarang")
        self.assertEqual(format_duration("2025-06", "2025-08"), "3 bln")
        self.assertEqual(format_duration("2023-01", "2024-02"), "1 thn 2 bln")

    def test_is_safe_next(self):
        self.assertTrue(is_safe_next("/forum/"))
        self.assertFalse(is_safe_next("https://situs-jahat.example"))
        self.assertFalse(is_safe_next("//situs-jahat.example"))


class AuthTest(BaseTest):
    def test_email_non_ui_ditolak(self):
        response = self.register(email="budi@gmail.com", verify=False)
        self.assertIn("@ui.ac.id", response.get_data(as_text=True))
        self.assertIsNone(self.db("SELECT 1 FROM users", one=True))

    def test_harus_verifikasi_sebelum_masuk(self):
        self.register(verify=False)
        response = self.login()
        self.assertIn("belum diverifikasi", response.get_data(as_text=True))

    def test_daftar_verifikasi_masuk(self):
        self.register()
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/forum/").status_code, 200)

    def test_kata_sandi_disimpan_sebagai_hash(self):
        self.register()
        user = self.db("SELECT password_hash FROM users", one=True)
        self.assertNotIn("rahasia123", user["password_hash"])

    def test_kata_sandi_salah(self):
        self.register()
        response = self.login(password="salah-total")
        self.assertIn("Email atau kata sandi salah", response.get_data(as_text=True))

    def test_alumni_wajib_tahun_lulus(self):
        response = self.register(status="alumni", verify=False)
        self.assertIn("Isi tahun lulus", response.get_data(as_text=True))

    def test_token_palsu_ditolak(self):
        self.register(verify=False)
        self.client.get("/verifikasi/token-palsu")
        self.assertEqual(self.db("SELECT is_verified FROM users", one=True)["is_verified"], 0)

    def test_halaman_terbatas_butuh_login(self):
        for path in ("/forum/", "/mahasiswa", "/pengalaman/tambah", "/profil/edit"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/masuk", response.headers["Location"])

    def test_next_tidak_bisa_keluar_situs(self):
        self.register()
        response = self.client.post(
            "/masuk?next=https://situs-jahat.example",
            data={"email": "budi@ui.ac.id", "password": "rahasia123"},
        )
        self.assertEqual(response.headers["Location"], "/")


class HomeTest(BaseTest):
    def test_beranda_tamu_menjelaskan_fitur(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("Yang bisa kamu lakukan di sini", page)
        self.assertIn("Cara kerjanya", page)

    def test_beranda_setelah_masuk_berisi_daftar_cek(self):
        self.register()
        self.login()
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("Halo, Budi", page)
        self.assertIn("0 dari 5 selesai", page)

        self.add_experience()
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("1 dari 5 selesai", page)

    def test_menu_utama_empat_bagian(self):
        page = self.client.get("/").get_data(as_text=True)
        nav = page.split('aria-label="Menu utama"')[1].split("</nav>")[0]
        self.assertEqual(nav.count("<a "), 4)
        self.assertIn("Jelajahi", nav)

    def test_chip_filter_mempertahankan_kata_kunci(self):
        page = self.client.get("/pengalaman?q=engineer").get_data(as_text=True)
        self.assertIn("/pengalaman?q=engineer&amp;jenis=magang", page)


class CsrfTest(BaseTest):
    csrf_enabled = True

    def test_post_tanpa_token_ditolak(self):
        response = self.client.post("/masuk", data={"email": "a@ui.ac.id", "password": "x"})
        self.assertEqual(response.status_code, 400)

    def test_post_dengan_token_diterima(self):
        self.client.get("/masuk")  # membuat token di sesi
        with self.client.session_transaction() as session:
            token = session["_csrf"]
        response = self.client.post("/masuk", data={"email": "a@ui.ac.id", "password": "x", "csrf_token": token})
        self.assertEqual(response.status_code, 200)


class ExperienceTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.register()
        self.login()

    def test_tambah_pengalaman_membuat_perusahaan_menunggu(self):
        self.add_experience()
        company = self.db("SELECT * FROM companies", one=True)
        self.assertEqual(company["name"], "Tokopedia")
        self.assertEqual(company["domain"], "tokopedia.com")
        self.assertEqual(company["is_approved"], 0)
        # Skill ganda (Python, python) hanya tersimpan sekali.
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM experience_skills", one=True)["n"], 2)

    def test_nama_perusahaan_tidak_dobel(self):
        self.add_experience()
        self.add_experience(company_name="tokopedia", position="Data Analyst Intern")
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM companies", one=True)["n"], 1)
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM experiences", one=True)["n"], 2)

    def test_tanggal_selesai_sebelum_mulai_ditolak(self):
        response = self.add_experience(start_date="2025-08", end_date="2025-06")
        self.assertIn("tidak boleh sebelum", response.get_data(as_text=True))
        self.assertIsNone(self.db("SELECT 1 FROM experiences", one=True))

    def test_masih_berjalan(self):
        self.add_experience(is_current="1", end_date="")
        self.assertIsNone(self.db("SELECT end_date FROM experiences", one=True)["end_date"])

    def test_visibilitas(self):
        self.add_experience(position="Posisi Publik", visibility="publik")
        self.add_experience(position="Posisi Sivitas", visibility="sivitas")
        self.add_experience(position="Posisi Privat", visibility="privat")
        with self.app.app_context():
            execute("UPDATE companies SET is_approved = 1")

        # Pemilik melihat semuanya di profilnya.
        own = self.client.get("/mahasiswa/1").get_data(as_text=True)
        for text in ("Posisi Publik", "Posisi Sivitas", "Posisi Privat"):
            self.assertIn(text, own)

        # Pengguna lain yang masuk: publik dan sivitas saja.
        self.logout()
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        other = self.client.get("/mahasiswa/1").get_data(as_text=True)
        self.assertIn("Posisi Sivitas", other)
        self.assertNotIn("Posisi Privat", other)

        # Pengunjung tanpa akun: publik saja.
        self.logout()
        guest = self.client.get("/pengalaman").get_data(as_text=True)
        self.assertIn("Posisi Publik", guest)
        self.assertNotIn("Posisi Sivitas", guest)
        self.assertNotIn("Posisi Privat", guest)

    def test_tidak_bisa_mengubah_milik_orang_lain(self):
        self.add_experience()
        self.logout()
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        self.assertEqual(self.client.get("/pengalaman/1/edit").status_code, 403)
        self.assertEqual(self.client.post("/pengalaman/1/hapus").status_code, 403)
        self.assertIsNotNone(self.db("SELECT 1 FROM experiences WHERE id = 1", one=True))

    def test_bukti_hanya_untuk_pemilik_dan_admin(self):
        self.add_experience(proof=(io.BytesIO(png_bytes()), "bukti.png"))
        experience = self.db("SELECT proof, verification FROM experiences", one=True)
        self.assertEqual(experience["verification"], "menunggu")
        url = f"/media/proofs/{experience['proof']}"
        with self.client.get(url) as response:
            self.assertEqual(response.status_code, 200)

        self.logout()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_file_bukan_gambar_ditolak(self):
        response = self.add_experience(proof=(io.BytesIO(b"<script>alert(1)</script>"), "jahat.png"))
        self.assertIn("Bukti harus berupa PDF atau gambar", response.get_data(as_text=True))
        self.assertIsNone(self.db("SELECT 1 FROM experiences", one=True))

    def test_mengubah_fakta_membatalkan_verifikasi(self):
        self.add_experience()
        with self.app.app_context():
            execute("UPDATE experiences SET verification = 'terverifikasi'")
        data = {
            "company_name": "Tokopedia", "position": "Posisi Lain", "type": "magang",
            "start_date": "2025-06", "end_date": "2025-08", "work_mode": "hybrid",
            "how_obtained": "portal", "visibility": "publik",
        }
        self.client.post("/pengalaman/1/edit", data=data, content_type="multipart/form-data")
        self.assertEqual(self.db("SELECT verification FROM experiences", one=True)["verification"], "belum")


class CompanyAndAdminTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.register()
        self.login()
        self.add_experience()
        self.add_experience(company_name="PT Tokopedia", position="QA Intern")
        self.logout()
        self.register(email="admin@ui.ac.id", name="Admin Tes")
        self.make_admin("admin@ui.ac.id")

    def test_perusahaan_muncul_setelah_disetujui(self):
        self.assertNotIn("Tokopedia", self.client.get("/perusahaan").get_data(as_text=True))
        self.assertEqual(self.client.get("/perusahaan/tokopedia").status_code, 404)
        self.login(email="admin@ui.ac.id")
        self.client.post("/admin/perusahaan/1/setujui")
        self.logout()
        page = self.client.get("/perusahaan").get_data(as_text=True)
        self.assertIn("Tokopedia", page)
        self.assertIn("1 magang", page)

    def test_panel_admin_tertutup_untuk_anggota(self):
        self.login()
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertEqual(self.client.post("/admin/perusahaan/1/setujui").status_code, 403)

    def test_filter_dan_urutan_perusahaan(self):
        self.login(email="admin@ui.ac.id")
        self.client.post("/admin/perusahaan/1/setujui")
        self.logout()
        semua = self.client.get("/perusahaan").get_data(as_text=True)
        self.assertIn("Tokopedia", semua)
        self.assertIn("dir-chip-n", semua)  # jumlah per industri tampil
        for urut in ("populer", "terbaru", "az", "ngawur"):
            self.assertEqual(self.client.get(f"/perusahaan?urut={urut}").status_code, 200)
        lain = self.client.get("/perusahaan?industri=Kesehatan").get_data(as_text=True)
        self.assertNotIn("Tokopedia", lain)
        self.assertIn("Hapus filter", lain)

    def test_filter_jelajahi(self):
        self.login(email="admin@ui.ac.id")
        self.client.post("/admin/perusahaan/1/setujui")
        semua = self.client.get("/pengalaman").get_data(as_text=True)
        self.assertIn("Software Engineer Intern", semua)
        self.assertNotIn("dir-active", semua)  # belum ada filter aktif
        hasil = self.client.get("/pengalaman?jenis=fulltime&terverifikasi=1").get_data(as_text=True)
        self.assertNotIn("Software Engineer Intern", hasil)
        self.assertIn("Hapus filter Terverifikasi", hasil)  # label filter bisa dihapus satu per satu

    def test_gabung_perusahaan(self):
        self.login(email="admin@ui.ac.id")
        self.client.post("/admin/perusahaan/gabung", data={"source_id": "2", "target_id": "1"})
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM companies", one=True)["n"], 1)
        self.assertEqual(
            self.db("SELECT COUNT(*) AS n FROM experiences WHERE company_id = 1", one=True)["n"], 2
        )

    def test_verifikasi_pengalaman(self):
        with self.app.app_context():
            execute("UPDATE experiences SET verification = 'menunggu' WHERE id = 1")
        self.login(email="admin@ui.ac.id")
        self.client.post("/admin/pengalaman/1/putuskan", data={"decision": "terverifikasi"})
        self.assertEqual(
            self.db("SELECT verification FROM experiences WHERE id = 1", one=True)["verification"],
            "terverifikasi",
        )

    def test_unggah_logo(self):
        self.login(email="admin@ui.ac.id")
        self.client.post(
            "/admin/perusahaan/1/edit",
            data={
                "name": "Tokopedia", "domain": "tokopedia.com", "industry": "E-commerce",
                "is_approved": "1", "logo": (io.BytesIO(png_bytes()), "logo.png"),
            },
            content_type="multipart/form-data",
        )
        company = self.db("SELECT * FROM companies WHERE id = 1", one=True)
        self.assertTrue(company["logo"].endswith(".png"))
        with self.client.get(f"/media/logos/{company['logo']}") as response:
            self.assertEqual(response.status_code, 200)
        self.assertIn(company["logo"], self.client.get("/perusahaan").get_data(as_text=True))

    def test_ekspor_csv(self):
        self.login(email="admin@ui.ac.id")
        response = self.client.get("/admin/ekspor.csv")
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("Budi Santoso", response.get_data(as_text=True))


class LogoFetchTest(BaseTest):
    """Pengambilan logo diuji dengan balasan tiruan, tanpa benar-benar memakai internet."""

    def setUp(self):
        super().setUp()
        self.app.config["LOGO_FETCH_ENABLED"] = True

    def test_logo_tersimpan(self):
        fake = mock.Mock(status_code=200, content=png_bytes())
        with self.app.app_context(), mock.patch("app.logos.requests.get", return_value=fake) as get:
            filename = fetch_logo("tokopedia.com")
            self.assertIn("tokopedia.com", get.call_args.args[0])
            path = os.path.join(self.app.config["UPLOAD_FOLDER"], "logos", filename)
            self.assertTrue(os.path.exists(path))

    def test_pindah_ke_penyedia_berikutnya(self):
        responses = [mock.Mock(status_code=404, content=b""), mock.Mock(status_code=200, content=png_bytes())]
        with self.app.app_context(), mock.patch("app.logos.requests.get", side_effect=responses) as get:
            self.assertIsNotNone(fetch_logo("tokopedia.com"))
            self.assertEqual(get.call_count, 2)

    def test_balasan_bukan_gambar(self):
        fake = mock.Mock(status_code=200, content=b"<html>bukan gambar</html>")
        with self.app.app_context(), mock.patch("app.logos.requests.get", return_value=fake):
            self.assertIsNone(fetch_logo("tokopedia.com"))

    def test_tanpa_internet(self):
        import requests

        with self.app.app_context(), mock.patch(
            "app.logos.requests.get", side_effect=requests.ConnectionError
        ):
            self.assertIsNone(fetch_logo("tokopedia.com"))


class ForumTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.register()
        self.login()
        self.category_id = self.db("SELECT id FROM categories WHERE slug = 'magang'", one=True)["id"]

    def create_thread(self, **extra):
        data = {
            "title": "Bagaimana cara mencari magang pertama?",
            "body": "Aku masih semester tiga dan bingung mulai dari mana.",
            "category_id": str(self.category_id),
        }
        data.update(extra)
        return self.client.post("/forum/buat", data=data)

    def test_buat_thread_dan_balas(self):
        self.create_thread()
        self.client.post("/forum/t/1/balas", data={"body": "Mulai dari proyek kecil."})
        self.client.post("/forum/t/1/balas", data={"body": "Setuju.", "parent_id": "1"})
        # Membalas "anak" tetap menempel ke balasan utama (maksimal dua tingkat).
        self.client.post("/forum/t/1/balas", data={"body": "Terima kasih.", "parent_id": "2"})
        parents = [row["parent_id"] for row in self.db("SELECT parent_id FROM replies ORDER BY id")]
        self.assertEqual(parents, [None, 1, 1])
        page = self.client.get("/forum/t/1").get_data(as_text=True)
        self.assertIn("Mulai dari proyek kecil.", page)
        self.assertIn("3 balasan", page)

    def test_judul_terlalu_pendek(self):
        response = self.create_thread(title="Hai")
        self.assertIn("minimal 8 huruf", response.get_data(as_text=True))

    def test_suara_bolak_balik(self):
        self.create_thread()
        self.client.post("/forum/t/1/suara")
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM votes", one=True)["n"], 1)
        self.client.post("/forum/t/1/suara")
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM votes", one=True)["n"], 0)

    def test_anonim_menyembunyikan_nama(self):
        self.create_thread(is_anonymous="1")
        self.logout()
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        page = self.client.get("/forum/t/1").get_data(as_text=True)
        self.assertIn("Anonim", page)
        self.assertNotIn("Budi Santoso", page)

    def test_isi_tidak_bisa_menyisipkan_html(self):
        self.create_thread(body="<script>alert('xss')</script> isi biasa")
        page = self.client.get("/forum/t/1").get_data(as_text=True)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_lapor_lalu_admin_menyembunyikan(self):
        self.create_thread()
        self.client.post("/forum/lapor", data={"thread_id": "1", "reason": "Isinya promosi judi."})
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM reports", one=True)["n"], 1)

        self.make_admin("budi@ui.ac.id")
        self.assertIn("Isinya promosi judi.", self.client.get("/admin/laporan").get_data(as_text=True))
        self.client.post("/admin/laporan/1/tindak", data={"action": "sembunyikan"})
        self.assertEqual(self.db("SELECT is_hidden FROM threads", one=True)["is_hidden"], 1)

        # Pengguna biasa tidak lagi bisa membuka thread yang disembunyikan.
        self.logout()
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        self.assertEqual(self.client.get("/forum/t/1").status_code, 404)

    def test_hanya_penulis_yang_bisa_menghapus(self):
        self.create_thread()
        self.logout()
        self.register(email="sari@ui.ac.id", name="Sari Dewi")
        self.login(email="sari@ui.ac.id")
        self.assertEqual(self.client.post("/forum/t/1/hapus").status_code, 403)
        self.assertEqual(self.client.get("/forum/t/1/edit").status_code, 403)


if __name__ == "__main__":
    unittest.main()


class LanguageTest(BaseTest):
    """Tombol bahasa: Indonesia bawaan, Inggris lewat /bahasa/en, tetap setelah masuk."""

    def test_bahasa_bawaan_indonesia(self):
        page = self.client.get("/perusahaan").get_data(as_text=True)
        self.assertIn('lang="id"', page)
        self.assertIn("Cari nama perusahaan", page)

    def test_ganti_ke_inggris_lalu_kembali(self):
        response = self.client.get("/bahasa/en?next=/perusahaan")
        self.assertEqual(response.headers["Location"], "/perusahaan")
        page = self.client.get("/perusahaan").get_data(as_text=True)
        self.assertIn('lang="en"', page)
        self.assertIn("Search company name", page)
        self.client.get("/bahasa/id?next=/")
        self.assertIn("Cari nama perusahaan", self.client.get("/perusahaan").get_data(as_text=True))

    def test_next_luar_situs_ditolak(self):
        response = self.client.get("/bahasa/en?next=https://contoh.com")
        self.assertEqual(response.headers["Location"], "/")

    def test_bahasa_tetap_setelah_masuk(self):
        self.register()
        self.client.get("/bahasa/en?next=/")
        self.login()
        self.assertIn("Sign out", self.client.get("/").get_data(as_text=True))

    def test_semua_teks_halaman_utama_punya_terjemahan(self):
        from app import i18n

        self.register()
        self.client.get("/bahasa/en?next=/")
        self.login()
        i18n.MISSING.clear()
        for url in ("/", "/perusahaan", "/pengalaman", "/mahasiswa", "/forum/", "/statistik",
                    "/pengalaman/tambah", "/profil/edit", "/forum/buat"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(sorted(i18n.MISSING), [])


class ForumAttachmentTest(BaseTest):
    """Lampiran foto dan PDF di thread dan balasan forum."""

    def setUp(self):
        super().setUp()
        self.register()
        self.login()
        self.category_id = self.db("SELECT id FROM categories LIMIT 1", one=True)["id"]

    def create_thread(self, files):
        return self.client.post("/forum/buat", data={
            "category_id": str(self.category_id), "title": "Tanya soal magang data",
            "body": "Ada yang punya pengalaman magang data analyst?", "files": files,
        }, content_type="multipart/form-data")

    def test_thread_dengan_foto_dan_pdf(self):
        response = self.create_thread([(io.BytesIO(png_bytes()), "foto.png"),
                                       (io.BytesIO(b"%PDF-1.4 isi"), "catatan.pdf")])
        self.assertEqual(response.status_code, 302)
        rows = self.db("SELECT kind, original_name FROM attachments ORDER BY id")
        self.assertEqual([(r["kind"], r["original_name"]) for r in rows], [("image", "foto.png"), ("pdf", "catatan.pdf")])
        page = self.client.get("/forum/t/1").get_data(as_text=True)
        self.assertIn("catatan.pdf", page)
        stored = self.db("SELECT stored_name FROM attachments WHERE kind = 'image'", one=True)["stored_name"]
        self.assertTrue(stored.endswith(".jpg"))  # foto ditulis ulang sebagai JPEG
        with self.client.get(f"/media/forum/{stored}") as media:
            self.assertEqual(media.status_code, 200)

    def test_file_palsu_ditolak(self):
        response = self.create_thread([(io.BytesIO(b"<script>alert(1)</script>"), "foto.png")])
        self.assertEqual(response.status_code, 200)  # form tampil lagi dengan pesan error
        self.assertIn("bukan foto", response.get_data(as_text=True))
        self.assertIsNone(self.db("SELECT 1 FROM threads", one=True))

    def test_lebih_dari_empat_file_ditolak(self):
        files = [(io.BytesIO(png_bytes()), f"f{i}.png") for i in range(5)]
        self.assertIn("maksimal 4", self.create_thread(files).get_data(as_text=True))

    def test_balasan_boleh_hanya_foto(self):
        self.create_thread([])
        self.client.post("/forum/t/1/balas", data={"body": "", "files": [(io.BytesIO(png_bytes()), "a.png")]},
                         content_type="multipart/form-data")
        self.assertEqual(self.db("SELECT COUNT(*) AS n FROM attachments WHERE reply_id IS NOT NULL", one=True)["n"], 1)

    def test_lampiran_forum_tertutup_untuk_tamu(self):
        self.create_thread([(io.BytesIO(png_bytes()), "foto.png")])
        stored = self.db("SELECT stored_name FROM attachments", one=True)["stored_name"]
        self.logout()
        with self.client.get(f"/media/forum/{stored}") as media:
            self.assertEqual(media.status_code, 403)

    def test_hapus_thread_menghapus_file(self):
        self.create_thread([(io.BytesIO(png_bytes()), "foto.png")])
        stored = self.db("SELECT stored_name FROM attachments", one=True)["stored_name"]
        path = os.path.join(self.tmp, "uploads", "forum", stored)
        self.assertTrue(os.path.exists(path))
        self.client.post("/forum/t/1/hapus")
        self.assertFalse(os.path.exists(path))


class MessageTest(BaseTest):
    """Chat pribadi: hanya dua orang di percakapan yang bisa membaca isinya."""

    def setUp(self):
        super().setUp()
        self.register(email="budi@ui.ac.id", name="Budi Santoso")      # id 1
        self.register(email="sari@ui.ac.id", name="Sari Wulandari")    # id 2
        self.register(email="tono@ui.ac.id", name="Tono Prasetyo")     # id 3
        self.login()

    def start_chat(self, user_id=2):
        response = self.client.post(f"/pesan/mulai/{user_id}")
        return int(response.headers["Location"].rsplit("/", 1)[1])

    def test_kirim_dan_terima_pesan(self):
        conversation_id = self.start_chat()
        self.assertEqual(self.start_chat(), conversation_id)  # pasangan yang sama, percakapan yang sama
        self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Halo Sari!"})
        self.logout()
        self.login(email="sari@ui.ac.id")
        home = self.client.get("/").get_data(as_text=True)
        self.assertRegex(home, r"data-unread-count>\s*1\s*<")  # angka di ikon pesan
        page = self.client.get(f"/pesan/{conversation_id}").get_data(as_text=True)
        self.assertIn("Halo Sari!", page)
        self.assertIsNotNone(self.db("SELECT read_at FROM messages", one=True)["read_at"])  # terbaca setelah dibuka

    def test_orang_lain_tidak_bisa_membaca(self):
        conversation_id = self.start_chat()
        self.client.post(f"/pesan/{conversation_id}/kirim", data={
            "body": "Rahasia", "files": [(io.BytesIO(png_bytes()), "a.png")]}, content_type="multipart/form-data")
        stored = self.db("SELECT stored_name FROM attachments", one=True)["stored_name"]
        self.logout()
        self.login(email="tono@ui.ac.id")
        self.assertEqual(self.client.get(f"/pesan/{conversation_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/pesan/{conversation_id}/baru").status_code, 404)
        self.assertEqual(self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "x"}).status_code, 404)
        with self.client.get(f"/media/chat/{stored}") as media:
            self.assertEqual(media.status_code, 403)

    def test_polling_mengirim_pesan_baru_saja(self):
        conversation_id = self.start_chat()
        self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Satu"})
        first_id = self.db("SELECT MAX(id) AS id FROM messages", one=True)["id"]
        self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Dua"})
        data = self.client.get(f"/pesan/{conversation_id}/baru?setelah={first_id}").get_json()
        self.assertIn("Dua", data["html"])
        self.assertNotIn("Satu", data["html"])

    def test_kirim_lewat_fetch_mengembalikan_json(self):
        conversation_id = self.start_chat()
        data = self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Halo", "setelah": "0"},
                                headers={"X-Requested-With": "fetch"}).get_json()
        self.assertIn("Halo", data["html"])
        response = self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": " "},
                                    headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.status_code, 400)

    def test_blokir(self):
        conversation_id = self.start_chat()
        self.logout()
        self.login(email="sari@ui.ac.id")
        self.client.post(f"/pesan/{conversation_id}/blokir")
        self.logout()
        self.login()
        self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Halo?"})
        self.assertIsNone(self.db("SELECT 1 FROM messages", one=True))

    def test_tidak_bisa_chat_diri_sendiri(self):
        self.assertEqual(self.client.post("/pesan/mulai/1").status_code, 400)

    def test_lapor_pesan_terlihat_admin(self):
        conversation_id = self.start_chat()
        self.client.post(f"/pesan/{conversation_id}/kirim", data={"body": "Pesan kasar"})
        self.logout()
        self.login(email="sari@ui.ac.id")
        message_id = self.db("SELECT id FROM messages", one=True)["id"]
        self.client.post(f"/pesan/lapor/{message_id}", data={"reason": "Kata-kata kasar"})
        self.make_admin("tono@ui.ac.id")
        self.logout()
        self.login(email="tono@ui.ac.id")
        self.assertIn("Pesan kasar", self.client.get("/admin/laporan").get_data(as_text=True))
        report_id = self.db("SELECT id FROM message_reports", one=True)["id"]
        self.client.post(f"/admin/laporan-pesan/{report_id}/tindak", data={"action": "sembunyikan"})
        self.assertEqual(self.db("SELECT is_hidden FROM messages", one=True)["is_hidden"], 1)


class MessageActionTest(BaseTest):
    """Balas, edit, dan hapus pesan chat."""

    def setUp(self):
        super().setUp()
        self.register(email="budi@ui.ac.id", name="Budi Santoso")      # id 1
        self.register(email="sari@ui.ac.id", name="Sari Wulandari")    # id 2
        self.register(email="tono@ui.ac.id", name="Tono Prasetyo")     # id 3
        self.login()
        self.conversation_id = self.start_chat()

    start_chat = MessageTest.start_chat

    def send(self, body, **extra):
        self.client.post(f"/pesan/{self.conversation_id}/kirim", data={"body": body, **extra})
        return self.db("SELECT MAX(id) AS id FROM messages", one=True)["id"]

    def as_sari(self):
        self.logout()
        self.login(email="sari@ui.ac.id")

    def test_balas_pesan(self):
        first = self.send("Kapan seleksinya?")
        self.as_sari()
        reply = self.send("Minggu depan", reply_to=str(first))
        self.assertEqual(self.db("SELECT reply_to_id FROM messages WHERE id = ?", (reply,), one=True)["reply_to_id"], first)
        page = self.client.get(f"/pesan/{self.conversation_id}").get_data(as_text=True)
        self.assertIn('class="b-quote"', page)
        self.assertIn("Kapan seleksinya?", page)

    def test_balas_pesan_percakapan_lain_diabaikan(self):
        other_conversation = self.start_chat(3)
        self.client.post(f"/pesan/{other_conversation}/kirim", data={"body": "Rahasia untuk Tono"})
        secret = self.db("SELECT MAX(id) AS id FROM messages", one=True)["id"]
        reply = self.send("Halo", reply_to=str(secret))
        self.assertIsNone(self.db("SELECT reply_to_id FROM messages WHERE id = ?", (reply,), one=True)["reply_to_id"])

    def test_edit_pesan_sendiri(self):
        message_id = self.send("Halo Sri")
        data = self.client.post(f"/pesan/pesan/{message_id}/edit", data={"body": "Halo Sari"},
                                headers={"X-Requested-With": "fetch"}).get_json()
        self.assertIn("Halo Sari", data["html"])
        self.assertIn("diedit", data["html"])
        row = self.db("SELECT body, edited_at FROM messages WHERE id = ?", (message_id,), one=True)
        self.assertEqual(row["body"], "Halo Sari")
        self.assertIsNotNone(row["edited_at"])

    def test_tidak_bisa_edit_atau_hapus_pesan_orang_lain(self):
        message_id = self.send("Pesan Budi")
        self.as_sari()
        self.assertEqual(self.client.post(f"/pesan/pesan/{message_id}/edit", data={"body": "diubah"}).status_code, 403)
        self.assertEqual(self.client.post(f"/pesan/pesan/{message_id}/hapus").status_code, 403)
        self.assertEqual(self.db("SELECT body FROM messages", one=True)["body"], "Pesan Budi")

    def test_hapus_pesan_dan_lampirannya(self):
        self.client.post(f"/pesan/{self.conversation_id}/kirim", data={
            "body": "Ini fotonya", "files": [(io.BytesIO(png_bytes()), "a.png")]}, content_type="multipart/form-data")
        message_id = self.db("SELECT MAX(id) AS id FROM messages", one=True)["id"]
        stored = self.db("SELECT stored_name FROM attachments", one=True)["stored_name"]
        self.client.post(f"/pesan/pesan/{message_id}/hapus")
        row = self.db("SELECT body, deleted_at FROM messages WHERE id = ?", (message_id,), one=True)
        self.assertEqual(row["body"], "")
        self.assertIsNotNone(row["deleted_at"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "uploads", "chat", stored)))
        self.as_sari()
        page = self.client.get(f"/pesan/{self.conversation_id}").get_data(as_text=True)
        self.assertIn("Pesan ini dihapus.", page)
        self.assertNotIn("Ini fotonya", page)

    def test_pesan_yang_dilaporkan_tetap_tersimpan_untuk_admin(self):
        message_id = self.send("Kata-kata kasar")
        self.as_sari()
        self.client.post(f"/pesan/lapor/{message_id}", data={"reason": "Kasar sekali"})
        self.logout()
        self.login()
        response = self.client.post(f"/pesan/pesan/{message_id}/edit", data={"body": "Maaf"},
                                    headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.status_code, 400)  # tidak bisa mengubah bukti
        self.client.post(f"/pesan/pesan/{message_id}/hapus")
        row = self.db("SELECT body, deleted_at FROM messages WHERE id = ?", (message_id,), one=True)
        self.assertEqual(row["body"], "Kata-kata kasar")
        self.assertIsNotNone(row["deleted_at"])

    def test_polling_mengirim_pesan_yang_berubah(self):
        message_id = self.send("Versi pertama")
        now = self.db("SELECT datetime('now', '-1 second') AS t", one=True)["t"]
        self.client.post(f"/pesan/pesan/{message_id}/edit", data={"body": "Versi kedua"})
        self.as_sari()
        data = self.client.get(f"/pesan/{self.conversation_id}/baru?setelah={message_id}&ubah={now}").get_json()
        self.assertEqual([item["id"] for item in data["changed"]], [message_id])
        self.assertIn("Versi kedua", data["changed"][0]["html"])
        self.assertTrue(data["now"])

    def test_mode_balas_dan_edit_tanpa_javascript(self):
        message_id = self.send("Halo")
        page = self.client.get(f"/pesan/{self.conversation_id}?edit={message_id}").get_data(as_text=True)
        self.assertIn(f"/pesan/pesan/{message_id}/edit", page)
        self.assertIn("Mengedit pesan", page)
        page = self.client.get(f"/pesan/{self.conversation_id}?balas={message_id}").get_data(as_text=True)
        self.assertIn(f'name="reply_to" value="{message_id}"', page)


class PasswordTest(BaseTest):
    """Lupa kata sandi, atur ulang, ganti kata sandi, dan pembatas percobaan masuk."""

    def setUp(self):
        super().setUp()
        self.register()

    def reset_link(self):
        """Ambil tautan atur ulang dari pesan flash (mode pengembangan)."""
        self.client.post("/lupa-kata-sandi", data={"email": "budi@ui.ac.id"})
        page = self.client.get("/masuk").get_data(as_text=True)
        match = re.search(r'<a href="(http://localhost/atur-ulang-kata-sandi/[^"]+)">', page)  # tautan, bukan teks
        self.assertIsNotNone(match)
        return match.group(1).replace("http://localhost", "")

    def test_lupa_kata_sandi_lalu_masuk_dengan_yang_baru(self):
        link = self.reset_link()
        response = self.client.post(link, data={"password": "sandiBaru2026", "password2": "sandiBaru2026"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.login(password="rahasia123").status_code, 200)  # sandi lama ditolak
        self.assertEqual(self.login(password="sandiBaru2026").status_code, 302)

    def test_tautan_atur_ulang_hanya_sekali_pakai(self):
        link = self.reset_link()
        self.client.post(link, data={"password": "sandiBaru2026", "password2": "sandiBaru2026"})
        response = self.client.get(link)
        self.assertIn("/lupa-kata-sandi", response.headers["Location"])

    def test_tautan_mode_pengembangan_bisa_diklik(self):
        # Pesan berisi tautan tidak boleh tampil sebagai teks HTML mentah (&lt;a href=...).
        page = self.client.get("/masuk").get_data(as_text=True)
        self.assertIn('<a href="http://localhost/verifikasi/', page)

    def test_tautan_palsu_ditolak(self):
        response = self.client.get("/atur-ulang-kata-sandi/token-palsu")
        self.assertIn("/lupa-kata-sandi", response.headers["Location"])

    def test_email_tidak_terdaftar_tetap_pesan_sama(self):
        response = self.client.post("/lupa-kata-sandi", data={"email": "tidakada@ui.ac.id"}, follow_redirects=True)
        self.assertIn("Jika email itu terdaftar", response.get_data(as_text=True))
        self.assertNotIn("atur-ulang-kata-sandi/", response.get_data(as_text=True))

    def test_kata_sandi_mudah_ditebak_ditolak(self):
        link = self.reset_link()
        for weak in ("12345678", "budi2026x", "pendek"):
            page = self.client.post(link, data={"password": weak, "password2": weak}).get_data(as_text=True)
            self.assertIn('class="error"', page, weak)

    def test_ganti_kata_sandi_mengeluarkan_perangkat_lain(self):
        self.login()
        other_device = self.app.test_client()
        other_device.post("/masuk", data={"email": "budi@ui.ac.id", "password": "rahasia123"})
        self.assertEqual(other_device.get("/profil/edit").status_code, 200)

        wrong = self.client.post("/akun/kata-sandi", data={
            "current": "salah", "password": "sandiBaru2026", "password2": "sandiBaru2026"})
        self.assertIn("Kata sandi saat ini salah", wrong.get_data(as_text=True))
        self.client.post("/akun/kata-sandi", data={
            "current": "rahasia123", "password": "sandiBaru2026", "password2": "sandiBaru2026"})

        self.assertEqual(self.client.get("/profil/edit").status_code, 200)   # perangkat ini tetap masuk
        self.assertEqual(other_device.get("/profil/edit").status_code, 302)  # perangkat lain keluar

    def test_terlalu_banyak_percobaan_gagal_dikunci(self):
        for _ in range(5):
            self.login(password="salah-terus")
        page = self.login(password="rahasia123").get_data(as_text=True)  # sandi benar pun ditolak sementara
        self.assertIn("Terlalu banyak percobaan", page)
        with self.app.app_context():
            from app.db import execute
            execute("UPDATE rate_limits SET created_at = datetime('now', '-20 minutes')")
        self.assertEqual(self.login(password="rahasia123").status_code, 302)  # setelah 15 menit boleh lagi

    def test_masuk_berhasil_menghapus_hitungan_gagal(self):
        for _ in range(4):
            self.login(password="salah")
        self.login()
        self.assertIsNone(self.db("SELECT 1 FROM rate_limits WHERE kind = 'login-gagal'", one=True))


class NotificationTest(BaseTest):
    """Notifikasi: balasan, suara, keputusan admin, dan halaman /notifikasi."""

    def setUp(self):
        super().setUp()
        self.register(email="budi@ui.ac.id", name="Budi Santoso")      # penulis thread
        self.register(email="sari@ui.ac.id", name="Sari Wulandari")
        self.register(email="tono@ui.ac.id", name="Tono Prasetyo")
        self.login()
        category_id = self.db("SELECT id FROM categories LIMIT 1", one=True)["id"]
        self.client.post("/forum/buat", data={
            "category_id": str(category_id), "title": "Tips wawancara teknis",
            "body": "Ada tips untuk wawancara teknis pertama?"})
        self.thread_id = self.db("SELECT id FROM threads", one=True)["id"]

    def switch(self, email):
        self.logout()
        self.login(email=email)

    def notifications_for(self, email):
        return self.db(
            "SELECT n.* FROM notifications n JOIN users u ON u.id = n.user_id WHERE u.email = ? ORDER BY n.id", (email,))

    def test_balasan_ke_thread(self):
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Balasanku sendiri"})
        self.assertEqual(self.notifications_for("budi@ui.ac.id"), [])  # membalas thread sendiri: tidak ada notifikasi
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Latihan soal di LeetCode"})
        rows = self.notifications_for("budi@ui.ac.id")
        self.assertEqual([r["kind"] for r in rows], ["balasan_thread"])
        self.switch("budi@ui.ac.id")
        page = self.client.get("/notifikasi/").get_data(as_text=True)
        self.assertIn("Sari Wulandari membalas thread-mu", page)

    def test_balasan_anonim_tidak_membuka_nama(self):
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Rahasia", "is_anonymous": "1"})
        self.switch("budi@ui.ac.id")
        page = self.client.get("/notifikasi/").get_data(as_text=True)
        self.assertIn("Seseorang (anonim)", page)
        self.assertNotIn("Sari Wulandari", page)
        # Identitas pengirim anonim bahkan tidak disimpan di tabel notifikasi.
        self.assertIsNone(self.notifications_for("budi@ui.ac.id")[0]["actor_id"])

    def test_balasan_ke_komentar(self):
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Komentar Sari"})
        reply_id = self.db("SELECT id FROM replies", one=True)["id"]
        self.switch("tono@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Setuju", "parent_id": str(reply_id)})
        self.assertEqual([r["kind"] for r in self.notifications_for("sari@ui.ac.id")], ["balasan_komentar"])
        self.assertEqual([r["kind"] for r in self.notifications_for("budi@ui.ac.id")],
                         ["balasan_thread", "balasan_thread"])

    def test_suara_digabung(self):
        for email in ("sari@ui.ac.id", "tono@ui.ac.id"):
            self.switch(email)
            self.client.post(f"/forum/t/{self.thread_id}/suara")
        self.client.post(f"/forum/t/{self.thread_id}/suara")  # Tono mencabut suara
        self.client.post(f"/forum/t/{self.thread_id}/suara")  # lalu memberi lagi: tidak dihitung dua kali
        rows = self.notifications_for("budi@ui.ac.id")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 2)
        self.switch("budi@ui.ac.id")
        self.assertIn("dan 1 orang lainnya memberi suara", self.client.get("/notifikasi/").get_data(as_text=True))

    def test_buka_notifikasi_menandai_dibaca(self):
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Halo"})
        notification_id = self.notifications_for("budi@ui.ac.id")[0]["id"]
        self.assertEqual(self.client.get(f"/notifikasi/{notification_id}/buka").status_code, 404)  # bukan milik Sari
        self.switch("budi@ui.ac.id")
        self.assertEqual(self.client.get("/notifikasi/jumlah").get_json()["notifications"], 1)
        response = self.client.get(f"/notifikasi/{notification_id}/buka")
        self.assertIn(f"/forum/t/{self.thread_id}#balasan-", response.headers["Location"])
        self.assertEqual(self.client.get("/notifikasi/jumlah").get_json()["notifications"], 0)

    def test_tandai_semua_dibaca(self):
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Satu"})
        self.client.post(f"/forum/t/{self.thread_id}/suara")
        self.switch("budi@ui.ac.id")
        self.client.post("/notifikasi/tandai-dibaca")
        self.assertEqual(self.client.get("/notifikasi/jumlah").get_json()["notifications"], 0)

    def test_keputusan_admin(self):
        self.add_experience(company_name="Startup Baru", company_website="startupbaru.id")
        experience_id = self.db("SELECT id FROM experiences", one=True)["id"]
        company_id = self.db("SELECT id FROM companies WHERE name = 'Startup Baru'", one=True)["id"]
        self.make_admin("tono@ui.ac.id")
        self.switch("tono@ui.ac.id")
        self.client.post(f"/admin/pengalaman/{experience_id}/putuskan", data={"decision": "ditolak"})
        self.client.post(f"/admin/perusahaan/{company_id}/setujui")
        kinds = [r["kind"] for r in self.notifications_for("budi@ui.ac.id")]
        self.assertEqual(kinds, ["verifikasi_ditolak", "perusahaan_disetujui"])
        self.switch("budi@ui.ac.id")
        page = self.client.get("/notifikasi/").get_data(as_text=True)
        self.assertIn("Software Engineer Intern di Startup Baru ditolak", page)
        self.assertIn("Startup Baru, perusahaan yang kamu tambahkan", page)

    def test_lonceng_di_navbar(self):
        self.switch("sari@ui.ac.id")
        self.client.post(f"/forum/t/{self.thread_id}/balas", data={"body": "Halo"})
        self.switch("budi@ui.ac.id")
        self.assertRegex(self.client.get("/").get_data(as_text=True), r"data-notification-count>\s*1\s*<")

