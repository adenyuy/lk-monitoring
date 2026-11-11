from datetime import datetime
from types import SimpleNamespace as NS

import pytest

from app import db, kom_siklus, schedule
from app.wa import pendengar as p

FASIL = "6281200000002"
LID = "258896000000001"
TS = int(datetime(2026, 11, 6, 9, 0).timestamp() * 1000)  # Jumat


def jid(user, server):
    return NS(User=user, Server=server)


KOSONG = jid("", "")


@pytest.fixture(autouse=True)
def siap(monkeypatch):
    p._db()
    kom_siklus._db()
    with db.tx() as c:
        for t in ("neo_pesan", "neo_lid", "kom_amat", "kom_balas", "kom_mulai"):
            c.execute(f"DELETE FROM {t}")
    monkeypatch.setattr(p, "_nomor_milik", lambda: {FASIL})
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 9, 10))  # Senin
    antre = []
    monkeypatch.setattr(p, "antrekan", antre.append)
    yield antre


def pesan(pid, keluar, teks, ts=TS, chat=None, alt=None):
    src = NS(IsGroup=False, IsFromMe=keluar, Chat=chat or jid(LID, "lid"),
             RecipientAlt=alt if keluar else KOSONG, SenderAlt=KOSONG if keluar else alt)
    return NS(Info=NS(MessageSource=src, ID=pid, Timestamp=ts), Message=NS(conversation=teks))


def centang(ids, ts=TS + 60_000):
    src = NS(IsGroup=False, IsFromMe=False, Chat=jid(LID, "lid"), SenderAlt=KOSONG)
    return NS(MessageSource=src, MessageIDs=ids, Timestamp=ts)


def test_pesan_keluar_lid_lalu_centang_lalu_balasan(siap):
    # blast lewat HP: chat @lid, nomor asli di RecipientAlt -> peta LID tersimpan
    p.on_pesan(pesan("A1", True, "Halo kak, mohon info kendala", alt=jid(FASIL, "s.whatsapp.net")))
    assert p.nomor_lid(LID) == FASIL and siap == [FASIL]
    # centang hanya membawa LID: tetap cocok ke fasil lewat peta
    p.on_centang(centang(["A1"]), "DELIVERED")
    p.on_centang(centang(["A1"], TS + 120_000), "READ")
    p.on_pesan(pesan("B1", False, "1. SD A\nKendala: hujan\nTindak lanjut: lembur", TS + 86_400_000,
                     alt=jid(FASIL, "s.whatsapp.net")))
    rows = p.baris_chat(FASIL)
    assert [(r.out, r.status) for r in rows] == [(True, "read"), (False, "")]
    assert rows[0].waktu == "09.00, 06/11/2026"
    # jalur siklus yang sama dengan WA Web: Jumat C2? tidak -> dibaca Jumat (R), Sabtu balasan Kendala (T)
    kom_siklus.catat_chat(FASIL, rows, __import__("app.chat_refresh", fromlist=["x"]).tanggal_pesan,
                          schedule.now().date())
    s = kom_siklus.siklus(FASIL, schedule.now().date())
    assert s.awal.isoformat() == "2026-11-06"
    hasil = kom_siklus.susun(s, kom_siklus.kejadian(FASIL, s), schedule.now().date(), {}, {})
    assert hasil["2026-11-07"] == "T" and "2026-11-09" not in hasil  # Senin sesi baru


def test_nomor_bukan_fasil_diabaikan(siap):
    p.on_pesan(pesan("X1", False, "promo", alt=jid("6289999999999", "s.whatsapp.net"),
                     chat=jid("777", "lid")))
    assert siap == [] and p.baris_chat("6289999999999") == []


def test_centang_dari_diri_sendiri_dan_grup_diabaikan(siap):
    p.on_pesan(pesan("A1", True, "x", alt=jid(FASIL, "s.whatsapp.net")))
    siap.clear()
    c = centang(["A1"])
    c.MessageSource.IsFromMe = True  # READ_SELF: kita membaca pesan fasil
    p.on_centang(c, "READ_SELF")
    assert siap == [] and p.baris_chat(FASIL)[0].status == "sent"


def test_status_tidak_turun(siap):
    p.simpan_pesan("A1", FASIL, True, "x", datetime(2026, 11, 6, 9), "read")
    p.naikkan_status(FASIL, ["A1"], "delivered", None)
    assert p.baris_chat(FASIL)[0].status == "read"


