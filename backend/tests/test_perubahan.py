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


def test_kalender_dan_log_per_hari_dengan_sesi(monkeypatch):
    from datetime import date

    with db.tx() as c:
        c.execute("DELETE FROM perubahan")
        c.execute("DELETE FROM aktivitas")
        c.execute("DELETE FROM sends")
        for w in ("2026-10-23T10:15:00", "2026-10-23T14:30:00", "2026-10-26T09:00:00"):
            c.execute("INSERT INTO perubahan(waktu, sumber, judul, ringkasan, rincian) VALUES(?,?,?,?,?)",
                      (w, "lk", "LK WEEK 1", "x", "[]"))
    k = perubahan.kalender(date(2026, 10, 1))
    assert k["bulan"] == "2026-10"
    assert k["hari"] == [{"tanggal": "2026-10-23", "broadcast": 0, "lk": 2, "fasil": 0},
                         {"tanggal": "2026-10-26", "broadcast": 0, "lk": 1, "fasil": 0}]
    assert k["paling_awal"] == "2026-10-23"
    assert perubahan.kalender(date(2026, 11, 1))["hari"] == []
    hari = perubahan.daftar(tanggal="2026-10-23")
    assert [x["sesi"] for x in hari] == [2, 1]
    assert hari[0]["sesi_label"] == "Sesi 2, 14.00–15.59"
    assert perubahan.daftar(tanggal="2026-10-26")[0]["sesi_label"] == "Sebelum sesi 1 (sebelum 10.00)"
