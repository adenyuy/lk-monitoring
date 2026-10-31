"""Ubah nama / nomor fasil: Broadcast, LK, dan riwayat lokal (sheet tiruan, tidak menyentuh Google)."""

import pytest

from app import db, store, ubah_fasil
from app.sheets import BroadcastRow, Sekolah, nomor_key

LAMA, BARU = "6281200000001", "6281399999999"


def test_gaya_mengikuti_isi_sel_lama():
    assert ubah_fasil.gaya("0812-0000-0001", BARU) == "081399999999"
    assert ubah_fasil.gaya("+62 812 0000 0001", BARU) == "+" + BARU
    assert ubah_fasil.gaya("https://wa.me/6281200000001", BARU) == "https://wa.me/" + BARU
    assert ubah_fasil.gaya("6281200000001", BARU) == BARU


def test_ganti_hanya_nomor_lama_di_sel_berisi_beberapa_nomor():
    assert ubah_fasil.ganti_di_sel("081200000001 / 085711112222", LAMA, BARU) == "081399999999 / 085711112222"


class SS:
    def __init__(self, isi):
        self.isi = isi  # {(kolom, baris): nilai}
        self.ditulis = {}

    def values_get(self, rng):
        return {"values": [["No", "Nama Petugas", "Nama Fasil", "Nomor HP", "Pesan"]]}

    def values_batch_get(self, ranges):
        out = []
        for r in ranges:
            sel = r.split("!")[1].split(":")[0]
            out.append({"values": [[self.isi.get((sel[0], int(sel[1:])), "")]]})
        return {"valueRanges": out}

    def values_batch_update(self, body):
        for d in body["data"]:
            self.ditulis[d["range"].split("!")[1]] = d["values"][0][0]


class Kol:
    fasil, nomor = "F", "G"


@pytest.fixture
def palsu(monkeypatch):
    db.set_setting("nama_petugas", "Sari Petugas")
    ss = SS({("D", 3): "0812-0000-0001", ("B", 3): "Sari Petugas"})
    bc = [BroadcastRow(2, "Sari Petugas", "Fasil Lain", "6281211110000", "", "", ""),
          BroadcastRow(3, "Sari Petugas", "Budi", LAMA, "0812-0000-0001", "", "")]
    lk = [Sekolah(10, "Sari Petugas", "111", "SD A", "", "Budi", "081200000001", "", None, "", "",
                  nomor_keys=[nomor_key(LAMA)]),
          Sekolah(11, "Petugas Lain", "222", "SD B", "", "Budi", "081200000001", "", None, "", "",
                  nomor_keys=[nomor_key(LAMA)])]
    lk_ditulis = []
    monkeypatch.setattr(ubah_fasil, "gspread_client", lambda: type("C", (), {"open_by_key": lambda self, k: ss})())
    monkeypatch.setattr(ubah_fasil, "read_broadcast", lambda refresh=False: bc)
    monkeypatch.setattr(ubah_fasil, "read_lk", lambda week, refresh=False: lk)
    monkeypatch.setattr(ubah_fasil, "week_aktif", lambda: "1")
    monkeypatch.setattr(ubah_fasil, "kolom_lk", lambda week, refresh=False: Kol())
    monkeypatch.setattr(ubah_fasil, "write_isian", lambda week, p, kol=None: lk_ditulis.extend(p))
    with db.tx() as c:
        for t in ubah_fasil.TABEL_NOMOR:
            c.execute(f"DELETE FROM {t}")
    yield ss, lk_ditulis
    with db.tx() as c:
        for t in ubah_fasil.TABEL_NOMOR:
            c.execute(f"DELETE FROM {t}")


def test_ubah_nama_dan_nomor(palsu):
    ss, lk_ditulis = palsu
    store.record_send(tanggal="2026-10-30", waktu="2026-10-30T10:00:00", sesi=1, nama_fasil="Budi", nomor=LAMA,
                      hash_pesan="x", status="terkirim")
    store.save_chat_status(LAMA, "dibalas", "siap", "2026-10-30T11:00:00")
    h = ubah_fasil.ubah(LAMA, " Budi  Santoso ", "0813-9999-9999")
    assert h.nomor == BARU and h.broadcast == 1 and h.lk == 1
    assert ss.ditulis == {"C3": "Budi Santoso", "D3": "081399999999"}
    (s, sel), = lk_ditulis
    assert s.npsn == "111" and sel == {"F": "Budi Santoso", "G": "081399999999"}
    assert not db.query("SELECT 1 FROM sends WHERE nomor = ?", (LAMA,))
    assert db.query("SELECT 1 FROM sends WHERE nomor = ?", (BARU,))
    assert store.chat_status_all()[BARU]["status"] == "dibalas"


def test_ubah_nama_saja(palsu):
    ss, lk_ditulis = palsu
    h = ubah_fasil.ubah(LAMA, "Budi S", "")
    assert h.nomor == LAMA and ss.ditulis == {"C3": "Budi S"}
    assert lk_ditulis[0][1] == {"F": "Budi S"}


def test_tolak_nomor_tidak_valid_atau_dipakai_fasil_lain(palsu):
    with pytest.raises(ubah_fasil.UbahFasilError):
        ubah_fasil.ubah(LAMA, "Budi", "12345")
    with pytest.raises(ubah_fasil.UbahFasilError):
        ubah_fasil.ubah(LAMA, "Budi", "081211110000")
    with pytest.raises(ubah_fasil.UbahFasilError):
        ubah_fasil.ubah(LAMA, "  ", "")


def test_tolak_bila_baris_broadcast_bergeser(palsu):
    ss, _ = palsu
    ss.isi[("D", 3)] = "0899-0000-0000"
    with pytest.raises(ubah_fasil.UbahFasilError):
        ubah_fasil.ubah(LAMA, "Budi", BARU)
    assert not ss.ditulis
