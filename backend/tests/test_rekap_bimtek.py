"""Rekap Bimtek dari folder tiruan (tanpa Google)."""

from datetime import datetime

from app import rekap_bimtek

KOLOM = ["NPSN", "Nama Sekolah", "Pendahuluan - Status Kirim", "Capaian Progres (%)", "Mingguan Terkirim", "Mingguan Due",
         "Bulanan Terkirim", "Bulanan Due", "Laporan 50% - Status Kirim", "Laporan 100% - Status Kirim", "Tgl Kirim 50%",
         "Hari Verif 50%"]


def _export(baris: list[list[str]]) -> str:
    return "\n".join(";".join(r) for r in [KOLOM] + baris)


def _sk(npsn: str, kirim50: str, tgl: str, progres: str = "40", hari: str = "") -> list[str]:
    return [npsn, f"SD {npsn}", "Sudah Dikirim", progres, "1", "1", "0", "0", kirim50, "Belum Due", tgl, hari]


def test_hitung_konversi_dan_dampak(tmp_path, monkeypatch):
    monkeypatch.setattr(rekap_bimtek, "_peta_pic", lambda: {"1": ("Ani", "Koor A", "PTN A", "2"), "2": ("Budi", "", "", "")})
    monkeypatch.setattr(rekap_bimtek, "simpan_lk_harian", lambda d: None)   # tanpa akses LK
    monkeypatch.setattr(rekap_bimtek.lk_baru, "npsn_mundur", lambda refresh=False: frozenset({"8"}))  # 8 mengundurkan diri
    d = tmp_path / "data-bimtek"
    for x in ("0-referensi", "1-sebelum/B1", "2-terbaru"):
        (d / x).mkdir(parents=True)
    (d / "0-referensi" / "jadwal_bimtek.csv").write_text(
        "kelompok;tag;mulai;selesai;catatan\nB1;Bimtek Lap 1;2026-10-12;2026-10-16;\nB2;Bimtek Lap 2;2026-11-03;2026-11-07;\n",
        encoding="utf-8")
    (d / "0-referensi" / "peserta.csv").write_text(
        "NPSN;Tag\n1;Bimtek Lap 1\n2;Bimtek Lap 1\n3;Bimtek Lap 1\n4;Bimtek Lap 1\n6;Bimtek Lap 2\n", encoding="utf-8")
    # peserta: 1 sudah sebelum bimtek, 2 & 3 kirim selama bimtek, 4 belum; pembanding 5 kirim selama, 6..8 belum
    # (6 peserta B2: belum dibimtek saat B1, jadi tetap pembanding B1),
    # 9 belum due (tidak dihitung). Sekolah 3 kirim ulang: export lama mencatat tanggal lebih awal.
    lama = _export([_sk("3", "Sudah Dikirim", "13/10/2026 10:00")])
    (d / "1-sebelum" / "B1" / "Export_Konstruksi_Sekolah_20261020_080000.csv").write_text(lama, encoding="utf-8")
    baru = _export([
        _sk("1", "Sudah Dikirim", "2026-10-01 09:00:00", hari="2"), _sk("2", "Sudah Dikirim", "2026-10-14 09:00:00", hari="1"),
        _sk("3", "Sudah Dikirim", "2026-11-01 09:00:00"), _sk("4", "Belum Dikirim", ""),
        _sk("5", "Sudah Dikirim", "2026-10-15 09:00:00", hari="5"), _sk("6", "Belum Dikirim", ""),
        _sk("7", "Belum Dikirim", ""), _sk("8", "Belum Dikirim", ""), _sk("9", "Belum Due", ""),
    ])
    (d / "2-terbaru" / "Export_Konstruksi_Sekolah_20261115_130000.csv").write_text(baru, encoding="utf-8")

    r = rekap_bimtek.hitung(d)
    assert r["data_terbaru"]["waktu"] == "2026-11-15T13:00" and r["wajib50"] == 7   # 8 mengundurkan diri: tidak dihitung
    b1 = r["kelompok"][0]
    l50 = b1["l50"]
    assert b1["tahap"] == "selesai" and b1["sekolah"] == 4
    assert l50["awal"] == 25.0 and l50["belum_awal"] == 3 and l50["n_awal"] == 1   # hanya sekolah 1 sebelum 12 Okt
    assert l50["t1"]["n"] == 3 and l50["t1"]["pct"] == 75.0           # 1, 2, 3 dari 4
    assert l50["t1"]["konversi"] == 66.7                              # 2 dan 3 (tanggal paling awal 13 Okt) dari 3
    assert l50["t1"]["konversi_banding"] == 33.3                      # 5 dari 5..7
    assert l50["t1"]["dampak"] == 33.4
    assert l50["verif_median"] == 1.0
    # export di 1-sebelum/B1 bertanggal 20 Okt (sesudah bimtek mulai): tidak dipakai sebagai kondisi sebelum,
    # jadi hanya Laporan 50% (dari tanggal kirim) yang punya data; komponen lain "belum ada data"
    assert "awal" not in b1
    komp = {k["kode"]: k for k in b1["komponen"]}
    assert komp["l50"]["ada"] and not komp["lp"]["ada"]
    assert komp["l50"]["konversi"] == 66.7 and komp["l50"]["awal_pct"] == 25.0 and komp["l50"]["akhir_pct"] == 75.0
    # Reviu 50% direkonstruksi dari tanggal kirim + hari verif, jadi ikut tersedia tanpa potret
    assert b1["capaian"]["komponen"] == ["l50", "l50_rev"] and komp["l50_rev"]["ada"]
    kurva = {s["kode"]: s for s in r["kurva"]["seri"]}
    assert kurva["B1"]["sekolah"] == 4 and "Non-peserta" not in kurva
    b2 = r["kelompok"][1]
    assert b2["sekolah"] == 1 and b2["l50"]["wajib_banding"] == 2   # pembanding B2: 5, 7 (peserta B1 sudah dibimtek)
    assert kurva["B1"]["nilai"][-1] == 75.0
    # baris per sekolah untuk halaman detail (kolom sesuai kolom_sekolah, tanpa nomor HP)
    kol = r["kolom_sekolah"]
    baris = {x[0]: dict(zip(kol, x)) for x in b1["sekolah_baris"]}
    assert {n: b["kategori"] for n, b in baris.items()} == {"1": "sebelum", "2": "saat", "3": "saat", "4": "belum"}
    assert baris["1"]["pic"] == "Ani" and baris["1"]["nama"] == "SD 1" and "hp" not in " ".join(kol)
    assert baris["1"]["koor"] == "Koor A" and baris["1"]["ptn"] == "PTN A" and baris["3"]["koor"] == ""
    assert baris["1"]["angkatan"] == "2" and baris["2"]["angkatan"] == ""
    i50 = r["komponen_urut"].index("l50")
    assert baris["4"]["awal_kode"][i50] == "B" and baris["4"]["akhir_kode"][i50] == "B"   # belum -> masih belum
    assert baris["2"]["awal_kode"][i50] == "B" and baris["2"]["akhir_kode"][i50] == "S"   # belum -> sudah
    assert baris["1"]["awal_kode"][0] == "-"                                               # Lap. Pendahuluan: tanpa data
    # hari terakhir bimtek (16 Okt): Lap. 50% dari tanggal kirim; 3 kirim 13 Okt (tanggal paling awal), 4 belum
    assert [baris[n]["t1_kode"][i50] for n in "1234"] == ["S", "S", "S", "B"]
    assert baris["1"]["t1_kode"][0] == "-"                      # tidak ada potret di 16-18 Okt untuk komponen lain
    assert "akhir1" not in b1 and baris["1"]["hotel"] == ""     # tanpa master hotel


