from datetime import datetime
from types import SimpleNamespace

import pytest

from app import db, terima_kasih
from app.wa import pengirim


@pytest.fixture()
def tk(monkeypatch, tmp_path):
    setting: dict = {}
    monkeypatch.setattr(db, "get_setting", lambda k, d=None: setting.get(k, d))
    monkeypatch.setattr(db, "set_setting", lambda k, v: setting.__setitem__(k, v))
    monkeypatch.setattr(terima_kasih, "_sesi", lambda: "WEEK 5 sesi 1")
    monkeypatch.setattr(terima_kasih.schedule, "now", lambda: datetime(2026, 11, 16, 10, 0))
    terima_kasih._siap = False
    with db.tx() as c:
        c.executescript("CREATE TABLE IF NOT EXISTS neo_pesan (id TEXT PRIMARY KEY, nomor TEXT, keluar INTEGER, "
                        "teks TEXT, waktu TEXT, status TEXT)")
    terkirim: list = []
    monkeypatch.setattr(pengirim, "kirim_satu",
                        lambda n, t: terkirim.append((n, t)) or (SimpleNamespace(status="terkirim", keterangan=""), "neonize"))
    import app.komunikasi as kom
    monkeypatch.setattr(kom, "petugas_saya", lambda: "Ani")
    return setting, terkirim


class _Timer:
    dibuat: list = []

    def __init__(self, detik, fn, args):
        self.detik, self.fn, self.args, self.daemon = detik, fn, args, False
        _Timer.dibuat.append(self)

    def start(self):
        pass


def test_mati_bawaan_dan_jam_kerja(tk, monkeypatch):
    setting, _ = tk
    assert not terima_kasih.jadwalkan("0812", "Fasil A", timer=_Timer)       # saklar bawaan mati
    setting[terima_kasih.KUNCI] = True
    _Timer.dibuat.clear()
    assert terima_kasih.jadwalkan("0812", "Fasil A", timer=_Timer)
    assert 60 <= _Timer.dibuat[0].detik <= 180 and _Timer.dibuat[0].daemon
    monkeypatch.setattr(terima_kasih.schedule, "now", lambda: datetime(2026, 11, 16, 22, 0))
    assert not terima_kasih.jadwalkan("0812", "Fasil A", timer=_Timer)      # di luar jam kerja


def test_sekali_per_sesi_dan_batal_bila_sudah_dibalas(tk):
    setting, terkirim = tk
    setting[terima_kasih.KUNCI] = True
    assert terima_kasih.kirim("0812", "Fasil A", "WEEK 5 sesi 1", "2026-11-16T09:59:00") == "terkirim"
    assert "Fasil A" in terkirim[0][1]
    assert terima_kasih.kirim("0812", "Fasil A", "WEEK 5 sesi 1", "2026-11-16T09:59:00") == "sudah"
    assert not terima_kasih.jadwalkan("0812", "Fasil A", timer=_Timer)      # sesi ini sudah dikirimi
    with db.tx() as c:
        c.execute("INSERT INTO neo_pesan VALUES ('p1', '0813', 1, 'oke pak', '2026-11-16T10:00:30', 'sent')")
    assert terima_kasih.kirim("0813", "Fasil B", "WEEK 5 sesi 1", "2026-11-16T10:00:00") == "dibalas"
    assert len(terkirim) == 1


def test_pakai_template_petugas(tk):
    setting, _ = tk
    setting["blast_template_saya"] = [{"id": "x", "judul": "Terima kasih", "jenis": "fasil",
                                       "teks": "Selamat {salam} {nama}, terima kasih! – {petugas}"}]
    assert terima_kasih.teks_untuk("Fasil A", "Ani", datetime(2026, 11, 16, 9)) == "Selamat pagi Fasil A, terima kasih! – Ani"
