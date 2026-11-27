-- Skema SQLite untuk uji coba web.
-- Mirip dengan schema.sql (PostgreSQL); beda hanya tipe data & UUID.
-- Produksi tetap memakai schema.sql.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lokasi (
  id    INTEGER PRIMARY KEY,
  nama  TEXT NOT NULL
);

INSERT OR IGNORE INTO lokasi (id, nama) VALUES (1, 'Toko Utama');

CREATE TABLE IF NOT EXISTS tenan (
  id          TEXT PRIMARY KEY,
  kode_prefix TEXT NOT NULL UNIQUE,
  nama        TEXT NOT NULL,
  kontak      TEXT,
  rekening    TEXT,
  aktif       INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  nama          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin','kasir','manajer','tenan')),
  tenan_id      TEXT REFERENCES tenan(id),
  aktif         INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role       TEXT NOT NULL CHECK (role IN ('admin','kasir','manajer','tenan')),
  permission TEXT NOT NULL,
  allowed    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (role, permission)
);

-- Penanda migrasi agar perbaikan hak akses tidak diulang setiap start.
CREATE TABLE IF NOT EXISTS migrasi (
  nama          TEXT PRIMARY KEY,
  dijalankan_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kesepakatan_tenan (
  id                 TEXT PRIMARY KEY,
  tenan_id           TEXT NOT NULL REFERENCES tenan(id),
  model              TEXT NOT NULL DEFAULT 'B' CHECK (model IN ('B','A')),
  tipe_komisi        TEXT NOT NULL DEFAULT 'persen' CHECK (tipe_komisi IN ('persen','tetap')),
  nilai_komisi       REAL NOT NULL DEFAULT 0 CHECK (nilai_komisi >= 0),
  periode_settlement TEXT NOT NULL DEFAULT 'mingguan'
                       CHECK (periode_settlement IN ('mingguan','bulanan')),
  cutoff             TEXT NOT NULL DEFAULT 'minggu',
  jatuh_tempo        TEXT NOT NULL DEFAULT 'senin',
  berlaku_dari       TEXT NOT NULL DEFAULT CURRENT_DATE,
  aktif              INTEGER NOT NULL DEFAULT 1,
  created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_kesepakatan_aktif
  ON kesepakatan_tenan(tenan_id) WHERE aktif = 1;

CREATE TABLE IF NOT EXISTS barang_titipan (
  id                TEXT PRIMARY KEY,
  tenan_id          TEXT NOT NULL REFERENCES tenan(id),
  kode              TEXT NOT NULL,
  nama              TEXT NOT NULL,
  harga_acuan_tenan INTEGER NOT NULL DEFAULT 0 CHECK (harga_acuan_tenan >= 0),
  harga_jual        INTEGER NOT NULL DEFAULT 0 CHECK (harga_jual >= 0),
  expired           TEXT,
  aktif             INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenan_id, kode)
);

CREATE TABLE IF NOT EXISTS stok_titipan (
  tenan_id   TEXT NOT NULL REFERENCES tenan(id),
  barang_id  TEXT NOT NULL REFERENCES barang_titipan(id),
  lokasi_id  INTEGER NOT NULL DEFAULT 1 REFERENCES lokasi(id),
  qty        INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tenan_id, barang_id, lokasi_id)
);

CREATE TABLE IF NOT EXISTS penerimaan (
  id           TEXT PRIMARY KEY,
  tenan_id     TEXT NOT NULL REFERENCES tenan(id),
  nomor        TEXT NOT NULL,
  tanggal      TEXT NOT NULL DEFAULT CURRENT_DATE,
  catatan      TEXT,
  status       TEXT NOT NULL DEFAULT 'DISETUJUI'
                 CHECK (status IN ('PENDING','DISETUJUI','DITOLAK')),
  created_by   TEXT REFERENCES users(id),
  validated_by TEXT REFERENCES users(id),
  validated_at TEXT,
  alasan_tolak TEXT,
  created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenan_id, nomor)
);

