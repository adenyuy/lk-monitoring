from types import SimpleNamespace

from app import pic_baru


def test_cari_kolom_dan_bersih_nama():
    atas = [["Judul laporan"], ["No", "Tim", "Kode Anggota", "Nama Anggota", "PTN", "NPSN"]]
    assert pic_baru.cari_kolom(atas) == (1, 5, 3)
    assert pic_baru.cari_kolom([["NPSN", "Nama Sekolah"]]) is None
    assert pic_baru.bersih_nama(" 1.1  Marvin Nugraha ") == "Marvin Nugraha"
    assert pic_baru.bersih_nama("Raihan Fauzi Nugraha") == "Raihan Fauzi Nugraha"


def _s(npsn, pic, baris):
    return SimpleNamespace(npsn=npsn, petugas=pic, nama=f"SD {npsn}", fasil="", baris=baris)


def test_rencana_isi_kosong_dan_beda(monkeypatch):
    sekolah = [_s("1", "", 4), _s("2", "Ani", 5), _s("3", "Ani", 6), _s("4", "", 7), _s("5", "", 8)]
    peta = {"1": "Budi", "2": "Ani", "3": "Budi", "5": "Orang Asing"}
    monkeypatch.setattr(pic_baru, "baca_pembagian", lambda link: ("File", "Penugasan Anggota", peta))
    monkeypatch.setattr(pic_baru.lk_baru, "week_aktif", lambda: 3)
    monkeypatch.setattr(pic_baru.lk_baru, "tab_week", lambda w: f"WEEK {w}")
    monkeypatch.setattr(pic_baru.lk_baru, "baca_semua", lambda w, refresh=False: sekolah)
    monkeypatch.setattr(pic_baru.lk_baru, "daftar_petugas", lambda: [{"nama": "Ani"}, {"nama": "Budi"}])
    r = pic_baru.rencana("x")
    assert [x["npsn"] for x in r["isi"]] == ["1"] and r["isi"][0]["pic"] == "Budi"
    assert [(x["npsn"], x["pic_lama"], x["pic"]) for x in r["beda"]] == [("3", "Ani", "Budi")]
    assert [x["npsn"] for x in r["tanpa"]] == ["4"]
    assert r["asing"] == ["Orang Asing"] and r["akan_ditulis"] == 1
    assert pic_baru.rencana("x", ganti_beda=True)["akan_ditulis"] == 2
