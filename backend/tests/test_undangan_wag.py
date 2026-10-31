"""Undangan WAG: blast link grup tim monitoring, sekali per fasil per link, terpisah dari Broadcast mingguan."""

import random
from datetime import datetime

import pytest

from app import db, store, undangan_wag
from app.schedule import TZ
from app.sender import Sender

from test_sender import Clock, FakeWA, rows

LINK = "https://chat.whatsapp.com/AbCdEfGhIj12345"


class CatatWA(FakeWA):
    def __init__(self):
        super().__init__()
        self.teks = []

    def open_chat(self, nomor, teks):
        self.teks.append(teks)
        return super().open_chat(nomor, teks)


@pytest.fixture(autouse=True)
def bersih():
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    db.set_setting("nama_petugas", "Sari Petugas")
    db.set_setting("batas_harian", 40)
    db.set_setting("kirim_akhir_pekan", False)
    db.delete_setting(undangan_wag.KUNCI)
    yield
    db.delete_setting(undangan_wag.KUNCI)


def make(wa, start="2026-10-26 14:00", n=4, lk=()):
    clock = Clock(datetime.strptime(start, "%Y-%m-%d %H:%M").replace(tzinfo=TZ))
    return Sender(wa=wa, sleep=clock.sleep, clock=clock, load_rows=lambda: rows(n), rng=random.Random(7),
                  load_lk=lambda: list(lk)), clock


def jalan(s):
    s.start()
    s.wait(10)
    return s.state


def test_validasi_pengaturan():
    with pytest.raises(undangan_wag.UndanganError):
        undangan_wag.simpan(aktif=True, link="", tim="", teks="")
    with pytest.raises(undangan_wag.UndanganError):
        undangan_wag.simpan(aktif=False, link="https://example.com/grup", tim="", teks="")
    with pytest.raises(undangan_wag.UndanganError):
        undangan_wag.simpan(aktif=False, link=LINK, tim="", teks="Halo tanpa tautan")
    p = undangan_wag.simpan(aktif=True, link="chat.whatsapp.com/AbCdEfGhIj12345?mode=r_c", tim=" 7 ", teks="")
    assert p.link == LINK and p.tim == "7" and p.teks == undangan_wag.TEKS_AWAL
    # teks awal lama yang tersimpan tanpa diedit ikut diganti teks awal terbaru
    db.set_setting(undangan_wag.KUNCI, {"aktif": True, "link": LINK, "tim": "7",
                                        "teks": undangan_wag._TEKS_AWAL_LAMA[0]})
    assert undangan_wag.pengaturan().teks == undangan_wag.TEKS_AWAL


def test_salam_dan_isi_pesan():
    p = undangan_wag.Pengaturan(aktif=True, link=LINK, tim="", teks=undangan_wag.TEKS_AWAL)
    teks = undangan_wag.susun(p, "Budi")
    assert "rekan fasilitator Budi" in teks and LINK in teks and "Tim Monitoring melalui" in teks
    assert undangan_wag.salam(datetime(2026, 10, 26, 10, 0)) == "pagi"
    assert undangan_wag.salam(datetime(2026, 10, 26, 14, 0)) == "siang"
    assert undangan_wag.salam(datetime(2026, 10, 26, 16, 0)) == "sore"
    assert undangan_wag.salam(datetime(2026, 10, 26, 19, 0)) == "malam"


def test_blast_undangan_sekali_per_fasil_dan_broadcast_tetap_jalan():
    undangan_wag.simpan(aktif=True, link=LINK, tim="7", teks="")
    wa = CatatWA()
    s, clock = make(wa)
    assert jalan(s).terkirim == 4
    assert all(t.startswith("Selamat siang rekan fasilitator Fasil") and LINK in t and "Tim Monitoring 7" in t
               for t in wa.teks)

    # Masih mode undangan: semua sudah diundang, minggu depan pun tidak diundang lagi
    clock.t = datetime(2026, 11, 2, 16, 0, tzinfo=TZ)
    assert not [i for i in s.antrean() if i.bisa_dikirim]

    # Link grup diganti: semua diundang lagi
    undangan_wag.simpan(aktif=True, link=LINK + "x", tim="7", teks="")
    assert len([i for i in s.antrean() if i.bisa_dikirim]) == 4

    # Mode dimatikan: undangan tidak dihitung sebagai Broadcast minggu ini
    clock.t = datetime(2026, 10, 26, 16, 0, tzinfo=TZ)
    undangan_wag.simpan(aktif=False, link=LINK, tim="7", teks="")
    wa2 = CatatWA()
    s.wa = wa2
    assert jalan(s).terkirim == 4
    assert wa2.teks == [f"Halo {i}" for i in range(4)]
    assert store.counts("2026-10-26")[0] == 8  # batas harian tetap satu untuk keduanya


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.access import Access
    from app.main import app
    from app.routers import send
    from app.sender import sender

    monkeypatch.setattr(sender, "load_rows", lambda: rows(3))
    monkeypatch.setattr(sender, "load_lk", lambda: [])
    app.dependency_overrides[send.wa_blast] = lambda: Access(email="uji@contoh.id", nama_petugas="Sari Petugas",
                                                             fitur=("wa_blast",))
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_undangan(client):
    r = client.post("/api/undangan-wag", json={"aktif": True, "link": "", "tim": "", "teks": ""})
    assert r.status_code == 400
    r = client.post("/api/undangan-wag", json={"aktif": True, "link": LINK, "tim": "3", "teks": ""})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["aktif"] and d["link"] == LINK and "Tim Monitoring 3" in d["contoh"] and "{salam}" not in d["contoh"]
    assert client.get("/api/undangan-wag").json()["aktif"]


