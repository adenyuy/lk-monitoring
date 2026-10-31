"""Perbarui status chat (dibaca / dibalas) untuk kiriman 7 hari terakhir.

Berjalan tiap 10 menit dan bisa dipicu manual, hanya bila jendela WhatsApp app
terbuka dan pengiriman TIDAK sedang berjalan (pengiriman selalu didahulukan).

Pindai awal: fasil yang belum tercatat dihubungi minggu ini (mis. pengguna baru, atau chat lewat HP) dicek sekali
per minggu. Bila minggu ini sudah ada pesan keluar di chat-nya, fasil itu dihitung sudah dihubungi, lalu status
dibaca / dibalasnya ikut tercatat, jadi langsung masuk kelompok yang benar.
"""

import json
import logging
import os
import re
import threading
from datetime import date, timedelta

from . import aktivitas, db, events, schedule, store, tagging, tahap
from .sender import sender
from .wa import actions
from .wa.browser import worker

log = logging.getLogger(__name__)
INTERVAL_DETIK = 10 * 60
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
            if info.status in ("dibaca", "dibalas") or info.centang in ("delivered", "read"):
                tagging.tandai(nomor, "hijau")
            balasan = info.balasan[-1] if info.balasan else ""
            store.save_chat_status(nomor, info.status, balasan, schedule.now().isoformat(timespec="seconds"),
                                   info.terakhir_masuk)
            diperbarui += 1
        events.publish("chat_diperbarui", jumlah=diperbarui)
        return {"diperbarui": diperbarui, "dicek": len(nomor_list)}
    except Exception as e:
        log.exception("Pembaruan chat gagal")
        return {"error": str(e)}
    finally:
        _lock.release()


def tanggal_pesan(waktu: str) -> date | None:
    """'10.37, 26/10/2026' atau '15.50, 10/30/2026' (atribut pesan WhatsApp, urutan ikut bahasa Chrome) -> date.
    Bila dua-duanya mungkin (mis. 5/11), dipilih yang tidak di masa depan dan paling dekat dengan hari ini."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", waktu or "")
    if not m:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hari_ini = schedule.now().date()
    calon = []
    for hari, bulan in ((a, b), (b, a)):
        try:
            calon.append(date(y, bulan, hari))
        except ValueError:
            pass
    lalu = [d for d in calon if d <= hari_ini]
    return max(lalu) if lalu else (min(calon) if calon else None)


def catat_dari_chat(nomor: str, rows: list[actions.Row], senin: date) -> str:
    """Catat kontak minggu ini dari isi chat (untuk fasil yang belum tercatat). Mengembalikan status yang dicatat."""
    minggu = [r for r in rows if (d := tanggal_pesan(r.waktu)) and d >= senin]
    keluar = [r for r in minggu if r.out and r.text]
    if not keluar:
        return ""
    ringkas = " ".join(keluar[-1].text.split())
    aktivitas.catat(nomor, "balas", "Chat minggu ini terdeteksi di WhatsApp: "
                    + (ringkas if len(ringkas) <= 70 else ringkas[:69] + "…"))
    info = actions.chat_info(minggu)
    balasan = info.balasan[-1] if info.balasan else ""
    store.save_chat_status(nomor, info.status, balasan, schedule.now().isoformat(timespec="seconds"),
                           info.terakhir_masuk)
    return info.status


def pindai_awal() -> int:
    """Cek sekali per minggu chat fasil yang belum tercatat dihubungi minggu ini."""
    from .sheets import nomor_milik

    senin = tahap.senin_iso()
    try:
        catatan = json.loads(db.get_setting("pindai_awal") or "{}")
    except ValueError:
        catatan = {}
    sudah = set(catatan.get("nomor", [])) if catatan.get("senin") == senin else set()
    kontak = tahap.kontak_minggu()
    try:
        semua = sorted(nomor_milik())
    except Exception:
        log.exception("Daftar fasil untuk pindai awal tidak terbaca")
        return 0
    sisa = [n for n in semua if n not in sudah and not kontak.get(n, {}).get("terkirim")]
    tercatat = 0
    for n in sisa:
        if sender.state.running:
            break
        try:
            _, rows = worker.call(lambda b, x=n: actions.read_thread(b, x), timeout=120)
        except actions.NotLoggedIn:
            break
        except Exception:
            log.exception("Pindai awal %s gagal", n)
            continue
        if catat_dari_chat(n, rows, date.fromisoformat(senin)):
            tercatat += 1
        sudah.add(n)
        db.set_setting("pindai_awal", json.dumps({"senin": senin, "nomor": sorted(sudah)}))
    if tercatat:
        events.publish("chat_diperbarui", jumlah=tercatat)
    return tercatat


def _pindai() -> None:
    if not _lock.acquire(blocking=False):
        return
    try:
        if not sender.state.running and worker.browser_open():
            pindai_awal()
    except Exception:
        log.exception("Pindai awal gagal")
    finally:
        _lock.release()


def _buka_wa() -> None:
    """WhatsApp yang pernah tertaut langsung dibuka saat aplikasi jalan, supaya chat bisa dicek tanpa menunggu."""
    if os.environ.get("LKM_WA_OTOMATIS_OFF") == "1" or not db.get_setting("wa_terhubung", False):
        return
    try:
        if not worker.browser_open():
            worker.call(lambda b: b.open(), timeout=90)
    except Exception:
        log.exception("WhatsApp tidak bisa dibuka otomatis")


PERTAMA_DETIK = 60  # cek pertama tak lama setelah aplikasi jalan


def _loop() -> None:
    _buka_wa()
    _wake.wait(PERTAMA_DETIK)
    _wake.clear()
    _pindai()
    refresh_once()
    while True:
        _wake.wait(INTERVAL_DETIK)
        _wake.clear()
        _pindai()
        refresh_once()


def start_background() -> None:
    # Sekali saja: chat yang terakhir dicek sebelum fitur "perlu dibalas" ada dicek ulang semua
    if not db.get_setting("perlu_balas_sejak"):
        db.set_setting("perlu_balas_sejak", schedule.now().isoformat(timespec="seconds"))
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="chat-refresh", daemon=True)
        _thread.start()


def trigger() -> None:
    _wake.set()
