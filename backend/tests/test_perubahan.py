from app import db, perubahan, sheets


def _bc(nomor, nama, pesan):
    return sheets.BroadcastRow(2, "Petugas Uji", nama, nomor, nomor, pesan, sheets.message_hash(pesan))


def test_broadcast_potret_pertama_tidak_dicatat_lalu_beda_dicatat():
    db.set_setting("nama_petugas", "Petugas Uji")
    db.delete_setting("potret_broadcast")
    a = _bc("6281200000001", "Fasil A", "Halo\n1. SD SATU\n2. SD DUA")
    perubahan.catat_broadcast([a])
    n0 = len(perubahan.daftar())
    a2 = _bc("6281200000001", "Fasil A", "Halo\n1. SD SATU\n2. SD TIGA")
    b = _bc("6281200000002", "Fasil B", "Halo\n1. SD EMPAT")
    perubahan.catat_broadcast([a2, b])
    log = perubahan.daftar()
    assert len(log) == n0 + 1
    assert log[0]["ringkasan"] == "1 fasil baru, 1 pesan berubah"
    assert "Fasil baru: Fasil B" in log[0]["rincian"]
    assert "Pesan Fasil A berubah: + SD TIGA; − SD DUA" in log[0]["rincian"]
    perubahan.catat_broadcast([a2, b])  # tidak berubah -> tidak dicatat
    assert len(perubahan.daftar()) == n0 + 1


def test_lk_perubahan_prioritas_dan_progres():
    db.set_setting("nama_petugas", "Petugas Uji")
    db.delete_setting("potret_lk:WEEK 9")
    baris = ["Petugas Uji", "111", "SD SATU", "Kab", "Fasil A", "6281200000001", "Prioritas 1", "",
             0.4, "Tidak", "Tidak", 0.4, "Tidak", "Tidak"]
    perubahan.catat_lk("WEEK 9", sheets.parse_lk([baris]))
    baris2 = list(baris)
    baris2[6], baris2[11], baris2[12] = "Prioritas 3", 0.55, "Ya"
    perubahan.catat_lk("WEEK 9", sheets.parse_lk([baris2]))
    e = perubahan.daftar()[0]
    assert e["judul"] == "LK WEEK 9"
    assert e["ringkasan"].startswith("1 sekolah P1 → P3")
    assert "SD SATU: progres 40,0% → 55,0%" in e["rincian"]
