"""Bypass jam kirim: blast boleh mulai dan terus jalan di luar 07.00–22.00 bila diminta."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app import blast, chat_refresh, db, schedule

MALAM = datetime(2026, 11, 12, 23, 15, tzinfo=schedule.TZ)


class WaPalsu:
    def __init__(self):
        self.terkirim = []

    def open_chat(self, nomor, pesan):
        self.terkirim.append(nomor)
        return SimpleNamespace(ok=True, alasan="")

    def send(self):
        return SimpleNamespace(status="terkirim", keterangan="")

    def clear_draft(self):
        pass


@pytest.fixture
def mesin(monkeypatch):
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    monkeypatch.setattr(blast.aktivitas, "catat", lambda *a, **k: None)
    monkeypatch.setattr(chat_refresh, "trigger", lambda *a, **k: None)
    yield blast.Mesin(wa=WaPalsu(), sleep=lambda s: None, clock=lambda: MALAM)
    with db.tx() as c:
        c.execute("DELETE FROM sends")


def _penerima():
    return [blast.Penerima(nomor=f"62811000000{i}", nama=f"Fasil {i}", pesan="Halo") for i in range(2)]


def test_di_luar_jam_ditolak_tanpa_bypass(mesin):
    with pytest.raises(blast.BlastError):
        mesin.start(_penerima(), blast.Aturan(), "Uji")


def test_bypass_jam_mengirim_semua(mesin):
    mesin.start(_penerima(), blast.Aturan(jeda_min=5, jeda_max=5), "Uji", abaikan_jam=True)
    mesin.wait(5)
    assert mesin.state.terkirim == 2
    assert mesin.state.abaikan_jam
    assert not mesin.state.berhenti_karena
