from datetime import datetime
from types import SimpleNamespace as NS

import pytest

from app import db, komunikasi, lk_baru, schedule, telepon
from app.wa import pendengar

NO = "6281200000003"


@pytest.fixture(autouse=True)
def bersih(monkeypatch):
    telepon._db()
    with db.tx() as c:
        c.execute("DELETE FROM telepon")
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 9, 10))  # Senin
    yield


def test_perlu_ditelepon():
    # Bara: Sabtu R, Senin R (Minggu dilewati)
    assert telepon.perlu({"2026-11-07": "R", "2026-11-09": "R"}, "2026-11-09") == (True, "2 hari hanya dibaca, belum membalas")
    # campuran kode sulit 2 hari kerja (C2 lalu R) juga perlu telepon / koordinator
    assert telepon.perlu({"2026-11-07": "C2", "2026-11-09": "R"}, "2026-11-09")[0] is True
    assert telepon.perlu({"2026-11-07": "TX", "2026-11-09": "C2"}, "2026-11-09")[0] is True
    assert telepon.perlu({"2026-11-07": "R", "2026-11-09": "K"}, "2026-11-09")[0] is False  # koor sudah dihubungi
    assert telepon.perlu({"2026-11-07": "C", "2026-11-09": "C"}, "2026-11-09")[0] is True
    assert telepon.perlu({"2026-11-09": "N"}, "2026-11-09")[0] is True
    assert telepon.perlu({"2026-11-07": "R", "2026-11-09": "T1"}, "2026-11-09")[0] is False
    # hari pertama Log Komunikasi: belum ada dua hari
    assert telepon.perlu({"2026-11-09": "R"}, "2026-11-09", "2026-11-09")[0] is False


def test_tidak_diangkat_menunda_sampai_besok():
    kode = {"2026-11-07": "R", "2026-11-09": "R"}
    telepon.catat(NO, "tidak")
    k = telepon.keadaan(NO, kode, "2026-11-09")
    assert not k["perlu"] and k["dicoba"] and k["terakhir"]["hasil"] == "tidak"
    kode["2026-11-10"] = "R"
    assert telepon.keadaan(NO, kode, "2026-11-10")["perlu"]  # besok masih belum ada kabar: muncul lagi


def test_diangkat_menulis_tp(monkeypatch):
    tulis = {}
    monkeypatch.setattr(lk_baru, "tulis_log_kom", lambda t, x: tulis.setdefault(t, x) and len(x))
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: lk_baru.LogKom({}, {}, {}))
    f = NS(nomor=NO, nama="Fasil Uji", sekolah=[NS(npsn="111"), NS(npsn="222")])
    r = komunikasi.catat_telepon(f, "diangkat")
    assert r["tp_ditulis"] == 2 and tulis == {"2026-11-09": {"111": "TP", "222": "TP"}}
    assert telepon.riwayat(NO)[0]["label"] == "Diangkat"


def test_tidak_diangkat_menulis_tx_tanpa_menimpa_kode_kuat(monkeypatch):
    tulis = {}
    monkeypatch.setattr(lk_baru, "tulis_log_kom", lambda t, x: tulis.setdefault(t, x) and len(x))
    monkeypatch.setattr(lk_baru, "pastikan_kode_dropdown", lambda k: True)
    monkeypatch.setattr(lk_baru, "pastikan_legenda", lambda: True)
    # 111 hari ini R (boleh diganti TX), 222 sudah T (fasil membalas: dibiarkan)
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: lk_baru.LogKom(
        {}, {}, {"111": {"2026-11-09": "R"}, "222": {"2026-11-09": "T"}}))
    f = NS(nomor=NO, nama="Fasil Uji", sekolah=[NS(npsn="111"), NS(npsn="222")])
    r = komunikasi.catat_telepon(f, "tidak")
    assert r["kode"] == "TX" and tulis == {"2026-11-09": {"111": "TX"}}


def test_prioritas_kode():
    assert lk_baru.kalah("", "TX") and lk_baru.kalah("R", "TX") and lk_baru.kalah("C2", "TX")
    assert not lk_baru.kalah("T", "TX") and not lk_baru.kalah("TP", "K") and lk_baru.kalah("TX", "K")
    assert not lk_baru.kalah("K", "TX")


