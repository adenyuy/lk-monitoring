"""Unggah daftar sekolah peserta bimtek yang laporan 50%-nya belum direviu (penanda di Rekap dan panel fasil)."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import bimtek
from .deps import require_feature

router = APIRouter(prefix="/api/bimtek")
wa_blast = require_feature("wa_blast")
MAKS_BYTE = 60 * 1024 * 1024


def _ringkas() -> dict[str, Any]:
    i = bimtek.info()
    if not i:
        return {"ada": False}
    return {"ada": True, "file": i["file"], "per_tanggal": i["per_tanggal"], "diunggah": i["diunggah"],
            "sekolah": len(i["sekolah"])}


@router.get("")
def status(_=Depends(wa_blast)) -> dict[str, Any]:
    return _ringkas()


@router.post("")
async def unggah(file: UploadFile = File(...), _=Depends(wa_blast)) -> dict[str, Any]:
    data = await file.read()
    if len(data) > MAKS_BYTE:
        raise HTTPException(400, "File terlalu besar (maks 60 MB).")
    try:
        bimtek.simpan(bimtek.baca(data, file.filename or "bimtek.xlsx"))
    except bimtek.BimtekError as e:
        raise HTTPException(400, str(e)) from e
    return _ringkas()


@router.delete("")
def hapus(_=Depends(wa_blast)) -> dict[str, Any]:
    bimtek.hapus()
    return _ringkas()
