import json

from fastapi.testclient import TestClient

from app import paths
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_startup_jalan(monkeypatch):
    """Lifespan aplikasi (startup/shutdown) harus jalan; kerja latarnya diganti tiruan."""
    from app import main
    dipanggil = []
    monkeypatch.setattr(main.chat_refresh, "start_background", lambda: dipanggil.append("chat"))
    monkeypatch.setattr(main.lk_otomatis, "picu", lambda: dipanggil.append("lk"))
    monkeypatch.setattr(main, "susulkan_riwayat", lambda: dipanggil.append("riwayat"))
    monkeypatch.setattr(main.worker, "shutdown", lambda: None)
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
    assert sorted(dipanggil) == ["chat", "lk", "riwayat"]


def test_me_belum_login():
    body = client.get("/api/me").json()
    assert body["logged_in"] is False
    assert body["settings"]["batas_harian"] == 40


def test_endpoint_api_tidak_ada():
    r = client.get("/api/tidak-ada")
    assert r.status_code == 404 and "tidak ada" in r.json()["detail"]


def test_endpoint_wajib_login():
    assert client.get("/api/petugas").status_code == 401
    assert client.get("/api/settings").status_code == 401


def test_upload_credentials_validasi():
    bad = client.post("/api/setup/credentials", files={"file": ("x.json", b'{"web": {}}', "application/json")})
    assert bad.status_code == 400 and "installed" in bad.json()["detail"]
    good = client.post(
        "/api/setup/credentials",
        files={"file": ("credentials.json", json.dumps({"installed": {"client_id": "x"}}).encode(), "application/json")},
    )
    assert good.status_code == 200
    assert paths.CREDENTIALS_FILE.exists()
    assert client.get("/api/me").json()["needs_credentials"] is False


def test_tampilan_dan_path_traversal():
    if not paths.WEB_OUT_DIR.exists():
        return  # web belum dibangun di lingkungan ini
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
    assert client.get("/../backend/app/config.py").status_code == 404


def test_keluar_mengulang_persiapan(monkeypatch):
    from app import db, google_auth
    from app.routers import core
    from app.sender import sender

    db.set_setting("setup_selesai", True)
    monkeypatch.setattr(google_auth, "logout", lambda: None)
    monkeypatch.setattr(sender.state, "running", True)
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        core.logout()
    assert db.get_setting("setup_selesai") is True
    monkeypatch.setattr(sender.state, "running", False)
    assert core.logout() == {"ok": True}
    assert db.get_setting("setup_selesai") is False


def test_tolak_permintaan_dari_situs_lain():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    assert c.post("/api/auth/logout", headers={"Origin": "https://situs-jahat.example"}).status_code == 403
    assert c.get("/api/health", headers={"Host": "jahat.example:8787"}).status_code == 403
    assert c.get("/api/health", headers={"Host": "127.0.0.1:8787"}).status_code == 200
    r = c.post("/api/settings", json={}, headers={"Origin": "http://127.0.0.1:8787"})
    assert r.status_code != 403


def test_pembaruan_tidak_aktif_di_folder_develop():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/pembaruan").json()
    assert r["aktif"] is False and r["ada_baru"] is False
    assert c.post("/api/pembaruan/pasang").status_code == 400


def test_paket_lk_monitoring_memasang_alamat_sheet(monkeypatch):
    import json

    from app import config, google_auth, paths

    for k in ("BROADCAST", "LK", "ACCESS"):
        monkeypatch.delenv(f"LKM_{k}_SHEET_ID", raising=False)
    f = paths.DATA_DIR / "sheets.json"
    f.unlink(missing_ok=True)
    cred = {"installed": {"client_id": "x", "client_secret": "y"}}
    try:
        google_auth.save_credentials(json.dumps(cred).encode())
        assert False, "credentials.json tanpa alamat sheet harus ditolak"
    except ValueError as e:
        assert "lk-monitoring.json" in str(e)
    paket = dict(cred, lkm_sheets={
        "broadcast": "https://docs.google.com/spreadsheets/d/AAAAAAAAAAAAAAAAAAAAAAAAAAAA/edit#gid=0",
        "lk": "BBBBBBBBBBBBBBBBBBBBBBBBBBBB", "akses": "CCCCCCCCCCCCCCCCCCCCCCCCCCCC"})
    google_auth.save_credentials(json.dumps(paket).encode())
    assert config.BROADCAST_SHEET_ID == "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert config.sheet_ids()["akses"] == "CCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    assert "lkm_sheets" not in json.loads(paths.CREDENTIALS_FILE.read_text())
    assert google_auth.has_credentials()
    f.unlink()
    paths.CREDENTIALS_FILE.unlink()


def test_bypass_wajib_kalimat_risiko(monkeypatch):
    from fastapi.testclient import TestClient
    from app import db
    from app.main import app
    from app.routers import send

    app.dependency_overrides[send.wa_blast] = lambda: None
    monkeypatch.setattr(send, "_kondisi", lambda: {})
    try:
        c = TestClient(app)
        assert c.post("/api/send/bypass", json={"aktif": True}).status_code == 400
        r = c.post("/api/send/bypass", json={"aktif": True, "konfirmasi": " Risiko ditanggung sendiri "})
        assert r.status_code == 200 and db.get_setting("bypass_sesi")
        assert c.post("/api/send/bypass", json={"aktif": False}).status_code == 200
        assert db.get_setting("bypass_sesi") is None
    finally:
        app.dependency_overrides.clear()
