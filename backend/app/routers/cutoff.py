"""Tarik Cutoff: hanya untuk akun dengan fitur 'cutoff' di sheet Akses."""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import cutoff, db, schedule
from .deps import require_feature

router = APIRouter(prefix="/api/cutoff")
admin = require_feature("cutoff")
MAKS_BYTE = 60 * 1024 * 1024


def _senin(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _minggu1(riwayat: list[dict]) -> date:
    """Senin awal WEEK 1: dari pengaturan, atau ditebak dari tarikan pertama, atau dari week aktif."""
    simpan = db.get_setting("cutoff_week1_senin")
    if simpan:
        return date.fromisoformat(simpan)
    for r in riwayat:
        if str(r["week"]).isdigit():
            d = date.fromisoformat(r["waktu"][:10])
            return _senin(d) - timedelta(weeks=int(r["week"]) - 1)
    aktif = int(db.get_setting("week", "1") or 1)
    return _senin(schedule.now().date()) - timedelta(weeks=aktif - 1)


@router.get("")
def info(_=Depends(admin)) -> dict[str, Any]:
    try:
        weeks = cutoff.daftar_week()
    except Exception as e:
        raise HTTPException(502, f"LK tidak bisa dibaca: {e}") from e
    riw = cutoff.riwayat()
    return {
        "weeks": weeks,
        "week_aktif": db.get_setting("week", "1"),
        "week1_senin": _minggu1(riw).isoformat(),
        "hari_ini": schedule.now().date().isoformat(),
        "riwayat": riw,
    }


@router.post("/cek")
async def cek(file: UploadFile = File(...), mode: str = Form(...), week: str = Form(...),
              _=Depends(admin)) -> dict[str, Any]:
    data = await file.read()
    if len(data) > MAKS_BYTE:
        raise HTTPException(400, "File terlalu besar (maks 60 MB).")
    if not week.strip().isdigit():
        raise HTTPException(400, "Week harus angka, misalnya 1.")
    try:
        r = cutoff.siapkan(data, file.filename or "cutoff", mode, week.strip())
    except cutoff.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Gagal membaca file atau LK: {e}") from e
    ringkas = {k: v for k, v in r.ringkasan.items() if k != "sheet_id"}
    return {"token": r.token, "tab": r.tab, "mode": r.mode, "file": r.nama_file, **ringkas}


class TulisReq(BaseModel):
    token: str


@router.post("/tulis")
def tulis(req: TulisReq, _=Depends(admin)) -> dict[str, Any]:
    try:
        return cutoff.tulis(req.token)
    except cutoff.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Gagal menulis ke LK: {e}") from e


class Minggu1Req(BaseModel):
    tanggal: date


@router.post("/week1")
def set_week1(req: Minggu1Req, _=Depends(admin)) -> dict[str, Any]:
    db.set_setting("cutoff_week1_senin", _senin(req.tanggal).isoformat())
    return info()
