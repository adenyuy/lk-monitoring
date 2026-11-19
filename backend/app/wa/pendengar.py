"""Pendengar WhatsApp (neonize): perangkat tertaut yang mendengarkan chat. Pengiriman lewat sesi yang sama ada di
wa/pengirim.py (neonize utama, WA Web cadangan).

Sumber utama status chat fasil: pesan keluar (dari aplikasi, WA Web, atau HP), centang diterima / dibaca, dan
balasan fasil masuk seketika, termasuk yang terjadi saat aplikasi mati (disusulkan WhatsApp saat tersambung lagi).
Isinya disimpan sebagai daftar pesan per fasil (neo_pesan) lalu diolah oleh jalur yang sama dengan pengecekan chat
lewat WA Web (chat_refresh.olah_chat), jadi siklus Log Komunikasi, Tindak Lanjut otomatis, dan status chat tetap sama.

Selama pendengar sehat, pengecekan chat lewat jendela WA Web dihentikan. Bila belum ditautkan atau terputus lebih
dari BATAS_PUTUS, aplikasi otomatis kembali memakai WA Web sebagai cadangan.

Hanya chat dengan nomor milik petugas (fasil, koordinator, kepala sekolah binaan) yang disimpan.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .. import db, paths, schedule
from .actions import ChatInfo, Row, chat_info
from . import neonize_siap

neonize_siap.siapkan()  # Mac tanpa libmagic: neonize tetap bisa dimuat

log = logging.getLogger(__name__)

SIMPAN_HARI = 21
BATAS_PUTUS = 15 * 60  # detik: lebih lama dari ini dianggap tidak sehat -> WA Web jadi cadangan
DB_SESI = paths.DATA_DIR / "neonize.db"
URUT = {"pending": 0, "sent": 1, "delivered": 2, "read": 3}

SCHEMA = """
CREATE TABLE IF NOT EXISTS neo_pesan (
    id     TEXT PRIMARY KEY,
    nomor  TEXT NOT NULL,
    keluar INTEGER NOT NULL,
    teks   TEXT NOT NULL DEFAULT '',
    waktu  TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT ''      -- pesan keluar: sent | delivered | read
);
CREATE INDEX IF NOT EXISTS neo_pesan_nomor ON neo_pesan(nomor, waktu);
CREATE TABLE IF NOT EXISTS neo_panggilan (
    id     TEXT PRIMARY KEY,
    nomor  TEXT NOT NULL,
    keluar INTEGER NOT NULL,
    hasil  TEXT NOT NULL,                -- diangkat | tidak
    waktu  TEXT NOT NULL,
    durasi INTEGER NOT NULL DEFAULT 0    -- detik
);
CREATE INDEX IF NOT EXISTS neo_panggilan_nomor ON neo_panggilan(nomor, waktu);
CREATE TABLE IF NOT EXISTS neo_lid (
    lid   TEXT PRIMARY KEY,
    nomor TEXT NOT NULL
);
"""
_siap = False


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
            if "media" not in {r[1] for r in c.execute("PRAGMA table_info(neo_pesan)")}:
                c.execute("ALTER TABLE neo_pesan ADD COLUMN media BLOB")  # pesan foto (protobuf) untuk diunduh nanti
        _siap = True


# ---------- penyimpanan (bisa dites tanpa neonize) ----------

def waktu_dari(ts: int | float) -> datetime:
    """Timestamp WhatsApp (detik atau milidetik) -> datetime lokal."""
    ts = float(ts or 0)
    if ts > 1e11:
        ts /= 1000
    kini = schedule.now()
    return datetime.fromtimestamp(ts, tz=kini.tzinfo) if ts else kini  # zona waktu sama dengan jam aplikasi (WIB)


MAKS_TEKS = 65536  # batas panjang pesan WhatsApp; pesan rekap panjang harus tersimpan utuh


def simpan_pesan(pid: str, nomor: str, keluar: bool, teks: str, waktu: datetime, status: str = "",
                 media: bytes | None = None) -> None:
    _db()
    with db.tx() as c:
        c.execute("INSERT INTO neo_pesan(id, nomor, keluar, teks, waktu, status, media) VALUES(?,?,?,?,?,?,?) "
                  "ON CONFLICT(id) DO UPDATE SET teks = CASE WHEN excluded.teks != '' THEN excluded.teks ELSE teks END, "
                  "media = COALESCE(excluded.media, media)",
                  (pid, nomor, int(keluar), teks[:MAKS_TEKS], waktu.isoformat(timespec="seconds"),
                   (status or "sent") if keluar else "", media))
        if keluar and status:
            _naik(c, nomor, [pid], status, None)


def _naik(c, nomor: str, ids: list[str], status: str, sampai: datetime | None) -> None:
    r = URUT.get(status, -1)
    tingkat = [k for k, v in URUT.items() if v < r]
    if not tingkat:
        return
    tanda = ",".join("?" * len(tingkat))
    if ids:
        c.execute(f"UPDATE neo_pesan SET status = ? WHERE keluar = 1 AND nomor = ? AND id IN ({','.join('?' * len(ids))}) "
                  f"AND status IN ({tanda}, '')", (status, nomor, *ids, *tingkat))
    if sampai is not None:  # dibaca/diterima berarti pesan sebelumnya juga
        c.execute(f"UPDATE neo_pesan SET status = ? WHERE keluar = 1 AND nomor = ? AND waktu <= ? "
                  f"AND status IN ({tanda}, '')", (status, nomor, sampai.isoformat(timespec="seconds"), *tingkat))


def naikkan_status(nomor: str, ids: list[str], status: str, sampai: datetime | None) -> None:
    _db()
    with db.tx() as c:
        _naik(c, nomor, ids, status, sampai)


def simpan_lid(lid: str, nomor: str) -> None:
    if not lid or not nomor:
        return
    _db()
    with db.tx() as c:
        c.execute("INSERT INTO neo_lid(lid, nomor) VALUES(?,?) ON CONFLICT(lid) DO UPDATE SET nomor = excluded.nomor",
                  (lid, nomor))


def nomor_lid(lid: str) -> str:
    _db()
    r = db.query_one("SELECT nomor FROM neo_lid WHERE lid = ?", (lid,))
    return r["nomor"] if r else ""


def baris_chat(nomor: str) -> list[Row]:
    """Pesan tersimpan sebagai baris chat (format sama dengan yang dibaca dari WA Web)."""
    _db()
    sejak = (schedule.now() - timedelta(days=SIMPAN_HARI)).isoformat(timespec="seconds")
    out = []
    for r in db.query("SELECT id, keluar, teks, waktu, status, media IS NOT NULL AS foto FROM neo_pesan "
                      "WHERE nomor = ? AND waktu >= ? ORDER BY waktu, rowid", (nomor, sejak)):
        w = datetime.fromisoformat(r["waktu"])
        out.append(Row(id=r["id"], out=bool(r["keluar"]), status=r["status"] if r["keluar"] else "", text=r["teks"],
                       waktu=f"{w:%H.%M}, {w:%d/%m/%Y}", foto=bool(r["foto"])))
    return out


def foto(nomor: str, pid: str) -> bytes | None:
    """Isi foto satu pesan. Diunduh sekali dari WhatsApp lalu disimpan di folder media; None bila tidak ada."""
    import hashlib

    _db()
    r = db.query_one("SELECT media FROM neo_pesan WHERE id = ? AND nomor = ?", (pid, nomor))
    if not r or not r["media"]:
        return None
    berkas = paths.DATA_DIR / "media" / f"{hashlib.sha1(pid.encode()).hexdigest()}.jpg"
    if berkas.exists():
        return berkas.read_bytes()
    if _klien is None:
        return None
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message

    data = _klien.download_any(Message.FromString(r["media"]))
    if not data:
        return None
    berkas.parent.mkdir(parents=True, exist_ok=True)
    berkas.write_bytes(data)
    return data


def simpan_panggilan(cid: str, nomor: str, keluar: bool, hasil: str, waktu: datetime, durasi: int = 0) -> None:
    _db()
    with db.tx() as c:
        c.execute("INSERT INTO neo_panggilan(id, nomor, keluar, hasil, waktu, durasi) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(id) DO NOTHING", (cid, nomor, int(keluar), hasil, waktu.isoformat(timespec="seconds"),
                                                 int(durasi or 0)))


def panggilan(nomor: str) -> list[dict[str, Any]]:
    """Log telepon WhatsApp dengan nomor ini (3 minggu terakhir), urut waktu."""
    _db()
    sejak = (schedule.now() - timedelta(days=SIMPAN_HARI)).isoformat(timespec="seconds")
    return [{"keluar": bool(r["keluar"]), "hasil": r["hasil"], "durasi": r["durasi"],
             "waktu": datetime.fromisoformat(r["waktu"]).replace(tzinfo=None)}
            for r in db.query("SELECT keluar, hasil, waktu, durasi FROM neo_panggilan WHERE nomor = ? AND waktu >= ? "
                              "ORDER BY waktu", (nomor, sejak))]


def ada_riwayat() -> bool:
    """Sudah ada pesan tersimpan dari pendengar (riwayat saat ditautkan sudah masuk)."""
    _db()
    return db.query_one("SELECT 1 AS x FROM neo_pesan LIMIT 1") is not None


def bersihkan() -> None:
    _db()
    batas = (schedule.now() - timedelta(days=SIMPAN_HARI + 7)).isoformat(timespec="seconds")
    with db.tx() as c:
        c.execute("DELETE FROM neo_pesan WHERE waktu < ?", (batas,))
        c.execute("DELETE FROM neo_panggilan WHERE waktu < ?", (batas,))


def olah(nomor: str) -> ChatInfo | None:
    """Olah ulang satu chat dari pesan tersimpan lewat jalur yang sama dengan pengecekan WA Web."""
    from .. import chat_refresh

    baris = baris_chat(nomor)
    info = chat_info(baris)
    if info.status == "belum_ada":
        return None
    chat_refresh.olah_chat(nomor, info, baris)
    return info


# ---------- status pendengar ----------

@dataclass
class Keadaan:
    status: str = "mati"   # mati | menghubungkan | qr | tersambung | putus | keluar | galat
    qr_svg: str = ""
    akun: str = ""
    sejak: float = field(default_factory=time.time)
    galat: str = ""
    terakhir: float = 0.0  # waktu kejadian terakhir diterima


keadaan = Keadaan()


def tertaut() -> bool:
    return DB_SESI.exists() and bool(db.get_setting("neonize_tertaut", False))


def sehat() -> bool:
    """Pendengar bisa diandalkan: tersambung, atau baru putus sebentar (WhatsApp akan menyusulkan kejadian)."""
    if keadaan.status == "tersambung":
        return True
    return keadaan.status in ("putus", "menghubungkan") and tertaut() and time.time() - keadaan.sejak < BATAS_PUTUS


def ringkas() -> dict[str, Any]:
    return {"status": keadaan.status, "tertaut": tertaut(), "sehat": sehat(), "qr_svg": keadaan.qr_svg,
            "akun": keadaan.akun, "galat": keadaan.galat,
            "sejak": datetime.fromtimestamp(keadaan.sejak).isoformat(timespec="seconds"),
            "terakhir": datetime.fromtimestamp(keadaan.terakhir).isoformat(timespec="seconds") if keadaan.terakhir else ""}


def _ubah(status: str, **kw) -> None:
    keadaan.status, keadaan.sejak = status, time.time()
    for k, v in kw.items():
        setattr(keadaan, k, v)
    try:
        from .. import events

        events.publish("pendengar", status=status)
    except Exception:
        pass


# ---------- antrean olah (kejadian neonize datang dari thread Go; olah di thread sendiri) ----------

_antre: set[str] = set()
_antre_lock = threading.Lock()
_bangun = threading.Event()
_pekerja: threading.Thread | None = None
_sinkron_berikut = 0.0


def antrekan(nomor: str) -> None:
    global _sinkron_berikut
    with _antre_lock:
        _antre.add(nomor)
        if not _sinkron_berikut:
            _sinkron_berikut = time.time() + 60  # Log Komunikasi di sheet ditulis paling cepat tiap menit
    _bangun.set()


def _kerja() -> None:
    global _sinkron_berikut
    while True:
        _bangun.wait(5)
        _bangun.clear()
        with _antre_lock:
            daftar = sorted(_antre)
            _antre.clear()
        if daftar:
            for n in daftar:
                try:
                    olah(n)
                except Exception:
                    log.exception("Chat %s dari pendengar gagal diolah", n)
            try:
                from .. import events

                events.publish("chat_diperbarui", jumlah=len(daftar))
            except Exception:
                pass
        if _sinkron_berikut and time.time() >= _sinkron_berikut:
            _sinkron_berikut = 0.0
            try:
                from .. import komunikasi

                komunikasi.sinkron_wa()
            except Exception:
                log.exception("Sinkron Log Komunikasi dari pendengar gagal")


def _mulai_pekerja() -> None:
    global _pekerja
    if _pekerja is None or not _pekerja.is_alive():
        _pekerja = threading.Thread(target=_kerja, name="pendengar-olah", daemon=True)
        _pekerja.start()


# ---------- neonize ----------

_klien = None
_thread: threading.Thread | None = None
_mulai_lock = threading.Lock()
_milik: tuple[float, set[str]] = (0.0, set())


def _nomor_milik() -> set[str]:
    global _milik
    if time.time() - _milik[0] > 600 or not _milik[1]:
        try:
            from ..sheets import nomor_milik

            _milik = (time.time(), set(nomor_milik()))
        except Exception:
            log.exception("Daftar nomor fasil untuk pendengar tidak terbaca")
    return _milik[1]


def _jid(j) -> tuple[str, str]:
    return (getattr(j, "User", "") or "", getattr(j, "Server", "") or "") if j is not None else ("", "")


def nomor_dari(utama, alt=None) -> str:
    """Nomor HP dari JID (bisa @s.whatsapp.net atau @lid). LID diterjemahkan lewat alt, peta tersimpan, atau neonize."""
    u, srv = _jid(utama)
    au, asrv = _jid(alt)
    if srv == "s.whatsapp.net" and u:
        return u
    if asrv == "s.whatsapp.net" and au:
        if srv == "lid" and u:
            simpan_lid(u, au)
        return au
    if srv == "lid" and u:
        n = nomor_lid(u)
        if n:
            return n
        if _klien is not None:
            try:
                pn = _klien.get_pn_from_lid(utama)
                if pn and pn.User:
                    simpan_lid(u, pn.User)
                    return pn.User
            except Exception:
                pass
    return ""


_MEDIA = (("imageMessage", "[foto]"), ("documentMessage", "[dokumen]"), ("documentWithCaptionMessage", "[dokumen]"),
          ("videoMessage", "[video]"), ("audioMessage", "[pesan suara]"))


def _teks(pesan) -> str:
    """Teks pesan; foto / dokumen / video / pesan suara diberi penanda supaya tetap terhitung sebagai balasan."""
    m = pesan
    for ambil in (lambda: m.conversation, lambda: m.extendedTextMessage.text, lambda: m.imageMessage.caption,
                  lambda: m.documentMessage.caption, lambda: m.videoMessage.caption):
        try:
            t = ambil()
            if t:
                for nama, tanda in _MEDIA:
                    try:
                        if m.HasField(nama):
                            return f"{tanda} {t}"
                    except Exception:
                        pass
                return t
        except Exception:
            continue
    for nama, tanda in _MEDIA:
        try:
            if m.HasField(nama):
                return tanda
        except Exception:
            continue
    return ""


def _media_foto(pesan) -> bytes | None:
    """Protobuf pesan foto (berisi kunci unduhan) untuk diunduh saat dibuka; None bila bukan foto."""
    try:
        return pesan.SerializeToString() if pesan.HasField("imageMessage") else None
    except Exception:
        return None


def _edit_dari(*pesan) -> tuple[str, Any] | None:
    """(ID pesan asli, isi baru) bila ini kabar pesan diedit. Kabar edit punya ID sendiri, jadi isinya harus menimpa
    pesan aslinya; bentuknya bisa langsung protocolMessage atau terbungkus editedMessage."""
    for m in pesan:
        try:
            if m.HasField("editedMessage"):
                m = m.editedMessage.message
            if m.HasField("protocolMessage"):
                p = m.protocolMessage
                if p.type == p.MESSAGE_EDIT and p.key.ID and p.HasField("editedMessage"):
                    return p.key.ID, p.editedMessage
        except (AttributeError, ValueError):
            continue
    return None


def on_pesan(e) -> None:
    src = e.Info.MessageSource
    if src.IsGroup:
        return
    keluar = bool(src.IsFromMe)
    nomor = nomor_dari(src.Chat, src.RecipientAlt if keluar else src.SenderAlt)
    keadaan.terakhir = time.time()
    if not nomor or nomor not in _nomor_milik():
        return
    pid, isi = _edit_dari(getattr(e, "Raw", None), e.Message) or (e.Info.ID, e.Message)
    simpan_pesan(pid, nomor, keluar, _teks(isi), waktu_dari(e.Info.Timestamp), "sent" if keluar else "", _media_foto(isi))
    antrekan(nomor)


def on_centang(e, nama_tipe: str) -> None:
    src = e.MessageSource
    if src.IsGroup or src.IsFromMe:  # READ_SELF dsb: tanda dari perangkat kita sendiri
        return
    status = {"DELIVERED": "delivered", "READ": "read", "PLAYED": "read"}.get(nama_tipe)
    if not status:
        return
    nomor = nomor_dari(src.Chat, src.SenderAlt)
    keadaan.terakhir = time.time()
    if not nomor or nomor not in _nomor_milik():
        return
    naikkan_status(nomor, list(e.MessageIDs), status, waktu_dari(e.Timestamp))
    antrekan(nomor)


def on_riwayat(e) -> None:
    """Riwayat chat saat pertama ditautkan: isi pesan 21 hari terakhir dengan fasil."""
    batas = schedule.now() - timedelta(days=SIMPAN_HARI)
    milik = _nomor_milik()
    sentuh = set()
    status_dari = {"SERVER_ACK": "sent", "DELIVERY_ACK": "delivered", "READ": "read", "PLAYED": "read"}
    # Percakapan di riwayat memakai LID; peta LID -> nomor HP dikirim terpisah di data yang sama.
    peta = 0
    for mp in getattr(e.Data, "phoneNumberToLidMappings", []):
        lid, pn = (mp.lidJID or "").partition("@")[0], (mp.pnJID or "").partition("@")[0]
        if lid and pn:
            simpan_lid(lid, pn)
            peta += 1
    jumlah = cocok = pesan = 0
    for conv in e.Data.conversations:
        jumlah += 1
        cid = conv.ID or ""
        u, _, srv = cid.partition("@")
        pn = (conv.pnJID or "").partition("@")[0]
        if srv == "lid" and pn:
            simpan_lid(u, pn)
        nomor = u if srv == "s.whatsapp.net" else (pn or nomor_lid(u) or _pn_dari_lid(u))
        if not nomor or nomor not in milik:
            continue
        cocok += 1
        for hm in conv.messages:
            w = hm.message
            if not w.key.ID:
                continue
            t = waktu_dari(w.messageTimestamp)
            if t < batas:
                continue
            keluar = bool(w.key.fromMe)
            st = status_dari.get(_nama_status(w), "sent") if keluar else ""
            pid, isi = _edit_dari(w.message) or (w.key.ID, w.message)
            simpan_pesan(pid, nomor, keluar, _teks(isi), t, st, _media_foto(isi))
            sentuh.add(nomor)
            pesan += 1
    telepon = _riwayat_telepon(getattr(e.Data, "callLogRecords", []), milik, batas, sentuh)
    log.info("Riwayat chat: %d percakapan, %d peta LID, %d cocok dengan fasil, %d pesan, %d telepon disimpan",
             jumlah, peta, cocok, pesan, telepon)
    for n in sentuh:
        antrekan(n)


def _nomor_teks(j: str) -> str:
    """Nomor HP dari JID berbentuk teks ("628..@s.whatsapp.net" atau "...@lid")."""
    u, _, srv = (j or "").partition("@")
    u = u.partition(":")[0]
    return (nomor_lid(u) or _pn_dari_lid(u)) if srv == "lid" else u


def _riwayat_telepon(catatan, milik: set[str], batas: datetime, sentuh: set[str]) -> int:
    n = 0
    for rec in catatan:
        try:
            if rec.groupJID:
                continue
            keluar = not rec.isIncoming
            lawan = rec.participants[0].userJID if keluar and len(rec.participants) else rec.callCreatorJID
            nomor = _nomor_teks(lawan)
            t = waktu_dari(rec.startTime)
            if not nomor or nomor not in milik or t < batas or not rec.callID:
                continue
            simpan_panggilan(rec.callID, nomor, keluar, "diangkat" if rec.callResult == 0 else "tidak", t, rec.duration)
            sentuh.add(nomor)
            n += 1
        except Exception:
            log.warning("Satu catatan telepon di riwayat tidak terbaca", exc_info=True)
    return n


def _pn_dari_lid(lid: str) -> str:
    """Tanya peta LID milik neonize (terisi dari riwayat & pesan)."""
    if _klien is None or not lid:
        return ""
    try:
        from neonize.utils.jid import build_jid

        pn = _klien.get_pn_from_lid(build_jid(lid, "lid"))
        if pn and pn.User:
            simpan_lid(lid, pn.User)
            return pn.User
    except Exception:
        pass
    return ""


# ---------- telepon WhatsApp ----------

_saya: set[str] = set()                       # nomor & LID akun sendiri
_panggilan: dict[str, dict[str, Any]] = {}    # callID -> {nomor, keluar, diangkat}
MIN_DERING = 20  # detik: panggilan tak diangkat yang lebih singkat (mis. dibatalkan petugas) tidak dicatat TX


def on_panggil(ev, jenis: str) -> None:
    """Kabar panggilan WhatsApp. Panggilan KELUAR ke fasil: diangkat -> TP, tidak -> dicatat "tidak diangkat"."""
    meta = ev.basicCallMeta
    cid = meta.callID or ""
    lawan = getattr(meta, "from")
    pembuat_u, _ = _jid(meta.callCreator)
    pembuat = nomor_dari(meta.callCreator, meta.callCreatorAlt)
    keluar = bool(_saya) and (pembuat_u in _saya or pembuat in _saya)
    nomor = nomor_dari(lawan) if keluar else pembuat
    log.info("Panggilan WhatsApp %s: %s %s, %s", jenis, "keluar" if keluar else "masuk",
             _samar(nomor) if nomor else "?", cid[:8])
    if not cid:
        return
    if jenis in ("offer", "notice"):
        _panggilan.setdefault(cid, {"nomor": nomor, "keluar": keluar, "diangkat": False, "mulai": time.time()})
    elif jenis == "accept":
        _panggilan.setdefault(cid, {"nomor": nomor, "keluar": keluar, "diangkat": False, "mulai": time.time()})
        _panggilan[cid]["diangkat"] = True
        _panggilan[cid]["angkat"] = time.time()
    elif jenis == "terminate":
        p = _panggilan.pop(cid, None)
        if not p or not p["nomor"] or p["nomor"] not in _nomor_milik():
            return
        try:  # log telepon untuk panel chat, masuk maupun keluar
            simpan_panggilan(cid, p["nomor"], p["keluar"], "diangkat" if p["diangkat"] else "tidak",
                             waktu_dari(p["mulai"]), int(time.time() - p["angkat"]) if p.get("angkat") else 0)
        except Exception:
            log.exception("Log telepon gagal disimpan")
        if not p["keluar"]:
            return
        hasil = "diangkat" if p["diangkat"] else "tidak"
        if hasil == "tidak" and time.time() - p["mulai"] < MIN_DERING:
            log.info("Panggilan %s dibatalkan sebelum %s detik: tidak dicatat", cid[:8], MIN_DERING)
            return
        threading.Thread(target=_catat_panggilan, args=(p["nomor"], hasil, cid), name="pendengar-telepon",
                         daemon=True).start()
    for k in [k for k, v in _panggilan.items() if time.time() - v["mulai"] > 3 * 3600]:  # panggilan basi
        _panggilan.pop(k, None)


def _catat_panggilan(nomor: str, hasil: str, cid: str) -> None:
    try:
        from .. import komunikasi

        f = next((x for x in komunikasi.fasil_saya().values() if x.nomor == nomor), None)
        if f is not None:
            komunikasi.catat_telepon(f, hasil, "wa", cid)
    except Exception:
        log.exception("Telepon WhatsApp gagal dicatat")


def _nama_status(w) -> str:
    try:
        return type(w).Status.Name(w.status)
    except Exception:
        return ""


def _jalan(baru: bool) -> None:
    global _klien
    try:
        from neonize.client import NewClient
        from neonize.events import (CallAcceptEv, CallOfferEv, CallOfferNoticeEv, CallTerminateEv, ConnectedEv,
                                    DisconnectedEv, HistorySyncEv, LoggedOutEv, MessageEv, PairStatusEv, ReceiptEv,
                                    StreamReplacedEv)
        from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
    except Exception as ex:  # neonize belum terpasang / tidak didukung OS ini
        log.exception("neonize tidak bisa dimuat")
        _ubah("galat", galat=f"Pendengar WhatsApp tidak bisa dimuat di laptop ini: {ex}")
        return

    paths.ensure_dirs()
    k = NewClient(str(DB_SESI), uuid=f"lkm-{time.time_ns()}",  # unik per sesi: sesi lama tidak mengganggu yang baru
                  props=DeviceProps(os="LK Monitoring", platformType=DeviceProps.DESKTOP),
                  new_device=baru)
    _klien = k

    @k.qr
    def _qr(_c, data: bytes) -> None:
        import segno

        _ubah("qr", qr_svg=segno.make_qr(data).svg_inline(scale=5, border=4, omitsize=True))

    @k.event(PairStatusEv)
    def _pair(_c, ev) -> None:
        if ev.Error:
            _ubah("galat", galat=f"Penautan gagal: {ev.Error}", qr_svg="")
            return
        db.set_setting("neonize_tertaut", True)
        _ubah("menghubungkan", qr_svg="", akun=_samar(ev.ID.User))

    @k.event(ConnectedEv)
    def _sambung(_c, _ev) -> None:
        db.set_setting("neonize_tertaut", True)
        akun = ""
        try:
            me = k.get_me()
            akun = _samar(me.JID.User)
            _saya.clear()
            _saya.update(x for x in (me.JID.User, me.LID.User) if x)
        except Exception:
            pass
        _ubah("tersambung", qr_svg="", galat="", akun=akun or keadaan.akun)

    @k.event(DisconnectedEv)
    def _putus(_c, _ev) -> None:
        _ubah("putus")

    @k.event(StreamReplacedEv)
    def _diganti(_c, _ev) -> None:
        _ubah("putus", galat="Sesi dipakai di tempat lain.")

    @k.event(LoggedOutEv)
    def _keluar(_c, _ev) -> None:
        db.set_setting("neonize_tertaut", False)
        _ubah("keluar", qr_svg="", galat="Perangkat dilepas dari HP. Tautkan ulang untuk membaca status chat langsung.")

    @k.event(MessageEv)
    def _pesan(_c, ev) -> None:
        try:
            on_pesan(ev)
        except Exception:
            log.exception("Pesan dari pendengar gagal dicatat")

    @k.event(ReceiptEv)
    def _centang(_c, ev) -> None:
        try:
            on_centang(ev, ev.ReceiptType.Name(ev.Type))
        except Exception:
            log.exception("Centang dari pendengar gagal dicatat")

    def _aman(fn, ev, *a):
        try:
            fn(ev, *a)
        except Exception:
            log.exception("Kabar telepon dari pendengar gagal dicatat")

    @k.event(CallOfferEv)
    def _tawar(_c, ev) -> None:
        _aman(on_panggil, ev, "offer")

    @k.event(CallOfferNoticeEv)
    def _tawar2(_c, ev) -> None:
        _aman(on_panggil, ev, "notice")

    @k.event(CallAcceptEv)
    def _terima(_c, ev) -> None:
        _aman(on_panggil, ev, "accept")

    @k.event(CallTerminateEv)
    def _selesai(_c, ev) -> None:
        _aman(on_panggil, ev, "terminate")

    @k.event(HistorySyncEv)
    def _riwayat(_c, ev) -> None:
        try:
            on_riwayat(ev)
        except Exception:
            log.exception("Riwayat chat dari pendengar gagal dicatat")

    _ubah("menghubungkan")
    try:
        k.connect()  # memblokir sampai klien berhenti
    except Exception as ex:
        log.exception("Pendengar WhatsApp berhenti")
        _ubah("galat", galat=str(ex))


def _samar(nomor: str) -> str:
    return f"{nomor[:4]}••••{nomor[-3:]}" if len(nomor) > 7 else nomor


def mulai(baru: bool = False) -> None:
    """Jalankan pendengar di latar (baru=True: tautkan perangkat baru lewat QR)."""
    global _thread
    if os.environ.get("LKM_WA_OTOMATIS_OFF") == "1":
        return
    with _mulai_lock:
        if _thread is not None and _thread.is_alive() and _klien is not None:  # sesudah lepas boleh mulai baru
            return
        _mulai_pekerja()
        bersihkan()
        _thread = threading.Thread(target=_jalan, args=(baru,), name="pendengar-wa", daemon=True)
        _thread.start()


def mulai_bila_tertaut() -> None:
    if tertaut():
        mulai()


def lepas() -> None:
    """Lepas perangkat tertaut (logout) dan hapus sesinya."""
    global _klien
    k = _klien
    if k is not None:
        try:
            k.logout()
        except Exception:
            log.exception("Logout pendengar gagal")
        try:
            k.disconnect()
        except Exception:
            pass
    _klien = None
    if _thread is not None:
        _thread.join(timeout=8)
    db.set_setting("neonize_tertaut", False)
    for f in (DB_SESI, DB_SESI.with_name(DB_SESI.name + "-wal"), DB_SESI.with_name(DB_SESI.name + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
    _ubah("mati", qr_svg="", akun="", galat="")


def berhenti() -> None:
    k = _klien
    if k is not None:
        try:
            k.disconnect()
        except Exception:
            pass
