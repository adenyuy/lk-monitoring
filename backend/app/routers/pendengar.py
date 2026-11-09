"""Pendengar WhatsApp (neonize): tautkan, lihat status, lepas."""

from typing import Any

from fastapi import APIRouter, Depends

from ..wa import pendengar
from .deps import require_feature

router = APIRouter(prefix="/api/pendengar")
wa_blast = require_feature("wa_blast")


@router.get("")
def status(_=Depends(wa_blast)) -> dict[str, Any]:
    return pendengar.ringkas()


@router.post("/tautkan")
def tautkan(_=Depends(wa_blast)) -> dict[str, Any]:
    """Mulai menautkan: QR muncul di status (qr_svg) untuk di-scan dari HP."""
    pendengar.mulai(baru=not pendengar.tertaut())
    return pendengar.ringkas()


@router.post("/lepas")
def lepas(_=Depends(wa_blast)) -> dict[str, Any]:
    pendengar.lepas()
    return pendengar.ringkas()
