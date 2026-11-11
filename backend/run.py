"""Jalankan server: python run.py [--reload]

Dijalankan lewat pythonw (tanpa jendela, dari start.bat) -> semua keluaran masuk ke
%APPDATA%\\LKMonitoring\\logs\\server.log supaya masalah tetap bisa dilacak.

Hanya satu server per laptop: bila sudah ada yang jalan, server kedua langsung berhenti. Bila server gagal
jalan (mis. port terpakai), prosesnya dimatikan total supaya tugas latarnya tidak tertinggal sebagai zombie.
"""

import os
import sys

import uvicorn

from app import config, kunci_server, paths

if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        paths.ensure_dirs()
        f = open(paths.LOG_DIR / "server.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stderr = f  # konfigurasi log uvicorn menulis ke sys.stdout/stderr ini
    kunci = kunci_server.ambil(paths.DATA_DIR / "server.lock")
    if kunci is None:
        print("LK Monitoring sudah berjalan di laptop ini; server kedua tidak dijalankan.", flush=True)
        sys.exit(0)
    kode = 0
    try:
        uvicorn.run(
            "app.main:app",
            host=config.HOST,
            port=config.PORT,
            reload="--reload" in sys.argv,
            log_level="info",
        )
    except SystemExit as e:
        kode = e.code if isinstance(e.code, int) else 1
    except BaseException:
        import traceback

        traceback.print_exc()
        kode = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(kode)  # matikan juga thread latar (WhatsApp, Log Komunikasi) yang masih hidup
