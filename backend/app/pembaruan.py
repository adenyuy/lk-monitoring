"""Cek versi baru (branch `release` di GitHub) dan pasang dengan memulai ulang aplikasi.

Hanya aktif di folder hasil install.bat (clone branch `release`). Di folder develop tidak melakukan apa-apa.
Pemasangan: jalankan start.bat (salinan, tanpa jendela) beberapa detik setelah server ini mati;
start.bat lalu `git reset` ke versi terbaru, memasang paket bila perlu, dan menyalakan server lagi.
"""

import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from . import config, paths

log = logging.getLogger(__name__)
INTERVAL_DETIK = 30 * 60
_lock = threading.Lock()
_hasil: dict[str, Any] = {"aktif": False, "versi": config.VERSION, "versi_baru": "", "ada_baru": False, "dicek": 0.0}
_tanpa_jendela = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git() -> str | None:
    g = shutil.which("git")
    if g:
        return g
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/cmd/git.exe",
              Path(os.environ.get("ProgramFiles", "")) / "Git/cmd/git.exe"):
        if p.exists():
            return str(p)
    return None


def _jalan(*arg: str, timeout: float = 60) -> str:
    git = _git()
    if not git:
        raise RuntimeError("git tidak ditemukan")
    r = subprocess.run([git, "-C", str(paths.REPO_DIR), *arg], capture_output=True, text=True, timeout=timeout,
                       creationflags=_tanpa_jendela)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {arg[0]} gagal")
    return r.stdout.strip()


def aktif() -> bool:
    """Hanya di folder install (clone branch release) dan bukan saat tes."""
    if os.environ.get("LKM_TANPA_PEMBARUAN"):
        return False
    if not (paths.REPO_DIR / ".git").exists() or not (paths.REPO_DIR / "start.bat").exists():
        return False
    try:
        return _jalan("rev-parse", "--abbrev-ref", "HEAD", timeout=10) == "release"
    except Exception:
        return False


def cek(paksa: bool = False) -> dict[str, Any]:
    """Bandingkan versi lokal dengan origin/release. Hasil di-cache 30 menit."""
    with _lock:
        if not paksa and time.time() - _hasil["dicek"] < INTERVAL_DETIK:
            return dict(_hasil)
        _hasil["dicek"] = time.time()
        _hasil["aktif"] = aktif()
        if not _hasil["aktif"]:
            return dict(_hasil)
        try:
            _jalan("fetch", "--depth", "1", "-q", "origin", "release")
            lokal = _jalan("rev-parse", "HEAD", timeout=10)
            remote = _jalan("rev-parse", "origin/release", timeout=10)
            _hasil["ada_baru"] = lokal != remote
            _hasil["versi_baru"] = (_jalan("show", "origin/release:backend/app/_version.txt", timeout=10)
                                    if _hasil["ada_baru"] else "")
        except Exception as e:  # offline, dsb.: coba lagi nanti
            log.info("Cek pembaruan dilewati: %s", e)
        return dict(_hasil)


def pasang() -> None:
    """Jalankan start.bat setelah server mati, lalu matikan server ini (WhatsApp ditutup rapi dulu)."""
    from .wa.browser import worker

    bat = paths.REPO_DIR / "start.bat"
    env = dict(os.environ, LKM_TANPA_BROWSER="1")  # tampilan yang sedang terbuka memuat ulang sendiri
    # Konsol tersembunyi diwarisi git/pip/ping di dalam start.bat, jadi tidak ada jendela yang berkedip
    flags = _tanpa_jendela | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(f'cmd /c ping -n 6 127.0.0.1 >nul & call "{bat}"', cwd=str(paths.REPO_DIR), env=env,
                     creationflags=flags, close_fds=True)

    def matikan() -> None:
        time.sleep(0.8)  # beri waktu respons terkirim
        try:
            worker.shutdown(timeout=10)
        finally:
            os._exit(0)

    threading.Thread(target=matikan, name="pembaruan", daemon=True).start()
