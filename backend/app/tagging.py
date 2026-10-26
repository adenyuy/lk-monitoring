"""Tandai warna nama + nomor fasil (kolom B:C) di tab 'Broadcast P1' sesuai hasil kirim.

Hijau  = terkirim dan sudah centang dua (diterima/dibaca)
Kuning = terkirim, masih centang satu
Merah  = nomor tidak terdaftar di WhatsApp

Penulisan berjalan di thread sendiri supaya pengiriman tidak tertahan. Warna tidak pernah
turun (hijau tidak kembali kuning) dan hanya ditulis bila berubah.
"""

import logging
import os
import queue
import threading

from . import config, db, schedule, store
from .sheets import cache, filter_petugas, gspread_client, parse_broadcast

log = logging.getLogger(__name__)

TAB = "Broadcast P1"
WARNA = {
    "hijau": {"red": 0.714, "green": 0.843, "blue": 0.659},   # #b6d7a8
    "kuning": {"red": 1.0, "green": 0.898, "blue": 0.6},      # #ffe599
    "merah": {"red": 0.918, "green": 0.6, "blue": 0.6},       # #ea9999
}
_PERINGKAT = {"kuning": 1, "hijau": 2, "merah": 2}

_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def aktif() -> bool:
    # Mati saat memakai data uji (LKM_BROADCAST_FILE) atau dimatikan lewat LKM_TAG_OFF / pengaturan.
    if os.environ.get("LKM_BROADCAST_FILE") or os.environ.get("LKM_TAG_OFF"):
        return False
    return bool(db.get_setting("tag_warna", True))


def warna_kirim(centang: str) -> str:
    """Warna untuk pesan yang baru terkirim, dari ikon status terakhir."""
    return "hijau" if centang in ("delivered", "read") else "kuning"


def perlu_ditulis(lama: str | None, baru: str) -> bool:
    if lama == baru:
        return False
    if lama is None:
        return True
    if lama == "merah" or baru == "merah":
        return baru == "merah" and lama != "merah"
    return _PERINGKAT[baru] > _PERINGKAT[lama]


def tandai(nomor: str, warna: str) -> None:
    """Antrekan penandaan. Aman dipanggil dari mana saja."""
    if warna not in WARNA or not nomor or not aktif():
        return
    if not perlu_ditulis(store.tag_all().get(nomor), warna):
        return
    _q.put((nomor, warna))
    _mulai()


def _mulai() -> None:
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_loop, name="tagging", daemon=True)
            _thread.start()


def _baris_milik() -> tuple[int, dict[str, list[int]]]:
    """(sheetId tab, {nomor: [baris]}) untuk fasil petugas ini di 'Broadcast P1'."""
    def load():
        ss = gspread_client().open_by_key(config.BROADCAST_SHEET_ID)
        ws = ss.worksheet(TAB)
        rows = filter_petugas(parse_broadcast(ws.get("A1:E")), db.get_setting("nama_petugas") or "")
        peta: dict[str, list[int]] = {}
        for r in rows:
            if r.nomor:
                peta.setdefault(r.nomor, []).append(r.baris)
        return ws.id, peta

    return cache.get("tag_baris", 600, load)


def tulis(nomor: str, warna: str) -> bool:
    sheet_id, peta = _baris_milik()
    baris = peta.get(nomor, [])
    if not baris:
        log.info("Nomor %s tidak ada di %s, lewati penandaan", nomor[-4:], TAB)
        return False
    ss = gspread_client().open_by_key(config.BROADCAST_SHEET_ID)
    ss.batch_update({"requests": [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": b - 1, "endRowIndex": b,
                      "startColumnIndex": 1, "endColumnIndex": 3},  # B:C
            "cell": {"userEnteredFormat": {"backgroundColor": WARNA[warna]}},
            "fields": "userEnteredFormat.backgroundColor",
        }} for b in baris
    ]})
    store.set_tag(nomor, warna, schedule.now().isoformat(timespec="seconds"))
    return True


def _loop() -> None:
    while True:
        nomor, warna = _q.get()
        try:
            if perlu_ditulis(store.tag_all().get(nomor), warna):
                tulis(nomor, warna)
        except Exception:
            log.exception("Penandaan warna Broadcast P1 gagal (akan dicoba lagi saat status berubah)")
