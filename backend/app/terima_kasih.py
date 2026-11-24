"""Ucapan terima kasih otomatis setelah fasil membalas dengan Kendala/Tindak lanjut (balasan yang jadi kode T).

Aturan:
- hanya bila saklar di halaman Blast dinyalakan (setting `terima_kasih_otomatis`, bawaan mati);
- hanya lewat WhatsApp langsung (neonize); bila belum tertaut, tidak dikirim (tidak membuka WA Web di latar);
- sekali per fasil (nomor) per sesi isian (WEEK + sesi);
- jeda acak 1-3 menit, hanya pukul 07.00-21.00;
- batal bila dalam jeda itu petugas sudah membalas sendiri.
Teks: template milik petugas di Blast yang judulnya memuat "terima kasih" (jenis fasil), selain itu teks bawaan.
"""

import logging
import random
import threading
from datetime import datetime
from typing import Any, Callable

from . import aktivitas, db, schedule

log = logging.getLogger(__name__)

KUNCI = "terima_kasih_otomatis"
TEKS_BAWAAN = ("Terima kasih atas informasinya, Bapak/Ibu {nama}. Sudah kami catat. Mohon terus dampingi sekolah binaan "
               "agar laporannya segera lengkap 🙏")
JEDA_DETIK = (60.0, 180.0)
JAM = (7, 21)

DDL = """
CREATE TABLE IF NOT EXISTS terima_kasih (
    nomor TEXT NOT NULL,
    sesi  TEXT NOT NULL,
    waktu TEXT NOT NULL,
    PRIMARY KEY (nomor, sesi)
);
"""
_siap = False


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(DDL)
        _siap = True


def aktif() -> bool:
    return db.get_setting(KUNCI, False) is True


def atur(nyala: bool) -> None:
    db.set_setting(KUNCI, bool(nyala))


def _salam(jam: int) -> str:
    return "pagi" if jam < 11 else "siang" if jam < 15 else "sore" if jam < 18 else "malam"


def teks_untuk(nama: str, petugas: str = "", sekarang: datetime | None = None) -> str:
    """Isi template terima kasih untuk fasil `nama`."""
    teks = TEKS_BAWAAN
    for t in db.get_setting("blast_template_saya", []) or []:
        if isinstance(t, dict) and t.get("jenis") == "fasil" and "terima kasih" in str(t.get("judul", "")).casefold():
            teks = str(t.get("teks") or teks)
            break
    jam = (sekarang or schedule.now()).hour
    return (teks.replace("{nama}", nama or "").replace("{petugas}", petugas or "")
            .replace("{salam}", _salam(jam)).strip())


def _sesi() -> str:
    from . import lk_baru

    week = lk_baru.week_aktif()
    return f"WEEK {week} sesi {lk_baru.blok_untuk(schedule.now().date())}"


def sudah(nomor: str, sesi: str) -> bool:
    _db()
    return db.query_one("SELECT 1 FROM terima_kasih WHERE nomor = ? AND sesi = ?", (nomor, sesi)) is not None


def jadwalkan(nomor: str, nama: str, timer: Callable[..., Any] = threading.Timer) -> bool:
    """Dipanggil saat balasan berformat Kendala/Tindak lanjut baru terbaca. True bila pengiriman dijadwalkan."""
    if not nomor or not aktif():
        return False
    now = schedule.now()
    if not (JAM[0] <= now.hour < JAM[1]):
        return False
    sesi = _sesi()
    if sudah(nomor, sesi):
        return False
    t = timer(random.uniform(*JEDA_DETIK), kirim, (nomor, nama, sesi, now.isoformat(timespec="seconds")))
    t.daemon = True
    t.start()
    return True


def kirim(nomor: str, nama: str, sesi: str, sejak: str) -> str:
    """Kirim bila masih memenuhi syarat. Mengembalikan: terkirim | mati | sudah | dibalas | belum_tertaut | gagal."""
    if not aktif():
        return "mati"
    if sudah(nomor, sesi):
        return "sudah"
    try:
        balas = db.query_one("SELECT 1 FROM neo_pesan WHERE nomor = ? AND keluar = 1 AND waktu > ?", (nomor, sejak))
    except Exception:  # noqa: BLE001 - tabel pendengar belum ada: WhatsApp langsung belum pernah ditautkan
        return "belum_tertaut"
    if balas:
        return "dibalas"  # petugas sudah membalas sendiri
    from . import komunikasi
    from .wa import pengirim

    try:
        petugas = komunikasi.petugas_saya()
    except Exception:  # noqa: BLE001
        petugas = ""
    teks = teks_untuk(nama, petugas)
    try:
        hasil = pengirim.kirim_satu(nomor, teks)
    except Exception:  # noqa: BLE001
        log.warning("Terima kasih otomatis gagal dikirim", exc_info=True)
        return "gagal"
    if hasil is None:
        return "belum_tertaut"
    r, _jalur = hasil
    if r.status != "terkirim":
        log.info("Terima kasih otomatis tidak terkirim: %s", r.keterangan or r.status)
        return "gagal"
    _db()
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO terima_kasih(nomor, sesi, waktu) VALUES(?,?,?)",
                  (nomor, sesi, schedule.now().isoformat(timespec="seconds")))
    aktivitas.catat(nomor, "kirim", "Terima kasih otomatis terkirim (balasan Kendala/Tindak lanjut)", nama)
    return "terkirim"
