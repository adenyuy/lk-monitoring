"""Pengirim pesan WhatsApp: neonize (utama) dengan WA Web sebagai cadangan.

Neonize dipakai bila perangkat tertaut sedang tersambung dan pengaturan `kirim_lewat` bukan "waweb". Bila tidak
(belum ditautkan, terputus, laptop Mac tanpa neonize), pengiriman otomatis lewat jendela WA Web seperti dulu.

Supaya tetap terlihat seperti orang mengetik: sebelum kirim, status "sedang mengetik…" ditampilkan beberapa detik
sesuai panjang pesan. Jeda antar pesan, batas harian, dan istirahat tetap diatur oleh mesin blast / sesi.
Pesan yang gagal TIDAK dikirim ulang otomatis lewat jalur lain, supaya fasil tidak menerima pesan ganda.
"""

import logging
import random
import threading
import time
from typing import Any, Callable

from .. import db, schedule
from . import pendengar
from .actions import OpenResult, SendResult

log = logging.getLogger(__name__)

KETIK_MIN, KETIK_MAKS = 2.0, 9.0      # detik "sedang mengetik…"
HURUF_PER_DETIK = 18.0
TUNGGU_CENTANG = 6.0                   # detik menunggu centang dua setelah terkirim
SIMPAN_CEK = 6 * 3600                  # hasil cek nomor terdaftar disimpan sementara

_cek: dict[str, tuple[float, Any]] = {}
_cek_lock = threading.Lock()


class NeoTidakSiap(Exception):
    """Neonize tidak bisa dipakai saat ini (pakai WA Web)."""


def lewat() -> str:
    """Pengaturan jalur kirim: 'neonize' (bawaan) atau 'waweb'."""
    v = str(db.get_setting("kirim_lewat", "neonize") or "neonize")
    return v if v in ("neonize", "waweb") else "neonize"


def neo_siap() -> bool:
    return (lewat() == "neonize" and pendengar._klien is not None and pendengar.keadaan.status == "tersambung")


def mesin_aktif() -> str:
    """Jalur yang akan dipakai untuk pesan berikutnya: 'neonize' atau 'waweb'."""
    return "neonize" if neo_siap() else "waweb"


def _klien():
    k = pendengar._klien
    if k is None or pendengar.keadaan.status != "tersambung":
        raise NeoTidakSiap("WhatsApp (neonize) tidak tersambung.")
    return k


def jid_nomor(nomor: str):
    """JID akun WhatsApp untuk `nomor`, atau None bila nomor tidak terdaftar. NeoTidakSiap bila tidak bisa dicek."""
    with _cek_lock:
        ada = _cek.get(nomor)
    if ada and time.time() - ada[0] < SIMPAN_CEK:
        return ada[1]
    try:
        hasil = _klien().is_on_whatsapp(nomor)
    except NeoTidakSiap:
        raise
    except Exception as e:
        raise NeoTidakSiap(f"Nomor tidak bisa dicek: {e}") from e
    r = hasil[0] if hasil else None
    jid = r.JID if r is not None and r.IsIn else None
    with _cek_lock:
        _cek[nomor] = (time.time(), jid)
    return jid


def lama_ketik(teks: str, rng: random.Random | None = None) -> float:
    rng = rng or random
    dasar = len(teks) / HURUF_PER_DETIK
    return max(KETIK_MIN, min(KETIK_MAKS, dasar * rng.uniform(0.7, 1.1)))


def _status_pesan(pid: str) -> str:
    pendengar._db()
    r = db.query_one("SELECT status FROM neo_pesan WHERE id = ?", (pid,))
    return (r["status"] if r else "") or "sent"


