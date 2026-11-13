from app import bimtek_lap, cutoff_baru, lk_baru
from app.lk_baru import Sekolah, parse_tata


def _s(npsn: str, bimtek: str = "", petugas: str = "Ani") -> Sekolah:
    return Sekolah(4, petugas, npsn, f"SD {npsn}", "1", "", "", "", "", "", "", "", "Fasil", "", bimtek=bimtek)


def test_cari_kolom_dan_peta():
    atas = [["Daftar"], ["NPSN", "Nama Sekolah", "Provinsi", "Kab/Kota", "Tag", "Helper"]]
    assert bimtek_lap.cari_kolom(atas) == (1, 0, 4)
    assert bimtek_lap.cari_kolom([["NPSN", "Bimtek Pelaporan"]]) == (0, 0, 1)
    assert bimtek_lap.cari_kolom([["NPSN", "Nama"]]) is None
    nilai = [["10107863", "SD A", "", "", "Bimtek Lap 1"], ["10107909.0", "SD B", "", "", " Bimtek  Lap 2 "],
             ["", "kosong"], ["123", "SD C"]]
    assert bimtek_lap.peta_dari_nilai(nilai, 0, 4) == {"10107863": "Bimtek Lap 1", "10107909": "Bimtek Lap 2"}


def test_urut_angka():
    assert sorted(["Bimtek Lap 10", "Bimtek Lap 2", "Bimtek Lap 1"], key=bimtek_lap.urut) == [
        "Bimtek Lap 1", "Bimtek Lap 2", "Bimtek Lap 10"]


def test_bandingkan():
    lk = [_s("1"), _s("2", "Bimtek Lap 1"), _s("3", "Bimtek Lap 1"), _s("4")]
    peta = {"1": "Bimtek Lap 2", "2": "Bimtek Lap 1", "3": "Bimtek Lap 3", "9": "Bimtek Lap 1"}
    b = bimtek_lap.bandingkan(lk, peta)
    assert [x["npsn"] for x in b["isi"]] == ["1"]
    assert b["beda"][0]["npsn"] == "3" and b["beda"][0]["bimtek_lama"] == "Bimtek Lap 1"
    assert b["tanpa"] == [{"npsn": "9", "bimtek": "Bimtek Lap 1"}]


def test_cocok_filter():
    a, b = _s("1", "Bimtek Lap 1"), _s("2")
    assert bimtek_lap.cocok(a, "") and bimtek_lap.cocok(b, "")
    assert bimtek_lap.cocok(a, "bimtek lap 1") and not bimtek_lap.cocok(b, "Bimtek Lap 1")
    assert bimtek_lap.cocok(b, "-") and not bimtek_lap.cocok(a, "-")


def test_parse_tata_kolom_bimtek_opsional():
    wajib = [j for j, f in lk_baru.IDENTITAS.items() if f not in lk_baru.IDENTITAS_OPSIONAL]

    def susun(identitas: list[str]):
        r3 = identitas + [k.judul for k in lk_baru.KOMPONEN]
        r3 += [""] * (40 - len(r3))
        r1 = [""] * 40 + ["SESI 1 (Senin–Rabu)"] + [""] * 25 + ["SESI 2 (Kamis–Sabtu)"] + [""] * 25
        r2 = [""] * 40
        for _ in range(2):
            for k in lk_baru.KOMPONEN:
                r2 += [k.pasangan, ""]
                r3 += ["Kendala", "Tindak Lanjut"]
        return parse_tata(r1, r2, r3)

    assert "bimtek" not in susun(wajib).identitas
    i = wajib.index("Angkatan") + 1
    t = susun(wajib[:i] + ["Bimtek Pelaporan"] + wajib[i:])
    assert t.identitas["bimtek"] == i and t.identitas["provinsi"] == i + 1


def test_baris_log_bimtek():
    xs = [_s("1", "Bimtek Lap 2", "Ani"), _s("2", "Bimtek Lap 1", "Budi"), _s("3", "Bimtek Lap 1", "Ani"), _s("4")]
    rows = cutoff_baru.baris_bimtek(xs, "Cutoff 5 (13/11)")
    kunci = [(r[1], r[2], r[3]) for r in rows]
    assert kunci == [("Bimtek Lap 1", "(semua)", 2), ("Bimtek Lap 1", "Ani", 1), ("Bimtek Lap 1", "Budi", 1),
                     ("Bimtek Lap 2", "(semua)", 1), ("Bimtek Lap 2", "Ani", 1)]
    assert all(len(r) == len(cutoff_baru.JUDUL_BIMTEK) for r in rows)


