from datetime import date
from types import SimpleNamespace

from app import lk_baru, paparan


def _kom(n_fasil, log):
    f = {f"f{i}": SimpleNamespace(nama=f"Fasil {i}", sekolah=[SimpleNamespace(npsn=str(i))]) for i in range(n_fasil)}
    kode = {str(i): ({"2026-11-02": "T", "2026-10-27": "R"} if i % 3 == 0 else {"2026-11-03": "C"}) for i in range(n_fasil)}
    tgl = {d: 4 + j for j, d in enumerate(["2026-10-26", "2026-10-27", "2026-10-28", "2026-11-02", "2026-11-03"])}
    lk = lk_baru.LogKom(tgl if log else {}, {}, kode if log else {})
    return paparan.komunikasi_mingguan(f, lk, date(2026, 11, 4))


def _data(n_fasil=30, n_masalah=12, log=True):
    fasil = [{"nama": f"Fasil {i}", "ptn": "Univ. Contoh", "koor": "Koor A", "sekolah": 5, "perlu": 3, "todo": 6,
              "selesai": i, "relevan": 40, "persen": round(i / 40 * 100), "progres": 40.0, "kom": "belum",
              "masalah": ["Reviu tertahan 5 hari"] if i < n_masalah else [], "saran": "Ingatkan fasil",
              "kategori": ["reviu"] if i < n_masalah else []} for i in range(n_fasil)]
    masalah = [f for f in fasil if f["masalah"]]
    return {
        "pic": "Petugas Uji", "week": 3, "cutoff": "Cutoff 2 (05/11)", "tanggal": "Kamis, 5 November 2026",
        "dibuat": "05/11 10.00",
        "profil": {"sekolah": 150, "fasil": n_fasil, "koor": 4, "jml_ptn": 2, "jml_kab": 9,
                   "rata_sekolah_per_fasil": 5.0, "maks_sekolah_per_fasil": 9,
                   "angkatan": [{"nama": "Angkatan 1", "jumlah": 80}, {"nama": "Angkatan 2", "jumlah": 70}],
                   "provinsi": [{"nama": "Kepulauan Bangka Belitung", "jumlah": 150}],
                   "kab": [], "ptn": [{"nama": "Universitas Contoh Panjang Sekali", "jumlah": 150}]},
        "fasil": fasil,
        "komunikasi": _kom(n_fasil, log),
        "bottleneck": {
            "posisi": [{"kode": "lp", "label": "Lap. Pendahuluan belum dikirim", "sekolah": 40, "fasil": 9},
                       {"kode": "mg", "label": "Lap. Mingguan", "sekolah": 12, "fasil": 4}],
            "reviu": {"rata": 4.2, "lewat3": 7, "menunggu": 20},
            "kendala": [{"teks": "Sekolah belum mengakses aplikasi", "sekolah": 5}],
            "sekolah_todo": 60, "sekolah": 150,
        },
        "masalah": masalah,
        "progres": {"ada": True, "label": "WEEK 3", "label_lalu": "WEEK 2", "per_komponen": True, "tambah": 40, "fasil": n_fasil, "fasil_naik": 12,
                    "fasil_diam": 6, "teratas": [{"nama": f"Fasil {i}", "tambah": 9 - i} for i in range(5)],
                    "diam": ["Fasil 7", "Fasil 8", "Fasil 9", "Fasil 10"],
                    "komponen": [{"kode": k.kode, "label": k.label, "lalu": 20.0, "kini": 35.0, "selisih": 15.0}
                                 for k in lk_baru.KOMPONEN]},
        "kategori": [{"kode": k, "label": lbl, "fasil": len(masalah) if k == "reviu" else 0}
                     for k, lbl in paparan.KATEGORI],
        "sebaran_fasil": [{"nama": "0–24%", "jumlah": 10}, {"nama": "25–49%", "jumlah": 10},
                          {"nama": "50–74%", "jumlah": 10}, {"nama": "75–99%", "jumlah": 0},
                          {"nama": "100%", "jumlah": 0}],
    }


def test_enam_slide_utama_satu_halaman():
    slides = paparan.susun(_data(), [k for k, _ in paparan.SLIDE if k not in paparan.BAWAAN_MATI])
    assert [s["kunci"] for s in slides] == ["profil", "fasil", "progres", "komunikasi", "bottleneck", "masalah",
                                              "langkah"]


