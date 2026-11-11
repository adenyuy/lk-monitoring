import pandas as pd
import pytest
import requests

from app import cutoff_baru, google_auth


def _df(**extra):
    base = {"NPSN": "123", "Nama Sekolah": "SD Uji", "Bulanan Due": "3", "Bulanan Terkirim": "2"}
    return pd.DataFrame([{**base, **extra}])


def test_bku_bpp_dari_kolom_bulanan():
    x = cutoff_baru.olah(_df(**{"Bulanan BKU Terkirim": "2", "Bulanan BPP Terkirim": "3"}))["123"]
    assert x["BKU"] == "2/3" and x["BPP"] == "3/3"


def test_bku_bpp_belum_due_dan_tanpa_target():
    x = cutoff_baru.olah(_df(**{"Bulanan Due": "Belum Due", "Bulanan BKU Terkirim": "0", "Bulanan BPP Terkirim": "0"}))
    assert x["123"]["BKU"] == "Belum Due"
    y = cutoff_baru.olah(_df(**{"Bulanan Due": "0", "Bulanan BKU Terkirim": "0", "Bulanan BPP Terkirim": "0"}))
    assert y["123"]["BPP"] == "-"


def test_tanpa_kolom_bku_tidak_diisi():
    x = cutoff_baru.olah(_df())["123"]
    assert "BKU" not in x and "BPP" not in x


def test_klien_coba_ulang_saat_koneksi_putus(monkeypatch):
    panggil = {"n": 0}

    def gagal_dua_kali(self, *a, **kw):
        panggil["n"] += 1
        if panggil["n"] <= 2:
            raise requests.exceptions.ConnectionError("Connection aborted.")
        return "ok"

    monkeypatch.setattr(google_auth.BackOffHTTPClient, "request", gagal_dua_kali)
    monkeypatch.setattr(google_auth.time, "sleep", lambda s: None)
    klien = google_auth._KlienUlang.__new__(google_auth._KlienUlang)
    assert klien.request("post", "x") == "ok" and panggil["n"] == 3


def test_klien_menyerah_setelah_batas(monkeypatch):
    def selalu_gagal(self, *a, **kw):
        raise requests.exceptions.ConnectionError("Connection aborted.")

    monkeypatch.setattr(google_auth.BackOffHTTPClient, "request", selalu_gagal)
    monkeypatch.setattr(google_auth.time, "sleep", lambda s: None)
    klien = google_auth._KlienUlang.__new__(google_auth._KlienUlang)
    with pytest.raises(requests.exceptions.ConnectionError):
        klien.request("post", "x")


class _SsPalsu:
    def __init__(self, judul, data):
        self.judul, self.data, self.tulis = judul, data, []

    def values_get(self, rng, params=None):
        return {"values": [self.judul] if rng.endswith("3") else self.data}

    def values_update(self, rng, params=None, body=None):
        self.tulis.append((rng, body["values"]))


def test_cutoff_hanya_menulis_kolom_komponen(monkeypatch):
    from app import lk_baru

    judul = ["PIC", "NPSN", "Nama Sekolah", "Fasilitator", "Status Laporan Pendahuluan",
             "Waktu Tunggu Reviu Laporan Pendahuluan", "Reviu Laporan Pendahuluan"]
    data = [["Petugas A", "123", "SD Lama", "Fasil Lama", "Belum", "", "-"]]
    ss = _SsPalsu(judul, data)
    t = lk_baru.Tata(identitas={"petugas": 0, "npsn": 1, "nama": 2, "fasil": 3}, komponen={"lp": 4, "lp_rev": 6},
                     tunggu={"lp_rev": 5}, isian={}, lebar=7)
    monkeypatch.setattr(lk_baru, "tata", lambda week, refresh=False: t)
    monkeypatch.setattr(lk_baru, "_ss", lambda: ss)
    df = pd.DataFrame([
        {"NPSN": "123", "Nama Sekolah": "SD Baru Ganti Nama", "Fasilitator": "Fasil Lain",
         "Pendahuluan - Status Kirim": "Sudah Dikirim", "Pendahuluan - Status Reviu": "Disetujui",
         "Hari Verif Pendahuluan": "2"},
        {"NPSN": "999", "Nama Sekolah": "SD Tambahan", "Fasilitator": "Fasil X",
         "Pendahuluan - Status Kirim": "Belum Dikirim", "Pendahuluan - Status Reviu": "Belum Dikirim",
         "Hari Verif Pendahuluan": ""}])
    monkeypatch.setattr(cutoff_baru, "baca", lambda data, nama: df)
    rc = cutoff_baru.siapkan(b"", "x.csv", 3)
    assert rc.kol_awal == 4
    assert rc.baris == [["Sudah", 2.0, "Sudah"]]  # identitas (PIC, nama, fasil) tidak ikut
    assert {b["kolom"] for b in rc.ringkasan["berubah"]} == {"Status Laporan Pendahuluan",
                                                              "Waktu Tunggu Reviu Laporan Pendahuluan",
                                                              "Reviu Laporan Pendahuluan"}
    assert rc.tambah[0][1] == "999" and rc.tambah[0][2] == "SD Tambahan"  # sekolah baru tetap lengkap


def test_rencana_log_kom_sekolah_baru_dan_pic():
    from types import SimpleNamespace as S

    semua = [S(npsn="1", petugas="Ani", nama="SD 1", ptn="P", koor="K", fasil="F"),
             S(npsn="2", petugas="Budi", nama="SD 2", ptn="P", koor="K", fasil="F"),
             S(npsn="3", petugas="Cici", nama="SD 3", ptn="Q", koor="L", fasil="G"),
             S(npsn="4", petugas="", nama="SD 4", ptn="Q", koor="L", fasil="G")]
    log_rows = [["Ani", "1"], ["", "2"], ["Dodi", 3.0]]  # NPSN bisa terbaca angka
    baru, ubah = cutoff_baru.rencana_log_kom(semua, log_rows)
    assert baru == [["", "4", "SD 4", "Q", "L", "G"]]
    assert ubah == [(4, "Budi"), (5, "Cici")]  # baris sheet mulai 3


def test_sekolah_baru_diwarnai_kuning():
    class W:
        title, id, col_count = "WEEK 4", 7, 83

    class SS:
        def __init__(self):
            self.req = []

        def values_get(self, rng):
            assert rng == "'WEEK 4'!A3:3"
            return {"values": [["PIC", "NPSN", "Nama"] + [""] * 75]}

        def batch_update(self, body):
            self.req += body["requests"]

    ss = SS()
    cutoff_baru.warnai_sekolah_baru(ss, W(), 2000, 3)
    rc = ss.req[0]["repeatCell"]
    assert rc["range"] == {"sheetId": 7, "startRowIndex": 1999, "endRowIndex": 2002,
                           "startColumnIndex": 0, "endColumnIndex": 78}
    assert rc["cell"]["userEnteredFormat"]["backgroundColor"] == cutoff_baru.KUNING
    assert rc["fields"] == "userEnteredFormat.backgroundColor"
