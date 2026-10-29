from app import sheets, tahap

BARIS = ["P", "11112222", "SD A", "Kab", "Fasil", "6281200000001", "Prioritas 1", "", 0.3, "Tidak", "Tidak",
         0.3, "Tidak", "Tidak"] + [""] * 12


def _sekolah(**ubah):
    s = sheets.parse_lk([BARIS])[0]
    for k, v in ubah.items():
        setattr(s, k, v)
    return s


def test_grup_relevan():
    assert tahap.grup_relevan(_sekolah()) == ["a", "b", "c"]
    # progres sudah >= 50%: alasan progres tidak perlu
    assert tahap.grup_relevan(_sekolah(progres=82.6, submit="Tidak", reviu="Tidak")) == ["b", "c"]


def test_lengkap_butuh_komunikasi_dan_alasan():
    s = _sekolah()
    assert not tahap.sekolah_lengkap(s, 1)
    s.komunikasi = "0. Terhubung"
    s.isian[1].update(a1="x", b1="y")
    assert not tahap.sekolah_lengkap(s, 1)  # alasan reviu (c) juga wajib
    s.isian[1].update(c1="z")
    assert tahap.sekolah_lengkap(s, 1) and not tahap.sekolah_lengkap(s, 2)


def test_tahap_otomatis_dan_manual(monkeypatch):
    monkeypatch.setenv("LKM_FAKE_NOW", "2026-10-28 10:00")  # Rabu; Senin = 2026-10-26
    s = _sekolah()
    kontak = {"terkirim": True, "dibaca": True, "dibalas": False}
    t = {x["kode"]: x["selesai"] for x in tahap.hitung("62", [s], kontak, {}, 1)}
    assert t == {"terkirim": True, "dibaca": True, "dibalas": False, "ditanya": False, "lk_lengkap": False}
    manual = {"ditanya": {"nilai": True, "sumber": "manual", "waktu": "2026-10-27T09:00:00"},
              "dibalas": {"nilai": True, "sumber": "manual", "waktu": "2026-10-20T09:00:00"}}  # minggu lalu
    t = {x["kode"]: x["selesai"] for x in tahap.hitung("62", [s], None, manual, 1)}
    assert t["ditanya"] and not t["terkirim"] and not t["dibalas"]


def test_kontak_minggu_mulai_dari_nol_tiap_senin(monkeypatch):
    from app import db, store

    monkeypatch.setenv("LKM_FAKE_NOW", "2026-10-28 10:00")
    with db.tx() as c:
        for tbl in ("sends", "aktivitas", "chat_status"):
            c.execute(f"DELETE FROM {tbl}")
        ins = "INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status) VALUES(?,?,?,?,?,?,?)"
        c.execute(ins, ("2026-10-21", "2026-10-21T10:00:00", 1, "A", "621", "h", "terkirim"))  # minggu lalu
        c.execute(ins, ("2026-10-26", "2026-10-26T10:00:00", 1, "B", "622", "h", "terkirim"))
    store.save_chat_status("621", "dibalas", "lama", "2026-10-21T11:00:00")
    store.save_chat_status("622", "dibalas", "baru", "2026-10-26T11:00:00")
    with db.tx() as c:
        c.execute("INSERT INTO aktivitas(waktu, nomor, nama, jenis, ringkasan) VALUES(?,?,?,?,?)",
                  ("2026-10-27T09:00:00", "623", "C", "balas", "Pesan: halo"))  # fasil di luar Broadcast
    k = tahap.kontak_minggu()
    assert "621" not in k or not k["621"]["terkirim"]
    assert k["622"]["dibalas"] and k["623"]["terkirim"] and not k["623"]["dibalas"]
    with db.tx() as c:
        for tbl in ("sends", "aktivitas", "chat_status"):
            c.execute(f"DELETE FROM {tbl}")


def test_tahap_kini_ambil_tahap_terjauh():
    from app.routers.rekap import _tahap_kini

    def t(*kode):
        return [{"kode": k, "selesai": k in kode} for k in ("terkirim", "dibaca", "dibalas", "ditanya", "lk_lengkap")]

    assert _tahap_kini(t(), 3, None) == "belum"
    assert _tahap_kini(t(), 3, {"gagal": True}) == "gagal"
    assert _tahap_kini(t("terkirim", "dibaca"), 3, None) == "dibaca"
    assert _tahap_kini(t("terkirim", "ditanya"), 3, None) == "ditanya"  # balasan lewat HP belum terdeteksi
    assert _tahap_kini(t("lk_lengkap"), 3, None) == "lk_lengkap"
    assert _tahap_kini(t(), 0, None) == "selesai"
