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
