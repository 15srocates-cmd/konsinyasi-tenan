# Status Proyek — Konsinyasi Tenan

Catatan serah terima supaya pekerjaan bisa dilanjutkan kapan saja.
Diperbarui: **27 November 2026**.

## 1. Keadaan saat ini

Aplikasi web Flask + SQLite sudah berjalan dan diuji. Fitur yang sudah ada:

- Login 4 role: `admin`, `kasir`, `manajer`, `tenan`
- Hak akses per fitur per role diatur admin lewat menu **Hak Akses**
- Nama kasir otomatis mengikuti akun yang login
- Master Tenan, barang titipan, penerimaan, penjualan, retur, settlement
- Kasir bergaya alur Youtap POS: Daftar Produk/Input Manual → Detail Pesanan (qty, harga, charge/discount, total) → tombol **BAYAR** → konfirmasi tunai/transfer/QRIS manual → struk
- Tenan baru **Sukabakmi** (`SBK`) dengan 18 produk dari gambar yang diberikan
- Edit barang: nama, kode, harga acuan, harga jual, expired, status aktif
- Edit Tenan lewat **popup** pada daftar Tenan: kode, nama, kontak, model, komisi, periode, tempo; perubahan kode otomatis menyesuaikan kode barang Tenan tersebut
- Dashboard tidak lagi menampilkan stok titipan; diganti grafik pendapatan 7 hari terakhir (komisi/margin vs penjualan) + stat pendapatan hari ini
- Role `tenan` sebagai Pengisi Tenan: input titipan berstatus `PENDING`, terbatas pada Tenan sendiri
- Kartu **Menunggu Validasi** di Dashboard admin untuk approve/reject; tidak ada halaman Waiting Room terpisah
- Laporan Harian Tenan (`/portal/laporan-harian`): barang habis, reject/rusak/ditolak, expired; hanya data Tenan sendiri
- Redirect aman: jika `dashboard.view` kasir dicabut, `/` langsung ke `/kasir`, tidak loop
- PostgreSQL schema sudah disiapkan, tetapi belum dipakai (belum terpasang di mesin)

## 2. Cara menjalankan lagi

```powershell
cd "D:\OneDrive\Documents\Default Project\web"
python app.py
```

Buka `http://127.0.0.1:5000`. Untuk akses dari HP, gunakan IP LAN komputer yang sama jaringannya.

Inisialisasi/reset database **hanya jika memang ingin menghapus data**:

```powershell
python app.py --init        # aman, menambah kolom baru bila belum ada
python app.py --init --reset # MENGHAPUS seluruh data lama
```

Jalankan uji otomatis tanpa menyentuh database utama:

```powershell
python -c "import os,tempfile,runpy,app; app.DB_PATH=os.path.join(tempfile.gettempdir(),'konsinyasi_smoke.db'); app.init_db(reset=True); runpy.run_path('smoke_test.py',run_name='__main__')"
```

## 3. Akun contoh

| Username | Password | Role | Catatan |
|---|---|---|---|
| `admin` | `admin123` | admin | Hak penuh; menu Hak Akses dikunci untuk admin |
| `kasir` | `kasir123` | kasir | Saat ini `dashboard.view = 0`, `kasir.use = 1` |
| `manajer` | `manajer123` | manajer | Lihat laporan & settlement |
| `tenan1` | `tenan123` | tenan | Pengisi + pemilik data Sukabakmi |
| `tenan2` | `tenan123` | tenan | Pengisi + pemilik data Sari Dagang |

## 4. File penting

- `web/app.py` — seluruh logika bisnis, route, permission
- `web/templates/` — tampilan (kasir, struk, barang, popup edit di `tenan.html`, hak_akses, `laporan_harian.html`, dll.)
- `web/static/kasir.js`, `web/static/style.css` — alur kasir & styling
- `web/schema_sqlite.sql` — skema uji coba SQLite
- `schema.sql` — skema produksi PostgreSQL
- `web/konsinyasi.db` — **database berisi perubahan hak akses user; jangan di-reset**
- `web/smoke_test.py` — uji alur otomatis
- `web/README.md` — panduan operasional
- `DOKUMEN-KONSEP.md` — keputusan bisnis
- `bp3-dashboard/` — baseline dashboard BP3 4 Pilar yang diimpor 23 Nov 2026 (lihat bagian 8)

## 5. Keputusan yang sudah disepakati

- Istilah **Tenan**, bukan supplier; kode unik per Tenan, tanpa barcode
- Model B default: toko bayar harga jual, Tenan kasih komisi; Model A sebagai opsi
- Rumus: `hutang per unit = harga jual − komisi per unit`
- Sukabakmi: Model B, komisi 20%, settlement mingguan
- Satu lokasi dulu, kolom `lokasi_id` sudah disiapkan
- QRIS manual, tanpa payment gateway
- Role `tenan` = Pengisi Tenan + Pemilik Tenan; input titipan dan laporan harian dibatasi pada Tenan sendiri
- Admin menjadi validator; Waiting Room berupa kartu di Dashboard, bukan halaman/route terpisah
- Barang lama (`SD-001`, `SD-002`, `MN-001`, `BJ-001`) tetap ada sebagai data uji tetapi `aktif = 0`
- Tenan tidak bisa diubah di form edit barang agar riwayat penjualan tidak berpindah
- Edit Tenan memakai popup, bukan halaman terpisah; field mengikuti kolom daftar Tenan. `kode_prefix` bisa diubah dan kode barang Tenan ikut disesuaikan (riwayat tetap memakai `barang_id`, bukan kode)

