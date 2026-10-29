import pandas as pd

from app import cutoff

CSV = (
    "NPSN,Nama Sekolah,Jenis Laporan,Periode Ke,Capaian (%),Sudah Submit,Sudah Review\n"
    "111,SD A,Laporan Mingguan,1,40,,\n"
    "111,SD A,Laporan Mingguan,2,55.5,,\n"
    "111,SD A,Laporan 50%,1,,Ya,Tidak\n"
    "222,SD B,Laporan Mingguan,1,13.12,,\n"
    "333,SD C,Laporan 50%,1,,ya,ya\n"
    "444,SD D,Laporan Mingguan,3,40.5,,\n"
    "444,SD D,Laporan Bulanan,1,46.17,,\n"
    "555,SD E,Laporan Bulanan,1,20,,\n"
    "111,SD A,Laporan Bulanan,1,50,,\n"
    "111,SD A,Laporan Pendahuluan,1,99,,\n"
).encode()


def test_baca_dan_olah():
    df = cutoff.baca(CSV, "cutoff.csv")
    progress, lap50 = cutoff.olah(df)
    # capaian tertinggi dari Laporan Mingguan + Bulanan; jenis lain (Pendahuluan) diabaikan; '13.12' tetap angka
    assert progress == {"111": 55.5, "222": 13.12, "444": 46.17, "555": 20.0}
    assert lap50 == {"111": ("Ya", "Tidak"), "333": ("Ya", "Ya")}
    assert cutoff.header_aneh(df) == ""


def test_capaian_dari_tanggal():
    assert cutoff.ke_capaian("2026-12-13 00:00:00") == 13.12


def test_prioritas_dan_blok():
    blok, prio = cutoff.bangun(["111", "222", "333", ""], {"111": 55.5, "222": 13.12}, {"111": ("Ya", "Tidak"), "333": ("Ya", "Ya")})
    assert prio == [["Prioritas 3"], ["Prioritas 1"], ["Prioritas 2"], [""]]
    assert blok[0] == [0.555, "Ya", "Tidak"] and blok[3] == ["", "", ""]


def test_tolak_file_aneh():
    import pytest
    with pytest.raises(cutoff.CutoffError):
        cutoff.baca(b"a,b\n1,2\n", "x.csv")
    with pytest.raises(cutoff.CutoffError):
        cutoff.baca(b"", "x.pdf")


def test_tulis_memakai_rencana(monkeypatch):
    tulisan = {}

    class SS:
        def values_batch_update(self, body):
            tulisan["values"] = body

        def batch_update(self, body):
            tulisan["format"] = body

    class GC:
        def open_by_key(self, _):
            return SS()

    monkeypatch.setattr(cutoff, "gspread_client", lambda: GC())
    r = cutoff.Rencana(token="t", mode="harian", week="1", tab="WEEK 1", nama_file="c.csv", n=2,
                       blok=[[0.5, "Ya", "Ya"], ["", "Tidak", "Tidak"]], prio=[["Selesai"], ["Prioritas 1"]],
                       ringkasan={"sheet_id": 9, "kolom": "M–O dan H"})
    cutoff._rencana["t"] = r
    hasil = cutoff.tulis("t")
    ranges = [d["range"] for d in tulisan["values"]["data"]]
    assert ranges == ["'WEEK 1'!M3:O4", "'WEEK 1'!H3:H4"]
    assert hasil["sekolah"] == 2
    assert cutoff.riwayat()[-1]["mode"] == "harian"
    import pytest
    with pytest.raises(cutoff.CutoffError):  # token sekali pakai
        cutoff.tulis("t")
