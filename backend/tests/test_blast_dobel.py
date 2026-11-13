"""Blast tidak mengirim ulang ke nomor yang hari ini sudah menerima blast bertopik sama."""

from datetime import datetime

import pytest
from fastapi import HTTPException

from app import db, schedule, store
from app.routers import blast as rb

HARI = datetime(2026, 11, 12, 11, 0, tzinfo=schedule.TZ)


@pytest.fixture(autouse=True)
def _siap(monkeypatch):
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    monkeypatch.setattr(rb.schedule, "now", lambda: HARI)
    monkeypatch.setattr(rb.komunikasi, "wa_otomatis", lambda: True)
    monkeypatch.setattr(rb, "_nomor_penerima", lambda jenis: {"a": ("6281100000001", "Fasil A"),
                                                              "b": ("6281100000002", "Fasil B")})
    dimulai = {}

    def start(daftar, aturan, judul, coba, topik="", abaikan_jam=False):
        dimulai["nomor"] = [p.nomor for p in daftar]
        return {"running": True}

    monkeypatch.setattr(rb.blast.mesin, "start", start)
    yield dimulai
    with db.tx() as c:  # jangan tinggalkan kiriman palsu untuk tes lain
        c.execute("DELETE FROM sends")


def _kirim(nomor, topik, waktu="2026-11-12T10:00:00", status="terkirim", coba=False):
    store.record_send(tanggal=waktu[:10], waktu=waktu, sesi=0, nama_fasil="", nomor=nomor,
                      hash_pesan="blast:x", status=status, coba=coba, topik=topik)


def _req(**kw):
    dasar = {"jenis": "fasil", "judul": "Tanya kendala", "topik": "Tanya kendala",
             "aturan": {"jeda_min": 50, "jeda_max": 60, "istirahat_setiap": 10, "istirahat_menit": 5},
             "kirim": [{"kunci": "a", "pesan": "halo A"}, {"kunci": "b", "pesan": "halo B"}]}
    return rb.StartReq(**{**dasar, **kw})


def test_lewati_yang_sudah_dikirimi_topik_sama_hari_ini(_siap):
    _kirim("6281100000001", "Tanya kendala")
    r = rb.start(_req())
    assert _siap["nomor"] == ["6281100000002"] and r["dobel"] == ["Fasil A"]


def test_topik_lain_kemarin_gagal_dan_uji_coba_tidak_menghalangi(_siap):
    _kirim("6281100000001", "Topik lain")
    _kirim("6281100000001", "Tanya kendala", waktu="2026-11-11T10:00:00")
    _kirim("6281100000002", "Tanya kendala", status="gagal")
    _kirim("6281100000002", "Tanya kendala", coba=True)
    r = rb.start(_req())
    assert _siap["nomor"] == ["6281100000001", "6281100000002"] and r["dobel"] == []


def test_kirim_ulang_sengaja(_siap):
    _kirim("6281100000001", "Tanya kendala")
    rb.start(_req(kirim_ulang=True))
    assert _siap["nomor"] == ["6281100000001", "6281100000002"]


def test_semua_sudah_dikirimi_ditolak(_siap):
    _kirim("6281100000001", "Tanya kendala")
    _kirim("6281100000002", "Tanya kendala")
    with pytest.raises(HTTPException) as e:
        rb.start(_req())
    assert e.value.status_code == 400 and "sudah dikirimi" in e.value.detail
