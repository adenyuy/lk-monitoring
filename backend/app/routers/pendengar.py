"""WhatsApp langsung (neonize): tautkan, lihat status, lepas, dan pilih jalur kirim pesan."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..wa import pendengar, pengirim
from .deps import require_feature

router = APIRouter(prefix="/api/pendengar")
wa_blast = require_feature("wa_blast")


@router.get("")
def status(_=Depends(wa_blast)) -> dict[str, Any]:
    return _ringkas()


def _ringkas() -> dict[str, Any]:
    return {**pendengar.ringkas(), "kirim_lewat": pengirim.lewat(), "mesin_kirim": pengirim.mesin_aktif()}


class LewatReq(BaseModel):
    lewat: str


@router.post("/kirim-lewat")
def kirim_lewat(req: LewatReq, _=Depends(wa_blast)) -> dict[str, Any]:
    """'neonize' = kirim langsung (utama, WA Web otomatis jadi cadangan); 'waweb' = selalu lewat jendela WA Web."""
    if req.lewat not in ("neonize", "waweb"):
        raise HTTPException(400, "Pilihan jalur kirim tidak dikenal.")
    db.set_setting("kirim_lewat", req.lewat)
    return _ringkas()


@router.post("/tautkan")
def tautkan(_=Depends(wa_blast)) -> dict[str, Any]:
    """Mulai menautkan: QR muncul di status (qr_svg) untuk di-scan dari HP."""
    pendengar.mulai(baru=not pendengar.tertaut())
    return _ringkas()


@router.post("/lepas")
def lepas(_=Depends(wa_blast)) -> dict[str, Any]:
    pendengar.lepas()
    return _ringkas()