## 6. Yang belum dikerjakan

- Migrasi produksi ke PostgreSQL + `psycopg` (Postgres belum terpasang di mesin)
- `app.secret_key` bisa di-set lewat environment variable `KONSINYASI_SECRET_KEY`; fallback bawaan masih untuk pengembangan, wajib diganti sebelum deploy publik
- Waitress/HTTPS + pengamanan produksi
- Fase mobile (direncanakan online-only)
- Import data/master dari Youtap bila ada export data
- Validasi stok sudah di server, tetapi konkurensi multi-kasir belum diuji

## 7. Cara melanjutkan di sesi baru

Buka OpenCode pada folder:

```
D:\OneDrive\Documents\Default Project
```

Lalu mulai sesi baru dan tempel prompt ini:

> Lanjutkan proyek konsinyasi Tenan di folder ini. Baca `STATUS-PROYEK.md`, `web/README.md`, dan `DOKUMEN-KONSEP.md` dulu. Jangan reset `web/konsinyasi.db` tanpa izin. Lanjutkan dari bagian "Yang belum dikerjakan" sesuai instruksi saya berikutnya.

Catatan: asisten tidak menyimpan ingatan percakapan antar-sesi secara otomatis. File `STATUS-PROYEK.md`, `web/README.md`, dan `DOKUMEN-KONSEP.md` adalah sumber kebenaran. Simpan pembaruan ke file ini setiap kali ada perubahan besar.

## 8. Modul terimpor: Dashboard BP3 4 Pilar

- Folder: `bp3-dashboard/`. File utama: `index.html` (salinan byte-for-byte dari
  `D:\OneDrive\Documents\Dashboard BP3 4 Pilar.html`, SHA-256
  `3466CA1FF2FCBA4ED18480661BE67E16FC9288CE7FAA5C9AEE3F80D43DFDA9C5`).
- Detail asal, cara menjalankan, dan batasan ada di `bp3-dashboard/README.md`.
- Analisis kebutuhan versi PRD ada di `bp3-dashboard/PRD.md` (draf 0.4: **dokumen usulan pertama** = `DASHBOARD PEMENANGAN PKS.docx`; dokumen pendukung mengisi angka/aturan; sebagian pertanyaan masih perlu keputusan stakeholder).
- Sumber otoritatif definisi/target ada di `bp3-dashboard/dokumen-sumber/` (Rapi DOCX + Scorecard XLSX); acuan utama ruang lingkup produk adalah `DASHBOARD PEMENANGAN PKS.docx`; angka di `index.html` sebagian masih demo.
- Kesenjangan utama yang sudah dicatat: blueprint belum punya kolom **Alur Kerja** (0/4 pilar) dan **Konektivitas** baru terisi 1/4 pilar; lihat PRD bagian 4.5 dan Lampiran D.
- **PRD implementasi versi 1.1 (final)** ada di `bp3-app/PRD.md` (Markdown, untuk developer) dan `bp3-app/PRD-v1.1.docx` (Word, untuk review DPP; pratinjau PDF `PRD-v1.1-preview.pdf`, 17 halaman). Keputusan penyusunan: MVP fokus scorecard 4 pilar, aplikasi Flask + SQLite baru di `bp3-app/`, login sederhana sejak MVP, semua level bisa input dulu, audit trail menyusul. PRD 1.1 menambah paket komunikasi DPP (HTML animasi + PNG + naskah 60 detik) dan 3 keputusan DPP sebagai prasyarat pembangunan.
- Ini **bahan awal** yang diadopsi 23 November 2026; bukan bagian dari aplikasi konsinyasi
  dan belum terhubung ke `web/` maupun database mana pun.
- Data masih contoh dan tersimpan di `localStorage` browser (`bp3_4pilar_dashboard_v1`).
- File asli di Documents sengaja tidak dihapus/diubah.

## 9. GitHub & sinkronisasi

- Repo yang dipakai: **public**, `https://github.com/15srocates-cmd/konsinyasi-tenan.git`, sudah terhubung sebagai `origin` dan branch `main` sudah di-push.
- Feedback klien dikirim lewat **WhatsApp langsung ke pembuat aplikasi**, bukan lewat GitHub Issues.
- Setiap selesai memperbaiki di OpenCode, jalankan `sync-github.ps1` agar perubahan otomatis di-`commit` lalu di-`push` ke `origin`.
- `.gitignore` sudah mencegah `web/konsinyasi.db`, folder `__pycache__`, dan proyek lain di workspace ikut ter-commit.
- Cara paling cepat untuk demo: `jalankan-internet.ps1` menyalakan Flask + Cloudflare Tunnel dan memberi URL `https://xxxx.trycloudflare.com` (tanpa kartu, tanpa hosting; laptop harus nyala, URL sementara).
- Deploy internet permanen tanpa kartu: **PythonAnywhere Free**. Panduan ada di `PYTHONANYWHERE.md`; `web/wsgi.py` membuat seed otomatis dan `update-pythonanywhere.sh` menarik perubahan dari GitHub + reload.
- `render.yaml` tetap disimpan sebagai alternatif auto-deploy penuh (Render meminta kartu hanya untuk verifikasi akun).
- Database di PythonAnywhere permanen di `~/konsinyasi-tenan/web/konsinyasi.db`, berbeda dengan Render yang kembali ke seed setelah deploy ulang.
- Sebelum dipakai publik sungguhan: ganti password contoh dan `KONSINYASI_SECRET_KEY`.