CREATE TABLE IF NOT EXISTS penerimaan_item (
  id                      TEXT PRIMARY KEY,
  penerimaan_id           TEXT NOT NULL REFERENCES penerimaan(id),
  barang_id               TEXT NOT NULL REFERENCES barang_titipan(id),
  qty                     INTEGER NOT NULL CHECK (qty > 0),
  expired                 TEXT,
  harga_acuan_saat_terima INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS penjualan (
  id              TEXT PRIMARY KEY,
  nomor           TEXT NOT NULL UNIQUE,
  tanggal         TEXT NOT NULL DEFAULT CURRENT_DATE,
  kasir           TEXT,
  total_penjualan INTEGER NOT NULL DEFAULT 0,
  total_komisi    INTEGER NOT NULL DEFAULT 0,
  metode_bayar    TEXT NOT NULL DEFAULT 'tunai'
                    CHECK (metode_bayar IN ('tunai','transfer','qris')),
  uang_diterima   INTEGER NOT NULL DEFAULT 0,
  kembalian       INTEGER NOT NULL DEFAULT 0,
  diskon          INTEGER NOT NULL DEFAULT 0,
  charge          INTEGER NOT NULL DEFAULT 0,
  total_akhir     INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS penjualan_item (
  id                          TEXT PRIMARY KEY,
  penjualan_id                TEXT NOT NULL REFERENCES penjualan(id),
  barang_id                   TEXT NOT NULL REFERENCES barang_titipan(id),
  qty                         INTEGER NOT NULL CHECK (qty > 0),
  harga_jual_saat_jual        INTEGER NOT NULL CHECK (harga_jual_saat_jual >= 0),
  harga_acuan_tenan_saat_jual INTEGER NOT NULL DEFAULT 0,
  model_saat_jual             TEXT NOT NULL CHECK (model_saat_jual IN ('B','A')),
  tipe_komisi_saat_jual       TEXT NOT NULL,
  komisi_per_unit_saat_jual   INTEGER NOT NULL DEFAULT 0,
  hutang_per_unit_saat_jual   INTEGER NOT NULL DEFAULT 0,
  subtotal_penjualan INTEGER GENERATED ALWAYS AS
    (qty * harga_jual_saat_jual) STORED,
  subtotal_komisi INTEGER GENERATED ALWAYS AS
    (qty * komisi_per_unit_saat_jual) STORED,
  subtotal_hutang INTEGER GENERATED ALWAYS AS
    (qty * hutang_per_unit_saat_jual) STORED,
  CHECK (komisi_per_unit_saat_jual <= harga_jual_saat_jual),
  CHECK (subtotal_hutang = subtotal_penjualan - subtotal_komisi)
);

CREATE TABLE IF NOT EXISTS retur_tenan (
  id         TEXT PRIMARY KEY,
  tenan_id   TEXT NOT NULL REFERENCES tenan(id),
  nomor      TEXT NOT NULL,
  tanggal    TEXT NOT NULL DEFAULT CURRENT_DATE,
  alasan     TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenan_id, nomor)
);

CREATE TABLE IF NOT EXISTS retur_tenan_item (
  id             TEXT PRIMARY KEY,
  retur_tenan_id TEXT NOT NULL REFERENCES retur_tenan(id),
  barang_id      TEXT NOT NULL REFERENCES barang_titipan(id),
  qty            INTEGER NOT NULL CHECK (qty > 0),
  expired        TEXT
);

CREATE TABLE IF NOT EXISTS retur_konsumen (
  id           TEXT PRIMARY KEY,
  penjualan_id TEXT NOT NULL REFERENCES penjualan(id),
  tanggal      TEXT NOT NULL DEFAULT CURRENT_DATE,
  alasan       TEXT,
  kondisi      TEXT NOT NULL CHECK (kondisi IN ('bisa_dijual','tidak_bisa_dijual')),
  created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS retur_konsumen_item (
  id                TEXT PRIMARY KEY,
  retur_konsumen_id TEXT NOT NULL REFERENCES retur_konsumen(id),
  penjualan_item_id TEXT NOT NULL REFERENCES penjualan_item(id),
  barang_id         TEXT NOT NULL REFERENCES barang_titipan(id),
  qty               INTEGER NOT NULL CHECK (qty > 0),
  koreksi_hutang    INTEGER NOT NULL DEFAULT 0 CHECK (koreksi_hutang <= 0),
  koreksi_komisi    INTEGER NOT NULL DEFAULT 0 CHECK (koreksi_komisi <= 0)
);

CREATE TABLE IF NOT EXISTS mutasi_titipan (
  id        TEXT PRIMARY KEY,
  tenan_id  TEXT NOT NULL REFERENCES tenan(id),
  barang_id TEXT NOT NULL REFERENCES barang_titipan(id),
  lokasi_id INTEGER NOT NULL DEFAULT 1 REFERENCES lokasi(id),
  jenis     TEXT NOT NULL CHECK (jenis IN
              ('TERIMA','JUAL','RETUR_TENAN','RETUR_KONSUMEN','KOREKSI')),
  qty       INTEGER NOT NULL CHECK (qty <> 0),
  ref_type  TEXT,
  ref_id    TEXT,
  tanggal   TEXT NOT NULL DEFAULT CURRENT_DATE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settlement (
  id                  TEXT PRIMARY KEY,
  tenan_id            TEXT NOT NULL REFERENCES tenan(id),
  periode_awal        TEXT NOT NULL,
  periode_akhir       TEXT NOT NULL,
  tanggal_jatuh_tempo TEXT NOT NULL,
  total_penjualan     INTEGER NOT NULL DEFAULT 0,
  total_komisi        INTEGER NOT NULL DEFAULT 0,
  total_koreksi       INTEGER NOT NULL DEFAULT 0,
  total_bayar         INTEGER NOT NULL DEFAULT 0,
  status              TEXT NOT NULL DEFAULT 'DRAFT'
                        CHECK (status IN ('DRAFT','DISETUJUI','DIBAYAR')),
  created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenan_id, periode_awal, periode_akhir),
  CHECK (periode_akhir >= periode_awal)
);

CREATE TABLE IF NOT EXISTS settlement_item (
  id            TEXT PRIMARY KEY,
  settlement_id TEXT NOT NULL REFERENCES settlement(id),
  barang_id     TEXT NOT NULL REFERENCES barang_titipan(id),
  qty_terjual   INTEGER NOT NULL DEFAULT 0,
  penjualan     INTEGER NOT NULL DEFAULT 0,
  komisi        INTEGER NOT NULL DEFAULT 0,
  koreksi       INTEGER NOT NULL DEFAULT 0,
  netto INTEGER GENERATED ALWAYS AS (penjualan - komisi + koreksi) STORED
);

-- Sinkronkan stok dari ledger mutasi.
-- Update dulu, baru insert jika baris belum ada dan qty positif.
-- (SQLite mengecek CHECK sebelum ON CONFLICT DO UPDATE, jadi UPSERT
--  tidak bisa dipakai untuk qty negatif.)
DROP TRIGGER IF EXISTS trg_sync_stok;
CREATE TRIGGER trg_sync_stok
AFTER INSERT ON mutasi_titipan
BEGIN
  UPDATE stok_titipan
     SET qty = qty + NEW.qty, updated_at = CURRENT_TIMESTAMP
   WHERE tenan_id = NEW.tenan_id
     AND barang_id = NEW.barang_id
     AND lokasi_id = NEW.lokasi_id;

  INSERT INTO stok_titipan (tenan_id, barang_id, lokasi_id, qty, updated_at)
  SELECT NEW.tenan_id, NEW.barang_id, NEW.lokasi_id, NEW.qty, CURRENT_TIMESTAMP
  WHERE NOT EXISTS (
    SELECT 1 FROM stok_titipan
    WHERE tenan_id = NEW.tenan_id
      AND barang_id = NEW.barang_id
      AND lokasi_id = NEW.lokasi_id
  )
  AND NEW.qty > 0;
END;

-- updated_at otomatis
CREATE TRIGGER IF NOT EXISTS trg_tenan_updated
AFTER UPDATE ON tenan BEGIN
  UPDATE tenan SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_kesepakatan_updated
AFTER UPDATE ON kesepakatan_tenan BEGIN
  UPDATE kesepakatan_tenan SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_barang_updated
AFTER UPDATE ON barang_titipan BEGIN
  UPDATE barang_titipan SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_settlement_updated
AFTER UPDATE ON settlement BEGIN
  UPDATE settlement SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE INDEX IF NOT EXISTS idx_barang_tenan_nama
  ON barang_titipan(tenan_id, nama);
CREATE INDEX IF NOT EXISTS idx_penjualan_tanggal
  ON penjualan(tanggal);
CREATE INDEX IF NOT EXISTS idx_penjualan_item_barang
  ON penjualan_item(barang_id);
CREATE INDEX IF NOT EXISTS idx_mutasi_barang_tanggal
  ON mutasi_titipan(barang_id, tanggal);
CREATE INDEX IF NOT EXISTS idx_settlement_tenan_periode
  ON settlement(tenan_id, periode_akhir);
CREATE INDEX IF NOT EXISTS idx_settlement_item_settlement
  ON settlement_item(settlement_id);
