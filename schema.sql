-- ============================================================
-- Skema PostgreSQL — Aplikasi Manajemen Stok Konsinyasi "Tenan"
-- Fase 1
--
-- Cara jalankan:
--   psql -U postgres -d konsinyasi -f schema.sql
--
-- Aman dijalankan ulang (idempotent), kecuali enum yang sudah
-- dibuat dengan nama berbeda.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- Enum
-- ------------------------------------------------------------

DO $$ BEGIN
  CREATE TYPE model_hutang AS ENUM ('B', 'A');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE tipe_komisi AS ENUM ('persen', 'tetap');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE periode_settlement AS ENUM ('mingguan', 'bulanan');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE jenis_mutasi AS ENUM
    ('TERIMA', 'JUAL', 'RETUR_TENAN', 'RETUR_KONSUMEN', 'KOREKSI');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE status_settlement AS ENUM ('DRAFT', 'DISETUJUI', 'DIBAYAR');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE kondisi_retur AS ENUM ('bisa_dijual', 'tidak_bisa_dijual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('admin', 'kasir', 'manajer', 'tenan');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ------------------------------------------------------------
-- Master
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lokasi (
  id    SMALLINT PRIMARY KEY,
  nama  VARCHAR(100) NOT NULL
);

INSERT INTO lokasi (id, nama)
VALUES (1, 'Toko Utama')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tenan (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kode_prefix  VARCHAR(10) NOT NULL UNIQUE,
  nama         VARCHAR(150) NOT NULL,
  kontak       VARCHAR(100),
  rekening     VARCHAR(100),
  aktif        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username      VARCHAR(50) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  nama          VARCHAR(150) NOT NULL,
  role          user_role NOT NULL,
  tenan_id      UUID REFERENCES tenan(id),
  aktif         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role       user_role NOT NULL,
  permission TEXT NOT NULL,
  allowed    BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (role, permission)
);

CREATE TABLE IF NOT EXISTS kesepakatan_tenan (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id            UUID NOT NULL REFERENCES tenan(id),
  model               model_hutang NOT NULL DEFAULT 'B',
  tipe_komisi         tipe_komisi NOT NULL DEFAULT 'persen',
  nilai_komisi        NUMERIC(12,2) NOT NULL DEFAULT 0
                        CHECK (nilai_komisi >= 0),
  periode_settlement  periode_settlement NOT NULL DEFAULT 'mingguan',
  cutoff              VARCHAR(20) NOT NULL DEFAULT 'minggu',
  jatuh_tempo         VARCHAR(20) NOT NULL DEFAULT 'senin',
  berlaku_dari        DATE NOT NULL DEFAULT CURRENT_DATE,
  aktif               BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT cek_nilai_komisi
    CHECK (tipe_komisi = 'tetap' OR nilai_komisi <= 100)
);

-- Hanya satu Kesepakatan aktif per Tenan
CREATE UNIQUE INDEX IF NOT EXISTS uq_kesepakatan_aktif
  ON kesepakatan_tenan (tenan_id) WHERE aktif;

CREATE TABLE IF NOT EXISTS barang_titipan (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id            UUID NOT NULL REFERENCES tenan(id),
  kode                VARCHAR(50) NOT NULL,
  nama                VARCHAR(150) NOT NULL,
  harga_acuan_tenan   BIGINT NOT NULL DEFAULT 0 CHECK (harga_acuan_tenan >= 0),
  harga_jual          BIGINT NOT NULL DEFAULT 0 CHECK (harga_jual >= 0),
  expired             DATE,
  aktif               BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_barang_per_tenan UNIQUE (tenan_id, kode)
);

-- Stok turunan dari mutasi; dipakai untuk tampilan cepat
CREATE TABLE IF NOT EXISTS stok_titipan (
  tenan_id    UUID NOT NULL REFERENCES tenan(id),
  barang_id   UUID NOT NULL REFERENCES barang_titipan(id),
  lokasi_id   SMALLINT NOT NULL DEFAULT 1 REFERENCES lokasi(id),
  qty         INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (tenan_id, barang_id, lokasi_id)
);

-- ------------------------------------------------------------
-- Penerimaan titipan
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS penerimaan (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id     UUID NOT NULL REFERENCES tenan(id),
  nomor        VARCHAR(50) NOT NULL,
  tanggal      DATE NOT NULL DEFAULT CURRENT_DATE,
  catatan      TEXT,
  status       VARCHAR(20) NOT NULL DEFAULT 'DISETUJUI'
                 CHECK (status IN ('PENDING','DISETUJUI','DITOLAK')),
  created_by   UUID REFERENCES users(id),
  validated_by UUID REFERENCES users(id),
  validated_at TIMESTAMPTZ,
  alasan_tolak TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_penerimaan_per_tenan UNIQUE (tenan_id, nomor)
);

CREATE TABLE IF NOT EXISTS penerimaan_item (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  penerimaan_id             UUID NOT NULL REFERENCES penerimaan(id),
  barang_id                 UUID NOT NULL REFERENCES barang_titipan(id),
  qty                       INTEGER NOT NULL CHECK (qty > 0),
  expired                   DATE,
  harga_acuan_saat_terima   BIGINT NOT NULL DEFAULT 0
                              CHECK (harga_acuan_saat_terima >= 0),
  kode_usulan               VARCHAR(50),
  nama_usulan               VARCHAR(200)
);

-- ------------------------------------------------------------
-- Penjualan
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS penjualan (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nomor             VARCHAR(50) NOT NULL UNIQUE,
  tanggal           DATE NOT NULL DEFAULT CURRENT_DATE,
  kasir             VARCHAR(100),
  total_penjualan   BIGINT NOT NULL DEFAULT 0 CHECK (total_penjualan >= 0),
  total_komisi      BIGINT NOT NULL DEFAULT 0 CHECK (total_komisi >= 0),
  metode_bayar      TEXT NOT NULL DEFAULT 'tunai'
                      CHECK (metode_bayar IN ('tunai','transfer','qris')),
  uang_diterima     BIGINT NOT NULL DEFAULT 0 CHECK (uang_diterima >= 0),
  kembalian         BIGINT NOT NULL DEFAULT 0 CHECK (kembalian >= 0),
  diskon            BIGINT NOT NULL DEFAULT 0 CHECK (diskon >= 0),
  charge            BIGINT NOT NULL DEFAULT 0 CHECK (charge >= 0),
  total_akhir       BIGINT NOT NULL DEFAULT 0 CHECK (total_akhir >= 0),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS penjualan_item (
  id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  penjualan_id                    UUID NOT NULL REFERENCES penjualan(id),
  barang_id                       UUID NOT NULL REFERENCES barang_titipan(id),
  qty                             INTEGER NOT NULL CHECK (qty > 0),

  -- Snapshot saat transaksi
  harga_jual_saat_jual            BIGINT NOT NULL CHECK (harga_jual_saat_jual >= 0),
  harga_acuan_tenan_saat_jual     BIGINT NOT NULL DEFAULT 0
                                    CHECK (harga_acuan_tenan_saat_jual >= 0),
  model_saat_jual                 model_hutang NOT NULL,
  tipe_komisi_saat_jual           tipe_komisi NOT NULL,
  komisi_per_unit_saat_jual       BIGINT NOT NULL DEFAULT 0
                                    CHECK (komisi_per_unit_saat_jual >= 0),
  hutang_per_unit_saat_jual       BIGINT NOT NULL
                                    CHECK (hutang_per_unit_saat_jual >= 0),

  -- Kolom turunan
  subtotal_penjualan  BIGINT GENERATED ALWAYS AS
    (qty * harga_jual_saat_jual) STORED,
  subtotal_komisi     BIGINT GENERATED ALWAYS AS
    (qty * komisi_per_unit_saat_jual) STORED,
  subtotal_hutang     BIGINT GENERATED ALWAYS AS
    (qty * hutang_per_unit_saat_jual) STORED,

  CONSTRAINT cek_komisi_maksimal
    CHECK (komisi_per_unit_saat_jual <= harga_jual_saat_jual),
  CONSTRAINT cek_hutang_konsisten
    CHECK (subtotal_hutang = subtotal_penjualan - subtotal_komisi)
);

-- ------------------------------------------------------------
-- Retur ke Tenan (barang tak laku)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS retur_tenan (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id   UUID NOT NULL REFERENCES tenan(id),
  nomor      VARCHAR(50) NOT NULL,
  tanggal    DATE NOT NULL DEFAULT CURRENT_DATE,
  alasan     TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_retur_tenan UNIQUE (tenan_id, nomor)
);

CREATE TABLE IF NOT EXISTS retur_tenan_item (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retur_tenan_id UUID NOT NULL REFERENCES retur_tenan(id),
  barang_id      UUID NOT NULL REFERENCES barang_titipan(id),
  qty            INTEGER NOT NULL CHECK (qty > 0),
  expired        DATE
);

-- ------------------------------------------------------------
-- Retur konsumen (barang sudah terjual)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS retur_konsumen (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  penjualan_id  UUID NOT NULL REFERENCES penjualan(id),
  tanggal       DATE NOT NULL DEFAULT CURRENT_DATE,
  alasan        TEXT,
  kondisi       kondisi_retur NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retur_konsumen_item (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retur_konsumen_id  UUID NOT NULL REFERENCES retur_konsumen(id),
  penjualan_item_id  UUID NOT NULL REFERENCES penjualan_item(id),
  barang_id          UUID NOT NULL REFERENCES barang_titipan(id),
  qty                INTEGER NOT NULL CHECK (qty > 0),

  -- Koreksi selalu negatif
  koreksi_hutang     BIGINT NOT NULL DEFAULT 0 CHECK (koreksi_hutang <= 0),
  koreksi_komisi     BIGINT NOT NULL DEFAULT 0 CHECK (koreksi_komisi <= 0)
);

-- ------------------------------------------------------------
-- Ledger mutasi (append-only)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mutasi_titipan (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id    UUID NOT NULL REFERENCES tenan(id),
  barang_id   UUID NOT NULL REFERENCES barang_titipan(id),
  lokasi_id   SMALLINT NOT NULL DEFAULT 1 REFERENCES lokasi(id),
  jenis       jenis_mutasi NOT NULL,
  qty         INTEGER NOT NULL CHECK (qty <> 0),
  ref_type    VARCHAR(30),
  ref_id      UUID,
  tanggal     DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT cek_tanda_mutasi CHECK (
    (jenis = 'TERIMA'        AND qty > 0) OR
    (jenis = 'JUAL'          AND qty < 0) OR
    (jenis = 'RETUR_TENAN'   AND qty < 0) OR
    (jenis = 'RETUR_KONSUMEN' AND qty > 0) OR
    (jenis = 'KOREKSI'       AND qty <> 0)
  )
);

-- ------------------------------------------------------------
-- Settlement
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS settlement (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenan_id              UUID NOT NULL REFERENCES tenan(id),
  periode_awal          DATE NOT NULL,
  periode_akhir         DATE NOT NULL,
  tanggal_jatuh_tempo   DATE NOT NULL,

  total_penjualan       BIGINT NOT NULL DEFAULT 0 CHECK (total_penjualan >= 0),
  total_komisi          BIGINT NOT NULL DEFAULT 0 CHECK (total_komisi >= 0),
  total_koreksi         BIGINT NOT NULL DEFAULT 0 CHECK (total_koreksi <= 0),
  total_bayar           BIGINT NOT NULL DEFAULT 0 CHECK (total_bayar >= 0),

  status                status_settlement NOT NULL DEFAULT 'DRAFT',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT cek_periode CHECK (periode_akhir >= periode_awal),
  CONSTRAINT uq_settlement_periode
    UNIQUE (tenan_id, periode_awal, periode_akhir)
);

CREATE TABLE IF NOT EXISTS settlement_item (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  settlement_id  UUID NOT NULL REFERENCES settlement(id),
  barang_id      UUID NOT NULL REFERENCES barang_titipan(id),
  qty_terjual    INTEGER NOT NULL DEFAULT 0 CHECK (qty_terjual >= 0),
  penjualan      BIGINT NOT NULL DEFAULT 0,
  komisi         BIGINT NOT NULL DEFAULT 0,
  koreksi        BIGINT NOT NULL DEFAULT 0 CHECK (koreksi <= 0),
  netto          BIGINT GENERATED ALWAYS AS
    (penjualan - komisi + koreksi) STORED
);

-- ------------------------------------------------------------
-- Trigger: updated_at
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'tenan', 'kesepakatan_tenan', 'barang_titipan', 'settlement'
  ] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_set_updated_at ON %I', t);
    EXECUTE format(
      'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I
       FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t
    );
  END LOOP;
END $$;

-- ------------------------------------------------------------
-- Trigger: jaga stok_titipan tetap sinkron dengan mutasi
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION sync_stok_titipan()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO stok_titipan (tenan_id, barang_id, lokasi_id, qty, updated_at)
  VALUES (NEW.tenan_id, NEW.barang_id, NEW.lokasi_id, NEW.qty, now())
  ON CONFLICT (tenan_id, barang_id, lokasi_id)
  DO UPDATE SET
    qty = stok_titipan.qty + EXCLUDED.qty,
    updated_at = now();

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_stok ON mutasi_titipan;
CREATE TRIGGER trg_sync_stok
  AFTER INSERT ON mutasi_titipan
  FOR EACH ROW EXECUTE FUNCTION sync_stok_titipan();

-- ------------------------------------------------------------
-- Trigger: transisi status settlement hanya maju
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION guard_settlement_status()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT', 'DISETUJUI') THEN
    RAISE EXCEPTION 'Transisi status tidak valid: % -> %', OLD.status, NEW.status;
  END IF;

  IF OLD.status = 'DISETUJUI' AND NEW.status NOT IN ('DISETUJUI', 'DIBAYAR') THEN
    RAISE EXCEPTION 'Transisi status tidak valid: % -> %', OLD.status, NEW.status;
  END IF;

  IF OLD.status = 'DIBAYAR' AND NEW.status <> 'DIBAYAR' THEN
    RAISE EXCEPTION 'Settlement yang sudah dibayar tidak bisa diubah statusnya';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_guard_status ON settlement;
CREATE TRIGGER trg_guard_status
  BEFORE UPDATE ON settlement
  FOR EACH ROW EXECUTE FUNCTION guard_settlement_status();

-- ------------------------------------------------------------
-- Index
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_barang_tenan_nama
  ON barang_titipan (tenan_id, nama);

CREATE INDEX IF NOT EXISTS idx_penjualan_tanggal
  ON penjualan (tanggal);

CREATE INDEX IF NOT EXISTS idx_penjualan_item_barang
  ON penjualan_item (barang_id);

CREATE INDEX IF NOT EXISTS idx_mutasi_barang_tanggal
  ON mutasi_titipan (barang_id, tanggal);

CREATE INDEX IF NOT EXISTS idx_settlement_tenan_periode
  ON settlement (tenan_id, periode_akhir);

CREATE INDEX IF NOT EXISTS idx_settlement_item_settlement
  ON settlement_item (settlement_id);

-- ------------------------------------------------------------
-- View: sisa hutang per Tenan (untuk dashboard)
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW v_hutang_tenan AS
WITH hutang_transaksi AS (
  SELECT bt.tenan_id, SUM(pi.subtotal_hutang) AS hutang
  FROM penjualan_item pi
  JOIN barang_titipan bt ON bt.id = pi.barang_id
  GROUP BY bt.tenan_id
),
koreksi_retur AS (
  SELECT bt.tenan_id, SUM(rki.koreksi_hutang) AS koreksi
  FROM retur_konsumen_item rki
  JOIN barang_titipan bt ON bt.id = rki.barang_id
  GROUP BY bt.tenan_id
),
dibayar AS (
  SELECT s.tenan_id, SUM(s.total_bayar) AS dibayar
  FROM settlement s
  WHERE s.status = 'DIBAYAR'
  GROUP BY s.tenan_id
)
SELECT
  t.id AS tenan_id,
  t.nama AS tenan,
  COALESCE(h.hutang, 0) AS total_hutang,
  COALESCE(k.koreksi, 0) AS total_koreksi,
  COALESCE(d.dibayar, 0) AS sudah_dibayar,
  COALESCE(h.hutang, 0)
    + COALESCE(k.koreksi, 0)
    - COALESCE(d.dibayar, 0) AS sisa_hutang
FROM tenan t
LEFT JOIN hutang_transaksi h ON h.tenan_id = t.id
LEFT JOIN koreksi_retur k ON k.tenan_id = t.id
LEFT JOIN dibayar d ON d.tenan_id = t.id;

-- ============================================================
-- Selesai
-- ============================================================
