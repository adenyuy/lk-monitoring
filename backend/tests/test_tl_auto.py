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
