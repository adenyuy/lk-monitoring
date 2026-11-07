from datetime import date

from app.cutoff_baru import hari_minggu, rencana_kolom_tanggal

H1 = ["LOG KOMUNIKASI FASIL", "", "", "", "", "", "WEEK 3 · 5–6 Nov 2026"]
H2 = ["PIC", "NPSN", "Nama Sekolah", "PTN", "Koordinator", "Fasilitator", "Kam 05/11", "Jum 06/11",
      "Rab 11/11", "Kam 12/11", "Jum 13/11", "", "Kode", "Arti"]


def test_minggu_senin_sampai_sabtu():
    assert hari_minggu(date(2026, 11, 7))[0] == date(2026, 11, 2)
    assert hari_minggu(date(2026, 11, 7))[-1] == date(2026, 11, 7)
    assert hari_minggu(date(2026, 11, 8))[0] == date(2026, 11, 9)  # Minggu: siapkan minggu depan


def test_minggu_ini_tambah_sabtu_tanpa_isi_hari_sebelum_log_dimulai():
    r = rencana_kolom_tanggal(H1, H2, date(2026, 11, 7))
    assert r.sisip == [(8, 7)]
    assert r.baris2 == {8: "Sab 07/11"}
    assert r.baris1 == {6: "WEEK 3 · 5–7 Nov 2026"}


def test_minggu_depan_lengkap_dengan_judul_week():
    h1 = H1 + ["", ""]
    h2 = H2[:8] + ["Sab 07/11"] + H2[8:]
    r = rencana_kolom_tanggal(h1, h2, date(2026, 11, 9))
    # Sen & Sel sebelum Rab 11/11, Sab sesudah Jum 13/11
    assert r.sisip == [(9, 8), (10, 9), (14, 13)]
    assert r.baris2 == {9: "Sen 09/11", 10: "Sel 10/11", 14: "Sab 14/11"}
    assert r.baris1 == {9: "WEEK 4 · 9–14 Nov 2026"}


def test_week_baru_dari_admin_di_akhir():
    h1 = ["LOG", "", "", "", "", "", "WEEK 4 · 9–14 Nov 2026"]
    h2 = H2[:6] + [f"{h} {d}/11" for h, d in zip(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab"], range(9, 15))]
    r = rencana_kolom_tanggal(h1, h2, date(2026, 11, 16), week=5)
    assert [i for i, _ in r.sisip] == [12, 13, 14, 15, 16, 17]
    assert r.baris1 == {12: "WEEK 5 · 16–21 Nov 2026"}
    assert r.baris2[17] == "Sab 21/11"


def test_judul_pindah_ke_kolom_pertama_dan_lintas_bulan():
    h2 = H2[:6] + ["Jum 27/11", "Rab 02/12"]
    h1 = ["", "", "", "", "", "", "WEEK 6 · 23–28 Nov 2026", "WEEK 7 · 2–5 Des 2026"]
    r = rencana_kolom_tanggal(h1, h2, date(2026, 12, 2))
    # Sen 30/11 jadi kolom pertama: judul pindah ke sana, judul lama di Rab dikosongkan
    assert r.baris1 == {7: "WEEK 7 · 30 Nov–5 Des 2026", 9: ""}


def test_sudah_lengkap():
    h1 = ["", "", "", "", "", "", "WEEK 4 · 9–14 Nov 2026"]
    h2 = H2[:6] + [f"{h} {d}/11" for h, d in zip(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab"], range(9, 15))]
    assert rencana_kolom_tanggal(h1, h2, date(2026, 11, 12)) is None


def test_tanpa_kolom_tanggal():
    assert rencana_kolom_tanggal([], ["PIC", "NPSN"], date(2026, 11, 9)) is None
