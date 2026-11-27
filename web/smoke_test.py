from datetime import date, timedelta

from app import DEFAULT_ACCESS, PERMISSIONS, ROLES, app, get_db

client = app.test_client()

# --- Login sebagai admin ---
res = client.post("/login", data={"username": "admin", "password": "admin123"})
print("POST login admin ->", res.status_code)
assert res.status_code == 302

pages = [
    "/", "/tenan", "/barang", "/penerimaan", "/penjualan",
    "/kasir", "/retur", "/settlement", "/users", "/hak-akses", "/profil",
]
for page in pages:
    res = client.get(page)
    print(f"GET {page:14} -> {res.status_code}")
    assert res.status_code == 200, page

with app.app_context():
    db = get_db()
    tenan = {r["kode_prefix"]: r for r in db.execute("SELECT * FROM tenan")}
    barang = {r["kode"]: r for r in db.execute("SELECT * FROM barang_titipan")}
    print("Tenan:", list(tenan))
    print("Barang:", list(barang))

# --- Edit nama barang ---
bid_edit = barang["SBK-001"]["id"]
res = client.get(f"/barang/{bid_edit}/edit")
print("GET edit barang ->", res.status_code)
assert res.status_code == 200
res = client.post(
    f"/barang/{bid_edit}/edit",
    data={
        "kode": "SBK-001",
        "nama": "Suka Chili Oil Original",
        "harga_acuan": "13000",
        "harga_jual": "22000",
        "expired": "",
        "aktif": "1",
    },
    follow_redirects=True,
)
print("POST edit barang ->", res.status_code)
assert res.status_code == 200
with app.app_context():
    db = get_db()
    diedit = db.execute("SELECT * FROM barang_titipan WHERE id = ?", (bid_edit,)).fetchone()
    assert diedit["nama"] == "Suka Chili Oil Original", diedit["nama"]
# Kembalikan nama semula
client.post(
    f"/barang/{bid_edit}/edit",
    data={
        "kode": "SBK-001", "nama": "Suka Chili Oil",
        "harga_acuan": "13000", "harga_jual": "22000",
        "expired": "", "aktif": "1",
    },
)

# --- Edit Tenan lewat popup pada daftar Tenan ---
tid_sd = tenan["SD"]["id"]
res = client.get("/tenan")
print("GET /tenan memuat popup edit ->", res.status_code)
assert res.status_code == 200
assert b"modal-edit-tenan" in res.data and b"bukaEditTenan" in res.data

with app.app_context():
    db = get_db()
    tsd = db.execute("SELECT * FROM tenan WHERE id = ?", (tid_sd,)).fetchone()
    ksd = db.execute(
        """SELECT * FROM kesepakatan_tenan
           WHERE tenan_id = ? AND aktif = 1""",
        (tid_sd,),
    ).fetchone()
    edit_lama = {
        "kode_prefix": tsd["kode_prefix"],
        "nama": tsd["nama"],
        "kontak": tsd["kontak"] or "",
        "model": ksd["model"] if ksd else "B",
        "tipe_komisi": ksd["tipe_komisi"] if ksd else "persen",
        "nilai_komisi": ksd["nilai_komisi"] if ksd else 0,
        "periode_settlement": ksd["periode_settlement"] if ksd else "mingguan",
        "jatuh_tempo": ksd["jatuh_tempo"] if ksd else "senin",
    }
edit_baru = {
    "kode_prefix": "SDX",
    "nama": "Sari Dagang (ubah)",
    "kontak": "0812-0000-0000",
    "model": "A",
    "tipe_komisi": "tetap",
    "nilai_komisi": "2500",
    "periode_settlement": "bulanan",
    "jatuh_tempo": "tanggal 5",
}
res = client.post(
    f"/tenan/{tid_sd}/edit", data=edit_baru, follow_redirects=True
)
print("POST edit Tenan lewat popup ->", res.status_code)
assert res.status_code == 200
with app.app_context():
    db = get_db()
    diedit = db.execute("SELECT * FROM tenan WHERE id = ?", (tid_sd,)).fetchone()
    kes = db.execute(
        "SELECT * FROM kesepakatan_tenan WHERE tenan_id = ? AND aktif = 1", (tid_sd,)
    ).fetchone()
    bg = db.execute(
        "SELECT kode FROM barang_titipan WHERE id = ?", (barang["SD-001"]["id"],)
    ).fetchone()
    print("Tenan setelah edit:", dict(diedit))
    print("Kesepakatan setelah edit:", dict(kes))
    assert diedit["kode_prefix"] == "SDX"
    assert diedit["nama"] == "Sari Dagang (ubah)"
    assert diedit["kontak"] == "0812-0000-0000"
    assert bg["kode"] == "SDX-001", bg["kode"]
    assert kes["model"] == "A" and kes["tipe_komisi"] == "tetap"
    assert kes["nilai_komisi"] == 2500
    assert kes["periode_settlement"] == "bulanan"
    assert kes["jatuh_tempo"] == "tanggal 5"
