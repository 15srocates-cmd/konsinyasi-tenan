# Dokumen Konsep — Aplikasi Manajemen Stok Konsinyasi "Tenan"

> Status: Konsep final Fase 1. Belum ada implementasi kode.

---

## 1. Ringkasan keputusan

| Aspek | Keputusan |
|---|---|
| Istilah pemasok | **Tenan** |
| Model hutang utama | **Model B**: toko bayar harga jual, Tenan memberi komisi |
| Model alternatif | **Model A** per Tenan, lewat Kesepakatan |
| Bentuk komisi Model B | **Persen dari harga jual** atau **nominal tetap per pcs**, sesuai Kesepakatan |
| Harga jual | **Ditentukan toko**, bebas berubah |
| Harga acuan Tenan | **Tetap dicatat** (informasi + cadangan Model A) |
| Retur ke Tenan | **Selalu diterima** |
| Retur konsumen, masih bisa dijual | **Kembali ke stok titipan** + penjualan dikoreksi |
| Retur konsumen, tidak bisa dijual | **Langsung diretunkan ke Tenan** + penjualan dikoreksi |
| Identifikasi barang | Tanpa barcode, pakai kode unik per Tenan |
| Lokasi | Satu lokasi, kolom `lokasi_id` tetap disiapkan |
| Periode settlement | **Default mingguan**, **opsi bulanan per Tenan** |
| Mobile | Online-only dulu; offline sync ditunda ke Fase 3 |
| Laporan settlement | **Ringkasan per Tenan**, drill-down per barang |

---

## 2. Prinsip utama

**Tenan tetap pemilik barang sampai barang terjual.** Toko hanya menyimpan dan menjualkan.

Konsekuensi:

- Stok titipan **bukan aset toko**
- Hutang ke Tenan muncul **saat barang terjual**, bukan saat barang datang
- Retur = barang kembali ke Tenan, tidak ada uang yang berubah
- Settlement = menyelesaikan hutang yang sudah terkumpul per periode

---

## 3. Istilah

| Istilah | Arti |
|---|---|
| Tenan | Pemilik barang / principal |
| Kesepakatan | Aturan komisi, periode, dan pembayaran per Tenan |
| Titipan | Barang yang dikirim Tenan ke toko |
| Penerimaan | Nota saat barang titipan datang |
| Mutasi | Catatan setiap perubahan qty, append-only |
| Settlement | Rekap + pembayaran ke Tenan |
| Retur Tenan | Pengembalian barang tak laku ke Tenan |
| Retur konsumen | Pengembalian barang yang sudah dijual |

---

## 4. Ruang lingkup Fase 1

### Termasuk

- Kelola Tenan & Kesepakatan, termasuk edit Tenan lewat popup pada daftar Tenan: kode, nama, kontak, model, komisi, periode, tempo; kode barang ikut disesuaikan jika prefix diubah, riwayat tetap memakai `barang_id`
- Kelola Barang Titipan
- Penerimaan titipan
- Penjualan
- Kasir web: keranjang, cari barang tanpa barcode, tunai/transfer/QRIS manual, struk opsional
- Alur kasir mengikuti pola Youtap POS: Daftar Produk/Input Manual → Detail Pesanan (charge/discount, total) → tombol BAYAR → konfirmasi pembayaran → struk. QRIS tetap manual.
- Login dengan 4 role: admin, kasir, manajer, tenan. Tenan mendapat portal read-only berisi data Tenan-nya sendiri.
- Hak akses per fitur per role dapat diubah admin lewat menu Hak Akses; nama kasir otomatis mengikuti akun yang login.
- Tenan Sukabakmi dengan 18 produk sesuai daftar harga yang diberikan (Suka Chili Oil, Suka Laksa, dll.).
- Retur ke Tenan
- Retur konsumen
- Stok titipan
- Settlement + laporan ringkasan & drill-down
- Web admin + mobile input (mode online)

