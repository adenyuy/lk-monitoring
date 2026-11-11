from app import lk_baru, todo
from app.komunikasi import tentukan
from app.lk_baru import Sekolah, parse_log_kom, parse_tata


def sekolah(**nilai) -> Sekolah:
    dasar = {"lp": "Sudah", "lp_rev": "Sudah", "progres": 0.6, "mg": "4/4", "mg_rev": "4/4", "bl": "1/1",
             "bl_rev": "1/1", "bku": "Sudah", "bpp": "Sudah", "l50": "Sudah", "l50_rev": "Sudah",
             "l100": "Belum Due", "l100_rev": "Belum Due"}
    dasar.update(nilai)
    isian = {b: {k.kode: ("", "") for k in lk_baru.KOMPONEN} for b in (1, 2)}
    return Sekolah(baris=4, petugas="Sari", npsn="1", nama="SD A", angkatan="4", provinsi="", kab="", kepsek="",
                   hp_kepsek="", ptn="", koor="", hp_koor="", fasil="Budi", hp_fasil="0812345678", nilai=dasar,
                   isian=isian)


def kode(r: todo.Rencana) -> list[str]:
    return [t.kode for t in r.todo]


def test_status_komponen():
    assert todo.status("mg", "3/5").status == "belum"
    assert todo.status("mg", "5/5").status == "selesai"
    assert todo.status("mg", "-").status == "kosong"
    assert todo.status("mg", "Belum Due").status == "due"
    assert todo.status("progres", 1.0).status == "selesai"
    assert todo.status("progres", 1.0033).status == "selesai"  # 100,33%, bukan 1%
    assert todo.status("progres", 0.42).tampil == "42%"
    assert todo.status("bku", "").status == "tanpa_data"
    assert todo.status("l50_rev", "Belum TTD Koor").status == "belum"


def test_pendahuluan_jadi_gerbang():
    r = todo.rencana(sekolah(lp="Belum", lp_rev="-", mg="0/3", bl="0/1", l50="Belum"))
    assert kode(r) == ["lp"]
    assert r.tahap == "pendahuluan"
    assert r.keterangan("mg") == "Menunggu Lap. Pendahuluan"
    assert r.keterangan("lp_rev") == todo.KOSONG
    assert r.keterangan("lp") == ""


def test_mingguan_dan_bulanan_berbarengan_bku_bpp_satu_paket():
    r = todo.rencana(sekolah(mg="3/4", bl="0/1", bku="Belum", bpp="Sudah"))
    assert kode(r) == ["mg", "paket_bulanan"]
    paket = r.todo[1]
    assert paket.komponen == ["bl", "bku"]
    assert paket.judul == "Unggah Bulanan + BKU"
    assert r.keterangan("bpp") == todo.SELESAI


def test_progres_kurang_dari_50_menahan_laporan_50():
    r = todo.rencana(sekolah(progres=0.3, l50="Belum", l50_rev="-"))
    assert kode(r) == ["progres"]
    assert r.keterangan("l50") == "Menunggu progres 50%"


def test_reviu_tugas_fasil():
    r = todo.rencana(sekolah(mg_rev="2/4", l50_rev="Revisi"))
    assert [(t.kode, t.pelaku) for t in r.todo] == [("mg_rev", "fasil"), ("l50_rev", "fasil")]


def test_laporan_100_menunggu_50():
    r = todo.rencana(sekolah(l50="Belum", progres=0.8, l100="Belum", l100_rev="-"))
    assert "l50" in kode(r)
    assert r.keterangan("l100") == "Menunggu Lap. 50%"


def test_keterangan_tidak_menimpa_isian_petugas():
    s = sekolah(mg="3/4")
    s.isian[1]["mg"] = ("2. Sekolah belum mengisi laporan mingguan", "Diingatkan via WA")
    s.isian[1]["bl"] = ("Berjalan", "Berjalan")
    r = todo.rencana(s)
    ubah = {(b, k): (a, c) for b, k, a, c in todo.keterangan_baru(s, r)}
    assert (1, "mg") not in ubah
    assert ubah[(1, "bl")] == (todo.SELESAI, todo.SELESAI)
    assert todo.lengkap(s, r, 1) and not todo.lengkap(s, r, 2)


def test_parse_tata_dan_log():
    r1 = ["DATA SEKOLAH"] + [""] * 30 + ["SESI SENIN"] + [""] * 25 + ["SESI RABU"] + [""] * 25
    r3 = list(lk_baru.IDENTITAS) + [k.judul for k in lk_baru.KOMPONEN]
    for k in lk_baru.KOMPONEN:
        if k.tunggu:
            r3.append(k.tunggu)
    r3 += [""] * (31 - len(r3))
    r2 = [""] * 31
    for _ in range(2):
        for k in lk_baru.KOMPONEN:
            r2 += [k.pasangan, ""]
            r3 += ["Kendala", "Tindak Lanjut"]
    t = parse_tata(r1, r2, r3)
    assert t.isian[1]["lp"] == (31, 32) and t.isian[2]["lp"] == (57, 58)
    from datetime import date
    lk = parse_log_kom([["PIC", "NPSN", "Nama", "Fasil", "Sen 09/11", "Sel 10/11"], ["X", "123", "SD", "B", "T", ""]],
                       date(2026, 11, 5))
    assert lk.tanggal == {"2026-11-09": 4, "2026-11-10": 5}
    assert lk.kode["123"] == {"2026-11-09": "T"}


def test_kelompok_komunikasi():
    minggu = ["2026-11-09", "2026-11-10", "2026-11-11"]
    assert tentukan({}, "2026-11-10", False, minggu) == "belum"
    assert tentukan({"2026-11-10": "C"}, "2026-11-10", False, minggu) == "terkirim"
    assert tentukan({"2026-11-10": "N"}, "2026-11-10", False, minggu) == "perlu_telepon"
    # sudah pernah membalas minggu ini: dibaca dua kali tidak membuatnya perlu ditelepon
    assert tentukan({"2026-11-09": "T", "2026-11-10": "R", "2026-11-11": "R"}, "2026-11-11", False, minggu) == "dibaca"
    assert tentukan({"2026-11-10": "R"}, "2026-11-10", False, minggu) == "dibaca"
    # R dua hari berturut-turut ditandai "perlu ditelepon" oleh telepon.keadaan (lihat test_telepon.py)
    assert tentukan({"2026-11-09": "R", "2026-11-10": "R"}, "2026-11-10", False, minggu) == "dibaca"
    assert tentukan({"2026-11-10": "T2"}, "2026-11-10", False, minggu) == "menunggu"
    assert tentukan({"2026-11-10": "TP"}, "2026-11-10", False, minggu) == "terhubung"
    assert tentukan({}, "2026-11-10", True, minggu) == "beres"


def test_kendala_petugas_berawalan_menunggu_bukan_otomatis():
    # "Menunggu pencairan" adalah pilihan Kendala petugas, bukan keterangan otomatis aplikasi
    assert not todo.otomatis("Menunggu pencairan")
    assert todo.otomatis("Menunggu Lap. Pendahuluan") and todo.otomatis(" Menunggu progres 50% ")
    s = sekolah(mg="3/4")
    s.isian[1]["mg"] = ("Menunggu pencairan", "Sedang proses pembuatan Laporan")
    r = todo.rencana(s)
    assert (1, "mg") not in {(b, k) for b, k, _, _ in todo.keterangan_baru(s, r)}
    assert todo.ringkas(s, r, 1)["todo"][0]["isian"]["mg"]["kendala"] == "Menunggu pencairan"
