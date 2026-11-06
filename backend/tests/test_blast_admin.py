from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import blast_admin as ba


def _s(npsn, pic, fasil, hp_fasil, koor="Koor A", hp_koor="0812000001", ptn="Univ A", prov="Prov. Aceh",
       angkatan="1", kepsek="Pak Kepsek", hp_kepsek="0813000001"):
    s = SimpleNamespace(npsn=npsn, petugas=pic, nama=f"SD {npsn}", fasil=fasil, hp_fasil=hp_fasil, koor=koor,
                        hp_koor=hp_koor, ptn=ptn, provinsi=prov, angkatan=angkatan, kepsek=kepsek,
                        hp_kepsek=hp_kepsek, kab="Kab X")
    s.nomor_fasil = lambda: [hp_fasil] if hp_fasil else []
    return s


SEKOLAH = [
    _s("1", "Ani", "Fasil Satu", "6281111"),
    _s("2", "Ani", "Fasil Satu", "6281111"),
    _s("3", "Budi", "Fasil Dua", "6282222", koor="Koor B", hp_koor="0812000002", ptn="Univ B", prov="Prov. Riau",
       angkatan="2", hp_kepsek=""),
]


def test_target_per_jenis():
    fasil = ba.target("fasil", SEKOLAH)
    assert [t.nama for t in fasil] == ["Fasil Dua", "Fasil Satu"]
    satu = next(t for t in fasil if t.nama == "Fasil Satu")
    assert satu.nilai["jumlah_sekolah"] == "2" and satu.pic == {"Ani"}
    koor = ba.target("koor", SEKOLAH)
    a = next(t for t in koor if t.nama == "Koor A")
    assert a.nilai["jumlah_fasil"] == "1" and a.nilai["jumlah_sekolah"] == "2"
    sek = ba.target("sekolah", SEKOLAH)
    assert len(sek) == 3 and sum(1 for t in sek if t.nomor) == 2


def test_saring_dan_rakit():
    fasil = ba.target("fasil", SEKOLAH)
    hasil = ba.saring(fasil, ba.Saring(provinsi=["Riau"]))
    assert [t.nama for t in hasil] == ["Fasil Dua"]
    assert ba.saring(fasil, ba.Saring(pic=["Ani"], angkatan=["2"])) == []
    teks = ba.rakit("{salam} {nama} ({ptn}), PIC {pic}, {jumlah_sekolah} sekolah", hasil[0])
    assert teks == "{salam} Fasil Dua (Univ B), PIC Budi, 1 sekolah"
    assert ba._sisa_variabel(ba.rakit("Halo {sekolah}", hasil[0])) == ["{sekolah}"]


def test_start_wajib_konfirmasi(monkeypatch):
    monkeypatch.setattr(ba, "_semua", lambda: SEKOLAH)
    req = ba.StartReq(jenis="koor", pesan="Halo {nama}", coba=False, konfirmasi="iya")
    with pytest.raises(HTTPException) as e:
        ba.start(req)
    assert "risiko ditanggung sendiri" in e.value.detail


def test_start_mengirim_ke_nomor_unik(monkeypatch):
    monkeypatch.setattr(ba, "_semua", lambda: SEKOLAH)
    monkeypatch.setattr(ba.komunikasi, "wa_otomatis", lambda: True)
    monkeypatch.setattr(ba, "_sudah_terkirim", lambda nh: set())
    dikirim = {}

    def start(daftar, aturan, judul, coba):
        dikirim["daftar"] = daftar
        return {"running": True}

    monkeypatch.setattr(ba.blast.mesin, "start", start)
    r = ba.start(ba.StartReq(jenis="fasil", pesan="{salam} {nama}", konfirmasi="Risiko ditanggung sendiri"))
    assert r["jumlah"] == 2
    assert sorted(p.pesan for p in dikirim["daftar"]) == ["{salam} Fasil Dua", "{salam} Fasil Satu"]
