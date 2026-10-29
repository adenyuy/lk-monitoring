"""Jalankan server: python run.py [--reload]

Dijalankan lewat pythonw (tanpa jendela, dari start.bat) -> semua keluaran masuk ke
%APPDATA%\\LKMonitoring\\logs\\server.log supaya masalah tetap bisa dilacak.
"""

import sys

import uvicorn

from app import config, paths

if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        paths.ensure_dirs()
        f = open(paths.LOG_DIR / "server.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stderr = f  # konfigurasi log uvicorn menulis ke sys.stdout/stderr ini
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload="--reload" in sys.argv,
        log_level="info",
    )
