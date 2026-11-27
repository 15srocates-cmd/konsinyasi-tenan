const BARANG = window.BARANG || [];
let cart = [];
let kategoriAktif = 'Semua';
let tabAktif = 'produk';

const KATEGORI = ['Semua', 'Suka', 'Makanan', 'Minuman'];

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function rupiah(n) {
  return 'Rp ' + Math.round(n || 0).toLocaleString('id-ID');
}

function kategoriBarang(b) {
  const nama = (b.nama || '').toLowerCase();
  if (nama.includes('suka')) return 'Suka';
  if (nama.includes('tea') || nama.includes('minuman')) return 'Minuman';
  return 'Makanan';
}

function pilihTab(tab) {
  tabAktif = tab;
  document.querySelectorAll('.tab-bar .tab').forEach(el => {
    el.classList.toggle('aktif', el.dataset.tab === tab);
  });
  document.getElementById('panel-produk').style.display = tab === 'produk' ? '' : 'none';
  document.getElementById('panel-manual').style.display = tab === 'manual' ? '' : 'none';
  if (tab === 'manual') document.getElementById('cari-manual').focus();
  else document.getElementById('cari').focus();
  renderSemuaProduk();
}

function renderKategori() {
  document.getElementById('kategori').innerHTML = KATEGORI.map(k => `
    <button type="button" class="chip ${k === kategoriAktif ? 'aktif' : ''}"
            onclick="pilihKategori('${k}')">${k}</button>
  `).join('');
}

function pilihKategori(k) {
  kategoriAktif = k;
  renderKategori();
  renderSemuaProduk();
}

function cocok(b, teks) {
  const q = (teks || '').toLowerCase().trim();
  return (!q ||
    b.kode.toLowerCase().includes(q) ||
    b.nama.toLowerCase().includes(q) ||
    b.tenan.toLowerCase().includes(q)) &&
    (kategoriAktif === 'Semua' || kategoriBarang(b) === kategoriAktif);
}

function renderSemuaProduk() {
  const qProduk = document.getElementById('cari').value;
  const qManual = document.getElementById('cari-manual').value;
  const list = BARANG.filter(b => cocok(b, qProduk));

  document.getElementById('daftar-barang').innerHTML = list.map(b => `
    <div class="produk ${b.stok <= 0 ? 'habis' : ''}"
         ${b.stok > 0 ? `onclick="tambah('${b.id}')"` : ''}>
      <div class="kode">${esc(b.kode)} · ${esc(b.tenan)}</div>
      <div class="nama">${esc(b.nama)}</div>
      <div class="harga">${rupiah(b.harga_jual)}</div>
      <div class="stok">Stok ${b.stok}</div>
    </div>`).join('') || '<div class="empty">Tidak ada barang yang cocok.</div>';

  const listManual = BARANG.filter(b => cocok(b, qManual));
  document.getElementById('daftar-manual').innerHTML = listManual.map(b => `
    <tr class="${b.stok <= 0 ? 'habis' : ''}">
      <td>${esc(b.kode)}</td>
      <td>${esc(b.nama)}<div class="muted">${esc(b.tenan)}</div></td>
      <td class="num">${rupiah(b.harga_jual)}</td>
      <td class="num">${b.stok}</td>
      <td><button type="button" class="secondary" ${b.stok <= 0 ? 'disabled' : ''}
                  onclick="tambah('${b.id}')">+</button></td>
    </tr>`).join('') || '<tr><td colspan="5" class="empty">Tidak ada barang yang cocok.</td></tr>';
}

function tambah(id) {
  const b = BARANG.find(x => x.id === id);
  if (!b || b.stok <= 0) return;
  const ada = cart.find(i => i.id === id);
  if (ada) {
    if (ada.qty >= b.stok) { alert('Stok tidak cukup'); return; }
    ada.qty += 1;
  } else {
    cart.push({
      id: b.id, kode: b.kode, nama: b.nama, tenan: b.tenan,
      qty: 1, harga: b.harga_jual, stok: b.stok
    });
  }
  renderCart();
}

function ubahQty(idx, delta) {
  const i = cart[idx];
  if (!i) return;
  i.qty = Math.max(1, Math.min(i.stok, i.qty + delta));
  renderCart();
}

function ubahHarga(idx, nilai) {
  if (!cart[idx]) return;
  cart[idx].harga = Math.max(0, parseInt(nilai) || 0);
  renderCart();
}

