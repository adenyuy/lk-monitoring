"""Pintu masuk Vercel: semua /api/* diarahkan ke sini (lihat vercel.json)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dasbor_online.app import app  # noqa: E402,F401
