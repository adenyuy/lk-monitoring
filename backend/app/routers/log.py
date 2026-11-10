"""Halaman Log: perubahan data Broadcast/LK dan riwayat per fasil."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import aktivitas, perubahan, schedule
from .deps import require_feature

router = APIRouter(prefix="/api/log")
wa_blast = require_feature("wa_blast")


def _tanggal(x: str) -> str:
    try:
        return date.fromisoformat(x).isoformat()
    except ValueError as e:
        raise HTTPException(400, "Format tanggal YYYY-MM-DD.") from e


@router.get("/kalender")
def kalender(bulan: str | None = None, _=Depends(wa_blast)) -> dict[str, Any]:
    """`bulan` = YYYY-MM (bawaan: bulan ini)."""
    try:
        awal = date.fromisoformat(f"{bulan}-01") if bulan else schedule.now().date().replace(day=1)
    except ValueError as e:
        raise HTTPException(400, "Format bulan YYYY-MM.") from e
    return perubahan.kalender(awal)


@router.get("/hari")
def hari(tanggal: str, _=Depends(wa_blast)) -> dict[str, Any]:
    t = _tanggal(tanggal)
    return {"tanggal": t, "perubahan": perubahan.daftar(tanggal=t), "aktivitas": aktivitas.daftar(tanggal=t)}


@router.get("/fasil")
def daftar_fasil(_=Depends(wa_blast)) -> dict[str, Any]:
    return {"fasil": aktivitas.fasil_tercatat()}


@router.get("/fasil/{nomor}")
def riwayat_fasil(nomor: str, _=Depends(wa_blast)) -> dict[str, Any]:
    return {"nomor": nomor, "aktivitas": aktivitas.daftar(nomor=nomor)}
