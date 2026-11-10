from types import SimpleNamespace

from app import tl_auto as ta
from app import todo
from app.wa.actions import Row

PESAN = """Selamat siang Bapak/Ibu Fasil, izin menindaklanjuti progres pelaporan sekolah dampingan Bapak/Ibu.

1. SD NEGERI 20 CONTOH
   • Kirim Laporan Pendahuluan
   Kendala: ...
   Tindak lanjut: ...

2. SD NEGERI 3 UJI
   • Kirim Laporan Pendahuluan
   Kendala: ...
   Tindak lanjut: ...

Mohon dibantu mengisi Kendala dan Tindak lanjut untuk tiap sekolah."""

BALAS = """1. SD Negeri 20 Contoh
Kendala: kepala sekolah sakit
Tindak lanjut: dikirim besok
setelah kepsek masuk

2.
Kendala: tidak ada
Tindak lanjut: sudah diingatkan

Terima kasih"""


def _todo(judul, komponen):
    return todo.Todo(kode=komponen[0], judul=judul, pelaku="sekolah", komponen=komponen)


def _sekolah(npsn, nama, isian=None):
    return SimpleNamespace(npsn=npsn, nama=nama, isian={2: isian or {}})


def test_baca_balasan_dan_daftar():
    j = ta.baca_balasan(BALAS)
    assert [(x.no, x.kendala, x.tl) for x in j] == [
        (1, "kepala sekolah sakit", "dikirim besok setelah kepsek masuk"),
        (2, "tidak ada", "sudah diingatkan"),  # "Terima kasih" sesudah baris kosong tidak ikut
    ]
    d = ta.baca_daftar(PESAN)
    assert [b.nama for b in d] == ["SD NEGERI 20 CONTOH", "SD NEGERI 3 UJI"]
    assert d[0].poin == ["Kirim Laporan Pendahuluan"]
    assert ta.baca_balasan(PESAN) == []  # pesan kita sendiri berisi titik-titik, bukan jawaban


def test_hanya_tindak_lanjut_dan_tidak_menimpa_petugas(monkeypatch):
    a = _sekolah("1", "SD NEGERI 20 CONTOH", {"lp": ("Kendala petugas", "")})
    b = _sekolah("2", "SD NEGERI 3 UJI", {"lp": ("", "TL petugas")})
    c = _sekolah("3", "SD NEGERI 9 LAIN", {"lp": ("", todo.BERJALAN)})
    rencana = {"1": [_todo("Kirim Laporan Pendahuluan", ["lp"]), _todo("Unggah Lap. Mingguan", ["mg"])],
               "2": [_todo("Kirim Laporan Pendahuluan", ["lp"])],
               "3": [_todo("Kirim Laporan Pendahuluan", ["lp"])]}
    monkeypatch.setattr(todo, "rencana", lambda s: SimpleNamespace(todo=rencana[s.npsn]))
    hasil = ta.rencana_isi(PESAN, BALAS, [b, a, c], 2, {"lp", "mg"})
    # mg tidak ada di pesan: tidak diisi; sekolah 2 sudah punya TL petugas: tidak ditimpa; kendala tidak diubah
    assert [(s.npsn, k, kd, tl) for s, _, k, kd, tl in hasil] == [
        ("1", "lp", "Kendala petugas", "dikirim besok setelah kepsek masuk")]


def test_tl_otomatis_boleh_ditimpa(monkeypatch):
    a = _sekolah("1", "SD NEGERI 20 CONTOH", {"lp": ("", "Menunggu Lap. Pendahuluan")})
    monkeypatch.setattr(todo, "rencana", lambda s: SimpleNamespace(todo=[_todo("Kirim Laporan Pendahuluan", ["lp"])]))
    hasil = ta.rencana_isi(PESAN, BALAS, [a], 2, {"lp"})
    assert [tl for *_, tl in hasil] == ["dikirim besok setelah kepsek masuk"]


def test_potong_balasan_ambil_setelah_permintaan_terakhir():
    rows = [Row("a", True, "read", "Kendala: ...\nTindak lanjut: ... lama"), Row("b", False, "", "balasan lama"),
            Row("c", True, "read", PESAN), Row("d", False, "", BALAS),
            Row("e", True, "read", "Info: mohon segera tindak lanjut laporan")]  # bukan permintaan format
    pesan, balas = ta.potong_balasan(rows)
    assert pesan == PESAN and balas == BALAS
    assert ta.potong_balasan(rows[:3]) is None


OPSI_LP = ["1. Tidak ada kendala", "2. Sekolah belum mengakses aplikasi", "3. Kendala akun / login",
           "4. Dokumen Laporan Pendahuluan belum lengkap", "7. Lainnya (jelaskan di tindak lanjut)"]


