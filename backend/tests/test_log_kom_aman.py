"""Log Komunikasi aman dari banyak laptop: kolom ganda, kolom bergeser, laptop bukan admin."""

import re
from datetime import date

import pytest

from app import cutoff_baru, lk_baru
from app.sheets import cache

TAB = lk_baru.TAB_LOG_KOM
NPSN = "12345678"
MINGGU_LALU = ["Sen 09/11", "Sel 10/11", "Rab 11/11", "Kam 12/11", "Jum 13/11", "Sab 14/11"]


def _idx(huruf: str) -> int:
    n = 0
    for ch in huruf:
        n = n * 26 + ord(ch) - 64
    return n - 1


class SheetPalsu:
    """Tab Log Komunikasi di memori: kolom = list sel (baris 1, 2, 3, ...)."""

    def __init__(self, judul2: list[str], baris3: list[str]):
        self.kol = [["", h, b] for h, b in zip(judul2, baris3)]
        self.sebelum_sisip = None  # dipanggil sekali sebelum sisipan pertama (laptop lain menyela)

    # --- baca ---
    def _sel(self, c: int, r: int) -> str:
        return self.kol[c][r] if c < len(self.kol) and r < len(self.kol[c]) else ""

    def values_get(self, rng: str, params=None):
        m = re.fullmatch(r"'[^']+'!([A-Z]+)(\d+)(?::([A-Z]+)(\d*))?", rng)
        c0, r0 = _idx(m.group(1)), int(m.group(2)) - 1
        c1 = _idx(m.group(3)) if m.group(3) else c0
        r1 = int(m.group(4)) - 1 if m.group(4) else (max(len(k) for k in self.kol) - 1 if m.group(3) else r0)
        return {"values": [[self._sel(c, r) for c in range(c0, min(c1, len(self.kol) - 1) + 1)]
                           for r in range(r0, r1 + 1)]}

    def values_batch_get(self, ranges):
        out = []
        for rng in ranges:
            c = _idx(re.search(r"!([A-Z]+)3", rng).group(1))
            out.append({"values": [[x] for x in self.kol[c][2:] if x]})
        return {"valueRanges": out}

    def worksheet(self, _):
        return type("W", (), {"id": 0, "row_count": 10})()

    def fetch_sheet_metadata(self, _):
        return {"sheets": [{"properties": {"sheetId": 0}, "merges": []}]}

    # --- tulis ---
    def batch_update(self, body):
        for req in body["requests"]:
            if "insertDimension" in req:
                if self.sebelum_sisip:
                    f, self.sebelum_sisip = self.sebelum_sisip, None
                    f(self)
                self.kol.insert(req["insertDimension"]["range"]["startIndex"], ["", "", ""])
            elif "moveDimension" in req:  # hanya ke kiri (yang dipakai aplikasi)
                m = req["moveDimension"]
                self.kol.insert(m["destinationIndex"], self.kol.pop(m["source"]["startIndex"]))
            elif "deleteDimension" in req:
                del self.kol[req["deleteDimension"]["range"]["startIndex"]]

    def values_batch_update(self, body):
        for d in body["data"]:
            m = re.search(r"!([A-Z]+)(\d+)$", d["range"])
            self.kol[_idx(m.group(1))][int(m.group(2)) - 1] = d["values"][0][0]

    def judul2(self) -> list[str]:
        return [k[1] for k in self.kol]


@pytest.fixture
def sheet(monkeypatch):
    s = SheetPalsu(["PIC", "NPSN", "Nama Sekolah", "PTN", "Koordinator", "Fasilitator", *MINGGU_LALU],
                   ["Sari", NPSN, "SD A", "PTN", "Koor", "Fasil", *[""] * 6])
    monkeypatch.setattr(lk_baru, "_ss", lambda: s)
    monkeypatch.setattr(cutoff_baru.schedule, "now", lambda: __import__("datetime").datetime(2026, 11, 16, 8))
    monkeypatch.setattr(lk_baru, "_cek_kom_terakhir", 1e18)  # cek baris NPSN tidak perlu di tes ini
    cache.drop("lk2_logkom")
    cutoff_baru._sudah_tgl.clear()
    yield s
    cache.drop("lk2_logkom")
    cutoff_baru._sudah_tgl.clear()


def test_kolom_ganda_yang_berisi_kode_tidak_dihapus(sheet):
    def laptop_lain(s):  # laptop lain baru saja menambah Sen 16/11 dan petugasnya sudah mengisi T
        s.kol.insert(12, ["", "Sen 16/11", "T"])

    sheet.sebelum_sisip = laptop_lain
    assert cutoff_baru.pastikan_tanggal_log(date(2026, 11, 16), ss=sheet)
    judul = sheet.judul2()
    assert judul.count("Sen 16/11") == 1
    assert sheet.kol[judul.index("Sen 16/11")][2] == "T"
    assert judul[12:18] == ["Sen 16/11", "Sel 17/11", "Rab 18/11", "Kam 19/11", "Jum 20/11", "Sab 21/11"]
    assert judul[6:12] == MINGGU_LALU  # minggu lalu utuh


def test_tulis_kode_ikut_kolom_yang_bergeser(sheet):
    lk_baru.baca_log_kom()  # cache: Sel 10/11 = kolom H
    sheet.kol.insert(6, ["", "Min 08/11", ""])  # admin menyisipkan kolom di depan; cache belum tahu
    assert lk_baru.tulis_log_kom("2026-11-10", {NPSN: "T1"}) == 1
    judul = sheet.judul2()
    assert sheet.kol[judul.index("Sel 10/11")][2] == "T1"
    assert sheet.kol[judul.index("Sen 09/11")][2] == ""


def test_laptop_bukan_admin_tidak_menambah_kolom(sheet, monkeypatch):
    monkeypatch.setattr(cutoff_baru, "laptop_admin", lambda: False)
    with pytest.raises(lk_baru.LkError):
        lk_baru.tulis_log_kom("2026-11-16", {NPSN: "T"})
    assert "Sen 16/11" not in sheet.judul2()


def test_laptop_admin_menambah_kolom_lalu_menulis(sheet, monkeypatch):
    monkeypatch.setattr(cutoff_baru, "laptop_admin", lambda: True)
    assert lk_baru.tulis_log_kom("2026-11-16", {NPSN: "T"}) == 1
    judul = sheet.judul2()
    assert sheet.kol[judul.index("Sen 16/11")][2] == "T"


def test_laptop_admin_gagal_dibaca_dianggap_bukan_admin(monkeypatch):
    from app import google_auth

    monkeypatch.setattr(google_auth, "current_email", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert cutoff_baru.laptop_admin() is False