function hapus(idx) {
  cart.splice(idx, 1);
  renderCart();
}

function subtotal() {
  return cart.reduce((s, i) => s + i.qty * i.harga, 0);
}

function nilaiDiskon() {
  const v = Math.max(0, parseInt(document.getElementById('diskon').value) || 0);
  return Math.min(v, subtotal());
}

function nilaiCharge() {
  return Math.max(0, parseInt(document.getElementById('charge').value) || 0);
}

function totalAkhir() {
  return subtotal() + nilaiCharge() - nilaiDiskon();
}

function togglePenyesuaian() {
  const el = document.getElementById('penyesuaian');
  el.style.display = el.style.display === 'none' ? '' : 'none';
}

function renderCart() {
  document.getElementById('cart-body').innerHTML = cart.map((i, idx) => `
    <tr>
      <td>${esc(i.nama)}<div class="muted">${esc(i.kode)} · ${esc(i.tenan)}</div></td>
      <td class="num">
        <div class="stepper">
          <button type="button" class="secondary" onclick="ubahQty(${idx}, -1)">−</button>
          <span>${i.qty}</span>
          <button type="button" class="secondary" onclick="ubahQty(${idx}, 1)">+</button>
        </div>
      </td>
      <td class="num">
        <input type="number" min="0" value="${i.harga}" style="width:100px"
               onchange="ubahHarga(${idx}, this.value)">
      </td>
      <td class="num">${rupiah(i.qty * i.harga)}</td>
      <td><button type="button" class="secondary" onclick="hapus(${idx})">×</button></td>
    </tr>`).join('');
  document.getElementById('kosong').style.display = cart.length ? 'none' : 'block';
  document.getElementById('subtotal').textContent = rupiah(subtotal());
  document.getElementById('diskon-tampil').textContent = rupiah(nilaiDiskon());
  document.getElementById('charge-tampil').textContent = rupiah(nilaiCharge());
  document.getElementById('total').textContent = rupiah(totalAkhir());
  document.getElementById('modal-total').textContent = rupiah(totalAkhir());
  hitungKembali();
}

function hitungKembali() {
  const metode = document.getElementById('metode').value;
  const uangInput = document.getElementById('uang');
  if (metode === 'tunai') {
    uangInput.disabled = false;
    const uang = parseInt(uangInput.value) || 0;
    document.getElementById('kembali').textContent = rupiah(Math.max(0, uang - totalAkhir()));
  } else {
    uangInput.disabled = true;
    uangInput.value = totalAkhir();
    document.getElementById('kembali').textContent = rupiah(0);
  }
}

function bukaModal() {
  const pesan = document.getElementById('pesan');
  if (!cart.length) { pesan.textContent = 'Belum ada item pesanan.'; return; }
  pesan.textContent = '';
  document.getElementById('modal-pesan').textContent = '';
  document.getElementById('modal-total').textContent = rupiah(totalAkhir());
  document.getElementById('uang').value = 0;
  document.getElementById('modal-bayar').style.display = '';
  hitungKembali();
}

function tutupModal() {
  document.getElementById('modal-bayar').style.display = 'none';
}

async function simpanBayar() {
  const pesan = document.getElementById('modal-pesan');
  pesan.textContent = '';
  const metode = document.getElementById('metode').value;
  const uang = metode === 'tunai' ? (parseInt(document.getElementById('uang').value) || 0) : totalAkhir();
  if (metode === 'tunai' && uang < totalAkhir()) {
    pesan.textContent = 'Uang diterima kurang dari total belanja.';
    return;
  }

  const payload = {
    items: cart.map(i => ({ barang_id: i.id, qty: i.qty, harga_jual: i.harga })),
    metode_bayar: metode,
    uang_diterima: uang,
    diskon: nilaiDiskon(),
    charge: nilaiCharge()
  };

  const res = await fetch('/kasir', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    pesan.textContent = data.error || 'Gagal menyimpan transaksi.';
    return;
  }
  window.location = '/struk/' + data.id;
}

document.getElementById('cari').addEventListener('input', renderSemuaProduk);
document.getElementById('cari-manual').addEventListener('input', renderSemuaProduk);
document.getElementById('bayar').addEventListener('click', bukaModal);
document.getElementById('simpan-bayar').addEventListener('click', simpanBayar);

renderKategori();
renderSemuaProduk();
renderCart();
