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


def make(wa, start="2026-10-26 14:00", n=4):
    clock = Clock(datetime.strptime(start, "%Y-%m-%d %H:%M").replace(tzinfo=TZ))
    return Sender(wa=wa, sleep=clock.sleep, clock=clock, load_rows=lambda: rows(n), rng=random.Random(7)), clock


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


def test_salam_dan_isi_pesan():
    p = undangan_wag.Pengaturan(aktif=True, link=LINK, tim="", teks=undangan_wag.TEKS_AWAL)
    teks = undangan_wag.susun(p, "Budi")
    assert "Bapak/Ibu Budi" in teks and LINK in teks and "Tim Monitoring melalui" in teks
    assert undangan_wag.salam(datetime(2026, 10, 26, 10, 0)) == "pagi"
    assert undangan_wag.salam(datetime(2026, 10, 26, 14, 0)) == "siang"
    assert undangan_wag.salam(datetime(2026, 10, 26, 16, 0)) == "sore"
    assert undangan_wag.salam(datetime(2026, 10, 26, 19, 0)) == "malam"


def test_blast_undangan_sekali_per_fasil_dan_broadcast_tetap_jalan():
    undangan_wag.simpan(aktif=True, link=LINK, tim="7", teks="")
    wa = CatatWA()
    s, clock = make(wa)
    assert jalan(s).terkirim == 4
    assert all(t.startswith("Selamat siang Bapak/Ibu Fasil") and LINK in t and "Tim Monitoring 7" in t
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
