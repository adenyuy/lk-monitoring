import json

from fastapi.testclient import TestClient

from app import paths
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


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