# Kembalikan data semula
client.post(f"/tenan/{tid_sd}/edit", data=edit_lama)

# --- Jual Model B, komisi tetap ---
res = client.post(
    "/penjualan",
    data={
        "nomor": "JUAL-SMOKE-001",
        "tanggal": date.today().isoformat(),
        "kasir": "Tester",
        "barang_1": barang["MN-001"]["id"],
        "qty_1": "5",
        "harga_1": "12000",
    },
    follow_redirects=True,
)
print("POST penjualan ->", res.status_code)
assert res.status_code == 200

with app.app_context():
    db = get_db()
    jual = db.execute("SELECT * FROM penjualan WHERE nomor='JUAL-SMOKE-001'").fetchone()
    print("Penjualan:", dict(jual))
    assert jual["total_penjualan"] == 60000
    assert jual["total_komisi"] == 10000
    pi = db.execute(
        "SELECT * FROM penjualan_item WHERE penjualan_id=?", (jual["id"],)
    ).fetchone()
    print("Item:", dict(pi))
    assert pi["hutang_per_unit_saat_jual"] == 10000

# --- Retur konsumen, masih bisa dijual ---
res = client.post(
    "/retur",
    data={
        "jenis_form": "konsumen",
        "penjualan_item_id": pi["id"],
        "qty": "2",
        "kondisi": "bisa_dijual",
        "alasan": "Salah kirim",
        "tanggal": date.today().isoformat(),
    },
    follow_redirects=True,
)
print("POST retur konsumen ->", res.status_code)
assert res.status_code == 200

with app.app_context():
    db = get_db()
    rki = db.execute("SELECT * FROM retur_konsumen_item").fetchone()
    print("Koreksi:", dict(rki))
    assert rki["koreksi_hutang"] == -20000
    assert rki["koreksi_komisi"] == -4000

# --- Settlement mingguan ---
awal = date.today() - timedelta(days=date.today().weekday())
res = client.post(
    "/settlement",
    data={
        "tenan_id": tenan["MN"]["id"],
        "periode_awal": awal.isoformat(),
        "periode_akhir": date.today().isoformat(),
    },
    follow_redirects=True,
)
print("POST settlement ->", res.status_code)
assert res.status_code == 200

with app.app_context():
    db = get_db()
    s = db.execute("SELECT * FROM settlement ORDER BY created_at DESC LIMIT 1").fetchone()
    print("Settlement:", dict(s))
    assert s["total_penjualan"] == 60000
    assert s["total_komisi"] == 10000
    assert s["total_koreksi"] == -20000
    assert s["total_bayar"] == 30000
    sid = s["id"]
    items = db.execute("SELECT * FROM settlement_item").fetchall()
    print("Settlement item:", [dict(i) for i in items])

res = client.get(f"/settlement/{sid}")
print("GET detail settlement ->", res.status_code)
assert res.status_code == 200

for status in ("DISETUJUI", "DIBAYAR"):
    res = client.post(f"/settlement/{sid}/status", data={"status": status})
    print(f"POST status {status} ->", res.status_code)
    assert res.status_code == 302

# --- Jual Model A (margin dari harga acuan) ---
res = client.post(
    "/penjualan",
    data={
        "nomor": "JUAL-SMOKE-002",
        "tanggal": date.today().isoformat(),
        "kasir": "Tester",
        "barang_1": barang["BJ-001"]["id"],
        "qty_1": "2",
        "harga_1": "12000",
    },
    follow_redirects=True,
)
print("POST penjualan Model A ->", res.status_code)
assert res.status_code == 200

with app.app_context():
    db = get_db()
    jual_a = db.execute(
        "SELECT * FROM penjualan WHERE nomor='JUAL-SMOKE-002'"
    ).fetchone()
    print("Penjualan Model A:", dict(jual_a))
    assert jual_a["total_penjualan"] == 24000
    assert jual_a["total_komisi"] == 6000
    item_a = db.execute(
        "SELECT * FROM penjualan_item WHERE penjualan_id=?", (jual_a["id"],)
    ).fetchone()
    assert item_a["model_saat_jual"] == "A"
    assert item_a["komisi_per_unit_saat_jual"] == 3000
    assert item_a["hutang_per_unit_saat_jual"] == 9000

# --- Kasir: tunai dengan kembalian ---
res = client.post(
    "/kasir",
    json={
        "items": [{"barang_id": barang["SBK-001"]["id"], "qty": 2, "harga_jual": 22000}],
        "kasir": "Nama yang Diabaikan",
        "metode_bayar": "tunai",
        "uang_diterima": 50000,
        "diskon": 2000,
        "charge": 3000,
    },
)
print("POST kasir ->", res.status_code)
data = res.get_json()
assert data and data["ok"], data
kid = data["id"]

res = client.get(f"/struk/{kid}")
print("GET struk ->", res.status_code)
assert res.status_code == 200

