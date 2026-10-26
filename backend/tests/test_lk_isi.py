import pytest
from fastapi import HTTPException

from app import db, sheets
from app.routers import lk

BARIS = ["Petugas Contoh", "11112222", "SD CONTOH 1", "Kab. Contoh", "Fasil Contoh", "6281200000001",
         "Prioritas 1", "3. Chat hanya di Read", 0.3, "Tidak", "Tidak", 0.32, "Tidak", "Tidak",
         "Alasan lama", "TL lama", "", "", "", "", "", "", "", "", "", "Z"]
OPSI = [["Catatan Komunikasi", "Alasan Belum 50%", "Alasan Belum Submit", "Alasan Belum Reviu"],
        ["0. Terhubung", "1. Progres belum diunggah", "1. Progres belum 50%", "1. Beban reviu"],
        ["3. Chat hanya di Read", "", "6. Lainnya", ""]]


def test_parse_isian_dan_validasi():
    s = sheets.parse_lk([BARIS])[0]
    assert s.komunikasi == "3. Chat hanya di Read"
    assert s.isian[1]["a1"] == "Alasan lama" and s.isian[1]["a2"] == "TL lama"
    assert s.isian[2]["c2"] == "Z"  # kolom AA
    v = sheets.parse_validasi(OPSI)
    assert v["komunikasi"] == ["0. Terhubung", "3. Chat hanya di Read"]
    assert v["alasan_submit"] == ["1. Progres belum 50%", "6. Lainnya"]
    assert v["alasan_reviu"] == ["1. Beban reviu"]


class FakeSS:
    def __init__(self, npsn_di_sheet):
        self.npsn = npsn_di_sheet
        self.ditulis = None

    def values_batch_get(self, ranges, params=None):
        return {"valueRanges": [{"values": [[self.npsn]]} for _ in ranges]}

    def values_batch_update(self, body):
        self.ditulis = body


def _pasang(monkeypatch, ss):
    class GC:
        def open_by_key(self, _):
            return ss
    monkeypatch.setattr(sheets, "gspread_client", lambda: GC())


def test_tulis_hanya_sel_yang_berubah(monkeypatch):
    ss = FakeSS(11112222.0)
    _pasang(monkeypatch, ss)
    s = sheets.parse_lk([BARIS])[0]
    sheets.write_isian("1", [(s, {"I": "0. Terhubung", "R": "6. Lainnya"})])
    assert ss.ditulis["valueInputOption"] == "RAW"
    assert [d["range"] for d in ss.ditulis["data"]] == ["'WEEK 1'!I3", "'WEEK 1'!R3"]


def test_tolak_bila_baris_bergeser(monkeypatch):
    ss = FakeSS("99999999")
    _pasang(monkeypatch, ss)
    s = sheets.parse_lk([BARIS])[0]
    with pytest.raises(sheets.LkWriteError):
        sheets.write_isian("1", [(s, {"I": "0. Terhubung"})])
    assert ss.ditulis is None


def _endpoint(monkeypatch):
    data = sheets.parse_lk([BARIS])
    ditulis = []
    db.set_setting("nama_petugas", "Petugas Contoh")
    monkeypatch.setattr(lk, "read_lk", lambda week: data)
    monkeypatch.setattr(lk, "read_validasi", lambda: sheets.parse_validasi(OPSI))
    monkeypatch.setattr(lk, "write_isian", lambda week, p: ditulis.extend(p))
    return data, ditulis


def test_endpoint_isi_menulis_dan_memperbarui_cache(monkeypatch):
    data, ditulis = _endpoint(monkeypatch)
    req = lk.IsiReq(blok=2, sekolah=[lk.Isian(npsn="11112222", komunikasi="0. Terhubung",
                                              isian={"b1": "6. Lainnya", "b2": "Dihubungi ulang besok"})])
    assert lk.isi(req) == {"disimpan": 1}
    assert ditulis[0][1] == {"I": "0. Terhubung", "X": "6. Lainnya", "Y": "Dihubungi ulang besok"}
    assert data[0].komunikasi == "0. Terhubung" and data[0].isian[2]["b1"] == "6. Lainnya"


def test_endpoint_tolak_pilihan_asing_dan_sekolah_lain(monkeypatch):
    _endpoint(monkeypatch)
    with pytest.raises(HTTPException) as e:
        lk.isi(lk.IsiReq(blok=1, sekolah=[lk.Isian(npsn="11112222", isian={"a1": "karangan sendiri"})]))
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        lk.isi(lk.IsiReq(blok=1, sekolah=[lk.Isian(npsn="55556666", komunikasi="0. Terhubung")]))
    assert e.value.status_code == 403
