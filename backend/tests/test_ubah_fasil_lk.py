"""Ubah nama / nomor fasil di LK format baru (sheet tiruan, tidak menyentuh Google)."""

import pytest

from app import db, komunikasi, lk_baru, ubah_fasil_lk
from app.lk_baru import LogKom, Sekolah

LAMA, BARU = "6281200000001", "6281399999999"


def _s(baris, npsn, fasil="Budi", hp="0812-0000-0001", petugas="Sari"):
    return Sekolah(baris, petugas, npsn, f"SD {npsn}", "1", "", "", "", "", "", "", "", fasil, hp)


class SS:
    def __init__(self, npsn_per_baris):
        self.npsn = npsn_per_baris
        self.ditulis = {}

    def values_batch_get(self, ranges, params=None):
        out = []
        for r in ranges:
            baris = int("".join(ch for ch in r.split("!")[1] if ch.isdigit()))
            out.append({"values": [[self.npsn.get(baris, "")]]})
        return {"valueRanges": out}

    def values_batch_update(self, body):
        for d in body["data"]:
            self.ditulis[d["range"]] = d["values"][0][0]


@pytest.fixture
def lk(monkeypatch):
    sekolah = [_s(10, "111"), _s(11, "222", hp="0812-0000-0001 / 085711112222"), _s(12, "333", "Ani", "081255556666")]
    ss = SS({10: "111", 11: "222", 12: "333"})
    r3 = [j for j, f in lk_baru.IDENTITAS.items() if f not in lk_baru.IDENTITAS_OPSIONAL]
    ident = {lk_baru.IDENTITAS[j]: i for i, j in enumerate(r3)}
    tata = lk_baru.Tata(ident, {}, {}, {}, len(r3))
    monkeypatch.setattr(komunikasi, "sekolah_saya", lambda refresh=False: sekolah)
    monkeypatch.setattr(lk_baru, "week_aktif", lambda: 4)
    monkeypatch.setattr(lk_baru, "tata", lambda week, refresh=False: tata)
    monkeypatch.setattr(lk_baru, "_ss", lambda: ss)
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: LogKom({}, {"111": 5, "222": 6}, {}))
    monkeypatch.setattr(lk_baru, "_baris_kom_cocok", lambda lk, npsn: True)
    return ss


def test_ganti_nomor_dan_nama(lk):
    r = ubah_fasil_lk.ubah(LAMA, "Budi Santoso", "0813 9999 9999")
    assert r["kunci"] == BARU and r["sekolah"] == 2
    tab = "'WEEK 4'"
    # Fasilitator = kolom L (indeks 11), No HP Fasilitator = M (12)
    assert lk.ditulis[f"{tab}!L10"] == "Budi Santoso" and lk.ditulis[f"{tab}!L11"] == "Budi Santoso"
    assert lk.ditulis[f"{tab}!M10"] == "081399999999"
    assert lk.ditulis[f"{tab}!M11"] == "081399999999 / 085711112222"   # nomor lain di sel dibiarkan
    assert not any(k.endswith("12") for k in lk.ditulis if k.startswith(tab))  # fasil lain tidak disentuh
    assert lk.ditulis["'Log Komunikasi'!D5"] == "Budi Santoso"


def test_riwayat_lokal_pindah(lk):
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO kirim_ulang (nomor, waktu) VALUES (?, ?)", (LAMA, "2026-11-10"))
        c.executescript(komunikasi.SCHEMA)
        c.execute("INSERT OR REPLACE INTO fasil_tag (kunci, tag, waktu) VALUES (?, ?, ?)", (LAMA, "prio", "x"))
    ubah_fasil_lk.ubah(LAMA, "Budi", BARU)
    with db.tx() as c:
        assert c.execute("SELECT count(*) FROM kirim_ulang WHERE nomor = ?", (BARU,)).fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM kirim_ulang WHERE nomor = ?", (LAMA,)).fetchone()[0] == 0
        assert c.execute("SELECT kunci FROM fasil_tag WHERE tag = 'prio'").fetchone()[0] == BARU


def test_ditolak(lk):
    with pytest.raises(ubah_fasil_lk.UbahFasilError, match="sudah dipakai"):
        ubah_fasil_lk.ubah(LAMA, "Budi", "081255556666")
    with pytest.raises(ubah_fasil_lk.UbahFasilError, match="Tidak ada yang berubah"):
        ubah_fasil_lk.ubah(LAMA, "Budi", "")
    with pytest.raises(ubah_fasil_lk.UbahFasilError, match="tidak ada di sekolah binaan"):
        ubah_fasil_lk.ubah("6289999", "X", "")
    lk.npsn[11] = "999"  # urutan sheet berubah
    with pytest.raises(ubah_fasil_lk.UbahFasilError, match="Urutan LK"):
        ubah_fasil_lk.ubah(LAMA, "Budi Baru", "")