def test_status_reviu_50_dari_export(tmp_path):
    f = tmp_path / "Export_Konstruksi_Sekolah_20261115_130000.csv"
    teks = _export([_sk("1", "Sudah Dikirim", "2026-11-01 09:00:00"), _sk("2", "Sudah Dikirim", "2026-11-02 09:00:00")])
    baris = teks.splitlines()
    baris[0] += ";Laporan 50% - Status Reviu"
    baris[1] += ";Selesai (TTD Koordinator)"
    baris[2] += ";Belum Direviu"
    f.write_text("\n".join(baris) + "\n", encoding="utf-8")
    assert rekap_bimtek.baca_export(f).rev50 == {"1": "setuju", "2": "menunggu"}


def test_waktu_dari_nama_file():
    assert rekap_bimtek.waktu_nama("Export_Konstruksi_Sekolah_20261115_130807.csv") == datetime(2026, 11, 15, 13, 8, 7)
    assert rekap_bimtek._tgl("05/11/2026 17:34") == datetime(2026, 11, 5, 17, 34)
    assert rekap_bimtek._tgl("2026-11-05 17:34:41") == datetime(2026, 11, 5, 17, 34, 41)


def test_baca_hotel_dari_master(tmp_path):
    ref = tmp_path / "0-referensi"
    ref.mkdir()
    assert rekap_bimtek.baca_hotel(tmp_path) == {}
    (ref / "master_bimtek.csv").write_text(
        "﻿NPSN;Nama Sekolah;Tag;Region;Hotel\n1;A;Bimtek Lap 1;Jakarta;Mercure  Ancol\n2;B;Bimtek Lap 5;;\n",
        encoding="utf-8")
    assert rekap_bimtek.baca_hotel(tmp_path) == {"1": ("Mercure Ancol", "Jakarta")}


