"""Mengambil logo perusahaan dari layanan logo publik berdasarkan nama domain.

Logo yang berhasil diambil disimpan sebagai file di server sendiri. Dengan begitu
halaman tetap menampilkan logo walaupun layanan luarnya berubah atau mati.
"""

import requests
from flask import current_app

from .utils import save_image_bytes

MAX_LOGO_BYTES = 2 * 1024 * 1024


def fetch_logo(domain):
    """Coba tiap penyedia secara berurutan. Kembalikan nama file logo, atau None jika gagal."""
    if not domain or not current_app.config["LOGO_FETCH_ENABLED"]:
        return None
    for template in current_app.config["LOGO_PROVIDERS"]:
        url = template.format(domain=domain)
        try:
            response = requests.get(url, timeout=4, headers={"User-Agent": "JejakPacil/1.0"})
        except requests.RequestException:
            continue  # tidak ada internet atau penyedia bermasalah: coba penyedia berikutnya
        if response.status_code != 200 or len(response.content) > MAX_LOGO_BYTES:
            continue
        try:
            return save_image_bytes(response.content, "logos", max_size=(256, 256))
        except ValueError:
            continue  # balasan bukan gambar yang bisa dibaca (mis. SVG atau halaman error)
    return None
