"""Buat file paket lk-monitoring.json untuk tim (khusus admin).

Paket = credentials.json (OAuth aplikasi desktop) + alamat tiga sheet tim. Teman cukup mengunggah satu file ini
di langkah "Masuk Google". Alamat sheet tidak pernah ditulis di repo karena sheet dibagikan lewat link.

Pakai:
    python buat_paket.py credentials.json LINK_BROADCAST LINK_LK LINK_AKSES [--eskalasi LINK] [-o lk-monitoring.json]

LINK_* boleh berupa link Google Sheets lengkap atau ID-nya saja.
Kirim hasilnya lewat jalur pribadi (WA/Drive terbatas), jangan diunggah ke repo.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def id_sheet(nilai: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", nilai)
    x = m.group(1) if m else nilai.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", x):
        sys.exit(f"Bukan link/ID Google Sheets yang valid: {nilai}")
    return x


def main() -> None:
    ap = argparse.ArgumentParser(description="Buat lk-monitoring.json untuk tim.")
    ap.add_argument("credentials", type=Path, help="credentials.json (OAuth client, tipe Desktop)")
    ap.add_argument("broadcast", help="link atau ID sheet Broadcast")
    ap.add_argument("lk", help="link atau ID sheet LK Monitoring")
    ap.add_argument("akses", help="link atau ID sheet Akses")
    ap.add_argument("--eskalasi", help="link atau ID sheet LK Eskalasi (opsional; bisa juga dipasang admin dari aplikasi)")
    ap.add_argument("-o", "--output", type=Path, default=Path("lk-monitoring.json"))
    a = ap.parse_args()

    data = json.loads(a.credentials.read_text(encoding="utf-8"))
    if "installed" not in data:
        sys.exit('credentials.json harus tipe "Desktop app" (ada bagian "installed").')
    data["lkm_sheets"] = {"broadcast": id_sheet(a.broadcast), "lk": id_sheet(a.lk), "akses": id_sheet(a.akses)}
    if a.eskalasi:
        data["lkm_sheets"]["eskalasi"] = id_sheet(a.eskalasi)
    a.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Selesai: {a.output.resolve()}")


if __name__ == "__main__":
    main()
