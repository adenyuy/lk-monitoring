"""Perbarui status chat (dibaca / dibalas) untuk kiriman 7 hari terakhir.

Berjalan tiap 10 menit dan bisa dipicu manual, hanya bila jendela WhatsApp app
terbuka dan pengiriman TIDAK sedang berjalan (pengiriman selalu didahulukan).

Pindai harian: chat semua fasil dibuka sekali per hari (yang belum dicek hari itu), supaya blast lewat HP ikut
terbaca: pesan keluarnya memulai siklus Log Komunikasi (kom_siklus) dengan tanggal pesan aslinya, lalu chat itu
ikut dipantau tiap 10 menit. Fasil yang belum tercatat dihubungi minggu ini juga dicatat sebagai sudah dihubungi.
Tombol "Saya sudah blast lewat HP" memicu pindai ulang semua chat saat itu juga (pindai_sekarang).
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


def _sibuk() -> bool:
    from .blast import sibuk

    return sibuk()

INTERVAL_DETIK = 10 * 60
HARI_KE_BELAKANG = 7

_lock = threading.Lock()
_wake = threading.Event()
_thread: threading.Thread | None = None


def refresh_once() -> dict:
    from .wa import pendengar

    if pendengar.sehat():  # status chat sudah masuk langsung; cukup perbarui Log Komunikasi (hari tanpa kejadian)
        try:
            from . import komunikasi

            komunikasi.sinkron_wa()
        except Exception:
            log.exception("Sinkron Log Komunikasi gagal")
        return {"dilewati": "Status chat dibaca langsung oleh pendengar WhatsApp."}
    if not _lock.acquire(blocking=False):
        return {"dilewati": "Pembaruan chat sedang berjalan."}
    try:
        if _sibuk():
            return {"dilewati": "Pengiriman sedang berjalan."}
        if not worker.browser_open():
            return {"dilewati": "Jendela WhatsApp belum dibuka."}
        if not db.get_setting("wa_otomatis", True):
            return {"dilewati": "WhatsApp otomatis dimatikan."}
        since = schedule.tanggal_str((schedule.now() - timedelta(days=HARI_KE_BELAKANG)).date())
        nomor_list = store.to_refresh(since)
        diperbarui = 0
        for nomor in nomor_list:
            if _sibuk():  # pengiriman dimulai di tengah jalan -> mengalah
                break
            info, baris = worker.call(lambda b, n=nomor: actions.read_thread(b, n), timeout=120)
            if info.status == "belum_ada":
                continue
            olah_chat(nomor, info, baris)
            diperbarui += 1
        events.publish("chat_diperbarui", jumlah=diperbarui)
        try:
            from . import komunikasi

            komunikasi.sinkron_wa()
        except Exception:
            log.exception("Sinkron Log Komunikasi gagal")
        return {"diperbarui": diperbarui, "dicek": len(nomor_list)}
    except Exception as e:
        log.exception("Pembaruan chat gagal")
        return {"error": str(e)}
    finally:
        _lock.release()


def olah_chat(nomor: str, info: actions.ChatInfo, baris: list[actions.Row]) -> None:
    """Olah isi satu chat (dari layar WA Web atau dari pendengar neonize): siklus Log Komunikasi, Tindak Lanjut
    otomatis, tag warna, dan status chat."""
    _catat_siklus(nomor, baris)
    if info.status == "dibalas":
        try:  # balasan berformat "Kendala: … Tindak lanjut: …" -> isi Tindak Lanjut di LK
            from . import tl_auto

            tl_auto.proses(nomor, baris)
        except Exception:
            log.exception("Tindak lanjut otomatis dari balasan gagal")
    if info.status in ("dibaca", "dibalas") or info.centang in ("delivered", "read"):
        tagging.tandai(nomor, "hijau")
    balasan = info.balasan[-1] if info.balasan else ""
    store.save_chat_status(nomor, info.status, balasan, schedule.now().isoformat(timespec="seconds"),
                           info.terakhir_masuk)


def _catat_siklus(nomor: str, baris: list[actions.Row]) -> None:
    """Catat centang & balasan untuk kode Log Komunikasi per siklus (lihat kom_siklus)."""
    try:
        from . import kom_siklus

        kom_siklus.catat_chat(nomor, baris, tanggal_pesan, schedule.now().date())
    except Exception:
        log.exception("Kejadian chat untuk Log Komunikasi gagal dicatat")


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


pindai_state = {"berjalan": False, "dicek": 0, "total": 0, "selesai": ""}


def pindai_awal(paksa: bool = False) -> int:
    """Buka chat semua fasil sekali per hari (paksa: semuanya sekarang, mis. sesudah blast lewat HP)."""
    from .sheets import nomor_milik

    senin = tahap.senin_iso()
    hari = schedule.now().date().isoformat()
    try:
        catatan = json.loads(db.get_setting("pindai_awal") or "{}")
    except ValueError:
        catatan = {}
    sudah = set(catatan.get("nomor", [])) if catatan.get("hari") == hari and not paksa else set()
    dicek = set() if paksa else {r["nomor"] for r in db.query(
        "SELECT nomor FROM chat_status WHERE substr(dicek, 1, 10) = ?", (hari,))}
    kontak = tahap.kontak_minggu()
    try:
        semua = sorted(nomor_milik())
    except Exception:
        log.exception("Daftar fasil untuk pindai harian tidak terbaca")
        return 0
    sisa = [n for n in semua if n not in sudah and n not in dicek]
    if not sisa:
        return 0
    pindai_state.update(berjalan=True, dicek=0, total=len(sisa), selesai="")
    tercatat = 0
    try:
        for n in sisa:
            if _sibuk():
                break
            try:
                _, rows = worker.call(lambda b, x=n: actions.read_thread(b, x), timeout=120)
            except actions.NotLoggedIn:
                break
            except Exception:
                log.exception("Pindai harian %s gagal", n)
                continue
            _catat_siklus(n, rows)
            if not kontak.get(n, {}).get("terkirim") and catat_dari_chat(n, rows, date.fromisoformat(senin)):
                tercatat += 1
            sudah.add(n)
            pindai_state["dicek"] += 1
            db.set_setting("pindai_awal", json.dumps({"hari": hari, "nomor": sorted(sudah)}))
    finally:
        pindai_state.update(berjalan=False, selesai=schedule.now().isoformat(timespec="seconds"))
    if tercatat:
        events.publish("chat_diperbarui", jumlah=tercatat)
    return tercatat


def pindai_sekarang() -> None:
    """Minta pindai ulang semua chat fasil (dijalankan di putaran latar berikutnya)."""
    db.set_setting("pindai_paksa", True)
    pindai_state.update(berjalan=True, dicek=0, total=0, selesai="")
    trigger()


def _pindai() -> None:
    from .wa import pendengar

    if pendengar.sehat():  # blast lewat HP sudah terbaca langsung; tidak perlu membuka chat satu per satu
        db.set_setting("pindai_paksa", False)
        pindai_state.update(berjalan=False)
        return
    if not _lock.acquire(blocking=False):
        return
    paksa = bool(db.get_setting("pindai_paksa", False))
    try:
        if not _sibuk() and worker.browser_open() and db.get_setting("wa_otomatis", True):
            if paksa:
                db.set_setting("pindai_paksa", False)
            pindai_awal(paksa)
        elif paksa:
            pindai_state.update(berjalan=False)
    except Exception:
        log.exception("Pindai harian gagal")
        pindai_state.update(berjalan=False)
    finally:
        _lock.release()


def _buka_wa() -> None:
    """WhatsApp yang pernah tertaut langsung dibuka saat aplikasi jalan, supaya chat bisa dicek tanpa menunggu."""
    if (os.environ.get("LKM_WA_OTOMATIS_OFF") == "1" or not db.get_setting("wa_terhubung", False)
            or not db.get_setting("wa_otomatis", True)):
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
