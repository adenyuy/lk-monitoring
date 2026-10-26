from app import sheets, tahap

BARIS = ["P", "11112222", "SD A", "Kab", "Fasil", "6281200000001", "Prioritas 1", "", 0.3, "Tidak", "Tidak",
         0.3, "Tidak", "Tidak"] + [""] * 12


def _sekolah(**ubah):
    s = sheets.parse_lk([BARIS])[0]
    for k, v in ubah.items():
        setattr(s, k, v)
    return s


def test_grup_relevan():
    assert tahap.grup_relevan(_sekolah()) == ["a", "b"]
    assert tahap.grup_relevan(_sekolah(progres=70.0, submit="Ya", reviu="Tidak")) == ["c"]
    assert tahap.grup_relevan(_sekolah(progres=70.0, submit="Ya", reviu="Ya")) == []


def test_lengkap_butuh_komunikasi_dan_alasan():
    s = _sekolah()
    assert not tahap.sekolah_lengkap(s, 1)
    s.komunikasi = "0. Terhubung"
    s.isian[1].update(a1="x", b1="y")
    assert tahap.sekolah_lengkap(s, 1) and not tahap.sekolah_lengkap(s, 2)


def test_tahap_otomatis_dan_manual():
    s = _sekolah()
    sends = [{"status": "terkirim", "coba": 0}]
    t = {x["kode"]: x["selesai"] for x in tahap.hitung("62", [s], sends, {"status": "dibaca"}, {}, 1)}
    assert t == {"terkirim": True, "dibaca": True, "dibalas": False, "ditanya": False, "lk_lengkap": False}
    manual = {"ditanya": {"nilai": True, "sumber": "manual", "waktu": "x"}}
    t = {x["kode"]: x["selesai"] for x in tahap.hitung("62", [s], [], None, manual, 1)}
    assert t["ditanya"] and not t["terkirim"]