def test_riwayat_saat_ditautkan(siap, monkeypatch):
    w = NS(key=NS(ID="H1", fromMe=True), messageTimestamp=TS // 1000, status=4, message=NS(conversation="blast lama"))
    lama = NS(key=NS(ID="H0", fromMe=True), messageTimestamp=TS // 1000 - 40 * 86400, status=4,
              message=NS(conversation="terlalu lama"))
    conv = NS(ID=f"{LID}@lid", pnJID=f"{FASIL}@s.whatsapp.net", messages=[NS(message=w), NS(message=lama)])
    lain = NS(ID="6289999999999@s.whatsapp.net", pnJID="", messages=[NS(message=w)])
    monkeypatch.setattr(p, "_nama_status", lambda _w: "READ")
    p.on_riwayat(NS(Data=NS(conversations=[conv, lain])))
    rows = p.baris_chat(FASIL)
    assert [(r.text, r.status) for r in rows] == [("blast lama", "read")] and siap == [FASIL]


def test_sehat_dan_cadangan(monkeypatch):
    monkeypatch.setattr(p, "tertaut", lambda: True)
    p.keadaan.status, p.keadaan.sejak = "tersambung", 0
    assert p.sehat()
    p.keadaan.status, p.keadaan.sejak = "putus", __import__("time").time() - 60
    assert p.sehat()  # baru putus sebentar
    p.keadaan.sejak = __import__("time").time() - p.BATAS_PUTUS - 1
    assert not p.sehat()  # terlalu lama: WA Web jadi cadangan
    p.keadaan.status = "mati"


def test_riwayat_lid_dipetakan_lewat_daftar_terpisah(siap, monkeypatch):
    monkeypatch.setattr(p, "_nama_status", lambda _w: "DELIVERY_ACK")
    w = NS(key=NS(ID="H2", fromMe=True), messageTimestamp=TS // 1000, status=3, message=NS(conversation="blast"))
    conv = NS(ID=f"{LID}@lid", pnJID="", messages=[NS(message=w)])  # tanpa pnJID, seperti riwayat asli
    peta = [NS(lidJID=f"{LID}@lid", pnJID=f"{FASIL}@s.whatsapp.net")]
    p.on_riwayat(NS(Data=NS(conversations=[conv], phoneNumberToLidMappings=peta)))
    assert [(r.text, r.status) for r in p.baris_chat(FASIL)] == [("blast", "delivered")] and siap == [FASIL]


def test_riwayat_dengan_jam_berzona_waktu(siap, monkeypatch):
    # jam aplikasi berzona waktu (WIB), timestamp WhatsApp tidak: dulu error "offset-naive and offset-aware"
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 9, 10, tzinfo=ZoneInfo("Asia/Jakarta")))
    monkeypatch.setattr(p, "_nama_status", lambda _w: "READ")
    ts = int(datetime(2026, 11, 6, 9, tzinfo=ZoneInfo("Asia/Jakarta")).timestamp())  # tidak bergantung zona waktu laptop
    w = NS(key=NS(ID="H3", fromMe=False), messageTimestamp=ts, status=0, message=NS(conversation="oke"))
    p.on_riwayat(NS(Data=NS(conversations=[NS(ID=f"{FASIL}@s.whatsapp.net", pnJID="", messages=[NS(message=w)])],
                            phoneNumberToLidMappings=[])))
    rows = p.baris_chat(FASIL)
    assert [r.text for r in rows] == ["oke"] and rows[0].waktu == "09.00, 06/11/2026"


def test_chat_lewat_hp_hari_ini_terhitung_di_blast():
    from app.routers import blast as rute

    p.simpan_pesan("N1", FASIL, True, "halo kak", datetime(2026, 11, 9, 8, 15), "sent")  # terbaca pendengar
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO kom_mulai VALUES(?, ?)", ("6281200000009", "2026-11-09"))  # terbaca WA Web
    try:
        hasil = rute._chat_hari_ini({FASIL, "6281200000009", "6281200000010"})
        assert hasil == {FASIL: "08.15", "6281200000009": "lewat HP"}
    finally:
        with db.tx() as c:
            c.execute("DELETE FROM kom_mulai WHERE nomor = '6281200000009'")
