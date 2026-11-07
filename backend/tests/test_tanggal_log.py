from datetime import date

from app.cutoff_baru import rencana_kolom_tanggal

H1 = ["LOG KOMUNIKASI FASIL", "", "", "", "", "", "WEEK 3 · 5–6 Nov 2026"]
H2 = ["PIC", "NPSN", "Nama Sekolah", "PTN", "Koordinator", "Fasilitator", "Kam 05/11", "Jum 06/11",
      "Rab 11/11", "Kam 12/11", "Jum 13/11", "", "Kode", "Arti"]


def test_sudah_ada():
    assert rencana_kolom_tanggal(H1, H2, date(2026, 11, 6)) is None


def test_sisip_urut_tanggal_dan_judul_week():
    # Senin 9/11 masuk sesudah Jum 06/11, sebelum Rab 11/11; kolom pertama minggu itu diberi judul WEEK 4
    assert rencana_kolom_tanggal(H1, H2, date(2026, 11, 9)) == (8, 7, "WEEK 4 · 9–13 Nov 2026")


def test_sambung_di_akhir_tanpa_judul_bila_minggunya_sudah_ada():
    h2 = H2[:8] + ["Sen 09/11"] + H2[8:]
    assert rencana_kolom_tanggal(H1, h2, date(2026, 11, 10)) == (9, 8, "")


def test_minggu_baru_sesudah_kolom_terakhir():
    assert rencana_kolom_tanggal(H1, H2, date(2026, 11, 16)) == (11, 10, "WEEK 5 · 16–20 Nov 2026")


def test_tanpa_kolom_tanggal():
    assert rencana_kolom_tanggal([], ["PIC", "NPSN"], date(2026, 11, 9)) is None
