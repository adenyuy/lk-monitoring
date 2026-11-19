"""Log perubahan data Broadcast/LK (daftar dan kalender per bulan)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import schedule
from .deps import require_feature

router = APIRouter(prefix="/api")
wa_blast = require_feature("wa_blast")



@router.get("/perubahan")
def daftar_perubahan(batas: int = 50, tanggal: str | None = None, _=Depends(wa_blast)) -> dict[str, Any]:
    from .. import perubahan

    if tanggal:
        try:
            date.fromisoformat(tanggal)
        except ValueError as e:
            raise HTTPException(400, "Format tanggal YYYY-MM-DD.") from e
    return {"items": perubahan.daftar(max(1, min(batas, 200)), tanggal)}


@router.get("/perubahan/kalender")
def kalender_perubahan(bulan: str | None = None, _=Depends(wa_blast)) -> dict[str, Any]:
    """`bulan` = YYYY-MM (bawaan: bulan ini)."""
    from .. import perubahan

    try:
        awal = date.fromisoformat(f"{bulan}-01") if bulan else schedule.now().date().replace(day=1)
    except ValueError as e:
        raise HTTPException(400, "Format bulan YYYY-MM.") from e
    return perubahan.kalender(awal)