### Ditunda

- Barcode / scanner
- Multi-cabang
- Offline sync mobile
- Ekspor PDF/Excel
- Notifikasi expired otomatis

---

## 5. Aturan bisnis

### 5.1 Model B — default

```
Komisi per unit       = sesuai Kesepakatan (persen × harga jual, atau nominal tetap)
Hutang per unit       = harga_jual - komisi_per_unit
Yang dibayar ke Tenan = Total Penjualan - Total Komisi + Koreksi
```

### 5.2 Model A — opsi per Tenan

```
Margin toko           = harga_jual - harga_acuan_tenan
Hutang per unit       = harga_jual - margin = harga_acuan_tenan
Yang dibayar ke Tenan = Total Penjualan - Margin + Koreksi
```

Model A memakai `harga_acuan_tenan_saat_jual` untuk menghitung margin. Komisi Kesepakatan tidak dipakai.

> Kedua model memakai **satu rumus**: `hutang per unit = harga_jual - komisi_per_unit`.
> Bedanya hanya isi `komisi_per_unit`: Model B = komisi, Model A = margin.

### 5.3 Komisi Model B

- `persen` → komisi per unit = `nilai_komisi% × harga_jual_saat_jual`
- `tetap` → komisi per unit = `nilai_komisi` (rupiah per pcs)
- Hasilnya disimpan sebagai `komisi_per_unit_saat_jual`

### 5.4 Snapshot harga

Setiap item penjualan menyimpan:

- `harga_jual_saat_jual`
- `harga_acuan_tenan_saat_jual` (dipakai Model A)
- `model_saat_jual`
- `tipe_komisi_saat_jual`
- `komisi_per_unit_saat_jual` (komisi di Model B, margin di Model A)
- `hutang_per_unit_saat_jual` = `harga_jual - komisi_per_unit`

Tujuan: perubahan harga atau kesepakatan hari ini tidak mengubah laporan lama.

### 5.5 Retur

| Kondisi | Stok | Uang |
|---|---|---|
| Retur ke Tenan, tak laku | Keluar | Tidak ada hutang, karena belum terjual |
| Retur konsumen, masih bisa dijual | Masuk stok titipan | Penjualan, hutang, komisi dikoreksi |
| Retur konsumen, tidak bisa dijual | Keluar ke Tenan | Penjualan, hutang, komisi dikoreksi |

Retur setelah settlement **tidak mengubah settlement lama**; koreksi masuk periode berjalan.

### 5.6 Periode settlement

Periode settlement = rentang transaksi yang direkap dan ditagihkan ke Tenan.

- **Default: mingguan** (Senin–Minggu, dibayar Senin berikutnya)
- **Opsi: bulanan** (1–akhir bulan, dibayar tanggal 5 berikutnya)
- Diatur per Tenan lewat Kesepakatan

Periode settlement **berbeda** dengan tanggal jatuh tempo:

| Istilah | Arti |
|---|---|
| Periode | Rentang transaksi yang dihitung |
| Jatuh tempo | Tanggal pembayaran setelah rekap disetujui |

Contoh:
```
Periode   : 1 – 7 Desember 2026
Dibuat    : 8 Desember 2026
Dibayar   : 8 Desember 2026 (Senin)
```

---

## 6. Alur kerja

### Penerimaan

```
Pilih Tenan → input kode/nama barang → qty → (opsional expired) → Simpan
→ Mutasi TERIMA (+qty)
```

### Penjualan

```
Pilih Tenan → cari barang → qty → sistem ambil harga jual aktif
→ hitung komisi sesuai Kesepakatan → Simpan
→ Mutasi JUAL (-qty), hutang & komisi terbentuk
```

### Retur konsumen

```
Pilih penjualan → pilih barang → qty → kondisi: bisa dijual / tidak
→ bisa dijual: stok +qty
→ tidak bisa: stok -qty, buat Retur Tenan
→ koreksi hutang & komisi
```

