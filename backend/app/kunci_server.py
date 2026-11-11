"""Kunci satu server per laptop.

Tanpa kunci ini, server kedua (mis. start.bat diklik dua kali) gagal memakai port, tapi tugas latarnya
(sinkron WhatsApp, kolom Log Komunikasi) sudah telanjur jalan dan prosesnya tidak pernah mati. Server
"zombie" itu terus menulis ke LK dengan kode lama.
"""

import os
from pathlib import Path
from typing import IO


def ambil(file: Path) -> IO | None:
    """Kunci eksklusif pada `file`. None bila sudah dipegang proses lain. Kunci lepas sendiri saat proses mati."""
    file.parent.mkdir(parents=True, exist_ok=True)
    f = open(file, "a+")  # noqa: SIM115 - harus tetap terbuka selama server jalan
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f
