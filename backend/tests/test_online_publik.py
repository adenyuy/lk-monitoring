"""Dashboard online: hanya Timeline yang terbuka tanpa login; halaman lain tetap 401."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dasbor_online import app as online  # noqa: E402
from app import timeline  # noqa: E402


def test_timeline_publik_lainnya_wajib_login(monkeypatch):
    monkeypatch.setattr(timeline, "baca", lambda: {"minggu": [], "komponen": []})
    c = TestClient(online.app)
    assert c.get("/api/dashboard/timeline").status_code == 200
    for url in ("/api/dashboard", "/api/ranking", "/api/dashboard/bimtek", "/api/log-online", "/api/auth/saya"):
        assert c.get(url).status_code == 401, url