### Settlement

```
Pilih Tenan + periode → rekap otomatis → DRAFT → DISETUJUI → DIBAYAR
```

---

## 7. Model data ringkas

| Entitas | Field penting |
|---|---|
| **Tenan** | `kode_prefix` (unik, bisa diedit lewat popup), nama, kontak, rekening, aktif — perubahan prefix ikut memperbarui kode barang Tenan tersebut |
| **KesepakatanTenan** | `tenan_id`, `model (B/A)`, `tipe_komisi`, `nilai_komisi`, `periode_settlement (mingguan/bulanan)`, `cutoff`, `jatuh_tempo`, `berlaku_dari`, aktif |
| **BarangTitipan** | `tenan_id`, `kode`, nama, `harga_acuan_tenan`, expired, aktif — unik `(tenan_id, kode)` |
| **Penerimaan** | `tenan_id`, tanggal, nomor |
| **PenerimaanItem** | `barang_id`, qty, expired, `harga_acuan_saat_terima` |
| **Penjualan** | tanggal, nomor, kasir |
| **PenjualanItem** | `barang_id`, qty, snapshot harga + komisi + hutang per unit |
| **ReturTenan** | `tenan_id`, tanggal, alasan, item(qty, expired) |
| **ReturKonsumen** | `penjualan_id`, tanggal, kondisi, item(qty, snapshot asal) |
| **MutasiTitipan** | `barang_id`, `jenis`, qty ±, `ref_type`, `ref_id` — append-only |
| **Settlement** | `tenan_id`, `periode_awal`, `periode_akhir`, `tanggal_jatuh_tempo`, total penjualan, komisi, koreksi, bayar, status |
| **SettlementItem** | `barang_id`, qty, penjualan, komisi, koreksi, netto |

---

## 8. Layar

### Web admin

- Dashboard: stok titipan per Tenan, hutang belum dibayar, expired mendekat
- Tenan & Kesepakatan
- BarangTitipan
- Penerimaan
- Settlement & Laporan

### Mobile

- Pilih Tenan → cari kode/nama → qty → Jual
- Retur konsumen
- Retur ke Tenan
- Lihat stok titipan

---

## 9. Format laporan settlement

### Ringkasan per Tenan

```
Tenan        : Sari Dagang
Periode      : 1 – 7 Desember 2026 (mingguan)
Model        : B — Komisi 20%
Penjualan    : Rp 450.000
Komisi       : Rp  90.000
Koreksi      : Rp  (15.000)
Dibayar      : Rp 345.000
Status       : DRAFT
```

### Drill-down per barang

```
Kode    Nama        Qty  Harga   Komisi/unit  Penjualan  Komisi  Netto
SD-001  Kopi A      30   15.000  3.000        450.000    90.000  360.000
```

---

## 10. Contoh perhitungan

| Tenan | Model | Transaksi | Dibayar ke Tenan | Pendapatan toko |
|---|---|---|---:|---:|
| Sari Dagang | B, 20% | 30 × Rp 15.000 | Rp 360.000 | Rp 90.000 |
| Mitra Niaga | B, tetap Rp 2.000 | 10 × Rp 12.000 | Rp 100.000 | Rp 20.000 |
| Bumi Jaya | A, acuan Rp 9.000 | 10 × Rp 12.000 | Rp 90.000 | Rp 30.000 margin |

---

## 11. Roadmap

1. **Fase 1**: alur inti + settlement (dokumen ini)
2. **Fase 2**: offline sync mobile + multi-cabang
3. **Fase 3**: barcode, notifikasi expired, ekspor laporan

---

## 12. Riwayat keputusan

- Retur konsumen tidak bisa dijual → langsung diretunkan ke Tenan: **setuju**
- Mobile Fase 1 online-only, offline sync ditunda: **setuju**
- Periode settlement: **default mingguan, opsi bulanan per Tenan**