def test_undangan_langsung_semua_fasil_tanpa_sesi_akhir_pekan_dan_batas_harian():
    undangan_wag.simpan(aktif=True, link=LINK, tim="", teks="")
    db.set_setting("batas_harian", 10)
    wa = CatatWA()
    s, clock = make(wa, start="2026-10-31 08:30", n=25)  # Sabtu, sebelum sesi 1
    k = s.kondisi()
    assert k.bisa_kirim and k.kode == "undangan" and k.kuota == 25
    st = jalan(s)
    assert st.terkirim == 25 and len(set(wa.sent)) == 25 and st.berhenti_karena == ""
    assert wa.teks[0].startswith("Selamat pagi")
    assert s.kondisi().kode == "antrean_habis"


def test_undangan_berhenti_di_luar_jam():
    undangan_wag.simpan(aktif=True, link=LINK, tim="", teks="")
    s, clock = make(CatatWA(), start="2026-10-31 22:30", n=3)
    assert s.kondisi().kode == "undangan_jam" and not s.kondisi().bisa_kirim


def test_undangan_mode_coba_tiga_pesan():
    undangan_wag.simpan(aktif=True, link=LINK, tim="", teks="")
    wa = CatatWA()
    s, clock = make(wa, start="2026-10-31 09:00", n=10)
    s.start(coba=True)
    s.wait(10)
    assert s.state.dicoba == 3 and not wa.sent


def sekolah(baris, fasil, nomor, petugas="Sari Petugas"):
    from app.sheets import Sekolah

    return Sekolah(baris, petugas, "1", "SD", "", fasil, nomor, "", None, "", "")


def test_semua_fasil_binaan_dari_lk_ikut_diundang():
    undangan_wag.simpan(aktif=True, link=LINK, tim="", teks="")
    lk = [
        sekolah(5, "Fasil 0", "0811-0000-0000"),      # sudah ada di Broadcast (nomor sama)
        sekolah(6, "Fasil LK Satu", "081299990001"),  # hanya di LK
        sekolah(7, "Fasil LK Satu", "081299990001"),  # sekolah kedua fasil yang sama
        sekolah(8, "Fasil Tanpa Nomor", ""),          # tanpa nomor: dicantumkan, dilewati
        sekolah(9, "Fasil Lain", "081299990009", petugas="Petugas Lain"),
    ]
    wa = CatatWA()
    s, clock = make(wa, start="2026-10-31 09:00", n=2, lk=lk)
    items = s.antrean()
    assert [i.nama_fasil for i in items] == ["Fasil 0", "Fasil 1", "Fasil LK Satu", "Fasil Tanpa Nomor"]
    assert items[-1].status == "dilewati"
    assert jalan(s).terkirim == 3
    assert "6281299990001" in wa.sent and "rekan fasilitator Fasil LK Satu" in wa.teks[-1]


def test_jeda_undangan_lebih_pendek_untuk_fasil_yang_pernah_membalas():
    undangan_wag.simpan(aktif=True, link=LINK, tim="", teks="")
    store.save_chat_status("6281100000001", "dibalas", "siap", "2026-10-30T10:00:00")
    s, clock = make(CatatWA(), start="2026-10-31 09:00", n=3)
    jeda = []
    s._jeda = (lambda asli: lambda nama, coba, nomor="": (jeda.append(nomor), asli(nama, coba, nomor)))(s._jeda)
    mulai = clock.t
    st = jalan(s)
    assert st.terkirim == 3 and jeda == ["6281100000001", "6281100000002"]
    total = (clock.t - mulai).total_seconds()
    assert 15 + 25 <= total <= 30 + 50 + 5
    from app import db as _db
    with _db.tx() as c:
        c.execute("DELETE FROM chat_status")
        c.execute("DELETE FROM aktivitas")
