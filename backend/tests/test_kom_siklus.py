from datetime import date
from types import SimpleNamespace as Row

import pytest

from app import db, kom_siklus as ks

JUM, SAB, SEN, SEL = date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 9), date(2026, 11, 10)
NO = "6281200000001"


def tgl(w):
    return date.fromisoformat(w) if w else None


@pytest.fixture(autouse=True)
def bersih():
    ks._db()
    with db.tx() as c:
        for t in ("kom_amat", "kom_balas", "kom_mulai"):
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sends WHERE nomor = ?", (NO,))
        c.execute("DELETE FROM aktivitas WHERE nomor = ?", (NO,))
    yield


def kirim(hari: date, status="terkirim", ket=""):
    with db.tx() as c:
        c.execute("INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status, keterangan, coba) "
                  "VALUES(?,?,0,'Fasil',?,'h',?,?,0)", (hari.isoformat(), f"{hari}T08:00:00", NO, status, ket))


def kode(hari, isi=None, auto=None):
    s = ks.siklus(NO, hari)
    return ks.susun(s, ks.kejadian(NO, s), hari, isi or {}, auto or {})


def test_skenario_jumat_sabtu_senin():
    kirim(JUM)
    # Jumat: diterima (centang dua), belum dibalas
    ks.catat_chat(NO, [Row(out=True, status="delivered", text="blast", waktu="2026-11-06")], tgl, JUM)
    assert kode(JUM) == {"2026-11-06": "C2"}
    # laptop mati Sabtu; Senin dicek: fasil membalas Sabtu tanpa Kendala/Tindak lanjut
    rows = [Row(out=True, status="read", text="blast", waktu="2026-11-06"),
            Row(out=False, status="", text="siap kak, nanti saya cek", waktu="2026-11-07")]
    ks.catat_chat(NO, rows, tgl, SEN)
    assert kode(SEN) == {"2026-11-06": "C2", "2026-11-07": "T1", "2026-11-09": "T1"}
    # Selasa fasil kirim Kendala / Tindak lanjut -> T mulai Selasa
    rows.append(Row(out=False, status="", text="1. SD A\nKendala: hujan\nTindak lanjut: lembur", waktu="2026-11-10"))
    ks.catat_chat(NO, rows, tgl, SEL)
    assert kode(SEL)["2026-11-10"] == "T" and kode(SEL)["2026-11-09"] == "T1"


def test_minggu_tidak_diisi_dan_dibaca_tanpa_balas():
    kirim(JUM)
    ks.catat_chat(NO, [Row(out=True, status="read", text="blast", waktu="2026-11-06")], tgl, SEN)
    # dibaca baru terlihat Senin; Jumat & Sabtu dianggap sudah diterima, Minggu dilewati
    assert kode(SEN) == {"2026-11-06": "C2", "2026-11-07": "C2", "2026-11-09": "R"}


def test_isian_petugas_dipertahankan_dan_diteruskan():
    kirim(JUM)
    ks.catat_chat(NO, [Row(out=True, status="read", text="b", waktu="2026-11-06"),
                       Row(out=False, status="", text="ok", waktu="2026-11-06")], tgl, JUM)
    # petugas menulis T sendiri di hari Jumat -> tidak ditimpa, Sabtu & Senin ikut T
    hasil = kode(SEN, isi={"2026-11-06": "T"})
    assert "2026-11-06" not in hasil and hasil == {"2026-11-07": "T", "2026-11-09": "T"}
    # sel yang dulu ditulis aplikasi boleh diperbarui
    assert kode(JUM, isi={"2026-11-06": "C"}, auto={"2026-11-06": "C"}) == {"2026-11-06": "T1"}


def test_blast_baru_memulai_siklus_baru():
    kirim(JUM)
    ks.catat_chat(NO, [Row(out=True, status="read", text="b", waktu="2026-11-06")], tgl, JUM)
    kirim(SEL)
    ks.catat_chat(NO, [Row(out=True, status="read", text="b", waktu="2026-11-06"),
                       Row(out=True, status="sent", text="b2", waktu="2026-11-10")], tgl, SEL)
    assert kode(SEL) == {"2026-11-10": "C"}


def test_nomor_tanpa_wa():
    kirim(JUM, "gagal", "Nomor tidak terdaftar di WhatsApp")
    assert kode(SAB) == {"2026-11-06": "N", "2026-11-07": "N"}


def test_konfirmasi():
    assert ks.konfirmasi("1. SD A\n*Kendala:* hujan")
    assert ks.konfirmasi("Tindak lanjut: minggu depan")
    assert not ks.konfirmasi("baik kak, kendalanya nanti saya kabari")