def test_lampiran_dipecah_per_halaman():
    slides = paparan.susun(_data(n_fasil=30, n_masalah=12), ["lampiran"])
    assert len(slides) == 3 + 2  # 30 fasil / 12 per halaman + 12 masalah / 7 per halaman
    assert slides[0]["catatan"] and not slides[1]["catatan"]
    assert all(s["lanjutan"] for s in slides[1:])


def test_semua_bentuk_muat_di_halaman():
    for log in (True, False):
        for s in paparan.susun(_data(log=log)):
            for b in s["bentuk"]:
                assert b["x"] >= 0 and b["y"] >= 0
                assert b["x"] + b.get("w", 0) <= paparan.W + 0.5, (s["kunci"], b)
                if b["t"] != "table":
                    assert b["y"] + b["h"] <= paparan.H + 0.5, (s["kunci"], b)
                    assert b["w"] > 0 and b["h"] > 0
                else:
                    assert abs(sum(c["w"] for c in b["cols"]) - b["w"]) < 1
                    assert all(c["w"] >= 32 for c in b["cols"])  # batas minimum lebar kolom Google Slides


def test_langkah_dan_catatan_bisa_diubah():
    d = _data()
    slides = paparan.susun(d, ["langkah", "profil"], ["Poin satu", "Poin dua"], {"profil": "Catatan saya"})
    assert [s["kunci"] for s in slides] == ["langkah", "profil"]
    teks = [b for b in slides[0]["bentuk"] if b.get("ubah") == "langkah"][0]
    assert teks["text"] == "Poin satu\nPoin dua" and teks["bullets"]
    assert slides[1]["catatan"] == "Catatan saya"


def test_langkah_awal_dari_data():
    out = paparan.langkah_awal(_data())
    assert any("Lap. Pendahuluan" in x or "lap. pendahuluan" in x for x in out)
    assert any("reviu" in x.lower() for x in out)


def test_permintaan_slides_id_unik_dan_lengkap():
    nomor = [0]
    req = []
    for i, s in enumerate(paparan.susun(_data())):
        req += paparan._permintaan(f"lkm{i:02d}", s["bentuk"], nomor)
    ids = [list(r.values())[0]["objectId"] for r in req if "createShape" in r or "createTable" in r]
    assert len(ids) == len(set(ids))
    assert all(5 <= len(x) <= 50 for x in ids)
    jenis = {list(r)[0] for r in req}
    assert {"createShape", "insertText", "updateTextStyle", "createTable", "createParagraphBullets",
            "updateTableBorderProperties"} <= jenis


def test_masalah_kategori():
    x = {"perlu": 2, "kom": "dibaca", "belum_ditelepon": False, "tanpa_progres": True, "tunggu_maks": 6.0,
         "todo": 3, "sekolah": 4, "fokus": []}
    alasan, saran, kat = paparan._masalah(x, 10)
    assert kat == ["sulit", "macet", "reviu", "rendah"]
    assert saran.startswith("Telepon")
    ok = {**x, "kom": "terhubung", "tanpa_progres": False, "tunggu_maks": 1.0}
    assert paparan._masalah(ok, 80) == ([], "", [])


def test_komunikasi_mingguan_banding_hari_yang_sama():
    k = _kom(9, True)
    assert k["sampai"] == "Rabu"
    ini, lalu = k["minggu"][0], k["minggu"][1]
    assert ini["rentang"] == "02/11–04/11" and lalu["rentang"] == "26/10–28/10"
    assert ini["grup"]["terhubung"] == 3 and ini["grup"]["centang"] == 6 and ini["dihubungi"] == 9
    assert lalu["grup"]["dibaca"] == 3 and lalu["grup"]["belum"] == 6
    centang = [x for x in k["kendala"] if x["kode"] == "centang"][0]
    assert centang["jumlah"] == 6 and centang["lalu"] == 0 and len(centang["contoh"]) == 3


def test_komunikasi_tanpa_log():
    k = _kom(4, False)
    assert len(k["minggu"]) == 1 and not k["minggu"][0]["ada_log"] and k["minggu"][0]["grup"]["belum"] == 4


