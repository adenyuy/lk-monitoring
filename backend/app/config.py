"""Konfigurasi aplikasi. Semua nilai di sini boleh publik (repo publik).

ID spreadsheet TIDAK ditulis di sini: sheet tim dibagikan lewat link, jadi ID-nya dirahasiakan.
ID dibaca dari `sheets.json` di folder data (dipasang dari file paket lk-monitoring.json kiriman admin),
atau dari variabel lingkungan LKM_BROADCAST_SHEET_ID / LKM_LK_SHEET_ID / LKM_ACCESS_SHEET_ID (develop & tes).
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
# Naikkan tiap ada endpoint baru; tampilan membandingkannya untuk mendeteksi server yang belum di-restart.
API_REV = 20

# --- Server ---
HOST = "127.0.0.1"  # hanya bisa diakses dari laptop ini
PORT = int(os.environ.get("LKM_PORT", "8787"))  # LKM_PORT hanya untuk uji
TIMEZONE = "Asia/Jakarta"
DEV_WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# --- Google ---
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Sheet Broadcast (tim). ID: lihat sheet_ids().
BROADCAST_TAB = "Broadcast"

# LK Monitoring
LK_WEEK_PREFIX = "WEEK "
LK_FIRST_ROW = 3

# Sheet Akses (milik admin, "LK Monitoring - Akses"). Kolom: email | nama_petugas | fitur
# Hanya akun yang diberi akses baca oleh admin yang bisa membukanya.
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
BATAS_HARIAN_AMAN = 50  # di atas ini wajib mengetik KALIMAT_RISIKO
KALIMAT_RISIKO = "risiko ditanggung sendiri"
BATAS_KUNING = 40  # > nilai ini: peringatan kuning
BATAS_MERAH = 50  # > nilai ini: peringatan merah (nomor pernah diblokir di pesan ke-51)


# --- ID sheet (rahasia, di luar repo) ---
SHEET_KEYS = {"broadcast": "BROADCAST_SHEET_ID", "lk": "LK_SHEET_ID", "akses": "ACCESS_SHEET_ID"}


def sheet_ids() -> dict[str, str]:
    """{"broadcast": id, "lk": id, "akses": id}; nilai kosong bila belum dipasang."""
    import json

    from . import paths

    out = {k: "" for k in SHEET_KEYS}
    f = paths.DATA_DIR / "sheets.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.update({k: str(data.get(k) or "") for k in SHEET_KEYS})
        except (ValueError, OSError):
            pass
    for k, nama in SHEET_KEYS.items():
        out[k] = os.environ.get(f"LKM_{nama}", out[k])
    return out


def __getattr__(nama: str) -> str:
    """config.BROADCAST_SHEET_ID dkk. tetap bisa dipakai seperti konstanta."""
    for k, v in SHEET_KEYS.items():
        if nama == v:
            return sheet_ids()[k]
    raise AttributeError(nama)
