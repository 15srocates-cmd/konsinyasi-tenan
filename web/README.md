# Web Admin Konsinyasi Tenan (versi uji coba)

Aplikasi web Flask + SQLite untuk mencoba alur konsinyasi sebelum dipindah ke PostgreSQL.

## Menjalankan

```powershell
cd web
python app.py --init
python app.py
```

Buka `http://127.0.0.1:5000`.

Data contoh otomatis dibuat saat database kosong: 4 Tenan (termasuk **Sukabakmi**), 18 produk SUKABAKMI + 4 barang uji lama (disembunyikan dari menu), stok awal, dan 1 penjualan contoh.

Reset data:

```powershell
python app.py --init --reset
```

Uji alur otomatis (akan menambah data contoh, jalankan setelah reset):

```powershell
python smoke_test.py
```

## Akses dari HP / perangkat lain

Secara default Flask hanya mendengar di `127.0.0.1`. Di `app.py` sudah diubah ke `0.0.0.0`, jadi perangkat lain dalam satu jaringan bisa mengakses.

1. Pastikan HP dan komputer terhubung ke **Wi-Fi yang sama**
2. Cari IP lokal komputer:

   ```powershell
   ipconfig
   ```

   Lihat baris **IPv4 Address** di adapter Wi-Fi/Ethernet, misalnya `192.168.1.10`

3. Jalankan aplikasi seperti biasa:

   ```powershell
   python app.py
   ```

4. Di browser HP, buka:

   ```
   http://192.168.1.10:5000
   ```

   (ganti dengan IP komputer Anda)

Jika tidak bisa diakses, izinkan Python lewat Windows Firewall saat popup muncul, atau jalankan PowerShell sebagai Administrator:

