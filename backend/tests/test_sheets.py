from app import sheets
from tests import lk_uji

# Semua nama, nomor, dan sekolah di file ini karangan (repo publik).
BROADCAST = [
    ["No", "Nama Fasil", "Nomor HP", "Pesan", "Nama Petugas"],
    ["1", "Fasil Satu", "https://wa.me/6281200001111", "Halo Pak Satu", "*Sari Petugas*"],
    ["2", "Fasil Dua", "https://wa.me/6281200002222", "Halo Bu Dua", " Sari  Petugas"],
    ["3", "Fasil Tiga", "https://wa.me/628111111111", "Halo", "Dimas Sari Petugas"],
    ["4", "Nomor Rusak", "bukan nomor", "Halo", "*Sari Petugas*"],
    ["5", "", "", "", ""],
]


def test_normalisasi_nama_petugas():
    assert sheets.normalize_petugas("*Sari Petugas*") == "sari petugas"
    assert sheets.clean_petugas("  *Sari   Petugas* ") == "Sari Petugas"


def test_normalisasi_nomor():
    assert sheets.normalize_nomor("https://wa.me/6281200001111") == "6281200001111"
    assert sheets.normalize_nomor("0812-0000-1111") == "6281200001111"
    assert sheets.normalize_nomor("+62 812 0000 1111") == "6281200001111"
    assert sheets.normalize_nomor("bukan nomor") == ""
    assert sheets.nomor_key("6281200001111") == sheets.nomor_key("081200001111")


def test_hash_pesan_abaikan_spasi_ujung_dan_line_ending():
    assert sheets.message_hash("a\r\nb ") == sheets.message_hash("a\nb")
    assert sheets.message_hash("a") != sheets.message_hash("b")


def test_parse_broadcast_dan_filter_nama_persis():
    rows = sheets.parse_broadcast(BROADCAST)
    assert len(rows) == 4  # baris tanpa petugas dilewati
    sari = sheets.filter_petugas(rows, "Sari Petugas")
    assert [r.nama_fasil for r in sari] == ["Fasil Satu", "Fasil Dua", "Nomor Rusak"]
    assert all(r.petugas == "Sari Petugas" for r in sari)
    assert sari[2].nomor == ""  # tidak valid, nanti ditandai Dilewati
    assert sari[0].baris == 2


def test_ringkasan_petugas_gabung_varian_nama():
    summary = sheets.petugas_summary(sheets.parse_broadcast(BROADCAST))
    assert summary == [
        {"nama": "Dimas Sari Petugas", "jumlah_fasil": 1},
        {"nama": "Sari Petugas", "jumlah_fasil": 3},
    ]


LK = [
    # B petugas, C npsn, D nama, E kab, F fasil, G nomor, H prioritas, I, J, K, L, M, N, O
    ["Sari Petugas", "90000001", "SD CONTOH 1", "Kab. Contoh", "Fasil Satu",
     "6281200001111", "Prioritas 1", "", 0.6, "Tidak", "Tidak", 0.65, "Tidak", "Tidak"],
    ["Sari Petugas", 90000002.0, "SD CONTOH 2", "Kab. Contoh", "Fasil Dua",
     "081200002222, 6281200002299", "Selesai", "", 0.5, "Ya", "Ya", "", "", ""],
    ["Petugas Lain", "90000003", "SD CONTOH 3", "Kab. Contoh", "Fasil Tiga",
     "6281200003333", "Prioritas 2", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", ""],
]


def test_parse_lk():
    data = lk_uji.parse(LK)
    assert len(data) == 3
    a = data[0]
    assert (a.baris, a.npsn, a.prioritas, a.progres, a.submit) == (3, "90000001", "Prioritas 1", 65.0, "Tidak")
    b = data[1]
    assert b.npsn == "90000002"  # 90000002.0 -> tanpa .0
    assert b.progres == 50.0  # harian kosong -> pakai baseline J
    assert b.submit == "Ya"
    assert len(b.nomor_keys) == 2  # dua nomor dalam satu sel


def test_sekolah_per_fasil_hanya_milik_petugas():
    m = sheets.sekolah_per_fasil(lk_uji.parse(LK), "*Sari Petugas*")
    assert sheets.nomor_key("6281200001111") in m
    assert sheets.nomor_key("6281200003333") not in m  # milik petugas lain
    assert m[sheets.nomor_key("081200002222")][0].nama == "SD CONTOH 2"
