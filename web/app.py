"""Aplikasi web konsinyasi 'Tenan' — versi uji coba dengan SQLite.

Versi produksi memakai PostgreSQL (schema.sql). Logika bisnis di file ini
sengaja dibuat tetap sama supaya mudah dipindah ke psycopg later.
"""

from __future__ import annotations

import calendar
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask, flash, g, jsonify, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "konsinyasi.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema_sqlite.sql")

app = Flask(__name__)
app.secret_key = os.environ.get("KONSINYASI_SECRET_KEY", "konsinyasi-dev-only")


# ------------------------------------------------------------------
# Autentikasi & kewenangan (dapat diatur admin lewat /hak-akses)
# ------------------------------------------------------------------

ROLES = ("admin", "kasir", "manajer", "tenan")

PERMISSIONS = [
    ("dashboard.view", "Dashboard — lihat"),
    ("tenan.view", "Tenan & Kesepakatan — lihat"),
    ("tenan.edit", "Tenan & Kesepakatan — ubah"),
    ("barang.view", "Barang titipan — lihat"),
    ("barang.edit", "Barang titipan — tambah/ubah"),
    ("penerimaan.view", "Penerimaan — lihat"),
    ("penerimaan.edit", "Penerimaan — catat"),
    ("penjualan.view", "Penjualan — lihat"),
    ("penjualan.edit", "Penjualan — input manual"),
    ("kasir.use", "Kasir & struk — pakai"),
    ("retur.view", "Retur — lihat"),
    ("retur.edit", "Retur konsumen — catat"),
    ("retur.edit_tenan", "Retur ke Tenan — catat"),
    ("settlement.view", "Settlement — lihat"),
    ("settlement.edit", "Settlement — buat / ubah status"),
    ("users.view", "User — lihat"),
    ("users.edit", "User — tambah / nonaktifkan"),
    ("permissions.view", "Hak akses — lihat"),
    ("permissions.edit", "Hak akses — ubah"),
]

# Hak yang tidak boleh dicabut dari admin agar admin tidak mengunci diri sendiri.
ADMIN_LOCKED = {"users.view", "users.edit", "permissions.view", "permissions.edit"}

# Dipakai halaman "akses ditolak" untuk mengarahkan user ke menu yang masih ia punya.
MENU_FALLBACK = [
    ("dashboard.view", "dashboard", "Dashboard"),
    ("kasir.use", "kasir", "Kasir"),
    ("penjualan.view", "penjualan", "Penjualan"),
    ("barang.view", "barang", "Barang Titipan"),
    ("retur.view", "retur", "Retur"),
    ("settlement.view", "settlement", "Settlement"),
    ("users.view", "users", "User"),
    ("permissions.view", "hak_akses", "Hak Akses"),
]

DEFAULT_ACCESS = {
    "admin": {key for key, _ in PERMISSIONS},
    "kasir": {
        "dashboard.view", "barang.view", "penjualan.view", "penjualan.edit",
        "kasir.use", "retur.view", "retur.edit",
    },
    "manajer": {
        "dashboard.view", "barang.view", "penjualan.view",
        "retur.view", "settlement.view", "settlement.edit",
    },
    "tenan": set(),
}


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ? AND aktif = 1", (user_id,)
    ).fetchone()


def can(permission: str, role: str | None = None) -> bool:
    if role is None:
        user = current_user()
        if not user:
            return False
        role = user["role"]
    row = get_db().execute(
        "SELECT allowed FROM role_permissions WHERE role = ? AND permission = ?",
        (role, permission),
    ).fetchone()
    if row is None:
        return permission in DEFAULT_ACCESS.get(role, set())
    return bool(row["allowed"])


def redirect_aman(user) -> str:
    """Tujuan redirect saat akses ditolak: menu pertama yang masih dimiliki user."""
    if user["role"] == "tenan":
        return url_for("portal")
    for key, endpoint, _ in MENU_FALLBACK:
        if can(key, user["role"]):
            return url_for(endpoint)
    return url_for("akses_ditolak")


@app.context_processor
def inject_user():
    return {"user": current_user(), "can": can}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login", next=request.path))
            if user["role"] not in roles:
                flash("Anda tidak memiliki kewenangan untuk halaman ini.", "err")
                return redirect(redirect_aman(user))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login", next=request.path))
            if not can(permission):
                flash("Anda tidak memiliki kewenangan untuk halaman ini.", "err")
                # Jangan redirect ke / (dashboard): bisa memicu loop jika
                # dashboard.view yang dicabut. Pilih menu pertama yang masih aktif.
                return redirect(redirect_aman(user))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def uid() -> str:
    return str(uuid.uuid4())


def short_no(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def today() -> str:
    return date.today().isoformat()


def rupiah(value) -> str:
    return f"{int(value or 0):,}".replace(",", ".")


app.jinja_env.filters["rupiah"] = rupiah


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND aktif = 1", (username,)
        ).fetchone()
        if user and check_password_hash(
            user["password_hash"], request.form.get("password", "")
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["nama"] = user["nama"]
            nxt = request.form.get("next") or request.args.get("next")
            if nxt and nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(
                url_for("portal" if user["role"] == "tenan" else "dashboard")
            )
        flash("Username atau password salah.", "err")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout")
def logout():
    session.clear()
    flash("Anda sudah logout.", "ok")
    return redirect(url_for("login"))


@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    if request.method == "POST":
        baru = request.form.get("password_baru", "")
        if len(baru) < 4:
            flash("Password minimal 4 karakter.", "err")
        else:
            db = get_db()
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(baru), session["user_id"]),
            )
            db.commit()
            flash("Password berhasil diperbarui.", "ok")
        return redirect(url_for("profil"))
    return render_template("profil.html", user=current_user())


@app.route("/akses-ditolak")
@login_required
def akses_ditolak():
    user = current_user()
    if user["role"] == "tenan":
        menu = [("portal", "Portal Tenan")]
    else:
        menu = [
            (endpoint, label)
            for key, endpoint, label in MENU_FALLBACK
            if can(key, user["role"])
        ]
    return render_template("akses_ditolak.html", menu=menu)


