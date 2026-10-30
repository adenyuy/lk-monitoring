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
    kol = {"mulai": "M", "akhir": "O", "label": "Harian", "npsn": "C", "prioritas": "H"}
    monkeypatch.setattr(cutoff, "_kolom", lambda week, mode: kol)
    r = cutoff.Rencana(token="t", mode="harian", week="1", tab="WEEK 1", nama_file="c.csv", n=2,
                       blok=[[0.5, "Ya", "Ya"], ["", "Tidak", "Tidak"]], prio=[["Selesai"], ["Prioritas 1"]],
                       ringkasan={"sheet_id": 9, "kolom": "M–O dan H"}, kol=dict(kol))
    cutoff._rencana["t"] = r
    hasil = cutoff.tulis("t")
    ranges = [d["range"] for d in tulisan["values"]["data"]]
    assert ranges == ["'WEEK 1'!M3:O4", "'WEEK 1'!H3:H4"]
    assert hasil["sekolah"] == 2
    assert cutoff.riwayat()[-1]["mode"] == "harian"
    import pytest
    with pytest.raises(cutoff.CutoffError):  # token sekali pakai
        cutoff.tulis("t")


def test_tulis_ditolak_bila_kolom_berubah_sejak_dicek(monkeypatch):
    import pytest
    monkeypatch.setattr(cutoff, "_kolom", lambda week, mode: {"mulai": "O", "akhir": "Q", "label": "Harian",
                                                              "npsn": "C", "prioritas": "H"})
    cutoff._rencana["u"] = cutoff.Rencana(token="u", mode="harian", week="1", tab="WEEK 1", nama_file="c.csv", n=1,
                                          blok=[[0.5, "Ya", "Ya"]], prio=[["Selesai"]],
                                          kol={"mulai": "M", "akhir": "O", "label": "Harian", "npsn": "C",
                                               "prioritas": "H"})
    with pytest.raises(cutoff.CutoffError, match="berubah"):
        cutoff.tulis("u")


def test_tanggal_kirim_jadi_serial():
    assert cutoff.ke_serial("46235.4971875") == 46235.4971875
    assert int(cutoff.ke_serial("2026-07-31 11:56:00")) == 46234
    assert int(cutoff.ke_serial("31/07/2026 11:56")) == 46234
    assert cutoff.ke_serial("") is None and cutoff.ke_serial("bukan tanggal") is None


def test_olah_raw_reviu():
    csv = ("NPSN,Tanggal Kirim,Kiriman Ke-\n10803808,2026-07-31 11:56:00,1\n,2026-08-01,1\n"
           "10803485,,2\n40306401,46250.75,2\n").encode()
    baris, tanpa = cutoff.olah_raw(cutoff.baca(csv, "raw.csv", min_kolom=2))
    assert [b[0] for b in baris] == [10803808, 40306401] and baris[1][1:] == [46250.75, 2]
    assert tanpa == 1


def test_tulis_waktu_tunggu(monkeypatch):
    tulisan = {"req": []}

    class SS:
        def batch_update(self, body):
            tulisan["req"] += body["requests"]

        def values_clear(self, rng):
            tulisan["clear"] = rng

        def values_batch_update(self, body):
            tulisan["values"] = body["data"]

    monkeypatch.setattr(cutoff, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: SS()})())
    monkeypatch.setattr(cutoff, "catat_bersama", lambda baris: tulisan.setdefault("log", baris))
    cutoff._rencana["w"] = cutoff.Rencana(token="w", mode="waktu_tunggu", week="", tab=cutoff.RAW_TAB, nama_file="raw.csv",
                                          n=3, blok=[[1, 46000.5, 1], [2, 46001.0, 1], [3, 46002.0, 2]], prio=[],
                                          ringkasan={"sheet_id": 5, "baris_grid": 3, "kolom": "A–C"})
    hasil = cutoff.tulis("w")
    assert tulisan["clear"] == "'Raw Reviu 50%'!A2:C"
    assert tulisan["values"][1] == {"range": "'Raw Reviu 50%'!A2:C4", "values": [[1, 46000.5, 1], [2, 46001.0, 1], [3, 46002.0, 2]]}
    assert tulisan["req"][0]["appendDimension"]["length"] == 1  # grid 3 baris, butuh 4
    assert hasil["sekolah"] == 3 and tulisan["log"][1] == "waktu_tunggu"


def test_riwayat_dari_catatan_dan_log(monkeypatch):
    x = cutoff.dari_catatan("Update terakhir (Mingguan (Baseline)): 26 Oct 2026 08:34\nsumber: a.csv", "1")
    assert (x["mode"], x["week"], x["waktu"][:16], x["file"], x["oleh"]) == ("mingguan", "1", "2026-10-26T08:34", "a.csv", "")
    h = cutoff.dari_catatan("Update terakhir (Harian): 29 Oct 2026 10:18\nsumber: b.csv\noleh: Kalica", "1")
    assert h["oleh"] == "Kalica" and cutoff.dari_catatan("P1 sekolah belum submit", "1") is None
    log = {"waktu": "2026-10-29T10:18:40+07:00", "mode": "harian", "week": "1", "file": "b.csv", "sekolah": 9000, "oleh": "Kalica"}
    monkeypatch.setattr(cutoff, "_baca_bersama", lambda: [x, h, log])
    monkeypatch.setattr(cutoff, "riwayat", lambda: [])
    cutoff.cache.clear()
    r = cutoff.riwayat_semua()
    assert len(r) == 2 and r[1]["sekolah"] == 9000 and r[1]["oleh"] == "Kalica"  # catatan + log digabung


def test_susulkan_riwayat_lokal_sekali(monkeypatch):
    from app import db
    ditambah = []
    lokal = [{"waktu": "2026-10-27T09:00:10+07:00", "mode": "harian", "week": "1", "file": "a.csv", "sekolah": 10},
             {"waktu": "2026-10-28T09:00:10+07:00", "mode": "harian", "week": "1", "file": "b.csv", "sekolah": 11}]
    monkeypatch.setattr(cutoff, "riwayat", lambda: lokal)
    monkeypatch.setattr(cutoff, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: None})())
    monkeypatch.setattr(cutoff, "_baca_log", lambda ss: [{**lokal[0], "waktu": "2026-10-27T09:00:55+07:00"}])
    monkeypatch.setattr(cutoff, "_tambah_log", lambda ss, baris: ditambah.extend(baris))
    db.set_setting("nama_petugas", "Petugas Uji")
    db.set_setting("cutoff_log_disusulkan", "")
    assert cutoff.susulkan_riwayat() == 1  # yang 27 Okt sudah ada di log (menit sama)
    assert ditambah[0][3] == "b.csv" and ditambah[0][5] == "Petugas Uji"
    assert cutoff.susulkan_riwayat() == 0  # hanya sekali


def test_kolom_cutoff_dari_judul(monkeypatch):
    from app import sheets
    from tests import lk_uji
    judul = lk_uji.JUDUL_LAMA[:9] + ["Status Komunikasi (bantuan)", "Waktu Tunggu"] + lk_uji.JUDUL_LAMA[9:]
    monkeypatch.setattr(cutoff, "kolom_lk", lambda week, refresh=False: sheets.parse_kolom(judul))
    assert cutoff._kolom("1", "mingguan")["mulai"] == "L" and cutoff._kolom("1", "harian")["akhir"] == "Q"
