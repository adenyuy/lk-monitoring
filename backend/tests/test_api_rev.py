"""API_REV backend dan web harus sama; kalau beda, aplikasi menampilkan banner "server perlu dijalankan ulang"."""

import re
from pathlib import Path

from app import config


def test_api_rev_sama_dengan_web():
    ts = (Path(__file__).resolve().parents[2] / "web" / "lib" / "types.ts").read_text(encoding="utf-8")
    m = re.search(r"export const API_REV = (\d+);", ts)
    assert m, "API_REV tidak ditemukan di web/lib/types.ts"
    assert int(m.group(1)) == config.API_REV, "Samakan API_REV di web/lib/types.ts dengan backend/app/config.py"
