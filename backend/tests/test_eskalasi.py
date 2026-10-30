from datetime import datetime

import pytest

from app import eskalasi

JUDUL = ["No.", "NPSN", "Nama Sekolah", "Fasilitator", "Petugas Monitoring", "Keterangan Permasalahan",
         "Permasalahan", "Tanggal Awal Permasalahan", "Tanggal Permasalahan Selesai", "Tim Monitoring",
         "Tim Aplikasi", "Tim Substansi", "PMO", "Tim Penyaluran", "Tim Regulasi", "Status Tindak lanjut"]
F = [False] * 6


class SS:
    def __init__(self, baris):
        self.baris, self.tulis, self.append = baris, None, None

    def values_get(self, rng, params=None):
        return {"values": [JUDUL] + self.baris}

    def values_batch_get(self, rng, params=None):
        return {"valueRanges": [{"values": [["Aplikasi & Akun"], ["Lainnya"]]},
                                {"values": [["Belum Ditindaklanjuti"], ["Selesai"]]}]}

    def values_batch_update(self, body):
        self.tulis = body

    def values_append(self, rng, params=None, body=None):
        self.append = (rng, params, body)


@pytest.fixture
def ss(monkeypatch):
    s = SS([
        [1, "111", "SD A", "Fasil A", "Petugas", "", "", "", "", *F, ""],
        [2, "222", "SD B", "Fasil A", "Petugas", "Akun error", "Aplikasi & Akun", 46323, "", True, *F[1:], "Proses"],
    ])
    monkeypatch.setattr(eskalasi, "sheet_id", lambda: "x")
    monkeypatch.setattr(eskalasi, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: s})())
    monkeypatch.setattr(eskalasi.schedule, "now", lambda: datetime(2026, 10, 30, 9))
    eskalasi.cache.clear()
    return s


def test_daftar_hanya_yang_terisi(ss):
    d = eskalasi.daftar(["111", "222"])
    assert [x["npsn"] for x in d] == ["222"]
    assert d[0]["tgl_awal"] == "2026-10-28" and d[0]["tim"] == ["Tim Monitoring"] and d[0]["status"] == "Proses"


def test_catat_isi_baris_sekolah_lalu_tambah_baris(ss):
    h = eskalasi.catat(["111", "222", "999"], " Fasil diganti ", "Lainnya", ["Tim Substansi", "Bukan Tim"])
    # 111 belum punya permasalahan: ditulis di barisnya (baris 5)
    rng = {d["range"]: d["values"][0][0] for d in ss.tulis["data"]}
    assert rng["'LK Eskalasi'!F5"] == "Fasil diganti" and rng["'LK Eskalasi'!G5"] == "Lainnya"
    assert rng["'LK Eskalasi'!H5"] == 46325 and rng["'LK Eskalasi'!L5"] is True and rng["'LK Eskalasi'!J5"] is False
    assert rng["'LK Eskalasi'!P5"] == "Belum Ditindaklanjuti" and ss.tulis["valueInputOption"] == "RAW"
    # 222 sudah punya: baris baru, data sekolah disalin, nomor lanjut
    baru = ss.append[2]["values"]
    assert len(baru) == 1 and baru[0][:7] == [3, "222", "SD B", "Fasil A", "Petugas", "Fasil diganti", "Lainnya"]
    assert ss.append[1]["insertDataOption"] == "OVERWRITE"
    assert h["dilewati"] == ["999"] and [d["baru"] for d in h["ditulis"]] == [False, True]


def test_catat_ditolak(ss):
    with pytest.raises(eskalasi.EskalasiError, match="tim"):
        eskalasi.catat(["111"], "x", "", [])
    with pytest.raises(eskalasi.EskalasiError, match="daftar pilihan"):
        eskalasi.catat(["111"], "x", "Ngarang", ["PMO"])
    with pytest.raises(eskalasi.EskalasiError, match="wajib"):
        eskalasi.catat(["111"], "  ", "", ["PMO"])


def test_id_dari_link():
    assert eskalasi._id_dari("https://docs.google.com/spreadsheets/d/AAAAAAAAAAAAAAAAAAAAAAAAAA/edit#gid=1") == "A" * 26


def test_kontak_pic(monkeypatch):
    class B:
        def values_get(self, rng, params=None):
            return {"values": [["No.", "Nama PIC", "Nomor PIC", "WhatsApp"], ["1", " Ani  Putri ", "6281234567890", ""],
                               ["2", "Tanpa Nomor", "", ""]]}
    monkeypatch.setattr(eskalasi, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: B()})())
    eskalasi.cache.clear()
    assert eskalasi.kontak_pic() == [{"nama": "Ani Putri", "nomor": "6281234567890"}]


def test_pasang_link_untuk_tim(monkeypatch, tmp_path):
    ditulis = []

    class S:
        def worksheets(self):
            return [type("W", (), {"title": eskalasi.TAB})(), type("W", (), {"title": eskalasi.TAB_PENGATURAN})()]

        def values_get(self, rng, params=None):
            return {"values": [["kunci"], ["lain"]]}

        def values_update(self, rng, params=None, body=None):
            ditulis.append((rng, body["values"][0][0]))

    monkeypatch.setattr(eskalasi, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: S()})())
    monkeypatch.setattr(eskalasi.paths, "DATA_DIR", tmp_path)
    monkeypatch.delenv("LKM_ESKALASI_SHEET_ID", raising=False)
    sid = "B" * 28
    assert eskalasi.pasang_link(f"https://docs.google.com/spreadsheets/d/{sid}/edit#gid=1", True) == sid
    assert ditulis == [("'Pengaturan'!A3:C3", "lk_eskalasi")]
    assert eskalasi.sheet_id() == sid  # tersimpan di sheets.json laptop ini
    with pytest.raises(eskalasi.EskalasiError):
        eskalasi.pasang_link("bukan link", False)


def test_chat_teman_hanya_kontak_pic(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.routers import eskalasi as r
    from app.wa import actions

    monkeypatch.setattr(eskalasi, "kontak_pic", lambda: [{"nama": "Ani", "nomor": "6281234567890"}])
    monkeypatch.setattr(r.chat, "_siap", lambda: None)
    baris = [actions.Row(id="1", out=False, text="Bisa, caranya begini", waktu="10.00", status="")]
    terkirim = []

    def jalan(fn, timeout):
        b = type("B", (), {"page": type("P", (), {"wait_for_timeout": lambda self, ms: None})()})()
        return fn(b)

    monkeypatch.setattr(r.chat, "_jalan", jalan)
    monkeypatch.setattr(actions, "read_thread", lambda b, n: (None, baris))
    monkeypatch.setattr(actions, "reply", lambda b, n, t: terkirim.append((n, t)) or type("R", (), {"status": "terkirim"})())
    app.dependency_overrides[r.wa_blast] = lambda: None
    try:
        c = TestClient(app)
        assert c.post("/api/eskalasi/teman/6289999999999/baca").status_code == 403  # bukan teman PIC
        assert c.post("/api/eskalasi/teman/081234567890/baca").json()["pesan"][0]["teks"] == "Bisa, caranya begini"
        assert c.post("/api/eskalasi/teman/6281234567890/kirim", json={"pesan": " tanya "}).status_code == 200
        assert terkirim == [("6281234567890", "tanya")]
    finally:
        app.dependency_overrides.clear()