def test_baca_file_csv_titik_koma():
    data = ("NPSN;Nama Sekolah;Provinsi;Kab/Kota;Tag;Helper\n"
            "10107863;SD A;Prov. Aceh;Kab. X;Bimtek Lap 1;1\n10107909;SD B;Prov. Aceh;Kab. X;Bimtek Lap 2;1\n").encode("utf-8-sig")
    nama, tab, peta = bimtek_lap.baca_file(data, "daftar.csv")
    assert (nama, tab) == ("daftar.csv", "CSV")
    assert peta == {"10107863": "Bimtek Lap 1", "10107909": "Bimtek Lap 2"}
    _, _, peta = bimtek_lap.baca_file(b"npsn,bimtek pelaporan\n1,Bimtek Lap 3\n", "x.csv")
    assert peta == {"1": "Bimtek Lap 3"}


def test_baca_file_excel_dan_salah():
    import io

    import openpyxl
    import pytest

    wb = openpyxl.Workbook()
    wb.active.title = "Catatan"
    wb.active.append(["bukan daftar"])
    ws = wb.create_sheet("Daftar")
    ws.append(["Judul"])
    ws.append(["NPSN", "Nama", "Tag"])
    ws.append([10107863, "SD A", "Bimtek Lap 10"])
    buf = io.BytesIO()
    wb.save(buf)
    _, tab, peta = bimtek_lap.baca_file(buf.getvalue(), "d.xlsx")
    assert tab == "Daftar" and peta == {"10107863": "Bimtek Lap 10"}
    with pytest.raises(bimtek_lap.BimtekLapError):
        bimtek_lap.baca_file(b"a;b\n1;2\n", "x.csv")
    with pytest.raises(bimtek_lap.BimtekLapError):
        bimtek_lap.baca_file(b"%PDF", "x.pdf")


def test_csv_asli_bila_ada():
    from pathlib import Path

    f = Path(__file__).resolve().parents[2] / "docs" / "knowledge" / \
        "260724_Perhitungan Sekolah ABT2 - Revit SD 2026 - Daftar Bimtek Pelaporan.csv"
    if not f.exists():
        return
    _, _, peta = bimtek_lap.baca_file(f.read_bytes(), f.name)
    assert len(peta) == 6432 and set(peta.values()) == {"Bimtek Lap 1", "Bimtek Lap 2", "Bimtek Lap 3"}


def test_simpan_file_dan_sumber(tmp_path, monkeypatch):
    from app import db, paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    simpan = {}
    monkeypatch.setattr(db, "set_setting", lambda k, v: simpan.__setitem__(k, v))
    monkeypatch.setattr(db, "get_setting", lambda k, d=None: simpan.get(k, d))
    assert bimtek_lap.sumber_terakhir() == "" and bimtek_lap.file_tersimpan() is None
    bimtek_lap.simpan_file("d.csv", "CSV", {"1": "Bimtek Lap 1"})
    assert bimtek_lap.sumber_terakhir() == "file"
    assert bimtek_lap.file_tersimpan() == ("d.csv", "CSV", {"1": "Bimtek Lap 1"})


def test_susun_legenda_c2():
    lama = [["T", "Respon baik"], ["C", "Centang satu"], ["N", "Tidak terhubung"], ["(kosong)", "Belum dihubungi"], [], []]
    baru = lk_baru.susun_legenda(lama, "C2", "Centang dua", setelah="C")
    assert [r[0] for r in baru] == ["T", "C", "C2", "N", "(kosong)"]
    assert lk_baru.susun_legenda(baru, "C2", "x", setelah="C") is None          # sudah ada: tidak diubah
    tanpa_c = lk_baru.susun_legenda([["T", "a"], ["(kosong)", "b"]], "C2", "x", setelah="C")
    assert [r[0] for r in tanpa_c] == ["T", "C2", "(kosong)"]