def test_ubahan_teks_dan_sel_tabel():
    d = _data()
    slides = paparan.susun(d, ["profil", "fasil"])
    i_judul = next(i for i, b in enumerate(slides[0]["bentuk"]) if b["t"] == "text" and b["text"] == "Profil sekolah binaan")
    i_tabel = next(i for i, b in enumerate(slides[1]["bentuk"]) if b["t"] == "table")
    sel = slides[1]["bentuk"][i_tabel]["rows"][0][0]
    out = paparan.terapkan_ubahan(slides, [
        {"kunci": "profil", "halaman": 0, "bentuk": i_judul, "asli": "Profil sekolah binaan", "baru": "Profil binaan"},
        {"kunci": "fasil", "halaman": 0, "bentuk": i_tabel, "sel": [0, 0], "asli": sel, "baru": "Nama baru"},
        {"kunci": "fasil", "halaman": 0, "bentuk": i_tabel, "sel": [-1, 1], "asli": "Sekolah", "baru": "Jml sekolah"},
        {"kunci": "profil", "halaman": 0, "bentuk": i_judul + 1, "asli": "teks lama", "baru": "diabaikan"},
        {"kunci": "profil", "halaman": 5, "bentuk": 0, "asli": "x", "baru": "y"},
    ])
    assert out[0]["bentuk"][i_judul]["text"] == "Profil binaan"
    assert out[0]["bentuk"][i_judul + 1]["text"] != "diabaikan"
    assert out[1]["bentuk"][i_tabel]["rows"][0][0] == "Nama baru"
    assert out[1]["bentuk"][i_tabel]["cols"][1]["label"] == "Jml sekolah"


def test_slide_progres_tanpa_week_lalu():
    d = {**_data(), "progres": {"ada": False, "label": "WEEK 1", "label_lalu": None}}
    s = paparan.susun(d, ["progres"])[0]
    assert any("Belum ada pembanding" in b.get("text", "") for b in s["bentuk"])
    assert "Belum ada periode" in paparan.catatan_awal(d)["progres"]


def test_catatan_dan_langkah_progres():
    d = _data()
    assert "bertambah 40 komponen" in paparan.catatan_awal(d)["progres"]
    assert any("belum bergerak sejak WEEK 2" in x for x in paparan.langkah_awal(d))


def test_banding_progres_per_fasil_dan_komponen():
    f = {"a": SimpleNamespace(nama="Ani", sekolah=[SimpleNamespace(npsn="1"), SimpleNamespace(npsn="2")]),
         "b": SimpleNamespace(nama="Budi", sekolah=[SimpleNamespace(npsn="3")])}
    lalu = {"1": {"lp": ("belum", None), "progres": ("belum", 20.0)}, "2": {"lp": ("selesai", None)},
            "3": {"lp": ("belum", None)}}
    kini = {"1": {"lp": ("selesai", None), "progres": ("belum", 40.0)}, "2": {"lp": ("selesai", None)},
            "3": {"lp": ("belum", None)}}
    pg = paparan.banding_progres(kini, lalu, {n: paparan._jml_selesai(x) for n, x in lalu.items()}, f,
                                 "Cutoff 2 (05/11)", "Cutoff 1 (04/11)")
    assert pg["tambah"] == 1 and pg["fasil_naik"] == 1 and pg["teratas"][0]["nama"] == "Ani"
    assert pg["diam"] == ["Budi"]
    lp = next(k for k in pg["komponen"] if k["kode"] == "lp")
    assert round(lp["lalu"]) == 33 and round(lp["kini"]) == 67 and round(lp["selisih"]) == 33
    pr = next(k for k in pg["komponen"] if k["kode"] == "progres")
    assert pr["lalu"] == 20.0 and pr["kini"] == 40.0
    # tanpa snapshot per komponen (hanya jumlah selesai): per fasil tetap jalan
    pg2 = paparan.banding_progres(kini, None, {"1": 0, "2": 1, "3": 0}, f, "Cutoff 2", "Cutoff 1")
    assert pg2["tambah"] == 1 and not pg2["per_komponen"] and all(k["lalu"] is None for k in pg2["komponen"])
