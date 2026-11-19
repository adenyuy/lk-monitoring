from types import SimpleNamespace

from app import pic_baru


def test_cari_kolom_dan_bersih_nama():
    atas = [["Judul laporan"], ["Tim", "Kode Anggota", "Nama Anggota", "PTN", "Koordinator", "Fasilitator"]]
    assert pic_baru.cari_kolom(atas) == (1, 5, 2, False)
    assert pic_baru.cari_kolom([["Nama Anggota", "Fasilitator", "NPSN"]]) == (0, 1, 0, True)
    assert pic_baru.cari_kolom([["NPSN", "Nama Anggota"]]) is None
    assert pic_baru.bersih_nama(" 1.1  Marvin Nugraha ") == "Marvin Nugraha"
    assert pic_baru.bersih_nama("Raihan Fauzi Nugraha") == "Raihan Fauzi Nugraha"


def test_peta_fasil_satu_fasil_satu_pic():
    nilai = [["Fasil A", "Ani"], ["fasil  a", "ani"], ["Fasil B", "Budi"], ["Fasil B", "Ani"], ["", "Ani"]]
    peta, ganda = pic_baru.peta_fasil(nilai, 0, 1)
    assert peta == {"fasil a": "Ani"} and ganda == {"Fasil B"}


def _s(npsn, pic, fasil, baris):
    return SimpleNamespace(npsn=npsn, petugas=pic, nama=f"SD {npsn}", fasil=fasil, baris=baris)


def test_rencana_pic_ikut_fasil(monkeypatch):
    sekolah = [_s("1", "", "Fasil A", 4), _s("2", "Ani", "Fasil A", 5), _s("3", "Ani", "Fasil B", 6),
               _s("4", "Ani", "Fasil Baru", 7), _s("5", "", "Fasil X", 8)]
    peta = {"fasil a": "Ani", "fasil b": "Budi", "fasil x": "Orang Asing"}
    monkeypatch.setattr(pic_baru, "baca_pembagian", lambda link: ("File", "Fasilitator per Anggota", peta, set()))
    monkeypatch.setattr(pic_baru.lk_baru, "week_aktif", lambda: 3)
    monkeypatch.setattr(pic_baru.lk_baru, "tab_week", lambda w: f"WEEK {w}")
    monkeypatch.setattr(pic_baru.lk_baru, "baca_semua", lambda w, refresh=False: sekolah)
    monkeypatch.setattr(pic_baru.lk_baru, "daftar_petugas", lambda: [{"nama": "Ani"}, {"nama": "Budi"}])
    r = pic_baru.rencana("x")
    assert [(x["npsn"], x["pic_lama"], x["pic"]) for x in r["ubah"]] == [("1", "", "Ani"), ("3", "Ani", "Budi")]
    assert r["tanpa"] == [{"fasil": "Fasil Baru", "sekolah": 1}]  # PIC lama dibiarkan
    assert r["asing"] == ["Orang Asing"] and r["akan_ditulis"] == 2
