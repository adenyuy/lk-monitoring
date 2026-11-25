"""Timeline mingguan: batas pekan Senin–Minggu, pembagi dinamis, dan fallback ke tab Timeline di LK."""

import pytest

from app import cutoff_baru, rekap_bimtek, timeline

# Kolom wajib export diletakkan sesudah 4 kolom yang dipakai, diisi "x" (pemisah ";" harus tertebak).
LAIN = [k for k in cutoff_baru.WAJIB if k != "NPSN"]
JUDUL = ";".join(["NPSN", "Tanggal PKS", "Tanggal Salur Tahap 1", "Pendahuluan - Tgl Kirim", *LAIN]) + "\n"


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LKM_BIMTEK_DIR", str(tmp_path))
    monkeypatch.setattr(timeline, "_cache", {})
    tersimpan = []
    monkeypatch.setattr(rekap_bimtek, "simpan_json", lambda tab, tanda, data: tersimpan.append(tab))
    (tmp_path / "2-terbaru").mkdir()
    return tmp_path, tersimpan


def test_kiriman_hari_minggu_masuk_pekan_itu(folder):
    d, _ = folder
    baris = (
        "1;01/09/2026;;13/09/2026 20:00",  # Minggu 13 Sep -> Sep W1 (7–13 Sep)
        "2;01/09/2026;;14/09/2026 08:00",  # Senin 14 Sep -> Sep W2
        "3;21/09/2026;;",                  # PKS Senin 21 Sep (Sep W3): pembagi naik
    )
    (d / "2-terbaru" / "Export_Uji_20261124_090000.csv").write_text(
        JUDUL + "".join(r + ";x" * len(LAIN) + "\n" for r in baris), encoding="utf-8")
    data = timeline.hitung()
    assert data["minggu"][0]["selesai"] == "2026-09-13"
    lp = next(k for k in data["komponen"] if k["kode"] == "lp")
    assert lp["pks"][:3] == [1, 2, 2]
    assert data["basis"]["pks"][:3] == [2, 2, 3]


def test_tanpa_export_baca_dari_lk(folder, monkeypatch):
    monkeypatch.setattr(timeline, "baca", lambda: {"minggu": [], "dari": "lk"})
    assert timeline.hitung()["dari"] == "lk"