def test_arsipkan_export(tmp_path, monkeypatch):
    monkeypatch.setattr(rekap_bimtek, "folder", lambda: tmp_path)
    f = rekap_bimtek.arsipkan_export(b"isi", "Export_Konstruksi_Sekolah_20261116_080000.csv")
    assert f == tmp_path / "3-harian" / "Export_Konstruksi_Sekolah_20261116_080000.csv" and f.read_bytes() == b"isi"
    g = rekap_bimtek.arsipkan_export(b"isi2", "cutoff hari ini.xlsx")
    assert g.parent.name == "3-harian" and g.suffix == ".xlsx" and rekap_bimtek.waktu_nama(g.name) is not None
    monkeypatch.setattr(rekap_bimtek, "folder", lambda: tmp_path / "tidak-ada")
    assert rekap_bimtek.arsipkan_export(b"isi", "Export_x_20261116_080000.csv") is None


def test_baca_salinan_lk_setelah_cutoff(tmp_path):
    import json
    f = tmp_path / "lk_cutoff_20261116_014628.json"
    f.write_text(json.dumps({"waktu": "2026-11-16T01:46:28", "file": "Export_x.csv", "sekolah": {
        "1": {"nilai": {"l50": "Sudah", "l50_rev": "Belum"}, "tunggu": {"l50_rev": 9}, "nama": "SD 1", "fasil": "Fa",
              "prov": "Prov. Aceh", "kab": "Kab. X"},
        "2": {"nilai": {"l50": "Sudah", "l50_rev": "Sudah"}, "tunggu": {}, "nama": "SD 2", "fasil": "Fb", "prov": "", "kab": ""},
    }}), encoding="utf-8")
    p = rekap_bimtek.baca_potret(f)
    assert p.lengkap and p.jenis == "cutoff" and p.waktu.day == 16
    assert p.rev50 == {"1": "menunggu", "2": "setuju"} and p.tunggu50 == {"1": 9.0}
    assert p.identitas["1"] == ("SD 1", "Fa", "Aceh", "Kab. X") and p.status["1"]["l50"] == "selesai"



def test_bimtek_aktif_dari_rekap(monkeypatch):
    from datetime import date
    rekap = {"kolom_sekolah": ["npsn", "nama", "hotel"], "kelompok": [
        {"kode": "B3", "tag": "Bimtek Lap 3", "mulai": "2026-11-09", "selesai": "2026-11-13", "sekolah_baris": [["1", "A", "H1"]]},
        {"kode": "B4", "tag": "Bimtek Lap 4", "mulai": "2026-11-16", "selesai": "2026-11-20",
         "sekolah_baris": [["2", "B", "Hotel X"], ["3", "C", ""]]},
    ]}
    monkeypatch.setattr(rekap_bimtek, "baca", lambda: rekap)
    a = rekap_bimtek.bimtek_aktif(date(2026, 11, 17))
    assert list(a) == ["bimtek lap 4"] and a["bimtek lap 4"]["kode"] == "B4" and a["bimtek lap 4"]["hotel"] == {"2": "Hotel X"}
    assert rekap_bimtek.bimtek_aktif(date(2026, 11, 21)) == {}
    monkeypatch.setattr(rekap_bimtek, "baca", lambda: None)
    assert rekap_bimtek.bimtek_aktif(date(2026, 11, 17)) == {}


def test_peta_bimtek_dari_rekap_untuk_cutoff(monkeypatch):
    from app import bimtek_lap
    monkeypatch.setattr(rekap_bimtek, "baca", lambda: {"kolom_sekolah": ["npsn", "nama"], "kelompok": [
        {"kode": "B4", "tag": "Bimtek Lap 4", "sekolah_baris": [["11", "A"], ["12", "B"]]},
        {"kode": "B5", "tag": "Bimtek Lap 5", "sekolah_baris": [["13", "C"]]}]})
    assert bimtek_lap.peta_dari_rekap() == {"11": "Bimtek Lap 4", "12": "Bimtek Lap 4", "13": "Bimtek Lap 5"}
    monkeypatch.setattr(rekap_bimtek, "baca", lambda: None)
    assert bimtek_lap.peta_dari_rekap() == {}
