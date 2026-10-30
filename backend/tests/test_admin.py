import pytest
from fastapi.testclient import TestClient

from app.access import Access, parse_access
from app.main import app
from app.routers import admin, deps

SAYA = Access(email="admin.contoh@contoh.id", nama_petugas="Admin Contoh", fitur=("wa_blast", "cutoff"), admin=True)


class WS:
    def __init__(self):
        self.isi = [["email", "nama_petugas", "fitur", "catatan"],
                    ["admin.contoh@contoh.id", "Admin Contoh", "wa_blast, cutoff", "admin"],
                    ["tim@contoh.id", "Petugas Contoh", "wa_blast", "user"]]

    def get_values(self, rng):
        return [list(r) for r in self.isi]

    def update(self, nilai, rng, value_input_option=None):
        self.isi[int(rng.split(":")[0][1:]) - 1] = nilai[0]

    def append_row(self, nilai, value_input_option=None, table_range=None):
        self.isi.append(nilai)

    def delete_rows(self, n):
        del self.isi[n - 1]


@pytest.fixture
def c(monkeypatch):
    ws = WS()
    monkeypatch.setattr(admin, "_ws", lambda: ws)
    monkeypatch.setattr(admin, "_segarkan", lambda: None)
    app.dependency_overrides[deps.require_admin] = lambda: SAYA
    yield TestClient(app), ws
    app.dependency_overrides.clear()


def test_catatan_admin():
    data = parse_access([["email", "nama_petugas", "fitur", "catatan"], ["a@x.id", "A", "wa_blast", "Admin"],
                         ["b@x.id", "B", "wa_blast"]])
    assert data["a@x.id"].admin and not data["b@x.id"].admin


def test_tambah_ubah_hapus(c):
    cl, ws = c
    r = cl.post("/api/admin/akses", json={"email": " Baru@Contoh.id ", "nama_petugas": "Petugas  Baru",
                                          "fitur": ["wa_blast", "ngawur"]})
    assert r.status_code == 200 and r.json()["baru"] and ws.isi[-1] == ["baru@contoh.id", "Petugas Baru", "wa_blast", "user"]
    assert cl.post("/api/admin/akses", json={"email": "tim@contoh.id", "nama_petugas": "X", "fitur": ["wa_blast"]}).status_code == 409
    r = cl.post("/api/admin/akses", json={"email": "tim@contoh.id", "nama_petugas": "Petugas Contoh",
                                          "fitur": ["wa_blast", "cutoff"], "admin": True, "email_lama": "tim@contoh.id"})
    assert r.status_code == 200 and ws.isi[2] == ["tim@contoh.id", "Petugas Contoh", "wa_blast, cutoff", "admin"]
    assert cl.delete("/api/admin/akses/tim@contoh.id").status_code == 200
    assert [x[0] for x in ws.isi[1:]] == ["admin.contoh@contoh.id", "baru@contoh.id"]


def test_tidak_bisa_mengunci_diri_sendiri(c):
    cl, _ = c
    assert cl.delete("/api/admin/akses/admin.contoh@contoh.id").status_code == 400
    r = cl.post("/api/admin/akses", json={"email": "admin.contoh@contoh.id", "nama_petugas": "Admin Contoh",
                                          "fitur": ["wa_blast"], "admin": False, "email_lama": "admin.contoh@contoh.id"})
    assert r.status_code == 400
    assert cl.post("/api/admin/akses", json={"email": "bukan-email", "nama_petugas": "X", "fitur": ["wa_blast"]}).status_code == 400
