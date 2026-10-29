"""Isian LK otomatis: saat fasil membalas, status komunikasi semua sekolahnya jadi "Terhubung".

Dijalankan di latar (tidak menahan pengecekan chat) dan tidak pernah menggagalkan aksi utama.
Sekolah yang sudah Selesai atau statusnya sudah Terhubung tidak disentuh.
"""

import logging
import os
import threading

from . import aktivitas, db, tahap
from .sheets import kolom_lk, nomor_key, read_lk, read_validasi, sekolah_per_fasil, week_aktif, write_isian

log = logging.getLogger(__name__)
_lock = threading.Lock()


def pilihan_terhubung(opsi: list[str]) -> str:
    """'0. Terhubung' dari daftar pilihan status komunikasi (tab validasi)."""
    return next((o for o in opsi if "terhubung" in o.lower() and "belum" not in o.lower()), "")


def terhubung(nomor: str) -> None:
    if os.environ.get("LKM_LK_OTOMATIS_OFF") == "1":
        return
    threading.Thread(target=tandai_terhubung, args=(nomor,), daemon=True).start()


def tandai_terhubung(nomor: str) -> int:
    """Tulis status komunikasi Terhubung ke sekolah fasil `nomor`. Mengembalikan jumlah sekolah yang diubah."""
    try:
        with _lock:
            week = week_aktif()
            petugas = db.get_setting("nama_petugas") or ""
            sekolah = sekolah_per_fasil(read_lk(week), petugas).get(nomor_key(nomor), [])
            target = pilihan_terhubung(read_validasi()["komunikasi"])
            ubah = [s for s in sekolah if tahap.perlu_isian(s) and s.komunikasi != target]
            if not target or not ubah:
                return 0
            kol = kolom_lk(week, refresh=True)
            write_isian(week, [(s, {kol.komunikasi: target}) for s in ubah], kol)
            for s in ubah:
                s.komunikasi = target
            aktivitas.catat(nomor, "lk", f"Status komunikasi otomatis “{target}” untuk {len(ubah)} sekolah "
                                         f"(fasil membalas)", ubah[0].fasil)
            return len(ubah)
    except Exception:
        log.exception("Gagal mengisi status komunikasi otomatis")
        return 0
