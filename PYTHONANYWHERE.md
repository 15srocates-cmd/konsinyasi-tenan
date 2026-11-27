# Deploy ke PythonAnywhere (gratis, tanpa kartu kredit)

Panduan ini memakai repo public `https://github.com/15srocates-cmd/konsinyasi-tenan.git`.
Ganti `<username>` di bawah dengan username PythonAnywhere Anda.

## 1. Siapkan akun & source

1. Daftar/login di https://www.pythonanywhere.com (pilih plan **Free**).
2. Buka console **Bash**, lalu jalankan:

```bash
git clone https://github.com/15srocates-cmd/konsinyasi-tenan.git
cd konsinyasi-tenan/web
python -m pip install --user -r requirements.txt
```

## 2. Buat Web App

1. Buka tab **Web** → **Add a new web app**.
2. Pilih **Manual configuration** → pilih Python **3.10/3.12** → lanjut sampai selesai.
3. Pada halaman web app, klik tautan **WSGI configuration file**
   (biasanya `/var/www/<username>_pythonanywhere_com_wsgi.py`).
4. Hapus seluruh isinya, lalu isi dengan:

```python
import sys

path = "/home/<username>/konsinyasi-tenan/web"
if path not in sys.path:
    sys.path.insert(0, path)

from wsgi import application
```

5. Simpan, lalu klik tombol hijau **Reload**.

## 3. Coba aplikasi

Buka:

```
https://<username>.pythonanywhere.com
```

Login memakai akun contoh:

```
admin / admin123
```

Database dibuat otomatis oleh `web/wsgi.py` saat web app pertama kali dimuat.

## 4. Update setelah saya push ke GitHub

PythonAnywhere free tidak otomatis menarik perubahan dari GitHub. Setiap ada push baru, jalankan di **Bash console**:

```bash
bash ~/konsinyasi-tenan/update-pythonanywhere.sh
```

Script itu melakukan `git pull origin main` lalu menyentuh `web/wsgi.py` supaya PythonAnywhere me-reload aplikasi.

## Catatan penting

- Berbeda dengan Render, database di PythonAnywhere **tersimpan permanen** di
  `~/konsinyasi-tenan/web/konsinyasi.db` dan tidak kembali ke seed saat reload.
- Ganti nilai `KONSINYASI_SECRET_KEY` di `web/wsgi.py` (atau WSGI file) sebelum
  dipakai publik sungguhan.
- Ganti juga password akun contoh (`admin/admin123`, `kasir/kasir123`, dll.).
- Karena repo public, jangan pernah commit file `.db` atau file berisi kredensial.
