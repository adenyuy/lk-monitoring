from app import db, lk_otomatis, sheets
from tests import lk_uji

BARIS = ["Petugas Uji", "{npsn}", "SD {npsn}", "Kab", "Fasil A", "6281200000001", "{prio}", "{kom}",
         0.3, "Tidak", "Tidak", 0.3, "Tidak", "Tidak"] + [""] * 12


def _baris(npsn, prio, kom):
    return [str(x).format(npsn=npsn, prio=prio, kom=kom) if isinstance(x, str) else x for x in BARIS]


def test_pilihan_terhubung():
    assert lk_otomatis.pilihan_terhubung(["Belum terhubung", "0. Terhubung", "3. Chat hanya di Read"]) == "0. Terhubung"


def test_fasil_membalas_semua_sekolahnya_jadi_terhubung(monkeypatch):
    data = lk_uji.parse([_baris("1", "Prioritas 1", ""), _baris("2", "Prioritas 3", "3. Chat hanya di Read"),
                         _baris("3", "Selesai", ""), _baris("4", "Prioritas 2", "0. Terhubung")])
    ditulis = []
    db.set_setting("nama_petugas", "Petugas Uji")
    monkeypatch.setattr(lk_otomatis, "week_aktif", lambda: "1")
    monkeypatch.setattr(lk_otomatis, "read_lk", lambda week: data)
    monkeypatch.setattr(lk_otomatis, "read_validasi", lambda: {"komunikasi": ["0. Terhubung", "3. Chat hanya di Read"]})
    monkeypatch.setattr(lk_otomatis, "kolom_lk", lambda week, refresh=False: lk_uji.KOL)
    monkeypatch.setattr(lk_otomatis, "write_isian", lambda week, p, kol=None: ditulis.extend(p))
    assert lk_otomatis.tandai_terhubung("6281200000001") == 2
    assert [(s.npsn, sel) for s, sel in ditulis] == [("1", {"I": "0. Terhubung"}), ("2", {"I": "0. Terhubung"})]
    assert data[0].komunikasi == "0. Terhubung"
    ditulis.clear()
    assert lk_otomatis.tandai_terhubung("6281200000001") == 0 and ditulis == []  # sudah Terhubung semua
