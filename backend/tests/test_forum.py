import re

import pytest
from fastapi.testclient import TestClient

from app import forum
from app.access import Access
from app.main import app
from app.routers import deps
from app.sheets import cache


class TabPalsu:
    """Tiruan worksheet gspread secukupnya untuk forum."""

    title = forum.TAB

    def __init__(self):
        self.rows: list[list[str]] = []

    def update(self, values, rng, value_input_option=None):
        self.rows[:1] = values

    def get_values(self, rng):
        m = re.fullmatch(r"A(\d+)", rng)
        if m:
            n = int(m.group(1))
            return [self.rows[n - 1][:1]] if n <= len(self.rows) else []
        return [list(r) for r in self.rows]

    def append_rows(self, rows, **kw):
        self.rows += [list(r) for r in rows]

    def batch_update(self, data, **kw):
        for d in data:
            kol, n = re.fullmatch(r"([A-Z]+)(\d+)", d["range"]).groups()
            self.rows[int(n) - 1][ord(kol) - 65] = d["values"][0][0]


@pytest.fixture
def tab(monkeypatch):
    t = TabPalsu()

    def ws(buat=False):
        if not t.rows and buat:
            t.update([forum.KOLOM], "A1")
        return t if t.rows else None

    monkeypatch.setattr(forum, "_ws", ws)
    cache.clear()
    yield t
    cache.clear()


A, B = "a@contoh.id", "b@contoh.id"


def test_alur_tanya_jawab_solusi(tab):
    tid = forum.buat_tanya(A, "Petugas A", "Kolom kendala tidak bisa diisi", "Kenapa ya?", "Isian LK", [])
    assert tab.rows[0] == forum.KOLOM
    j1 = forum.buat_jawab(B, "Petugas B", tid, "Cek apakah WEEK aktif sudah benar", [])
    forum.buat_jawab(A, "Petugas A", tid, "Oke dicoba", [])

    r = forum.ringkas(forum.baca(), B)
    assert r[0]["jawaban"] == 2 and not r[0]["selesai"] and not r[0]["milik_saya"]

    with pytest.raises(forum.ForumError, match="penulisnya"):
        forum.pilih_solusi(B, False, tid, j1)  # hanya penanya
    forum.pilih_solusi(A, False, tid, j1)
    d = forum.detail(tid, A, False)
    assert d["solusi"] == j1 and d["jawaban"][0]["id"] == j1  # jawaban terpilih di atas

    forum.hapus(B, False, j1)  # menghapus jawaban terpilih ikut melepas solusi
    d = forum.detail(tid, A, False)
    assert d["solusi"] == "" and len(d["jawaban"]) == 1
    assert len(tab.rows) == 4  # baris tidak pernah dihapus, hanya ditandai


def test_tanya_sekaligus_jawaban_sendiri(tab):
    tid = forum.buat_tanya(A, "Petugas A", "Cara ganti nomor WA", "", "Aplikasi", [], jawaban="Scan QR ulang")
    d = forum.detail(tid, B, False)
    assert d["solusi"] and d["jawaban"][0]["isi"] == "Scan QR ulang"
    assert forum.ringkas(forum.baca(), B)[0]["selesai"]


def test_ubah_dan_hak(tab):
    tid = forum.buat_tanya(A, "Petugas A", "Judul awal panjang", "isi", "", [])
    with pytest.raises(forum.ForumError):
        forum.ubah(B, False, tid, "Judul diubah orang lain", None, None, None)
    forum.ubah(B, True, tid, "Judul diubah admin", None, "Sekolah", None)  # admin boleh
    d = forum.detail(tid, A, False)
    assert d["judul"] == "Judul diubah admin" and d["topik"] == "Sekolah" and d["diubah"]
    forum.hapus(A, False, tid)
    assert forum.baca() == []


def test_validasi(tab):
    with pytest.raises(forum.ForumError, match="minimal"):
        forum.buat_tanya(A, "A", "abc", "", "", [])
    with pytest.raises(forum.ForumError, match="Maksimal"):
        forum.buat_tanya(A, "A", "Judul cukup", "", "", ["a", "b", "c", "d", "e"])
    with pytest.raises(forum.ForumError, match="tidak valid"):
        forum.buat_tanya(A, "A", "Judul cukup", "", "", ["../x"])
    tid = forum.buat_tanya(A, "A", "Judul cukup", "", "", [])
    with pytest.raises(forum.ForumError, match="kosong"):
        forum.buat_jawab(B, "B", tid, " ", [])
    # teks diawali "=" disimpan apa adanya (RAW), bukan rumus
    forum.buat_jawab(B, "B", tid, "=HYPERLINK(1)", [])
    assert tab.rows[-1][forum.KOLOM.index("isi")] == "=HYPERLINK(1)"


def test_api(tab):
    app.dependency_overrides[deps.require_access] = lambda: Access(A, "Petugas A", ("wa_blast",))
    try:
        c = TestClient(app)
        r = c.post("/api/forum/tanya", json={"judul": "Pertanyaan lewat API", "isi": "isi", "topik": "Sekolah"})
        tid = r.json()["id"]
        assert c.post(f"/api/forum/{tid}/jawab", json={"isi": "jawaban"}).status_code == 200
        d = c.get("/api/forum").json()
        assert d["items"][0]["jawaban"] == 1 and "Sekolah" in d["topik"]
        assert c.get(f"/api/forum/{tid}").json()["jawaban"][0]["milik_saya"]
        assert c.post("/api/forum/tanya", json={"judul": "x"}).status_code == 400
        assert c.get("/api/forum/tidakada").status_code == 400
    finally:
        app.dependency_overrides.clear()
