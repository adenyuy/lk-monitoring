"""Perbarui status chat (dibaca / dibalas) untuk kiriman 7 hari terakhir.

Berjalan tiap 15 menit dan bisa dipicu manual, hanya bila jendela WhatsApp app
terbuka dan pengiriman TIDAK sedang berjalan (pengiriman selalu didahulukan).
"""

import logging
import threading
from datetime import timedelta

from . import events, schedule, store
from .sender import sender
from .wa import actions
from .wa.browser import worker

log = logging.getLogger(__name__)
INTERVAL_DETIK = 15 * 60
HARI_KE_BELAKANG = 7

_lock = threading.Lock()
_wake = threading.Event()
_thread: threading.Thread | None = None


def refresh_once() -> dict:
    if not _lock.acquire(blocking=False):
        return {"dilewati": "Pembaruan chat sedang berjalan."}
    try:
        if sender.state.running:
            return {"dilewati": "Pengiriman sedang berjalan."}
        if not worker.browser_open():
            return {"dilewati": "Jendela WhatsApp belum dibuka."}
        since = schedule.tanggal_str((schedule.now() - timedelta(days=HARI_KE_BELAKANG)).date())
        nomor_list = store.to_refresh(since)
        diperbarui = 0
        for nomor in nomor_list:
            if sender.state.running:  # pengiriman dimulai di tengah jalan -> mengalah
                break
            info = worker.call(lambda b, n=nomor: actions.read_chat(b, n), timeout=120)
            if info.status == "belum_ada":
                continue
            balasan = info.balasan[-1] if info.balasan else ""
            store.save_chat_status(nomor, info.status, balasan, schedule.now().isoformat(timespec="seconds"))
            diperbarui += 1
        events.publish("chat_diperbarui", jumlah=diperbarui)
        return {"diperbarui": diperbarui, "dicek": len(nomor_list)}
    except Exception as e:
        log.exception("Pembaruan chat gagal")
        return {"error": str(e)}
    finally:
        _lock.release()


def _loop() -> None:
    while True:
        _wake.wait(INTERVAL_DETIK)
        _wake.clear()
        refresh_once()


def start_background() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="chat-refresh", daemon=True)
        _thread.start()


def trigger() -> None:
    _wake.set()
