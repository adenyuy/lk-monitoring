from app import sheets

BROADCAST = [
    ["No", "Nama Fasil", "Nomor HP", "Pesan", "Nama Petugas"],
    ["1", "Fasil Satu", "https://wa.me/6281200000101", "Halo Pak Fasil", "*Sari Petugas*"],
    ["2", "Fasil Dua", "https://wa.me/6281200000102", "Halo Bu Fasil", " Marvin  Nugraha"],
    ["3", "Fasil Jonathan", "https://wa.me/628111111111", "Halo", "Budi Petugas"],
    ["4", "Nomor Rusak", "bukan nomor", "Halo", "*Sari Petugas*"],
    ["5", "", "", "", ""],
]


def test_normalisasi_nama_petugas():
    assert sheets.normalize_petugas("*Sari Petugas*") == "sari petugas"
    assert sheets.clean_petugas("  *Marvin   Nugraha* ") == "Sari Petugas"


def test_normalisasi_nomor():
    assert sheets.normalize_nomor("https://wa.me/6281200000101") == "6281200000101"
    assert sheets.normalize_nomor("0812-0000-0101") == "6281200000101"
    assert sheets.normalize_nomor("+62 812 0000 0101") == "6281200000101"
    assert sheets.normalize_nomor("bukan nomor") == ""
    assert sheets.nomor_key("6281200000101") == sheets.nomor_key("081200000101")


def test_hash_pesan_abaikan_spasi_ujung_dan_line_ending():
    assert sheets.message_hash("a\r\nb ") == sheets.message_hash("a\nb")
    assert sheets.message_hash("a") != sheets.message_hash("b")


def test_parse_broadcast_dan_filter_nama_persis():
    rows = sheets.parse_broadcast(BROADCAST)
    assert len(rows) == 4  # baris tanpa petugas dilewati
    marvin = sheets.filter_petugas(rows, "Sari Petugas")
    assert [r.nama_fasil for r in marvin] == ["Fasil Satu", "Fasil Dua", "Nomor Rusak"]
    assert all(r.petugas == "Sari Petugas" for r in marvin)
    assert marvin[2].nomor == ""  # tidak valid, nanti ditandai Dilewati
    assert marvin[0].baris == 2


def test_ringkasan_petugas_gabung_varian_nama():
    summary = sheets.petugas_summary(sheets.parse_broadcast(BROADCAST))
    assert summary == [
        {"nama": "Budi Petugas", "jumlah_fasil": 1},
        {"nama": "Sari Petugas", "jumlah_fasil": 3},
    ]


LK = [
    # B petugas, C npsn, D nama, E kab, F fasil, G nomor, H prioritas, I, J, K, L, M, N, O
    ["Sari Petugas", "20518751", "SD NEGERI 2 DAMPIT", "Kab. Malang", "Fasil Satu",
     "6281200000101", "Prioritas 1", "", 0.6, "Tidak", "Tidak", 0.65, "Tidak", "Tidak"],
    ["Sari Petugas", 10101475.0, "SD NEGERI 10 TANAH JAMBO AYE", "Kab. Aceh Utara", "Fasil Empat",
     "081200000104, 6281200000105", "Selesai", "", 0.5, "Ya", "Ya", "", "", ""],
    ["Rina Petugas", "40305574", "UPT SD NEGERI 10 BILA", "Kab. Sidrap", "Fasil Tiga",
     "6281200000103", "Prioritas 2", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", ""],
]


def test_parse_lk():
    data = sheets.parse_lk(LK)
    assert len(data) == 3
    a = data[0]
    assert (a.baris, a.npsn, a.prioritas, a.progres, a.submit) == (3, "20518751", "Prioritas 1", 65.0, "Tidak")
    b = data[1]
    assert b.npsn == "10101475"  # 10101475.0 -> tanpa .0
    assert b.progres == 50.0  # harian kosong -> pakai baseline J
    assert b.submit == "Ya"
    assert len(b.nomor_keys) == 2  # dua nomor dalam satu sel


def test_sekolah_per_fasil_hanya_milik_petugas():
    m = sheets.sekolah_per_fasil(sheets.parse_lk(LK), "*Sari Petugas*")
    assert sheets.nomor_key("6281200000101") in m
    assert sheets.nomor_key("6281200000103") not in m  # milik Rina
    assert m[sheets.nomor_key("081200000104")][0].nama == "SD NEGERI 10 TANAH JAMBO AYE"
