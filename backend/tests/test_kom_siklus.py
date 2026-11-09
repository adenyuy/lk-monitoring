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
    assert tulis == {  # 06/11 = C2 tapi dropdown terkunci: dilewati, TIDAK diganti C (maknanya beda)
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


def test_blast_hp_senin_memulai_siklus_baru(monkeypatch):
    # blast lewat HP ke banyak fasil hari Senin = putaran (chat satuan tidak mengulang siklus)
    monkeypatch.setattr(ks, "putaran", lambda hari: [KAM, SEN])
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


def test_balasan_minggu_ikut_senin_walau_senin_blast_baru(monkeypatch):
    # blast lewat HP ke banyak fasil hari Senin = putaran (chat satuan tidak mengulang siklus)
    monkeypatch.setattr(ks, "putaran", lambda hari: [KAM, SEN])
    rows = [Row(out=True, status="read", text="blast Kamis", waktu="2026-11-05"),
            Row(out=False, status="", text="Kendala: hujan", waktu="2026-11-08"),
            Row(out=True, status="sent", text="blast Senin", waktu="2026-11-09")]
    ks.catat_chat(NO, rows, tgl, SEN)
    assert ks.siklus(NO, SEN).awal == SEN
    assert kode(SEN) == {"2026-11-09": "T"}


def test_cek_baris_log_kom_satu_permintaan(monkeypatch):
    from app import lk_baru

    minta = []

    class Ss:
        def values_get(self, rng, params=None):
            minta.append(rng)
            return {"values": [["NPSN"], ["111"], [222.0], [""], ["444"]]}

    monkeypatch.setattr(lk_baru, "_ss", lambda: Ss())
    lk = lk_baru.LogKom({}, {"111": 2, "222": 3, "444": 5}, {})
    assert lk_baru._baris_kom_cocok(lk, ["111", "222", "444"])
    assert minta == ["'Log Komunikasi'!B1:B5"]  # satu rentang, berapa pun jumlah sekolahnya
    lk.baris["444"] = 4  # baris bergeser
    assert not lk_baru._baris_kom_cocok(lk, ["444"])


def test_tanpa_bukti_kosong_dan_tebakan_lama_dihapus():
    kirim(JUM)  # terkirim dari aplikasi, chat belum pernah terbaca
    assert ks.susun_semua(NO, SEN, {}, {}) == {}  # tidak menebak C
    # C lama buatan aplikasi dihapus; isian petugas dibiarkan
    hasil = ks.susun_semua(NO, SEN, {"2026-11-06": "C", "2026-11-07": "TP"}, {"2026-11-06": "C", "2026-11-07": "C"})
    assert hasil == {"2026-11-06": "", "2026-11-09": "TP"}  # isian petugas diteruskan ke Senin


def test_siklus_lama_berhenti_sebelum_siklus_baru():
    kirim(date(2026, 11, 2))
    ks.catat_chat(NO, [Row(out=True, status="read", text="a", waktu="2026-11-02"),
                       Row(out=False, status="", text="ok", waktu="2026-11-02")], tgl, SEN)
    kirim(JUM)
    ks.catat_chat(NO, [Row(out=True, status="read", text="a", waktu="2026-11-02"),
                       Row(out=False, status="", text="ok", waktu="2026-11-02"),
                       Row(out=True, status="delivered", text="b", waktu="2026-11-06")], tgl, SEN)
    h = ks.susun_semua(NO, SEN, {}, {})
    assert h["2026-11-05"] == "T1" and h["2026-11-06"] == "C2" and h["2026-11-09"] == "C2"


def test_fasil_tanpa_kiriman_tebakan_dihapus():
    assert ks.susun_semua(NO, SEN, {"2026-11-06": "C"}, {"2026-11-06": "C"}) == {"2026-11-06": ""}
    assert ks.susun_semua(NO, SEN, {"2026-11-06": "R"}, {}) == {}  # isian petugas


def test_putaran_mengakhiri_siklus_fasil_yang_tidak_ikut():
    # putaran 2 Nov (fasil ini ikut) lalu putaran Jumat 6 Nov ke fasil lain: fasil ini kosong sejak 6 Nov
    kirim(date(2026, 11, 2))
    ks.catat_chat(NO, [Row(out=True, status="read", text="a", waktu="2026-11-02"),
                       Row(out=False, status="", text="ok", waktu="2026-11-02")], tgl, SEN)
    put = [date(2026, 11, 2), JUM]
    h = ks.susun_semua(NO, SEN, {}, {}, put)
    assert h["2026-11-05"] == "T1" and "2026-11-06" not in h and "2026-11-09" not in h
    assert ks.status_sekarang(NO, SEN, put) == ""  # di halaman Blast: belum di-chat di putaran terakhir
    # sel buatan aplikasi sesudah putaran baru dikosongkan
    assert ks.susun_semua(NO, SEN, {"2026-11-06": "T1"}, {"2026-11-06": "T1"}, put)["2026-11-06"] == ""


def test_putaran_dari_jumlah_fasil():
    for i in range(ks.MIN_PUTARAN):
        with db.tx() as c:
            c.execute("INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status, keterangan, coba) "
                      "VALUES('2026-11-06','2026-11-06T08:00:00',0,'F',?,'blast:x','terkirim','',0)", (f"6281{i:09d}",))
        c = None
    with db.tx() as c:  # survei ke banyak fasil bukan putaran
        for i in range(10):
            c.execute("INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status, keterangan, coba) "
                      "VALUES('2026-11-03','2026-11-03T08:00:00',3,'F',?,'svy:x','terkirim','',0)", (f"6282{i:09d}",))
    try:
        p = ks.putaran(SEN)
        assert JUM in p and date(2026, 11, 3) not in p
    finally:
        with db.tx() as c:
            c.execute("DELETE FROM sends WHERE nomor LIKE '6281_________' OR nomor LIKE '6282_________'")


def test_t_hanya_bila_menyebut_kendala_atau_tindak_lanjut():
    assert ks.konfirmasi("kendalanya sekolah belum upload BKU, sudah saya ingatkan")
    assert ks.konfirmasi("SD A tidak ada kendala pak")
    assert ks.konfirmasi("Tindak lanjutnya minggu depan kepsek kirim laporan")
    # balasan lain tetap T1, walau panjang atau berisi laporan/foto
    assert not ks.konfirmasi("Berikut update progres minggu ke-2 sekolah binaan")
    assert not ks.konfirmasi("sudah saya ingatkan kepseknya kak, " * 3)
    assert not ks.konfirmasi("[foto]") and not ks.konfirmasi("[dokumen] laporan.pdf")
    assert not ks.konfirmasi("oke kak siap")
    assert not ks.konfirmasi("baik kak, kendalanya nanti saya kabari")


def test_konfirmasi_dihitung_ulang_saat_chat_dibaca_lagi():
    ks.catat_balas(NO, [(JUM, "sudah dikirim laporan panjang sekali")])
    with db.tx() as c:  # catatan lama dengan aturan lama (dulu dianggap T)
        c.execute("UPDATE kom_balas SET konfirmasi = 1 WHERE nomor = ?", (NO,))
    ks.catat_balas(NO, [(JUM, "sudah dikirim laporan panjang sekali"), (JUM, "oke")])
    assert db.query_one("SELECT konfirmasi FROM kom_balas WHERE nomor = ?", (NO,))["konfirmasi"] == 0
    ks.catat_balas(NO, [(JUM, "oke"), (JUM, "Kendala: hujan")])
    assert db.query_one("SELECT konfirmasi FROM kom_balas WHERE nomor = ?", (NO,))["konfirmasi"] == 1


def test_respon_lambat_t2():
    kirim(date(2026, 11, 2))
    ks.catat_chat(NO, [Row(out=True, status="read", text="a", waktu="2026-11-02"),
                       Row(out=False, status="", text="oke kak", waktu="2026-11-05")], tgl, SEN)
    h = ks.susun_semua(NO, SEN, {}, {}, [date(2026, 11, 2)])
    assert h["2026-11-04"] == "C2" and h["2026-11-05"] == "T2"  # baru dibalas hari kerja ke-3


def test_chat_lanjutan_di_tengah_siklus_tidak_mengulang():
    # blast Jumat dari aplikasi; Sabtu petugas chat "gimana kak?" (bukan putaran) -> siklus Jumat tetap jalan
    kirim(JUM)
    rows = [Row(out=True, status="read", text="blast", waktu="2026-11-06"),
            Row(out=True, status="read", text="gimana kak?", waktu="2026-11-07")]
    ks.catat_chat(NO, rows, tgl, SEN)
    put = [JUM]
    s = ks.daftar_siklus(NO, SEN, put)
    assert [x.awal for x in s] == [JUM]
    assert ks.susun_semua(NO, SEN, {}, {}, put) == {"2026-11-06": "C2", "2026-11-07": "C2", "2026-11-09": "R"}


def test_chat_satuan_di_luar_siklus_memulai_siklus():
    # fasil tidak ikut putaran Jumat; Senin petugas chat dia sendiri -> siklus baru mulai Senin
    ks.catat_chat(NO, [Row(out=True, status="delivered", text="halo kak, gimana progresnya?", waktu="2026-11-09")],
                  tgl, SEN)
    assert [x.awal for x in ks.daftar_siklus(NO, SEN, [JUM])] == [SEN]
