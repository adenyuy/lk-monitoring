"""Lokasi file. Data pengguna disimpan di luar folder repo supaya update tidak menyentuhnya."""

import os
from pathlib import Path

APP_DIR_NAME = "LKMonitoring"

# backend/app/paths.py -> repo root dua tingkat di atas folder backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
WEB_OUT_DIR = REPO_DIR / "web" / "out"


def _data_dir() -> Path:
    # LKM_DATA_DIR dipakai test agar tidak menyentuh data asli.
    override = os.environ.get("LKM_DATA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME


DATA_DIR = _data_dir()
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.json"
DB_FILE = DATA_DIR / "data.db"
CHROME_PROFILE_DIR = DATA_DIR / "chrome-profile"
LOG_DIR = DATA_DIR / "logs"


def ensure_dirs() -> None:
    for d in (DATA_DIR, CHROME_PROFILE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