```powershell
New-NetFirewallRule -DisplayName "Konsinyasi Flask 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

> `debug=True` hanya untuk pengembangan. Jangan ekspos ke internet publik. Untuk akses dari luar jaringan, gunakan server produksi (Waitress) + HTTPS + login.

## Yang bisa dicoba

1. **Tenan & Kesepakatan** — tambah Tenan, atur model B/A, komisi persen/tetap, periode mingguan/bulanan; klik **Edit** pada baris Tenan untuk membuka popup berisi kode, nama, kontak, model, komisi, periode, dan tempo (kode barang ikut disesuaikan bila kode diubah)
2. **Barang Titipan** — tambah barang dengan kode unik per Tenan; klik **Edit** pada baris barang untuk mengubah nama, kode, harga acuan, harga jual, expired, atau status aktif/nonaktif
3. **Penerimaan** — catat titipan masuk; stok otomatis bertambah lewat mutasi `TERIMA`
4. **Penjualan** — input hingga 3 barang; komisi/margin dan hutang dihitung otomatis
5. **Retur** — retur konsumen (masuk stok atau retur Tenan) dan retur barang tak laku
6. **Settlement** — rekap per periode, ringkasan + drill-down per barang, status `DRAFT → DISETUJUI → DIBAYAR`
7. **Dashboard** — stok titipan, hutang per Tenan, settlement jatuh tempo

## Login & Kewenangan

Semua halaman memerlukan login. Akun contoh (dibuat otomatis saat reset):

| Username | Password | Role | Kewenangan |
|---|---|---|---|
| `admin` | `admin123` | admin | Semua menu, termasuk Tenan/Kesepakatan, Penerimaan, Settlement, User |
| `kasir` | `kasir123` | kasir | Dashboard, Barang (lihat), Penjualan, Kasir, Retur konsumen |
| `manajer` | `manajer123` | manajer | Dashboard, Barang/Penjualan/Retur (lihat), Settlement |
| `tenan1` | `tenan123` | tenan | Portal khusus Tenan **Sukabakmi** (read-only, hanya data sendiri) |
| `tenan2` | `tenan123` | tenan | Portal Tenan Sari Dagang |

Tambah user: menu **User** (hanya admin). User tenan wajib dihubungkan ke salah satu Tenan. Password bisa diubah sendiri lewat menu **Profil**.

### Hak akses bisa diatur admin

Menu **Hak Akses** (khusus admin) berisi matriks fitur × role. Admin bisa mencentang/menghapus centang setiap fitur untuk role admin, kasir, manajer, dan tenan. Perubahan langsung dipakai oleh navigasi dan pengecekan route.

- Hak `User` dan `Hak Akses` untuk **admin selalu aktif** agar admin tidak mengunci diri sendiri
- Role `tenan` tetap diarahkan ke `/portal` (datanya dibatasi otomatis berdasarkan `tenan_id`)
- Contoh: cabut centang `kasir.use` pada role kasir → kasir langsung tidak bisa membuka menu Kasir
- Jika `dashboard.view` dicabut, membuka `/` tidak menyebabkan redirect berulang; aplikasi otomatis mengarahkan ke menu pertama yang masih aktif (misalnya `/kasir`). Jika tidak ada menu aktif, muncul halaman **Akses Ditolak** berisi tautan logout/profil.

> `app.secret_key` masih hardcoded untuk uji coba. Ganti dengan environment variable sebelum dipakai produksi.

## Fitur Kasir (alur bergaya Youtap POS)

Buka menu **Kasir**. Layar dibagi tiga bagian:

1. **Daftar Produk / Input Manual** (kiri)
   - Tab **Daftar Produk**: grid produk + filter kategori (Semua, Suka, Makanan, Minuman) + kolom cari
   - Tab **Input Manual**: cari barang lewat kode/nama dalam bentuk tabel — karena aplikasi ini tanpa barcode, semua input memang dilakukan manual
   - Klik produk (atau tombol `+`) untuk menambah ke pesanan
2. **Detail Pesanan** (tengah)
   - Qty bisa diubah dengan tombol `−` / `+`, harga default bisa diubah
   - Tombol **Add Charge or Discount** untuk diskon atau biaya tambahan
   - Ringkasan: Subtotal → Diskon → Biaya tambahan → **Total**
   - Tombol besar **BAYAR** membuka layar konfirmasi pembayaran
3. **Kode QRIS** (kanan)
   - Panel QRIS manual: pelanggan scan, kasir konfirmasi pembayaran secara manual

Alur lengkap:

- Pilih produk → periksa Detail Pesanan → tekan **BAYAR** → pilih **Tunai / Transfer / QRIS manual** → **Simpan Transaksi** → halaman struk
- **Nama kasir diambil otomatis dari akun yang login** (tidak bisa diubah; input manual diabaikan server)
- Kembalian dihitung otomatis untuk tunai; untuk transfer/QRIS uang diterima = total
- Struk **tidak langsung dicetak** — ada tombol **Cetak Struk** (bisa disimpan sebagai PDF lewat browser)
- Diskon/biaya tambahan tersimpan di `penjualan` (`diskon`, `charge`, `total_akhir`) dan tampil di struk. Komisi/settlement tetap dihitung dari harga barang sebelum diskon, sesuai kesepakatan Tenan.

> Catatan: ini meniru **alur** kasir Youtap POS (pilih produk → keranjang → charge/discount → bayar → struk), bukan tampilan persis aplikasi mobile-nya. QRIS tetap manual, tanpa payment gateway.

## Mengedit nama barang

1. Login sebagai **admin** (atau role lain yang diberi hak `barang.edit` oleh admin)
2. Buka menu **Barang Titipan**
3. Klik tombol **Edit** di baris barang yang ingin diubah
4. Ubah kolom **Nama barang** (bisa juga kode, harga acuan, harga jual, expired, dan centangan aktif)
5. Klik **Simpan Perubahan**

Tenan sengaja tidak bisa diubah di form edit supaya riwayat penjualan lama tidak berpindah ke Tenan lain. Kode barang bisa diubah asalkan tetap unik dalam Tenan yang sama.

Perubahan nama/harga langsung dipakai kasir untuk transaksi berikutnya. Transaksi yang sudah lalu tetap menyimpan data barang saat transaksi terjadi (`penjualan_item`), jadi laporan lama tidak berubah.

> Barang yang dinonaktifkan hilang dari daftar kasir tetapi datanya tetap tersimpan.

Endpoint `/kasir` menerima JSON, jadi nanti bisa dipakai ulang oleh aplikasi mobile.

## Daftar Menu SUKABAKMI (Tenan Sukabakmi)

| Kode | Produk | Harga jual |
|---|---|---:|
| SBK-001 | Suka Chili Oil | 22.000 |
| SBK-002 | Suka Laksa | 25.000 |
| SBK-003 | Suka Maka | 25.000 |
| SBK-004 | Suka Original Jamur/Rebus | 19.000 |
| SBK-005 | Bakso Rebus | 19.000 |
| SBK-006 | Pangsit Rebus (2 pcs) | 5.000 |
| SBK-007 | Bakso Goreng | 7.000 |
| SBK-008 | Lumpia Kulit Tahu Ayam | 20.000 |
| SBK-009 | Lumpia Kulit Tahu Udang | 20.000 |
| SBK-010 | Siomay Ayam | 20.000 |
| SBK-011 | Siomay Noki | 20.000 |
| SBK-012 | Siomay Udang | 20.000 |
| SBK-013 | Siomay Cumi | 20.000 |
| SBK-014 | Siomay Kepiting | 20.000 |
| SBK-015 | Hakau | 20.000 |
| SBK-016 | Hlaitkau | 20.000 |
| SBK-017 | Ajk Minekar | 5.000 |
| SBK-018 | Liang Tea | 10.000 |

Harga acuan Tenan diisi otomatis ≈60% dari harga jual. Komisi Sukabakmi: **Model B, 20% dari harga jual**, settlement mingguan.

## Batasan versi uji coba

- Satu nota penerimaan = satu jenis barang
- Tanpa barcode (cari barang lewat kode/nama)
- Satu lokasi
- Mobile belum dibuat
- Expired baru disimpan, belum ada notifikasi otomatis

## Pindah ke PostgreSQL

Skema produksi ada di `../schema.sql`. Logika bisnis di `app.py` sudah mengikuti skema tersebut.

Yang perlu diubah saat migrasi:

| Bagian | SQLite (dev) | PostgreSQL (produksi) |
|---|---|---|
| Koneksi | `sqlite3.connect(DB_PATH)` | `psycopg.connect(...)` |
| Placeholder | `?` | `%s` |
| UUID | `uuid.uuid4()` dari Python | `gen_random_uuid()` atau tetap dari Python |
| Waktu | `CURRENT_TIMESTAMP` (TEXT) | `TIMESTAMPTZ` |
| Enum | `CHECK (...)` | `CREATE TYPE ... AS ENUM` |
| `updated_at` | trigger SQLite | trigger PL/pgSQL |

Query, formula komisi, dan hampir seluruh struktur tabel sudah identik.

## Catatan penting

- `hutang per unit = harga_jual - komisi_per_unit`
  - Model B → `komisi_per_unit` = komisi
  - Model A → `komisi_per_unit` = margin (`harga_jual - harga_acuan`)
- `stok_titipan` bukan sumber kebenaran; `mutasi_titipan` adalah ledger-nya
- Retur setelah settlement tidak mengubah settlement lama
