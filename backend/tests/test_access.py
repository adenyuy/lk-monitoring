import pytest

from app import access


def test_parse_akses():
    values = [
        ["Email", "Nama_Petugas", "Fitur"],
        ["admin.contoh@contoh.id", "*Sari Petugas*", "wa_blast, cutoff"],
        ["tim@contoh.id", "Petugas Contoh", "wa_blast, fitur_ngawur"],
        ["", "Tanpa Email", "wa_blast"],
    ]
    data = access.parse_access(values)
    assert set(data) == {"admin.contoh@contoh.id", "tim@contoh.id"}
    m = data["admin.contoh@contoh.id"]
    assert m.nama_petugas == "Sari Petugas"
    assert m.has("cutoff") and m.has("wa_blast")
    assert data["tim@contoh.id"].fitur == ("wa_blast",)  # fitur tak dikenal diabaikan


def test_kolom_akses_wajib():
    with pytest.raises(access.AccessError):
        access.parse_access([["email", "nama"]])


def test_sheet_akses_belum_diatur(monkeypatch):
    monkeypatch.setattr(access.config, "ACCESS_SHEET_ID", "")
    with pytest.raises(access.AccessError, match="belum diatur"):
        access.read_access()
