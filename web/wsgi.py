"""Entry point WSGI untuk PythonAnywhere / hosting WSGI lainnya.

WSGI tidak menjalankan blok `if __name__ == "__main__"` di app.py,
jadi init_db() dipanggil di sini agar database contoh dibuat otomatis.
"""

import os

# Ganti nilai ini di WSGI file PythonAnywhere sebelum dipakai publik.
os.environ.setdefault("KONSINYASI_SECRET_KEY", "konsinyasi-dev-only")

from app import app, init_db

init_db()
application = app