def test_sinkron_menulis_semua_hari(monkeypatch):
    from app import komunikasi, lk_baru, schedule
    from datetime import datetime

    kirim(JUM)
    ks.catat_chat(NO, [Row(out=True, status="delivered", text="b", waktu="2026-11-06"),
                       Row(out=False, status="", text="oke", waktu="2026-11-07")], tgl, SEN)
    f = Row(nomor=NO, sekolah=[Row(npsn="111"), Row(npsn="222")])
    tulis = {}
    monkeypatch.setattr(komunikasi, "fasil_saya", lambda: {"f": f})
    monkeypatch.setattr(komunikasi, "wa_otomatis", lambda: True)
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 9, 10))
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: lk_baru.LogKom(
        {}, {}, {"222": {"2026-11-07": "TP"}}))
    monkeypatch.setattr(lk_baru, "tulis_log_kom", lambda t, x: tulis.setdefault(t, x) and len(x))
    monkeypatch.setattr(lk_baru, "pastikan_kode_dropdown", lambda k: False)  # dropdown tidak bisa ditambah
    komunikasi._db()
    with db.tx() as c:
        c.execute("DELETE FROM kom_auto")
    komunikasi.sinkron_wa()
    assert tulis == {"2026-11-06": {"111": "C", "222": "C"},  # C2 diganti C karena dropdown terkunci
                     "2026-11-07": {"111": "T1"},              # 222 diisi TP oleh petugas
                     "2026-11-09": {"111": "T1", "222": "TP"}}


KAM = date(2026, 11, 5)


def test_blast_lewat_hp_terbaca_dari_chat():
    # tidak ada kiriman dari aplikasi; Kamis blast lewat HP, terbaca saat chat dibuka Senin
    rows = [Row(out=True, status="read", text="blast HP", waktu="2026-11-05"),
            Row(out=False, status="", text="baik kak", waktu="2026-11-07"),
            Row(out=True, status="read", text="makasih kak", waktu="2026-11-07")]  # membalas fasil: bukan blast
    ks.catat_chat(NO, rows, tgl, SEN)
    assert ks.siklus(NO, SEN).awal == KAM
    assert kode(SEN) == {"2026-11-05": "C2", "2026-11-06": "C2", "2026-11-07": "T1", "2026-11-09": "T1"}
    from app import store
    assert NO in store.to_refresh("2026-11-03")  # sesudahnya ikut dipantau tiap 10 menit


def test_blast_hp_senin_memulai_siklus_baru():
    rows = [Row(out=True, status="read", text="blast Kamis", waktu="2026-11-05"),
            Row(out=False, status="", text="ok", waktu="2026-11-07"),
            Row(out=True, status="delivered", text="blast Senin", waktu="2026-11-09")]
    ks.catat_chat(NO, rows, tgl, SEN)
    assert ks.siklus(NO, SEN).awal == SEN
    assert kode(SEN) == {"2026-11-09": "C2"}


def test_awal_siklus():
    rows = [Row(out=True, status="", text="a", waktu="2026-11-05"), Row(out=True, status="", text="b", waktu="2026-11-05"),
            Row(out=False, status="", text="c", waktu="2026-11-06"), Row(out=True, status="", text="d", waktu="2026-11-06"),
            Row(out=True, status="", text="e", waktu="")]
    assert ks.awal_siklus(rows, [tgl(r.waktu) for r in rows]) == [KAM]


def test_balasan_minggu_ikut_senin():
    # blast Kamis; fasil membalas Minggu; Senin tanpa blast baru -> Senin T1 (Minggu tidak ditulis)
    rows = [Row(out=True, status="read", text="blast", waktu="2026-11-05"),
            Row(out=False, status="", text="siap kak", waktu="2026-11-08")]
    ks.catat_chat(NO, rows, tgl, SEN)
    assert kode(SEN) == {"2026-11-05": "C2", "2026-11-06": "C2", "2026-11-07": "C2", "2026-11-09": "T1"}


def test_balasan_minggu_ikut_senin_walau_senin_blast_baru():
    rows = [Row(out=True, status="read", text="blast Kamis", waktu="2026-11-05"),
            Row(out=False, status="", text="Kendala: hujan", waktu="2026-11-08"),
            Row(out=True, status="sent", text="blast Senin", waktu="2026-11-09")]
    ks.catat_chat(NO, rows, tgl, SEN)
    assert ks.siklus(NO, SEN).awal == SEN
    assert kode(SEN) == {"2026-11-09": "T"}