def kirim_neo(nomor: str, teks: str, jid=None, sleep: Callable[[float], None] = time.sleep) -> SendResult:
    """Kirim satu pesan teks lewat neonize. Tidak pernah dicoba ulang lewat jalur lain."""
    k = _klien()
    if jid is None:
        jid = jid_nomor(nomor)
        if jid is None:
            return SendResult("gagal", "Nomor tidak terdaftar di WhatsApp.")
    try:
        # diimpor di sini: neonize tidak terpasang di CI (Linux) dan Mac lama; tanpa itu tetap jalan tanpa status mengetik
        from neonize.utils.enum import ChatPresence, ChatPresenceMedia

        k.send_chat_presence(jid, ChatPresence.CHAT_PRESENCE_COMPOSING, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
        sleep(lama_ketik(teks))
        k.send_chat_presence(jid, ChatPresence.CHAT_PRESENCE_PAUSED, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
    except Exception:
        log.debug("Status mengetik tidak terkirim", exc_info=True)  # tidak menghalangi pengiriman
    try:
        resp = k.send_message(jid, teks)
    except Exception as e:
        log.warning("Kirim lewat neonize gagal ke %s: %s", pendengar._samar(nomor), e)
        return SendResult("gagal", f"WhatsApp menolak pesan: {e}")

    # pesan dari perangkat ini tidak selalu muncul lagi sebagai kejadian: simpan sendiri supaya chat & siklus terisi
    pid = getattr(resp, "ID", "") or f"neo-{time.time_ns()}"
    pendengar.simpan_pesan(pid, nomor, True, teks, schedule.now(), "sent")
    pendengar.antrekan(nomor)
    sampai = time.time() + TUNGGU_CENTANG
    status = "sent"
    while time.time() < sampai:
        status = _status_pesan(pid)
        if status != "sent":
            break
        sleep(0.5)
    return SendResult("terkirim", centang=status)


class PengirimWA:
    """Adaptor kirim untuk mesin blast & sesi (antarmuka sama dengan WorkerWA).

    open_chat memilih jalur untuk satu pesan; send memakai jalur yang sama. Kalau neonize tidak bisa mengecek
    nomor (mis. baru terputus), pesan itu lewat WA Web. Begitu pesan dikirim, jalurnya tidak diganti lagi."""

    def __init__(self, web=None, sleep: Callable[[float], None] = time.sleep) -> None:
        if web is None:
            from ..sender import WorkerWA

            web = WorkerWA()
        self.web = web
        self.sleep = sleep
        self.jalur = ""
        self._neo: tuple[str, str, Any] | None = None

    def open_chat(self, nomor: str, teks: str) -> OpenResult:
        self._neo = None
        if neo_siap():
            try:
                jid = jid_nomor(nomor)
            except NeoTidakSiap as e:
                log.warning("Neonize tidak bisa dipakai (%s); pesan ini lewat WA Web", e)
            else:
                self.jalur = "neonize"
                if jid is None:
                    return OpenResult(False, "nomor_tidak_terdaftar")
                self._neo = (nomor, teks, jid)
                return OpenResult(True)
        self.jalur = "waweb"
        return self.web.open_chat(nomor, teks)

    def send(self) -> SendResult:
        if self._neo is not None:
            nomor, teks, jid = self._neo
            self._neo = None
            try:
                return kirim_neo(nomor, teks, jid, self.sleep)
            except NeoTidakSiap as e:
                return SendResult("gagal", f"{e} Coba kirim lagi.")
        return self.web.send()

    def clear_draft(self) -> None:
        if self._neo is not None or self.jalur == "neonize":
            self._neo = None
            return
        self.web.clear_draft()


def kirim_satu(nomor: str, teks: str) -> tuple[SendResult, str] | None:
    """Kirim satu pesan (balas chat) lewat neonize bila siap. None = pakai WA Web."""
    if not neo_siap():
        return None
    try:
        jid = jid_nomor(nomor)
    except NeoTidakSiap:
        return None
    if jid is None:
        return SendResult("gagal", "Nomor tidak terdaftar di WhatsApp."), "neonize"
    return kirim_neo(nomor, teks, jid), "neonize"
