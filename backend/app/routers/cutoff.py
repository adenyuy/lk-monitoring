"""Tarik Cutoff (LK format baru): hanya untuk akun dengan fitur 'cutoff' di sheet Akses."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import cutoff_baru, google_auth, komunikasi, lk_baru
from .deps import require_feature
from .lkb import _jalan

router = APIRouter(prefix="/api/cutoff")
admin = require_feature("cutoff")
MAKS_BYTE = 60 * 1024 * 1024


@router.get("")
def info(_=Depends(admin)) -> dict[str, Any]:
    weeks = _jalan(lk_baru.daftar_week, True)
    return {
        "weeks": weeks,
        "week_aktif": weeks[-1] if weeks else None,
        "senin_baru": cutoff_baru.senin_berikutnya().isoformat(),
        "riwayat": cutoff_baru.riwayat(),
        "log_progres": _jalan(cutoff_baru.baca_log_progres),
        "status": cutoff_baru.status(),
        "kolom_wajib": list(cutoff_baru.WAJIB),
        "cutoff_terakhir": _cutoff_terakhir(),
    }


def _cutoff_terakhir() -> str:
    try:
        return komunikasi.label_cutoff()
    except Exception:
        return ""


@router.post("/cek")
async def cek(file: UploadFile = File(...), week: int = Form(...), _=Depends(admin)) -> dict[str, Any]:
    data = await file.read()
    if len(data) > MAKS_BYTE:
        raise HTTPException(400, "File terlalu besar (maks 60 MB).")
    try:
        r = cutoff_baru.siapkan(data, file.filename or "cutoff.csv", week)
    except cutoff_baru.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    except lk_baru.LkError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Gagal membaca file atau LK: {e}") from e
    return {"token": r.token, "file": r.nama_file, "week": r.week, **r.ringkasan}


class TulisReq(BaseModel):
    token: str


@router.post("/tulis")
def tulis(req: TulisReq, _=Depends(admin)) -> dict[str, Any]:
    try:
        cutoff_baru.mulai_tulis(req.token, google_auth.current_email() or "")
    except cutoff_baru.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    return cutoff_baru.status()


@router.get("/status")
def status(_=Depends(admin)) -> dict[str, Any]:
    return cutoff_baru.status()


class WeekReq(BaseModel):
    senin: date


@router.post("/week-baru")
def week_baru(req: WeekReq, _=Depends(admin)) -> dict[str, Any]:
    try:
        return cutoff_baru.buat_week(req.senin)
    except (cutoff_baru.CutoffError, lk_baru.LkError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"WEEK baru gagal dibuat: {e}") from e
