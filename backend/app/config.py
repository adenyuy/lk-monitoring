"""Konfigurasi aplikasi. Semua nilai di sini boleh publik (repo publik).

ID spreadsheet bukan rahasia: akses tetap dibatasi oleh izin Google masing-masing akun.
"""

import os
from dataclasses import dataclass

from .paths import BACKEND_DIR


def _read_version() -> str:
    # release.yml menulis file ini saat membuat branch release.
    f = BACKEND_DIR / "app" / "_version.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return os.environ.get("LKM_VERSION", "dev")


VERSION = _read_version()

# --- Server ---
HOST = "127.0.0.1"  # hanya bisa diakses dari laptop ini
PORT = 8787
TIMEZONE = "Asia/Jakarta"
DEV_WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# --- Google ---
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Sheet Broadcast (tim)
BROADCAST_SHEET_ID = "ID_SHEET_BROADCAST"
BROADCAST_TAB = "Broadcast"

# LK Monitoring
LK_SHEET_ID = "ID_SHEET_LK"
LK_WEEK_PREFIX = "WEEK "
LK_FIRST_ROW = 3

# Sheet Akses (milik admin, "LK Monitoring - Akses"). Kolom: email | nama_petugas | fitur
# Hanya akun yang diberi akses baca oleh admin yang bisa membukanya.
ACCESS_SHEET_ID = os.environ.get("LKM_ACCESS_SHEET_ID", "ID_SHEET_AKSES")
ACCESS_TAB = "Akses"
FEATURES = ("wa_blast", "cutoff")

# Cache baca sheet (detik)
BROADCAST_CACHE_SECONDS = 300
LK_CACHE_SECONDS = 600
ACCESS_CACHE_SECONDS = 300


# --- WA Blast ---
@dataclass(frozen=True)
class Sesi:
    no: int
    mulai: str  # "HH:MM"
    sampai: str  # "HH:MM", inklusif
    kuota: int


SESI = (
    Sesi(1, "10:00", "13:59", 10),
    Sesi(2, "14:00", "15:59", 10),
    Sesi(3, "16:00", "18:59", 15),
    Sesi(4, "19:00", "20:59", 15),
    Sesi(5, "21:00", "22:00", 10),
)

JEDA_MIN_DETIK = 45
JEDA_MAX_DETIK = 120

BATAS_HARIAN_DEFAULT = 40
BATAS_HARIAN_MIN = 10
BATAS_HARIAN_MAX = 70
BATAS_KUNING = 40  # > nilai ini: peringatan kuning
BATAS_MERAH = 50  # > nilai ini: peringatan merah (nomor pernah diblokir di pesan ke-51)
