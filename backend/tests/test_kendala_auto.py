from types import SimpleNamespace

from app import kendala_auto as ka
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

2.
Kendala: tidak ada
Tindak lanjut: sudah diingatkan"""

OPSI = {"lp": ["1. Kepala sekolah sakit atau berhalangan", "2. Tidak ada kendala"]}


def _todo(judul, komponen):
    return todo.Todo(kode=komponen[0], judul=judul, pelaku="sekolah", komponen=komponen)


def _sekolah(npsn, nama, isian=None):
    return SimpleNamespace(npsn=npsn, nama=nama, isian={2: isian or {}})


def test_baca_balasan_dan_daftar():
    j = ka.baca_balasan(BALAS)
    assert [(x.no, x.kendala, x.tl) for x in j] == [(1, "kepala sekolah sakit", "dikirim besok"),
                                                   (2, "tidak ada", "sudah diingatkan")]
    d = ka.baca_daftar(PESAN)
    assert [b.nama for b in d] == ["SD NEGERI 20 CONTOH", "SD NEGERI 3 UJI"]
    assert d[0].poin == ["Kirim Laporan Pendahuluan"]
    assert ka.baca_balasan(PESAN) == []  # pesan kita sendiri berisi titik-titik, bukan jawaban


def test_pilih_kendala():
    assert ka.pilih_kendala("tidak ada", OPSI["lp"]) == "2. Tidak ada kendala"
    assert ka.pilih_kendala("Kepala sekolah sakit", OPSI["lp"]) == "1. Kepala sekolah sakit atau berhalangan"
    assert ka.pilih_kendala("hujan deras", OPSI["lp"]) == "hujan deras"


def test_rencana_isi_tidak_menimpa_isian_petugas(monkeypatch):
    a = _sekolah("1", "SD NEGERI 20 CONTOH")
    b = _sekolah("2", "SD NEGERI 3 UJI", {"lp": ("Isian petugas", "")})
    rencana = {"1": [_todo("Kirim Laporan Pendahuluan", ["lp"]), _todo("Unggah Lap. Mingguan", ["mg"])],
               "2": [_todo("Kirim Laporan Pendahuluan", ["lp"])]}
    monkeypatch.setattr(todo, "rencana", lambda s: SimpleNamespace(todo=rencana[s.npsn]))
    hasil = ka.rencana_isi(PESAN, BALAS, [b, a], 2, OPSI, {"lp", "mg"})
    assert [(s.npsn, k, kd, tl) for s, _, k, kd, tl in hasil] == [
        ("1", "lp", "1. Kepala sekolah sakit atau berhalangan", "dikirim besok"),  # mg tidak ada di pesan: tidak diisi
        ("2", "lp", "Isian petugas", "sudah diingatkan"),                         # kendala petugas tetap
    ]


def test_potong_balasan_ambil_setelah_permintaan_terakhir():
    rows = [Row("a", True, "read", "Kendala: ... lama"), Row("b", False, "", "balasan lama"),
            Row("c", True, "read", PESAN), Row("d", False, "", BALAS)]
    pesan, balas = ka.potong_balasan(rows)
    assert pesan == PESAN and balas == BALAS
    assert ka.potong_balasan(rows[:3]) is None
