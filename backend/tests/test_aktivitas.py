from app import aktivitas, db, store
from app.main import app
from fastapi.testclient import TestClient


def _bersih():
    with db.tx() as c:
        c.execute("DELETE FROM aktivitas")
        c.execute("DELETE FROM sends")
        c.execute("DELETE FROM chat_status")


def test_riwayat_fasil_gabung_kirim_dan_kejadian(monkeypatch):
    _bersih()
    monkeypatch.setattr(aktivitas, "_nama_map", lambda: {"6281200000001": "Fasil A"})
    with db.tx() as c:
        c.execute("INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status) VALUES(?,?,?,?,?,?,?)",
                  ("2026-10-26", "2026-10-26T10:05:00", 1, "Fasil A", "6281200000001", "h", "terkirim"))
    store.save_chat_status("6281200000001", "dibaca", "", "2026-10-26T10:30:00")
    store.save_chat_status("6281200000001", "dibalas", "Siap, segera saya cek", "2026-10-26T11:00:00")
    store.save_chat_status("6281200000001", "dibalas", "Siap, segera saya cek", "2026-10-26T11:05:00")  # sama
    aktivitas.catat("6281200000001", "lk", "Sesi Senin–Rabu: 2 sekolah disimpan")
    r = aktivitas.daftar(nomor="6281200000001")
    assert [x["jenis"] for x in r][-1] == "kirim"
    assert sorted(x["jenis"] for x in r) == ["dibaca", "dibalas", "kirim", "lk"]
    assert all(x["nama"] == "Fasil A" for x in r)
    assert next(x for x in r if x["jenis"] == "kirim")["sesi"] == 1
    _bersih()


def test_batas_di_atas_aman_wajib_konfirmasi(monkeypatch):
    from app.routers import deps

    app.dependency_overrides[deps.require_login] = lambda: "uji@contoh.id"
    try:
        c = TestClient(app)
        r = c.post("/api/settings", json={"batas_harian": 60})
        assert r.status_code == 400
        r = c.post("/api/settings", json={"batas_harian": 60, "konfirmasi_risiko": "  Risiko ditanggung  SENDIRI "})
        assert r.status_code == 200
        assert db.get_setting("batas_harian") == 60
        assert c.post("/api/settings", json={"batas_harian": 45}).status_code == 200
    finally:
        app.dependency_overrides.clear()
        db.set_setting("batas_harian", 40)
