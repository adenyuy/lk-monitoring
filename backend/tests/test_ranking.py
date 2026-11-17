"""Ranking PIC: urutan, persen komponen, isian Kendala/TL, Log Komunikasi per fasil, filter bimtek."""

from datetime import datetime

import pytest

from app import lk_baru, ranking
from app.lk_baru import LogKom, Sekolah

SENIN = "2026-11-16"


def sekolah(npsn: str, petugas: str, fasil: str, hp: str, bimtek: str = "", isian_lp=("", ""), **nilai) -> Sekolah:
    dasar = {"lp": "Sudah", "lp_rev": "Sudah", "progres": 1.0, "mg": "4/4", "mg_rev": "4/4", "bl": "1/1",
             "bl_rev": "1/1", "bku": "Sudah", "bpp": "Sudah", "l50": "Sudah", "l50_rev": "Sudah",
             "l100": "Belum Due", "l100_rev": "Belum Due"}
    dasar.update(nilai)
    isian = {b: {k.kode: ("", "") for k in lk_baru.KOMPONEN} for b in (1, 2)}
    isian[1]["lp"] = isian_lp
    return Sekolah(baris=4, petugas=petugas, npsn=npsn, nama=f"SD {npsn}", angkatan="4", provinsi="", kab="",
                   kepsek="", hp_kepsek="", ptn="", koor="", hp_koor="", fasil=fasil, hp_fasil=hp, bimtek=bimtek,
                   nilai=dasar, isian=isian)


@pytest.fixture
def data(monkeypatch):
    semua = [
        sekolah("1", "Sari", "Budi", "081200000001", bimtek="Bimtek Lap 1"),
        sekolah("2", "Sari", "Budi", "081200000001"),
        # Rudi: Lap. Pendahuluan belum, Kendala diisi petugas; TL berisi keterangan otomatis (tidak dihitung)
        sekolah("3", "Rudi", "Ani", "081200000002", lp="Belum", lp_rev="-",
                isian_lp=("Sekolah belum login", "Menunggu Lap. Pendahuluan")),
    ]
    monkeypatch.setattr(lk_baru, "baca_semua", lambda: semua)
    monkeypatch.setattr(lk_baru, "tanpa_mundur", lambda s: s)
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: LogKom({SENIN: 6}, {"3": 3}, {"3": {SENIN: "T"}}))
    monkeypatch.setattr(lk_baru, "sesi_hari", lambda: lk_baru.SESI_BAWAAN)
    monkeypatch.setattr(ranking.schedule, "now", lambda: datetime(2026, 11, 17, 10))
    ranking._simpan.clear()
    yield
    ranking._simpan.clear()


def test_urutan_dan_persen(data):
    r = ranking.hitung()
    sari, rudi = r["pic"]
    assert (sari["nama"], sari["peringkat"], sari["selesai"], sari["harus"], sari["persen"]) == ("Sari", 1, 22, 22, 100.0)
    # lp_rev "-" tidak dihitung harus; lp belum -> 9 dari 10
    assert (rudi["nama"], rudi["peringkat"], rudi["selesai"], rudi["harus"]) == ("Rudi", 2, 9, 10)
    assert rudi["persen"] == 90.0
    assert (r["nasional"]["selesai"], r["nasional"]["harus"]) == (31, 32)


def test_kendala_tl_dan_log_komunikasi(data):
    rudi = ranking.hitung()["pic"][1]
    lp = next(k for k in rudi["komponen"] if k["kode"] == "lp")
    assert (lp["belum"], lp["kendala"], lp["tl"], lp["fasil_belum"]) == (1, 1, 0, 1)
    assert lp["kom"] == {"T": 1}
    assert (rudi["log_isi"], rudi["log_slot"], rudi["log_persen"]) == (1, 1, 100.0)
    sari = ranking.hitung()["pic"][0]
    assert (sari["fasil"], sari["log_isi"], sari["log_slot"]) == (1, 0, 1)  # dua sekolah, satu fasil


def test_filter_bimtek(data):
    r = ranking.hitung("Bimtek Lap 1")
    assert [(p["nama"], p["sekolah"]) for p in r["pic"]] == [("Sari", 1)]
    assert r["pilihan_bimtek"] == ["Bimtek Lap 1"]
    assert {p["nama"] for p in ranking.hitung("-")["pic"]} == {"Sari", "Rudi"}
