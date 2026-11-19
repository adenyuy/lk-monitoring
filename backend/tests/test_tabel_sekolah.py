from types import SimpleNamespace as NS

from app import todo
from app.routers import lkb


def _todo(kode, *komponen):
    return todo.Todo(kode=kode, judul=kode, pelaku="sekolah", komponen=list(komponen or [kode]))


def _sekolah(isian):
    return NS(npsn="1", nama="SD A", angkatan="4", fasil="Fasil A", isian={1: isian}, nomor_fasil=lambda: ["6281200000001"])


def test_isian_terisi_hanya_bila_kendala_dan_tl_diisi_petugas():
    r = NS(todo=[_todo("lp"), _todo("mg"), _todo("bulanan", "bl", "bku"), _todo("l50")])
    s = _sekolah({"lp": ("Dana belum cair", "Dihubungi"), "mg": ("Dana belum cair", ""),
                  "bl": ("Kendala", "TL"), "bku": ("Kendala", "TL"), "l50": (todo.DUE, "TL")})
    assert todo.isian_terisi(s, r, 1) == 2
    assert todo.isian_terisi(s, r, 2) == 0


def test_tabel_sekolah_berisi_kolom_yang_dipakai_halaman():
    s = _sekolah({"lp": ("Kendala", "TL")})
    assert lkb.tabel_sekolah([s], {"1": NS(todo=[_todo("lp"), _todo("mg")])}, 1) == [
        {"npsn": "1", "nama": "SD A", "angkatan": "4", "kunci": "6281200000001", "fasil": "Fasil A", "todo": 2, "isian": 1}]