@app.route("/users", methods=["GET", "POST"])
@permission_required("users.view")
def users():
    db = get_db()
    if request.method == "POST":
        if not can("users.edit"):
            flash("Anda tidak memiliki kewenangan untuk mengubah user.", "err")
            return redirect(url_for("users"))
        if request.form.get("aksi") == "toggle":
            db.execute(
                """UPDATE users
                   SET aktif = CASE WHEN aktif = 1 THEN 0 ELSE 1 END
                   WHERE id = ? AND id <> ?""",
                (request.form["user_id"], session["user_id"]),
            )
            db.commit()
            flash("Status user diperbarui.", "ok")
            return redirect(url_for("users"))

        role = request.form["role"]
        tenan_id = request.form.get("tenan_id") or None
        if role == "tenan" and not tenan_id:
            flash("User dengan role tenan wajib memilih Tenan.", "err")
        else:
            try:
                db.execute(
                    """INSERT INTO users
                       (id, username, password_hash, nama, role, tenan_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (uid(), request.form["username"].strip(),
                     generate_password_hash(request.form["password"]),
                     request.form["nama"].strip(), role, tenan_id),
                )
                db.commit()
                flash("User berhasil dibuat.", "ok")
            except sqlite3.IntegrityError:
                db.rollback()
                flash("Username sudah dipakai.", "err")
        return redirect(url_for("users"))

    rows = db.execute(
        """SELECT u.*, t.nama AS tenan
           FROM users u LEFT JOIN tenan t ON t.id = u.tenan_id
           ORDER BY u.role, u.username"""
    ).fetchall()
    tenans = db.execute("SELECT * FROM tenan WHERE aktif = 1 ORDER BY nama").fetchall()
    return render_template("users.html", rows=rows, tenans=tenans)


@app.route("/hak-akses", methods=["GET", "POST"])
@permission_required("permissions.view")
def hak_akses():
    db = get_db()
    if request.method == "POST":
        if not can("permissions.edit"):
            flash("Anda tidak memiliki kewenangan untuk mengubah hak akses.", "err")
            return redirect(url_for("hak_akses"))
        for role in ROLES:
            for key, _ in PERMISSIONS:
                allowed = 1 if request.form.get(f"{role}|{key}") else 0
                if role == "admin" and key in ADMIN_LOCKED:
                    allowed = 1
                db.execute(
                    """INSERT INTO role_permissions (role, permission, allowed)
                       VALUES (?, ?, ?)
                       ON CONFLICT(role, permission) DO UPDATE SET allowed = excluded.allowed""",
                    (role, key, allowed),
                )
        db.commit()
        flash("Hak akses diperbarui.", "ok")
        return redirect(url_for("hak_akses"))

    rows = db.execute("SELECT * FROM role_permissions").fetchall()
    matrix = {(r["role"], r["permission"]): bool(r["allowed"]) for r in rows}
    return render_template(
        "hak_akses.html",
        permissions=PERMISSIONS,
        roles=ROLES,
        matrix=matrix,
        locked=ADMIN_LOCKED,
    )


@app.route("/portal")
@role_required("tenan")
def portal():
    """Portal read-only khusus Tenan: hanya data miliknya sendiri."""
    db = get_db()
    tenan_id = current_user()["tenan_id"]
    if not tenan_id:
        flash("User tenan belum terhubung ke data Tenan.", "err")
        return redirect(url_for("logout"))

    stok = db.execute(
        """SELECT b.kode, b.nama AS barang, s.qty
           FROM stok_titipan s
           JOIN barang_titipan b ON b.id = s.barang_id
           WHERE s.tenan_id = ? AND s.qty > 0
           ORDER BY b.kode""",
        (tenan_id,),
    ).fetchall()
    penjualan = db.execute(
        """SELECT p.nomor, p.tanggal, b.kode, b.nama AS barang,
                  pi.qty, pi.harga_jual_saat_jual,
                  pi.subtotal_penjualan, pi.subtotal_komisi, pi.subtotal_hutang
           FROM penjualan_item pi
           JOIN penjualan p ON p.id = pi.penjualan_id
           JOIN barang_titipan b ON b.id = pi.barang_id
           WHERE b.tenan_id = ?
           ORDER BY p.tanggal DESC LIMIT 30""",
        (tenan_id,),
    ).fetchall()
    settlement = db.execute(
        """SELECT * FROM settlement
           WHERE tenan_id = ? ORDER BY periode_akhir DESC""",
        (tenan_id,),
    ).fetchall()

    total_hutang = db.execute(
        """SELECT COALESCE(SUM(pi.subtotal_hutang), 0)
           FROM penjualan_item pi
           JOIN barang_titipan b ON b.id = pi.barang_id
           WHERE b.tenan_id = ?""",
        (tenan_id,),
    ).fetchone()[0]
    total_koreksi = db.execute(
        """SELECT COALESCE(SUM(rki.koreksi_hutang), 0)
           FROM retur_konsumen_item rki
           JOIN barang_titipan b ON b.id = rki.barang_id
           WHERE b.tenan_id = ?""",
        (tenan_id,),
    ).fetchone()[0]
    dibayar = db.execute(
        """SELECT COALESCE(SUM(total_bayar), 0)
           FROM settlement
           WHERE tenan_id = ? AND status = 'DIBAYAR'""",
        (tenan_id,),
    ).fetchone()[0]

    return render_template(
        "portal.html",
        stok=stok,
        penjualan=penjualan,
        settlement=settlement,
        total_hutang=total_hutang,
        total_koreksi=total_koreksi,
        dibayar=dibayar,
        sisa=total_hutang + total_koreksi - dibayar,
    )


# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(reset: bool = False) -> None:
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        db.executescript(fh.read())

    # Migrasi ringan: database lama belum punya kolom diskon/charge.
    kolom = {r["name"] for r in db.execute("PRAGMA table_info(penjualan)")}
    for nama, ddl in [
        ("diskon", "INTEGER NOT NULL DEFAULT 0"),
        ("charge", "INTEGER NOT NULL DEFAULT 0"),
        ("total_akhir", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if nama not in kolom:
            db.execute(f"ALTER TABLE penjualan ADD COLUMN {nama} {ddl}")
    db.execute(
        "UPDATE penjualan SET total_akhir = total_penjualan WHERE total_akhir = 0"
    )

    seed_permissions(db)
    seed_data(db)
    db.commit()
    db.close()


# ------------------------------------------------------------------
# Logika bisnis
# ------------------------------------------------------------------

def kesepakatan_aktif(db, tenan_id: str):
    return db.execute(
        """SELECT * FROM kesepakatan_tenan
           WHERE tenan_id = ? AND aktif = 1
           ORDER BY berlaku_dari DESC LIMIT 1""",
        (tenan_id,),
    ).fetchone()


def hitung_komisi(ks, harga_jual: int, harga_acuan: int):
    """Kembalikan (komisi_per_unit, tipe_yang_disimpan).

    Model B: komisi sesuai kesepakatan.
    Model A: komisi = margin = harga jual - harga acuan.
    """
    if ks is None:
        raise ValueError("Tenan belum punya Kesepakatan aktif")
    if ks["model"] == "A":
        return int(harga_jual - harga_acuan), "tetap"
    if ks["tipe_komisi"] == "persen":
        return int(round(harga_jual * float(ks["nilai_komisi"]) / 100)), "persen"
    return int(ks["nilai_komisi"]), "tetap"


def tambah_mutasi(db, barang, jenis: str, qty: int, ref_type: str, ref_id: str, tanggal: str):
    db.execute(
        """INSERT INTO mutasi_titipan
           (id, tenan_id, barang_id, lokasi_id, jenis, qty, ref_type, ref_id, tanggal)
           VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""",
        (uid(), barang["tenan_id"], barang["id"], jenis, qty, ref_type, ref_id, tanggal),
    )


def catat_penerimaan(db, tenan_id, nomor, tanggal, items, catatan=""):
    pid = uid()
    db.execute(
        "INSERT INTO penerimaan (id, tenan_id, nomor, tanggal, catatan) VALUES (?, ?, ?, ?, ?)",
        (pid, tenan_id, nomor, tanggal, catatan),
    )
    for item in items:
        barang = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (item["barang_id"],)).fetchone()
        if not barang or barang["tenan_id"] != tenan_id:
            raise ValueError("Barang tidak cocok dengan Tenan yang dipilih")
        qty = int(item["qty"])
        if qty <= 0:
            raise ValueError("Jumlah harus lebih dari 0")
        db.execute(
            """INSERT INTO penerimaan_item
               (id, penerimaan_id, barang_id, qty, expired, harga_acuan_saat_terima)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (uid(), pid, barang["id"], qty, item.get("expired") or None, barang["harga_acuan_tenan"]),
        )
        tambah_mutasi(db, barang, "TERIMA", qty, "penerimaan", pid, tanggal)
    return pid