with app.app_context():
    db = get_db()
    k = db.execute("SELECT * FROM penjualan WHERE id = ?", (kid,)).fetchone()
    print("Kasir:", dict(k))
    assert k["total_penjualan"] == 44000
    assert k["diskon"] == 2000
    assert k["charge"] == 3000
    assert k["total_akhir"] == 45000
    assert k["uang_diterima"] == 50000
    assert k["kembalian"] == 5000
    assert k["metode_bayar"] == "tunai"
    assert k["kasir"] == "Administrator", k["kasir"]

res = client.get("/kasir")
print("GET /kasir alur baru ->", res.status_code)
assert res.status_code == 200
assert b"Daftar Produk" in res.data
assert b"Input Manual" in res.data
assert b"Detail Pesanan" in res.data
assert b"Kode QRIS" in res.data
assert b"Add Charge or Discount" in res.data

res = client.get("/")
print("GET dashboard akhir ->", res.status_code)
assert res.status_code == 200

# --- Uji kewenangan per role ---
anon = app.test_client()
res = anon.get("/")
print("GET / tanpa login ->", res.status_code)
assert res.status_code == 302 and "/login" in res.headers["Location"]

kasir = app.test_client()
res = kasir.post("/login", data={"username": "kasir", "password": "kasir123"})
assert res.status_code == 302
for page,expected in [("/kasir", 200), ("/penjualan", 200), ("/barang", 200),
                      ("/tenan", 302), ("/settlement", 302), ("/users", 302)]:
    res = kasir.get(page)
    print(f"kasir GET {page:14} -> {res.status_code}")
    assert res.status_code == expected, page
res = kasir.post(f"/tenan/{tid_sd}/edit", data=edit_baru)
print("kasir POST edit Tenan ->", res.status_code)
assert res.status_code == 302, "Kasir tidak boleh menyimpan edit Tenan"

manajer = app.test_client()
res = manajer.post("/login", data={"username": "manajer", "password": "manajer123"})
assert res.status_code == 302
for page,expected in [("/settlement", 200), ("/kasir", 302),
                      ("/tenan", 302), ("/users", 302)]:
    res = manajer.get(page)
    print(f"manajer GET {page:14} -> {res.status_code}")
    assert res.status_code == expected, page

tenan = app.test_client()
res = tenan.post("/login", data={"username": "tenan1", "password": "tenan123"})
print("login tenan ->", res.status_code, res.headers.get("Location"))
assert res.status_code == 302
res = tenan.get("/portal")
print("GET /portal ->", res.status_code)
assert res.status_code == 200
assert b"Sukabakmi" in res.data
assert b"Mitra Niaga" not in res.data, "Portal Tenan menampilkan data Tenan lain"
res = tenan.get("/")
print("tenan GET / ->", res.status_code)
assert res.status_code == 302

# --- Admin mengubah hak akses role kasir ---
def semua_hak():
    return {
        f"{role}|{key}": "1"
        for role in ROLES for key, _ in PERMISSIONS
        if key in DEFAULT_ACCESS[role]
    }

# Kasus yang dilaporkan: dashboard.view kasir dicabut, kasir.use tetap aktif.
hak = semua_hak()
hak.pop("kasir|dashboard.view")
res = client.post("/hak-akses", data=hak, follow_redirects=True)
print("POST hak akses (dashboard.view kasir dicabut) ->", res.status_code)
assert res.status_code == 200

kasir2 = app.test_client()
res = kasir2.post("/login", data={"username": "kasir", "password": "kasir123"})
assert res.status_code == 302
res = kasir2.get("/")
print("kasir GET / ->", res.status_code, res.headers.get("Location"))
assert res.status_code == 302
assert res.headers["Location"] == "/kasir", "Harusnya masuk ke Kasir, bukan loop ke /"
res = kasir2.get("/akses-ditolak")
print("kasir GET /akses-ditolak ->", res.status_code)
assert res.status_code == 200
assert b"Kasir" in res.data
assert kasir2.get("/kasir").status_code == 200
res = kasir2.get("/", follow_redirects=True)
print("kasir GET / follow redirect ->", res.status_code)
assert res.status_code == 200, "Masih ada redirect loop"

# Kasus kedua: kasir.use dicabut.
hak = semua_hak()
hak.pop("kasir|kasir.use")
res = client.post("/hak-akses", data=hak, follow_redirects=True)
assert res.status_code == 200
kasir2b = app.test_client()
kasir2b.post("/login", data={"username": "kasir", "password": "kasir123"})
res = kasir2b.get("/kasir")
print("kasir GET /kasir setelah kasir.use dicabut ->", res.status_code)
assert res.status_code == 302
assert res.headers["Location"] != "/kasir"
print("kasir GET /kasir setelah kasir.use dicabut -> Location", res.headers["Location"])

# Kembalikan hak akses semula
res = client.post("/hak-akses", data=semua_hak(), follow_redirects=True)
assert res.status_code == 200
kasir3 = app.test_client()
kasir3.post("/login", data={"username": "kasir", "password": "kasir123"})
assert kasir3.get("/kasir").status_code == 200
assert kasir3.get("/").status_code == 200

print("\nSMOKE TEST SELESAI")
