"""Isian LK otomatis: status komunikasi sekolah mengikuti keadaan chat fasil minggu ini.

- Fasil membalas                          -> "0. Terhubung"
- Pesan dibaca tapi tidak dibalas         -> "3. Chat hanya di Read"
- Nomor tidak terdaftar di WhatsApp       -> "1. Nomor Tidak Terhubung Whatsapp"

Terhubung menimpa status kosong atau status otomatis lain (Read / Tidak terhubung / Checklist 1); status lain
hanya mengisi yang kosong, jadi pilihan manual (mis. "Respon Lambat") tidak tertimpa. Sekolah Selesai tidak disentuh.
Dijalankan di latar (tidak menahan pengecekan chat) dan tidak pernah menggagalkan aksi utama.
"""

import logging
import os
import threading
import time

from . import aktivitas, db, tahap
from .send_queue import GAGAL_PERMANEN
from .sheets import kolom_lk, nomor_key, read_lk, read_validasi, sekolah_per_fasil, week_aktif, write_isian

log = logging.getLogger(__name__)
_lock = threading.Lock()
_bangun = threading.Event()
_mulai = threading.Lock()
_thread: threading.Thread | None = None

TERHUBUNG, TIDAK_WA, HANYA_READ = "terhubung", "tidak_wa", "read"


def pilihan(opsi: list[str], jenis: str) -> str:
    """Teks pilihan status komunikasi (tab validasi) untuk `jenis`."""
    def cocok(o: str) -> bool:
        t = o.lower()
        if jenis == TERHUBUNG:
            return "terhubung" in t and "tidak" not in t and "belum" not in t
        if jenis == TIDAK_WA:
            return "tidak terhubung" in t or ("tidak" in t and "whatsapp" in t)
        return "read" in t or "dibaca" in t

    return next((o for o in opsi if cocok(o)), "")


def pilihan_terhubung(opsi: list[str]) -> str:
    return pilihan(opsi, TERHUBUNG)


def _boleh_ditimpa(nilai: str, jenis: str) -> bool:
    t = nilai.strip().lower()
    if not t:
        return True
    return jenis == TERHUBUNG and ("read" in t or "tidak terhubung" in t or "checklist" in t)


def status_minggu() -> dict[str, str]:
    """{nomor: jenis} dari kiriman dan pengecekan chat minggu ini."""
    senin = tahap.senin_iso()
    out: dict[str, str] = {}
    for r in db.query("SELECT nomor FROM sends WHERE coba = 0 AND status = 'gagal' AND waktu >= ? AND keterangan LIKE ?",
                      (senin, f"%{GAGAL_PERMANEN}%")):
        out[r["nomor"]] = TIDAK_WA
    for n, k in tahap.kontak_minggu().items():
        if k["dibalas"]:
            out[n] = TERHUBUNG
        elif k["dibaca"]:
            out[n] = HANYA_READ
        elif k["terkirim"] and out.get(n) == TIDAK_WA:
            del out[n]  # sempat gagal tapi akhirnya terkirim
    # Membalas minggu ini walau pesan kita terkirim minggu lalu
    for r in db.query("SELECT nomor FROM chat_status WHERE status = 'dibalas' AND waktu_balasan >= ?", (senin,)):
        out[r["nomor"]] = TERHUBUNG
    return out


def sinkron() -> int:
    """Tulis status komunikasi otomatis ke LK. Mengembalikan jumlah sekolah yang diubah."""
    try:
        with _lock:
            status = status_minggu()
            petugas = db.get_setting("nama_petugas") or ""
            if not status or not petugas:
                return 0
            week = week_aktif()
            per_fasil = sekolah_per_fasil(read_lk(week, refresh=True), petugas)
            opsi = read_validasi()["komunikasi"]
            ubah, catatan = [], []
            for nomor, jenis in status.items():
                target = pilihan(opsi, jenis)
                sekolah = [s for s in per_fasil.get(nomor_key(nomor), [])
                           if tahap.perlu_isian(s) and s.komunikasi != target and _boleh_ditimpa(s.komunikasi, jenis)]
                if target and sekolah:
                    ubah += [(s, target) for s in sekolah]
                    catatan.append((nomor, target, sekolah))
            if not ubah:
                return 0
            kol = kolom_lk(week, refresh=True)
            write_isian(week, [(s, {kol.komunikasi: t}) for s, t in ubah], kol)
            for s, t in ubah:
                s.komunikasi = t
            for nomor, t, sekolah in catatan:
                aktivitas.catat(nomor, "lk", f"Status komunikasi otomatis “{t}” untuk {len(sekolah)} sekolah",
                                sekolah[0].fasil)
            return len(ubah)
    except Exception:
        log.exception("Gagal mengisi status komunikasi otomatis")
        return 0


def _loop() -> None:
    while True:
        _bangun.wait()
        time.sleep(5)  # kumpulkan beberapa pemicu (satu putaran cek chat) jadi sekali tulis
        _bangun.clear()
        sinkron()


def picu() -> None:
    """Jadwalkan sinkron di latar. Aman dipanggil berkali-kali."""
    if os.environ.get("LKM_LK_OTOMATIS_OFF") == "1":
        return
    global _thread
    _bangun.set()
    with _mulai:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_loop, name="lk-otomatis", daemon=True)
            _thread.start()