def catat_penjualan(db, nomor, tanggal, kasir, items, metode="tunai",
                    uang_diterima=0, diskon=0, charge=0):
    if not items:
        raise ValueError("Minimal satu barang harus diisi")
    metode = metode if metode in ("tunai", "transfer", "qris") else "tunai"
    uang = int(uang_diterima or 0)
    diskon = int(diskon or 0)
    charge = int(charge or 0)
    if diskon < 0 or charge < 0:
        raise ValueError("Diskon dan biaya tambahan tidak boleh negatif")
    penjualan_id = uid()
    db.execute(
        """INSERT INTO penjualan
           (id, nomor, tanggal, kasir, metode_bayar, uang_diterima, diskon, charge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (penjualan_id, nomor, tanggal, kasir or "", metode, uang, diskon, charge),
    )
    total_jual = 0
    total_komisi = 0
    for item in items:
        barang = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (item["barang_id"],)).fetchone()
        if not barang:
            raise ValueError("Barang tidak ditemukan")
        qty = int(item["qty"])
        harga = int(item["harga_jual"])
        if qty <= 0 or harga < 0:
            raise ValueError("Jumlah dan harga tidak valid")

        stok = db.execute(
            """SELECT COALESCE(SUM(qty), 0) AS qty FROM stok_titipan
               WHERE tenan_id = ? AND barang_id = ?""",
            (barang["tenan_id"], barang["id"]),
        ).fetchone()["qty"]
        if qty > stok:
            raise ValueError(f"Stok {barang['kode']} hanya {stok}")

        ks = kesepakatan_aktif(db, barang["tenan_id"])
        komisi, tipe = hitung_komisi(ks, harga, barang["harga_acuan_tenan"])
        hutang = harga - komisi

        db.execute(
            """INSERT INTO penjualan_item
               (id, penjualan_id, barang_id, qty, harga_jual_saat_jual,
                harga_acuan_tenan_saat_jual, model_saat_jual,
                tipe_komisi_saat_jual, komisi_per_unit_saat_jual,
                hutang_per_unit_saat_jual)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (uid(), penjualan_id, barang["id"], qty, harga,
             barang["harga_acuan_tenan"], ks["model"], tipe, komisi, hutang),
        )
        tambah_mutasi(db, barang, "JUAL", -qty, "penjualan", penjualan_id, tanggal)
        total_jual += qty * harga
        total_komisi += qty * komisi

    if diskon > total_jual:
        raise ValueError("Diskon tidak boleh lebih besar dari subtotal")
    total_akhir = total_jual + charge - diskon
    kembalian = max(0, uang - total_akhir) if metode == "tunai" else 0
    db.execute(
        """UPDATE penjualan
           SET total_penjualan = ?, total_komisi = ?, uang_diterima = ?, kembalian = ?,
               diskon = ?, charge = ?, total_akhir = ?
           WHERE id = ?""",
        (total_jual, total_komisi, uang, kembalian,
         diskon, charge, total_akhir, penjualan_id),
    )
    return penjualan_id