def test_kendala_di_luar_dropdown_jadi_lainnya_digabung_koma():
    assert ta.isi_kendala("Dana sudah cair", "Sedang proses pembuatan Laporan", OPSI_LP) == (
        "7. Lainnya (jelaskan di tindak lanjut)", "Dana sudah cair, Sedang proses pembuatan Laporan")
    assert ta.isi_kendala("Dana sudah cair", "", OPSI_LP) == ("7. Lainnya (jelaskan di tindak lanjut)", "Dana sudah cair")
    assert ta.isi_kendala("tidak ada", "aman", OPSI_LP) == ("1. Tidak ada kendala", "aman")
    assert ta.isi_kendala("Dokumen laporan pendahuluan belum lengkap", "dilengkapi", OPSI_LP)[0].startswith("4.")
    assert ta.isi_kendala("3", "reset", OPSI_LP) == ("3. Kendala akun / login", "reset")
    assert ta.isi_kendala("Lainnya", "x", OPSI_LP) == ("7. Lainnya (jelaskan di tindak lanjut)", "x")
    assert ta.isi_kendala("Dana sudah cair", "y", []) == ("Dana sudah cair", "y")  # tanpa dropdown: apa adanya


def test_balasan_per_todo():
    teks = """1. SD NEGERI 7 CONTOH
   • Lengkapi Laporan Mingguan (20/21 terunggah)
   Kendala: sinyal
   Tindak lanjut: minggu depan
   • Unggah Bulanan + BKU + BPP (4/5 terunggah)
   Kendala: bendahara cuti
   Tindak lanjut: menunggu bendahara"""
    j = ta.baca_balasan(teks)
    assert len(j) == 1 and not j[0].kendala
    assert ta.isian_todo(j[0], "Lengkapi Laporan Mingguan", 2) == ("sinyal", "minggu depan")
    assert ta.isian_todo(j[0], "Unggah Bulanan + BKU + BPP", 2) == ("bendahara cuti", "menunggu bendahara")
    assert ta.isian_todo(j[0], "Kirim Laporan Pendahuluan", 2) is None
    # contoh balasan satu to-do
    j = ta.baca_balasan("9. SD NEGERI 12 UJI\n   • Kirim Laporan Pendahuluan\n"
                        "   Kendala: Dana sudah cair\n   Tindak lanjut: Sedang proses pembuatan Laporan")
    assert ta.isian_todo(j[0], "Kirim Laporan Pendahuluan", 1) == ("Dana sudah cair", "Sedang proses pembuatan Laporan")


def test_rencana_isi_kendala_kosong_ikut_diisi(monkeypatch):
    a = _sekolah("1", "SD NEGERI 20 CONTOH", {"lp": ("", "")})
    b = _sekolah("2", "SD NEGERI 3 UJI", {"lp": ("Kendala petugas", "")})
    rencana = {"1": [_todo("Kirim Laporan Pendahuluan", ["lp"])], "2": [_todo("Kirim Laporan Pendahuluan", ["lp"])]}
    monkeypatch.setattr(todo, "rencana", lambda s: SimpleNamespace(todo=rencana[s.npsn]))
    balas = """1. SD NEGERI 20 CONTOH
   • Kirim Laporan Pendahuluan
   Kendala: Dana sudah cair
   Tindak lanjut: Sedang proses pembuatan Laporan
2. SD NEGERI 3 UJI
   • Kirim Laporan Pendahuluan
   Kendala: Dana sudah cair
   Tindak lanjut: proses"""
    out = ta.rencana_isi(PESAN, balas, [a, b], 2, {"lp"}, {"lp": OPSI_LP})
    assert [(s.npsn, k, kd, tl) for s, _, k, kd, tl in out] == [
        ("1", "lp", "7. Lainnya (jelaskan di tindak lanjut)", "Dana sudah cair, Sedang proses pembuatan Laporan"),
        ("2", "lp", "Kendala petugas", "Dana sudah cair, proses"),
    ]


def test_rentang_sesi_blast():
    from datetime import date

    from app import lk_baru
    from app.routers.blast import rentang_sesi

    lama = lk_baru.SESI_BAWAAN  # judul sheet sekarang: SESI SENIN – SELASA / SESI RABU – JUMAT
    assert rentang_sesi(date(2026, 11, 10), lama) == (date(2026, 11, 9), date(2026, 11, 10))   # Selasa: sesi 1
    assert rentang_sesi(date(2026, 11, 14), lama) == (date(2026, 11, 11), date(2026, 11, 15))  # Sabtu: sesi 2
    baru = {1: lk_baru.rentang_hari("SESI SENIN – RABU · DIISI PETUGAS"),
            2: lk_baru.rentang_hari("SESI KAMIS – SABTU · DIISI PETUGAS")}
    assert baru == {1: (0, 2, "Senin–Rabu"), 2: (3, 5, "Kamis–Sabtu")}
    assert lk_baru.blok_untuk(date(2026, 11, 11), baru) == 1  # Rabu
    assert lk_baru.blok_untuk(date(2026, 11, 12), baru) == 2  # Kamis
    assert lk_baru.blok_untuk(date(2026, 11, 15), baru) == 2  # Minggu ikut sesi terakhir
    assert rentang_sesi(date(2026, 11, 11), baru) == (date(2026, 11, 9), date(2026, 11, 11))
    assert lk_baru.label_blok(2, baru) == "Kamis–Sabtu"
    assert lk_baru.rentang_hari("SESI RABU – JUMAT · DIISI PETUGAS") == (2, 4, "Rabu–Jumat")
