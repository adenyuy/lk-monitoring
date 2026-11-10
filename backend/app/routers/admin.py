"""Halaman Admin: kelola pengguna di sheet Akses dan unduh paket lk-monitoring.json untuk anggota baru."""

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import config, paths
from ..access import Access, read_access
from ..sheets import cache, gspread_client
from .deps import require_admin

router = APIRouter(prefix="/api/admin")
JUDUL = ["email", "nama_petugas", "fitur", "catatan"]
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ws():
    return gspread_client().open_by_key(config.ACCESS_SHEET_ID).worksheet(config.ACCESS_TAB)


def _baris() -> list[dict[str, Any]]:
    """Isi tab Akses apa adanya (termasuk fitur yang tidak dikenal), dengan nomor baris sheet."""
    nilai = _ws().get_values("A1:D")
    if not nilai or [str(h).strip().casefold() for h in nilai[0][:3]] != JUDUL[:3]:
        raise HTTPException(409, "Judul tab Akses harus: email, nama_petugas, fitur, catatan.")
    out = []
    for n, r in enumerate(nilai[1:], start=2):
        r = list(r) + [""] * (4 - len(r))
        if not str(r[0]).strip():
            continue
        out.append({"baris": n, "email": str(r[0]).strip(), "nama_petugas": str(r[1]).strip(),
                    "fitur": [f.strip() for f in str(r[2]).split(",") if f.strip()],
                    "catatan": str(r[3]).strip()})
    return out


def _segarkan() -> None:
    cache.clear()
    read_access(refresh=True)


@router.get("/akses")
def daftar(_: Access = Depends(require_admin)) -> dict[str, Any]:
    try:
        return {"pengguna": _baris(), "fitur": list(config.FEATURES)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Sheet Akses tidak bisa dibaca: {e}") from e


class PenggunaReq(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    nama_petugas: str = Field(min_length=1, max_length=200)
    fitur: list[str] = Field(default_factory=list, max_length=10)
    admin: bool = False
    email_lama: str = ""  # diisi saat mengubah pengguna yang sudah ada


@router.post("/akses")
def simpan(req: PenggunaReq, acc: Access = Depends(require_admin)) -> dict[str, Any]:
    email = req.email.strip().casefold()
    if not RE_EMAIL.match(email):
        raise HTTPException(400, "Format email tidak valid.")
    fitur = [f for f in config.FEATURES if f in req.fitur]
    if not fitur:
        raise HTTPException(400, "Pilih minimal satu fitur.")
    lama = (req.email_lama or email).strip().casefold()
    if lama == acc.email and not req.admin:
        raise HTTPException(400, "Status admin akun Anda sendiri tidak bisa dicabut dari sini.")
    rows = _baris()
    # Tanpa email_lama = tambah baru (email yang sudah ada ditolak, bukan ditimpa diam-diam)
    target = next((r for r in rows if r["email"].casefold() == lama), None) if req.email_lama else None
    if req.email_lama and not target:
        raise HTTPException(404, "Pengguna yang diubah tidak ada lagi di sheet Akses. Muat ulang halaman.")
    if any(r["email"].casefold() == email and r is not target for r in rows):
        raise HTTPException(409, f"{email} sudah terdaftar.")
    nilai = [email, " ".join(req.nama_petugas.split()), ", ".join(fitur), "admin" if req.admin else "user"]
    ws = _ws()
    if target:
        ws.update([nilai], f"A{target['baris']}:D{target['baris']}", value_input_option="RAW")
    else:
        ws.append_row(nilai, value_input_option="RAW", table_range="A1:D1")
    _segarkan()
    return {"pengguna": _baris(), "baru": target is None}


@router.delete("/akses/{email}")
def hapus(email: str, acc: Access = Depends(require_admin)) -> dict[str, Any]:
    e = email.strip().casefold()
    if e == acc.email:
        raise HTTPException(400, "Akun Anda sendiri tidak bisa dihapus dari sini.")
    target = next((r for r in _baris() if r["email"].casefold() == e), None)
    if not target:
        raise HTTPException(404, "Pengguna ini tidak ada di sheet Akses.")
    _ws().delete_rows(target["baris"])
    _segarkan()
    return {"pengguna": _baris()}


@router.get("/paket")
def paket(_: Access = Depends(require_admin)) -> Response:
    """lk-monitoring.json = credentials aplikasi + alamat sheet tim, untuk dikirim ke anggota baru lewat jalur pribadi."""
    if not paths.CREDENTIALS_FILE.exists():
        raise HTTPException(409, "credentials.json belum ada di laptop ini.")
    data = json.loads(paths.CREDENTIALS_FILE.read_text(encoding="utf-8"))
    ids = config.sheet_ids()
    sheets = {k: ids[k] for k in config.SHEET_KEYS}
    try:
        from .. import eskalasi
        sheets["eskalasi"] = eskalasi.sheet_id()
    except Exception:
        pass  # opsional
    data["lkm_sheets"] = sheets
    return Response(json.dumps(data, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="lk-monitoring.json"'})