def catat_retur_konsumen(db, penjualan_item_id, qty, kondisi, alasan, tanggal):
    pi = db.execute(
        """SELECT pi.*, p.tanggal AS tanggal_jual, b.tenan_id
           FROM penjualan_item pi
           JOIN penjualan p ON p.id = pi.penjualan_id
           JOIN barang_titipan b ON b.id = pi.barang_id
           WHERE pi.id = ?""",
        (penjualan_item_id,),
    ).fetchone()
    if not pi:
        raise ValueError("Item penjualan tidak ditemukan")
    qty = int(qty)
    if qty <= 0 or qty > pi["qty"]:
        raise ValueError(f"Jumlah retur harus antara 1 dan {pi['qty']}")

    koreksi_hutang = -qty * pi["hutang_per_unit_saat_jual"]
    koreksi_komisi = -qty * pi["komisi_per_unit_saat_jual"]

    rid = uid()
    db.execute(
        """INSERT INTO retur_konsumen
           (id, penjualan_id, tanggal, alasan, kondisi)
           VALUES (?, ?, ?, ?, ?)""",
        (rid, pi["penjualan_id"], tanggal, alasan or "", kondisi),
    )
    db.execute(
        """INSERT INTO retur_konsumen_item
           (id, retur_konsumen_id, penjualan_item_id, barang_id, qty,
            koreksi_hutang, koreksi_komisi)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (uid(), rid, pi["id"], pi["barang_id"], qty, koreksi_hutang, koreksi_komisi),
    )

    barang = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (pi["barang_id"],)).fetchone()
    if kondisi == "bisa_dijual":
        tambah_mutasi(db, barang, "RETUR_KONSUMEN", qty, "retur_konsumen", rid, tanggal)
    else:
        tambah_mutasi(db, barang, "RETUR_TENAN", -qty, "retur_konsumen", rid, tanggal)
    return rid


def catat_retur_tenan(db, barang_id, qty, tanggal, alasan):
    barang = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (barang_id,)).fetchone()
    if not barang:
        raise ValueError("Barang tidak ditemukan")
    qty = int(qty)
    if qty <= 0:
        raise ValueError("Jumlah harus lebih dari 0")
    rid = uid()
    db.execute(
        """INSERT INTO retur_tenan (id, tenan_id, nomor, tanggal, alasan)
           VALUES (?, ?, ?, ?, ?)""",
        (rid, barang["tenan_id"], short_no("RT"), tanggal, alasan or ""),
    )
    db.execute(
        """INSERT INTO retur_tenan_item (id, retur_tenan_id, barang_id, qty, expired)
           VALUES (?, ?, ?, ?, ?)""",
        (uid(), rid, barang_id, qty, barang["expired"]),
    )
    tambah_mutasi(db, barang, "RETUR_TENAN", -qty, "retur_tenan", rid, tanggal)
    return rid


def tanggal_jatuh_tempo(ks, periode_akhir: str) -> str:
    akhir = date.fromisoformat(periode_akhir)
    if ks and ks["periode_settlement"] == "mingguan":
        return (akhir + timedelta(days=1)).isoformat()
    try:
        hari = int(ks["jatuh_tempo"]) if ks else 5
    except (TypeError, ValueError):
        hari = 5
    tahun, bulan = (akhir.year + 1, 1) if akhir.month == 12 else (akhir.year, akhir.month + 1)
    hari = min(hari, calendar.monthrange(tahun, bulan)[1])
    return date(tahun, bulan, hari).isoformat()


def buat_settlement(db, tenan_id, awal, akhir):
    ks = kesepakatan_aktif(db, tenan_id)
    if not ks:
        raise ValueError("Tenan belum punya Kesepakatan aktif")

    penjualan = db.execute(
        """SELECT pi.barang_id,
                  SUM(pi.qty) AS qty,
                  SUM(pi.subtotal_penjualan) AS penjualan,
                  SUM(pi.subtotal_komisi) AS komisi
           FROM penjualan_item pi
           JOIN penjualan p ON p.id = pi.penjualan_id
           JOIN barang_titipan b ON b.id = pi.barang_id
           WHERE b.tenan_id = ? AND p.tanggal BETWEEN ? AND ?
           GROUP BY pi.barang_id""",
        (tenan_id, awal, akhir),
    ).fetchall()
    if not penjualan:
        raise ValueError("Tidak ada penjualan pada periode ini")

    koreksi = {
        row["barang_id"]: row["koreksi"]
        for row in db.execute(
            """SELECT rki.barang_id, SUM(rki.koreksi_hutang) AS koreksi
               FROM retur_konsumen_item rki
               JOIN retur_konsumen r ON r.id = rki.retur_konsumen_id
               JOIN barang_titipan b ON b.id = rki.barang_id
               WHERE b.tenan_id = ? AND r.tanggal BETWEEN ? AND ?
               GROUP BY rki.barang_id""",
            (tenan_id, awal, akhir),
        ).fetchall()
    }

    sid = uid()
    total_penjualan = total_komisi = total_koreksi = total_bayar = 0
    detail = []
    for row in penjualan:
        kor = int(koreksi.get(row["barang_id"], 0))
        netto = row["penjualan"] - row["komisi"] + kor
        detail.append((row, kor))
        total_penjualan += row["penjualan"]
        total_komisi += row["komisi"]
        total_koreksi += kor
        total_bayar += netto

    # Header dulu, baru item agar foreign key terpenuhi
    db.execute(
        """INSERT INTO settlement
           (id, tenan_id, periode_awal, periode_akhir, tanggal_jatuh_tempo,
            total_penjualan, total_komisi, total_koreksi, total_bayar)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sid, tenan_id, awal, akhir, tanggal_jatuh_tempo(ks, akhir),
         total_penjualan, total_komisi, total_koreksi, total_bayar),
    )
    for row, kor in detail:
        db.execute(
            """INSERT INTO settlement_item
               (id, settlement_id, barang_id, qty_terjual, penjualan, komisi, koreksi)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid(), sid, row["barang_id"], row["qty"], row["penjualan"], row["komisi"], kor),
        )
    return sid


# ------------------------------------------------------------------
# Data contoh
# ------------------------------------------------------------------

def seed_permissions(db):
    for role in ROLES:
        for key, _ in PERMISSIONS:
            allowed = 1 if key in DEFAULT_ACCESS[role] else 0
            if role == "admin" and key in ADMIN_LOCKED:
                allowed = 1
            db.execute(
                """INSERT OR IGNORE INTO role_permissions (role, permission, allowed)
                   VALUES (?, ?, ?)""",
                (role, key, allowed),
            )


def seed_data(db):
    if db.execute("SELECT COUNT(*) FROM tenan").fetchone()[0] > 0:
        return

    tenans = [
        ("SD", "Sari Dagang", "0812-1111", "BCA 123456"),
        ("MN", "Mitra Niaga", "0813-2222", "Mandiri 654321"),
        ("BJ", "Bumi Jaya", "0814-3333", "BNI 111222"),
        ("SBK", "Sukabakmi", "0815-4444", "BCA 888999"),
    ]
    for kode, nama, kontak, rekening in tenans:
        db.execute(
            "INSERT INTO tenan (id, kode_prefix, nama, kontak, rekening) VALUES (?, ?, ?, ?, ?)",
            (uid(), kode, nama, kontak, rekening),
        )

    by_kode = {r["kode_prefix"]: r["id"] for r in db.execute("SELECT * FROM tenan")}
    kesepakatans = [
        (by_kode["SD"], "B", "persen", 20, "mingguan", "minggu", "senin"),
        (by_kode["MN"], "B", "tetap", 2000, "bulanan", "akhir_bulan", "5"),
        (by_kode["BJ"], "A", "tetap", 0, "mingguan", "minggu", "senin"),
        (by_kode["SBK"], "B", "persen", 20, "mingguan", "minggu", "senin"),
    ]
    for tenan_id, model, tipe, nilai, periode, cutoff, tempo in kesepakatans:
        db.execute(
            """INSERT INTO kesepakatan_tenan
               (id, tenan_id, model, tipe_komisi, nilai_komisi,
                periode_settlement, cutoff, jatuh_tempo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (uid(), tenan_id, model, tipe, nilai, periode, cutoff, tempo),
        )

    # Barang lama dipertahankan sebagai data uji Model A/B, tapi disembunyikan
    # dari daftar menu (aktif = 0). Menu yang tampil adalah produk Sukabakmi.
    barangs = [
        (by_kode["SD"], "SD-001", "Kopi A", 10000, 15000, 0),
        (by_kode["SD"], "SD-002", "Kopi B", 12000, 18000, 0),
        (by_kode["MN"], "MN-001", "Teh B", 8000, 12000, 0),
        (by_kode["BJ"], "BJ-001", "Gula C", 9000, 12000, 0),
    ]
    produk_sbk = [
        ("SBK-001", "Suka Chili Oil", 22000),
        ("SBK-002", "Suka Laksa", 25000),
        ("SBK-003", "Suka Maka", 25000),
        ("SBK-004", "Suka Original Jamur/Rebus", 19000),
        ("SBK-005", "Bakso Rebus", 19000),
        ("SBK-006", "Pangsit Rebus (2 pcs)", 5000),
        ("SBK-007", "Bakso Goreng", 7000),
        ("SBK-008", "Lumpia Kulit Tahu Ayam", 20000),
        ("SBK-009", "Lumpia Kulit Tahu Udang", 20000),
        ("SBK-010", "Siomay Ayam", 20000),
        ("SBK-011", "Siomay Noki", 20000),
        ("SBK-012", "Siomay Udang", 20000),
        ("SBK-013", "Siomay Cumi", 20000),
        ("SBK-014", "Siomay Kepiting", 20000),
        ("SBK-015", "Hakau", 20000),
        ("SBK-016", "Hlaitkau", 20000),
        ("SBK-017", "Ajk Minekar", 5000),
        ("SBK-018", "Liang Tea", 10000),
    ]
    for kode, nama, jual in produk_sbk:
        acuan = int(round(jual * 0.6 / 500) * 500)
        barangs.append((by_kode["SBK"], kode, nama, acuan, jual, 1))

    for tenan_id, kode, nama, acuan, jual, aktif in barangs:
        db.execute(
            """INSERT INTO barang_titipan
               (id, tenan_id, kode, nama, harga_acuan_tenan, harga_jual, aktif)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid(), tenan_id, kode, nama, acuan, jual, aktif),
        )

    by_barang = {r["kode"]: r for r in db.execute("SELECT * FROM barang_titipan")}
    penerimaan_seed = [("SD", "SD-001", 100), ("SD", "SD-002", 50),
                       ("MN", "MN-001", 80), ("BJ", "BJ-001", 60)]
    for kode, _, _ in produk_sbk:
        penerimaan_seed.append(("SBK", kode, 30))
    nomor_by_tenan = {}
    for tenan_kode, barang_kode, qty in penerimaan_seed:
        tenan_id = by_kode[tenan_kode]
        nomor_by_tenan[tenan_kode] = nomor_by_tenan.get(tenan_kode, 0) + 1
        catat_penerimaan(
            db, tenan_id,
            f"TER-{tenan_kode}-{nomor_by_tenan[tenan_kode]:03d}",
            today(),
            [{"barang_id": by_barang[barang_kode]["id"], "qty": qty}],
            "Data contoh",
        )

    catat_penjualan(
        db, "JUAL-CONTO-001", today(), "Admin Contoh",
        [
            {"barang_id": by_barang["SD-001"]["id"], "qty": 30, "harga_jual": 15000},
            {"barang_id": by_barang["BJ-001"]["id"], "qty": 10, "harga_jual": 12000},
        ],
    )

    users_contoh = [
        ("admin", "admin123", "Administrator", "admin", None),
        ("kasir", "kasir123", "Kasir Toko", "kasir", None),
        ("manajer", "manajer123", "Manajer", "manajer", None),
        ("tenan1", "tenan123", "Sukabakmi", "tenan", by_kode["SBK"]),
        ("tenan2", "tenan123", "Sari Dagang", "tenan", by_kode["SD"]),
    ]
    for username, password, nama, role, tenan_id in users_contoh:
        db.execute(
            """INSERT INTO users
               (id, username, password_hash, nama, role, tenan_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (uid(), username, generate_password_hash(password), nama, role, tenan_id),
        )


# ------------------------------------------------------------------
# Route
# ------------------------------------------------------------------

@app.route("/")
@permission_required("dashboard.view")
def dashboard():
    db = get_db()
    hutang = db.execute(
        """WITH hutang_transaksi AS (
             SELECT b.tenan_id, SUM(pi.subtotal_hutang) AS hutang
             FROM penjualan_item pi
             JOIN barang_titipan b ON b.id = pi.barang_id
             GROUP BY b.tenan_id
           ),
           koreksi_retur AS (
             SELECT b.tenan_id, SUM(rki.koreksi_hutang) AS koreksi
             FROM retur_konsumen_item rki
             JOIN barang_titipan b ON b.id = rki.barang_id
             GROUP BY b.tenan_id
           ),
           dibayar AS (
             SELECT tenan_id, SUM(total_bayar) AS dibayar
             FROM settlement WHERE status = 'DIBAYAR'
             GROUP BY tenan_id
           )
           SELECT t.nama AS tenan,
                  COALESCE(h.hutang, 0) AS total_hutang,
                  COALESCE(k.koreksi, 0) AS total_koreksi,
                  COALESCE(d.dibayar, 0) AS sudah_dibayar,
                  COALESCE(h.hutang, 0) + COALESCE(k.koreksi, 0)
                    - COALESCE(d.dibayar, 0) AS sisa_hutang
           FROM tenan t
           LEFT JOIN hutang_transaksi h ON h.tenan_id = t.id
           LEFT JOIN koreksi_retur k ON k.tenan_id = t.id
           LEFT JOIN dibayar d ON d.tenan_id = t.id
           ORDER BY t.nama"""
    ).fetchall()
    jatuh_tempo = (
        date.today() + timedelta(days=7)
    ).isoformat()
    settlement_dekat = db.execute(
        """SELECT s.*, t.nama AS tenan FROM settlement s
           JOIN tenan t ON t.id = s.tenan_id
           WHERE s.status <> 'DIBAYAR' AND s.tanggal_jatuh_tempo <= ?
           ORDER BY s.tanggal_jatuh_tempo""",
        (jatuh_tempo,),
    ).fetchall()
    penjualan_terakhir = db.execute(
        "SELECT * FROM penjualan ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    # Grafik pendapatan 7 hari terakhir (termasuk hari tanpa transaksi).
    awal_grafik = (date.today() - timedelta(days=6)).isoformat()
    per_hari = db.execute(
        """SELECT tanggal,
                  COALESCE(SUM(total_akhir), 0) AS penjualan,
                  COALESCE(SUM(total_komisi), 0) AS pendapatan
           FROM penjualan
           WHERE tanggal >= ?
           GROUP BY tanggal
           ORDER BY tanggal""",
        (awal_grafik,),
    ).fetchall()
    peta = {r["tanggal"]: r for r in per_hari}
    grafik = []
    for i in range(6, -1, -1):
        tanggal = (date.today() - timedelta(days=i)).isoformat()
        r = peta.get(tanggal)
        grafik.append(
            {
                "tanggal": tanggal,
                "penjualan": r["penjualan"] if r else 0,
                "pendapatan": r["pendapatan"] if r else 0,
            }
        )
    grafik_maks = max(
        [r["penjualan"] for r in grafik] + [r["pendapatan"] for r in grafik] + [1]
    )

    return render_template(
        "dashboard.html",
        hutang=hutang,
        settlement_dekat=settlement_dekat,
        penjualan_terakhir=penjualan_terakhir,
        grafik=grafik,
        grafik_maks=grafik_maks,
    )


@app.route("/tenan", methods=["GET", "POST"])
@permission_required("tenan.view")
def tenan():
    db = get_db()
    if request.method == "POST":
        if not can("tenan.edit"):
            flash("Anda tidak memiliki kewenangan untuk mengubah Tenan.", "err")
            return redirect(url_for("tenan"))
        try:
            db.execute(
                "INSERT INTO tenan (id, kode_prefix, nama, kontak, rekening) VALUES (?, ?, ?, ?, ?)",
                (uid(), request.form["kode_prefix"].strip().upper(),
                 request.form["nama"].strip(), request.form.get("kontak", ""),
                 request.form.get("rekening", "")),
            )
            db.commit()
            flash("Tenan berhasil ditambahkan", "ok")
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Kode prefix sudah dipakai", "err")
        return redirect(url_for("tenan"))

    rows = db.execute(
        """SELECT t.*, k.model, k.tipe_komisi, k.nilai_komisi,
                  k.periode_settlement, k.jatuh_tempo
           FROM tenan t
           LEFT JOIN kesepakatan_tenan k
             ON k.tenan_id = t.id AND k.aktif = 1
           ORDER BY t.nama"""
    ).fetchall()
    return render_template("tenan.html", rows=rows)


@app.route("/tenan/<tid>/edit", methods=["POST"])
@permission_required("tenan.edit")
def tenan_edit(tid):
    """Simpan perubahan dari popup Edit pada daftar Tenan."""
    db = get_db()
    row = db.execute("SELECT * FROM tenan WHERE id = ?", (tid,)).fetchone()
    if not row:
        flash("Tenan tidak ditemukan.", "err")
        return redirect(url_for("tenan"))

    kode = request.form.get("kode_prefix", "").strip().upper()
    nama = request.form.get("nama", "").strip()
    model = request.form.get("model", "B")
    tipe = request.form.get("tipe_komisi", "persen")
    periode = request.form.get("periode_settlement", "mingguan")
    tempo = request.form.get("jatuh_tempo", "senin").strip() or "senin"

    if not kode or not nama:
        flash("Kode dan nama Tenan wajib diisi.", "err")
        return redirect(url_for("tenan"))
    if model not in ("A", "B") or tipe not in ("persen", "tetap") \
            or periode not in ("mingguan", "bulanan"):
        flash("Model, bentuk komisi, atau periode tidak valid.", "err")
        return redirect(url_for("tenan"))
    try:
        nilai = float(request.form.get("nilai_komisi") or 0)
        if nilai < 0:
            raise ValueError("negatif")
    except ValueError:
        flash("Nilai komisi harus berupa angka.", "err")
        return redirect(url_for("tenan"))

    try:
        bentrok = db.execute(
            "SELECT id FROM tenan WHERE kode_prefix = ? AND id <> ?", (kode, tid)
        ).fetchone()
        if bentrok:
            raise sqlite3.IntegrityError("Kode prefix sudah dipakai Tenan lain")

        # Jika prefix berubah, sesuaikan kode barang Tenan ini agar tetap konsisten.
        ubah_barang = []
        if kode != row["kode_prefix"]:
            awalan = row["kode_prefix"] + "-"
            for b in db.execute(
                "SELECT id, kode FROM barang_titipan WHERE tenan_id = ?", (tid,)
            ).fetchall():
                if not b["kode"].startswith(awalan):
                    continue
                kode_baru = kode + b["kode"][len(awalan) - 1:]
                ada = db.execute(
                    """SELECT id FROM barang_titipan
                       WHERE tenan_id = ? AND kode = ? AND id <> ?""",
                    (tid, kode_baru, b["id"]),
                ).fetchone()
                if ada:
                    raise sqlite3.IntegrityError(
                        f"Kode barang {kode_baru} sudah dipakai"
                    )
                ubah_barang.append((kode_baru, b["id"]))

        db.execute(
            """UPDATE tenan
                  SET kode_prefix = ?, nama = ?, kontak = ?,
                      updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
            (kode, nama, request.form.get("kontak", "").strip(), tid),
        )
        for kode_baru, bid in ubah_barang:
            db.execute(
                "UPDATE barang_titipan SET kode = ? WHERE id = ?", (kode_baru, bid)
            )

        kes = db.execute(
            """SELECT id FROM kesepakatan_tenan
               WHERE tenan_id = ? AND aktif = 1""",
            (tid,),
        ).fetchone()
        if kes:
            db.execute(
                """UPDATE kesepakatan_tenan
                      SET model = ?, tipe_komisi = ?, nilai_komisi = ?,
                          periode_settlement = ?, jatuh_tempo = ?,
                          updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                (model, tipe, nilai, periode, tempo, kes["id"]),
            )
        else:
            db.execute(
                """INSERT INTO kesepakatan_tenan
                   (id, tenan_id, model, tipe_komisi, nilai_komisi,
                    periode_settlement, cutoff, jatuh_tempo, berlaku_dari)
                   VALUES (?, ?, ?, ?, ?, ?, 'minggu', ?, CURRENT_DATE)""",
                (uid(), tid, model, tipe, nilai, periode, tempo),
            )

        db.commit()
        flash("Data Tenan berhasil diperbarui.", "ok")
    except sqlite3.IntegrityError as exc:
        db.rollback()
        flash(f"Gagal memperbarui Tenan: {exc}", "err")
    return redirect(url_for("tenan"))


@app.route("/kesepakatan", methods=["POST"])
@permission_required("tenan.edit")
def kesepakatan():
    db = get_db()
    tenan_id = request.form["tenan_id"]
    db.execute(
        "UPDATE kesepakatan_tenan SET aktif = 0 WHERE tenan_id = ? AND aktif = 1",
        (tenan_id,),
    )
    db.execute(
        """INSERT INTO kesepakatan_tenan
           (id, tenan_id, model, tipe_komisi, nilai_komisi,
            periode_settlement, cutoff, jatuh_tempo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (uid(), tenan_id, request.form["model"], request.form["tipe_komisi"],
         float(request.form.get("nilai_komisi") or 0),
         request.form["periode_settlement"],
         request.form.get("cutoff") or "minggu",
         request.form.get("jatuh_tempo") or "senin"),
    )
    db.commit()
    flash("Kesepakatan diperbarui", "ok")
    return redirect(url_for("tenan"))


@app.route("/barang", methods=["GET", "POST"])
@permission_required("barang.view")
def barang():
    db = get_db()
    if request.method == "POST":
        if not can("barang.edit"):
            flash("Anda tidak memiliki kewenangan untuk menambah barang.", "err")
            return redirect(url_for("barang"))
        try:
            db.execute(
                """INSERT INTO barang_titipan
                   (id, tenan_id, kode, nama, harga_acuan_tenan, harga_jual, expired)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (uid(), request.form["tenan_id"], request.form["kode"].strip().upper(),
                 request.form["nama"].strip(), int(request.form.get("harga_acuan") or 0),
                 int(request.form.get("harga_jual") or 0),
                 request.form.get("expired") or None),
            )
            db.commit()
            flash("Barang ditambahkan", "ok")
        except (sqlite3.IntegrityError, ValueError):
            db.rollback()
            flash("Gagal menambah barang (kode duplikat?)", "err")
        return redirect(url_for("barang"))

    rows = db.execute(
        """SELECT b.*, t.nama AS tenan, COALESCE(s.qty, 0) AS stok
           FROM barang_titipan b
           JOIN tenan t ON t.id = b.tenan_id
           LEFT JOIN stok_titipan s
             ON s.barang_id = b.id AND s.tenan_id = b.tenan_id
           WHERE b.aktif = 1 ORDER BY t.nama, b.kode"""
    ).fetchall()
    tenans = db.execute("SELECT * FROM tenan WHERE aktif = 1 ORDER BY nama").fetchall()
    return render_template("barang.html", rows=rows, tenans=tenans)


@app.route("/barang/<bid>/edit", methods=["GET", "POST"])
@permission_required("barang.edit")
def barang_edit(bid):
    db = get_db()
    row = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (bid,)).fetchone()
    if not row:
        flash("Barang tidak ditemukan.", "err")
        return redirect(url_for("barang"))

    if request.method == "POST":
        try:
            db.execute(
                """UPDATE barang_titipan
                      SET kode = ?, nama = ?, harga_acuan_tenan = ?, harga_jual = ?,
                          expired = ?, aktif = ?
                    WHERE id = ?""",
                (
                    request.form["kode"].strip().upper(),
                    request.form["nama"].strip(),
                    int(request.form.get("harga_acuan") or 0),
                    int(request.form.get("harga_jual") or 0),
                    request.form.get("expired") or None,
                    1 if request.form.get("aktif") else 0,
                    bid,
                ),
            )
            db.commit()
            flash("Barang berhasil diperbarui.", "ok")
            return redirect(url_for("barang"))
        except (sqlite3.IntegrityError, ValueError) as exc:
            db.rollback()
            flash(f"Gagal memperbarui barang: {exc}", "err")

    tenan = db.execute(
        "SELECT nama FROM tenan WHERE id = ?", (row["tenan_id"],)
    ).fetchone()
    return render_template("barang_edit.html", r=row, tenan=tenan["nama"])


@app.route("/penerimaan", methods=["GET", "POST"])
@permission_required("penerimaan.view")
def penerimaan():
    db = get_db()
    if request.method == "POST":
        if not can("penerimaan.edit"):
            flash("Anda tidak memiliki kewenangan untuk mencatat penerimaan.", "err")
            return redirect(url_for("penerimaan"))
        try:
            catat_penerimaan(
                db,
                request.form["tenan_id"],
                request.form["nomor"].strip(),
                request.form.get("tanggal") or today(),
                [{"barang_id": request.form["barang_id"],
                  "qty": request.form["qty"],
                  "expired": request.form.get("expired")}],
                request.form.get("catatan", ""),
            )
            db.commit()
            flash("Penerimaan titipan dicatat", "ok")
        except (ValueError, sqlite3.IntegrityError) as exc:
            db.rollback()
            flash(f"Gagal: {exc}", "err")
        return redirect(url_for("penerimaan"))

    rows = db.execute(
        """SELECT p.*, t.nama AS tenan,
                  COUNT(pi.id) AS jumlah_item, SUM(pi.qty) AS total_qty
           FROM penerimaan p
           JOIN tenan t ON t.id = p.tenan_id
           LEFT JOIN penerimaan_item pi ON pi.penerimaan_id = p.id
           GROUP BY p.id ORDER BY p.tanggal DESC"""
    ).fetchall()
    tenans = db.execute("SELECT * FROM tenan WHERE aktif = 1 ORDER BY nama").fetchall()
    barangs = db.execute(
        """SELECT b.*, t.nama AS tenan FROM barang_titipan b
           JOIN tenan t ON t.id = b.tenan_id
           WHERE b.aktif = 1 ORDER BY t.nama, b.kode"""
    ).fetchall()
    return render_template("penerimaan.html", rows=rows, tenans=tenans, barangs=barangs, today=today())


@app.route("/penjualan", methods=["GET", "POST"])
@permission_required("penjualan.view")
def penjualan():
    db = get_db()
    if request.method == "POST":
        if not can("penjualan.edit"):
            flash("Anda tidak memiliki kewenangan untuk input penjualan.", "err")
            return redirect(url_for("penjualan"))
        items = []
        for i in range(1, 4):
            barang_id = request.form.get(f"barang_{i}")
            qty = request.form.get(f"qty_{i}")
            harga = request.form.get(f"harga_{i}")
            if barang_id and qty and harga:
                items.append({"barang_id": barang_id, "qty": qty, "harga_jual": harga})
        try:
            catat_penjualan(
                db,
                request.form["nomor"].strip(),
                request.form.get("tanggal") or today(),
                current_user()["nama"],
                items,
                metode=request.form.get("metode_bayar", "tunai"),
                uang_diterima=request.form.get("uang_diterima", 0),
            )
            db.commit()
            flash("Penjualan dicatat", "ok")
        except (ValueError, sqlite3.IntegrityError) as exc:
            db.rollback()
            flash(f"Gagal: {exc}", "err")
        return redirect(url_for("penjualan"))

    rows = db.execute("SELECT * FROM penjualan ORDER BY tanggal DESC, created_at DESC").fetchall()
    barangs = db.execute(
        """SELECT b.*, t.nama AS tenan, COALESCE(s.qty, 0) AS stok
           FROM barang_titipan b
           JOIN tenan t ON t.id = b.tenan_id
           LEFT JOIN stok_titipan s
             ON s.barang_id = b.id AND s.tenan_id = b.tenan_id
           WHERE b.aktif = 1 ORDER BY t.nama, b.kode"""
    ).fetchall()
    return render_template(
        "penjualan.html", rows=rows, barangs=barangs, today=today(),
        nama_kasir=current_user()["nama"],
    )


@app.route("/kasir", methods=["GET", "POST"])
@permission_required("kasir.use")
def kasir():
    """Layar kasir web: keranjang di browser, submit sekali ke server."""
    db = get_db()
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        items = payload.get("items") or []
        metode = payload.get("metode_bayar", "tunai")
        uang = payload.get("uang_diterima", 0)
        diskon = payload.get("diskon", 0)
        charge = payload.get("charge", 0)
        nama_kasir = current_user()["nama"]
        try:
            nomor = (
                "KAS-" + datetime.now().strftime("%Y%m%d") + "-"
                + uuid.uuid4().hex[:5].upper()
            )
            sid = catat_penjualan(
                db, nomor, today(), nama_kasir, items,
                metode=metode, uang_diterima=uang,
                diskon=diskon, charge=charge,
            )
            db.commit()
            return jsonify({"ok": True, "id": sid, "nomor": nomor})
        except (ValueError, sqlite3.IntegrityError, TypeError) as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    barangs = db.execute(
        """SELECT b.*, t.nama AS tenan, COALESCE(s.qty, 0) AS stok
           FROM barang_titipan b
           JOIN tenan t ON t.id = b.tenan_id
           LEFT JOIN stok_titipan s
             ON s.barang_id = b.id AND s.tenan_id = b.tenan_id
           WHERE b.aktif = 1
           ORDER BY t.nama, b.kode"""
    ).fetchall()
    return render_template(
        "kasir.html",
        barangs=barangs,
        barangs_json=json.dumps([dict(r) for r in barangs]),
        today=today(),
        nama_kasir=current_user()["nama"],
    )


@app.route("/struk/<sid>")
@permission_required("kasir.use")
def struk(sid):
    db = get_db()
    penjualan = db.execute("SELECT * FROM penjualan WHERE id = ?", (sid,)).fetchone()
    if not penjualan:
        flash("Transaksi tidak ditemukan", "err")
        return redirect(url_for("kasir"))
    items = db.execute(
        """SELECT pi.*, b.kode, b.nama AS barang, t.nama AS tenan
           FROM penjualan_item pi
           JOIN barang_titipan b ON b.id = pi.barang_id
           JOIN tenan t ON t.id = b.tenan_id
           WHERE pi.penjualan_id = ?
           ORDER BY b.kode""",
        (sid,),
    ).fetchall()
    return render_template("struk.html", p=penjualan, items=items)


@app.route("/retur", methods=["GET", "POST"])
@permission_required("retur.view")
def retur():
    db = get_db()
    if request.method == "POST":
        jenis = request.form.get("jenis_form")
        if jenis == "konsumen" and not can("retur.edit"):
            flash("Anda tidak memiliki kewenangan untuk retur konsumen.", "err")
            return redirect(url_for("retur"))
        if jenis != "konsumen" and not can("retur.edit_tenan"):
            flash("Anda tidak memiliki kewenangan untuk retur ke Tenan.", "err")
            return redirect(url_for("retur"))
        try:
            if jenis == "konsumen":
                catat_retur_konsumen(
                    db,
                    request.form["penjualan_item_id"],
                    request.form["qty"],
                    request.form["kondisi"],
                    request.form.get("alasan", ""),
                    request.form.get("tanggal") or today(),
                )
                flash("Retur konsumen dicatat", "ok")
            else:
                catat_retur_tenan(
                    db,
                    request.form["barang_id"],
                    request.form["qty"],
                    request.form.get("tanggal") or today(),
                    request.form.get("alasan", ""),
                )
                flash("Retur ke Tenan dicatat", "ok")
            db.commit()
        except (ValueError, sqlite3.IntegrityError) as exc:
            db.rollback()
            flash(f"Gagal: {exc}", "err")
        return redirect(url_for("retur"))

    item_jual = db.execute(
        """SELECT pi.id, pi.qty, pi.harga_jual_saat_jual,
                  b.kode, b.nama AS barang, p.nomor AS nota, t.nama AS tenan
           FROM penjualan_item pi
           JOIN penjualan p ON p.id = pi.penjualan_id
           JOIN barang_titipan b ON b.id = pi.barang_id
           JOIN tenan t ON t.id = b.tenan_id
           ORDER BY p.tanggal DESC LIMIT 30"""
    ).fetchall()
    barangs = db.execute(
        """SELECT b.*, t.nama AS tenan, COALESCE(s.qty, 0) AS stok
           FROM barang_titipan b
           JOIN tenan t ON t.id = b.tenan_id
           LEFT JOIN stok_titipan s
             ON s.barang_id = b.id AND s.tenan_id = b.tenan_id
           WHERE b.aktif = 1 ORDER BY t.nama, b.kode"""
    ).fetchall()
    retur_tenan_rows = db.execute(
        """SELECT r.*, t.nama AS tenan, SUM(ri.qty) AS total_qty
           FROM retur_tenan r
           JOIN tenan t ON t.id = r.tenan_id
           JOIN retur_tenan_item ri ON ri.retur_tenan_id = r.id
           GROUP BY r.id ORDER BY r.tanggal DESC"""
    ).fetchall()
    retur_konsumen_rows = db.execute(
        """SELECT r.*, p.nomor AS nota, SUM(ri.qty) AS total_qty
           FROM retur_konsumen r
           JOIN penjualan p ON p.id = r.penjualan_id
           JOIN retur_konsumen_item ri ON ri.retur_konsumen_id = r.id
           GROUP BY r.id ORDER BY r.tanggal DESC"""
    ).fetchall()
    return render_template(
        "retur.html", item_jual=item_jual, barangs=barangs,
        retur_tenan_rows=retur_tenan_rows, retur_konsumen_rows=retur_konsumen_rows,
        today=today(),
    )


@app.route("/settlement", methods=["GET", "POST"])
@permission_required("settlement.view")
def settlement():
    db = get_db()
    if request.method == "POST":
        if not can("settlement.edit"):
            flash("Anda tidak memiliki kewenangan untuk mengubah settlement.", "err")
            return redirect(url_for("settlement"))
        try:
            sid = buat_settlement(
                db, request.form["tenan_id"],
                request.form["periode_awal"], request.form["periode_akhir"],
            )
            db.commit()
            flash("Settlement dibuat", "ok")
            return redirect(url_for("settlement_detail", sid=sid))
        except (ValueError, sqlite3.IntegrityError) as exc:
            db.rollback()
            flash(f"Gagal: {exc}", "err")
            return redirect(url_for("settlement"))

    rows = db.execute(
        """SELECT s.*, t.nama AS tenan, k.periode_settlement
           FROM settlement s
           JOIN tenan t ON t.id = s.tenan_id
           LEFT JOIN kesepakatan_tenan k
             ON k.tenan_id = s.tenan_id AND k.aktif = 1
           ORDER BY s.periode_akhir DESC"""
    ).fetchall()
    tenans = db.execute("SELECT * FROM tenan WHERE aktif = 1 ORDER BY nama").fetchall()
    awal = date.today() - timedelta(days=date.today().weekday())
    return render_template(
        "settlement.html", rows=rows, tenans=tenans,
        default_awal=awal.isoformat(), default_akhir=today(),
    )


@app.route("/settlement/<sid>")
@permission_required("settlement.view")
def settlement_detail(sid):
    db = get_db()
    head = db.execute(
        """SELECT s.*, t.nama AS tenan
           FROM settlement s JOIN tenan t ON t.id = s.tenan_id
           WHERE s.id = ?""",
        (sid,),
    ).fetchone()
    if not head:
        flash("Settlement tidak ditemukan", "err")
        return redirect(url_for("settlement"))
    items = db.execute(
        """SELECT si.*, b.kode, b.nama AS barang
           FROM settlement_item si
           JOIN barang_titipan b ON b.id = si.barang_id
           WHERE si.settlement_id = ? ORDER BY b.kode""",
        (sid,),
    ).fetchall()
    return render_template("settlement_detail.html", s=head, items=items)


@app.route("/settlement/<sid>/status", methods=["POST"])
@permission_required("settlement.edit")
def settlement_status(sid):
    db = get_db()
    target = request.form["status"]
    db.execute("UPDATE settlement SET status = ? WHERE id = ?", (target, sid))
    db.commit()
    flash(f"Status diperbarui menjadi {target}", "ok")
    return redirect(url_for("settlement_detail", sid=sid))


if __name__ == "__main__":
    import sys

    if "--init" in sys.argv:
        init_db(reset="--reset" in sys.argv)
        print(f"Database siap: {DB_PATH}")
    else:
        init_db()
        port = int(os.environ.get("PORT", "5000"))
        if os.environ.get("USE_WAITRESS") == "1":
            from waitress import serve
            serve(app, host="0.0.0.0", port=port)
        else:
            debug = os.environ.get("FLASK_DEBUG", "0") == "1"
            app.run(host="0.0.0.0", port=port, debug=debug)