def test_panggilan_whatsapp_keluar(monkeypatch):
    dicatat = []
    monkeypatch.setattr(pendengar, "_nomor_milik", lambda: {NO})
    monkeypatch.setattr(pendengar, "_catat_panggilan", lambda n, h, c: dicatat.append((n, h, c)))
    monkeypatch.setattr(pendengar.threading, "Thread",
                        lambda target, args, **kw: NS(start=lambda: target(*args)))
    pendengar._saya.clear()
    pendengar._saya.add("6285000000001")
    me = NS(User="6285000000001", Server="s.whatsapp.net")
    kosong = NS(User="", Server="")
    fasil = NS(User=NO, Server="s.whatsapp.net")

    def ev(cid):
        return NS(basicCallMeta=NS(callID=cid, callCreator=me, callCreatorAlt=kosong, **{"from": fasil}))

    for j in ("offer", "accept", "terminate"):
        pendengar.on_panggil(ev("A1"), j)
    jam = [1000.0]
    monkeypatch.setattr(pendengar.time, "time", lambda: jam[0])
    pendengar.on_panggil(ev("B2"), "offer")
    jam[0] += 25  # berdering 25 detik, tidak diangkat -> dicatat
    pendengar.on_panggil(ev("B2"), "terminate")
    pendengar.on_panggil(ev("D4"), "offer")
    jam[0] += 5   # dibatalkan setelah 5 detik -> tidak dicatat
    pendengar.on_panggil(ev("D4"), "terminate")
    assert dicatat == [(NO, "diangkat", "A1"), (NO, "tidak", "B2")]
    # panggilan MASUK dari fasil tidak dicatat sebagai telepon kita
    masuk = NS(basicCallMeta=NS(callID="C3", callCreator=fasil, callCreatorAlt=kosong, **{"from": fasil}))
    for j in ("offer", "terminate"):
        pendengar.on_panggil(masuk, j)
    assert len(dicatat) == 2


def test_satu_panggilan_satu_catatan():
    telepon.catat(NO, "tidak", "wa", "X9")
    telepon.catat(NO, "diangkat", "wa", "X9")
    assert [r["hasil"] for r in telepon.riwayat(NO)] == ["diangkat"]


def test_fasil_belum_pernah_ditelepon():
    k = telepon.keadaan("6281299999999", {"2026-11-07": "R", "2026-11-09": "R"}, "2026-11-09")
    assert k["perlu"] and k["terakhir"] is None
    assert telepon.keadaan("", {}, "2026-11-09")["terakhir"] is None


def test_koordinator_dihubungi_menulis_k_dan_tag(monkeypatch):
    tulis = {}
    monkeypatch.setattr(lk_baru, "tulis_log_kom", lambda t, x: tulis.setdefault(t, {}).update(x) or len(x))
    monkeypatch.setattr(lk_baru, "pastikan_kode_dropdown", lambda k: True)
    monkeypatch.setattr(lk_baru, "pastikan_legenda", lambda: True)
    monkeypatch.setattr(lk_baru, "baca_log_kom", lambda refresh=False: lk_baru.LogKom(
        {}, {}, {"111": {"2026-11-09": "C2"}, "333": {"2026-11-09": "T"}}))
    monkeypatch.setattr(lk_baru, "rentang_blok", lambda hari: (datetime(2026, 11, 9).date(), datetime(2026, 11, 11).date()))
    koor = "6281200000099"
    komunikasi._db_koor()
    with db.tx() as c:
        c.execute("DELETE FROM kom_koor")
        c.execute("DELETE FROM chat_status WHERE nomor = ?", (koor,))
    a = NS(kunci="A", nomor=NO, nama="Fasil A", koor="Koor X", sekolah=[NS(npsn="111"), NS(npsn="222")])
    b = NS(kunci="B", nomor="6281200000004", nama="Fasil B", koor="Koor X", sekolah=[NS(npsn="333")])
    r = komunikasi.catat_koor([a, b], koor)
    # 111 (C2) dan 222 (kosong) jadi K; 333 sudah T (fasil membalas) dibiarkan
    assert tulis == {"2026-11-09": {"111": "K", "222": "K"}} and r["ditulis"] == 2
    assert komunikasi.koor_belum_balas(["A", "B", "Z"]) == {"A", "B"}
    # koordinator membalas setelahnya: tag hilang
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO chat_status(nomor, status, balasan_terakhir, waktu_balasan, dicek) "
                  "VALUES(?, 'dibalas', 'siap', '2026-11-09T11:00:00', '2026-11-09T11:00:00')", (koor,))
    assert komunikasi.koor_belum_balas(["A", "B"]) == set()
