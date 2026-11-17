"""Titik masuk aplikasi. Jalankan dengan:  python run.py"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True hanya untuk pengembangan: server otomatis memuat ulang saat kode berubah.
    app.run(debug=True)

###http://127.0.0.1:5000/