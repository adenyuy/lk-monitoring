"""Kirim WA Blast: status, antrean, mulai/stop, pembaruan chat, aliran peristiwa (SSE)."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import chat_refresh, events
from ..sender import NotAllowed, sender
from .deps import require_feature

router = APIRouter(prefix="/api")
wa_blast = require_feature("wa_blast")


def _kondisi() -> dict[str, Any]:
    try:
        return sender.kondisi().as_dict()
    except NotAllowed as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Data Broadcast tidak bisa dibaca: {e}") from e


@router.get("/send/state")
def send_state(_=Depends(wa_blast)) -> dict[str, Any]:
    return {"pengiriman": sender.snapshot(), "kondisi": _kondisi()}


class StartIn(BaseModel):
    coba: bool = False


@router.post("/send/start")
def send_start(body: StartIn, _=Depends(wa_blast)) -> dict[str, Any]:
    try:
        return sender.start(coba=body.coba)
    except NotAllowed as e:
        raise HTTPException(409, str(e)) from e


class BypassIn(BaseModel):
    aktif: bool
    konfirmasi: str = ""


@router.post("/send/bypass")
def send_bypass(body: BypassIn, _=Depends(wa_blast)) -> dict[str, Any]:
    """Nyalakan/matikan bypass sesi untuk hari ini. Menyalakan wajib mengetik kalimat risiko."""
    from .. import config, db, schedule

    if body.aktif:
        if " ".join(body.konfirmasi.lower().split()) != config.KALIMAT_RISIKO:
            raise HTTPException(400, f"Ketik “{config.KALIMAT_RISIKO}” untuk menyalakan bypass sesi.")
        now = schedule.now()
        db.set_setting("bypass_sesi", {"tanggal": schedule.tanggal_str(now.date()),
                                       "waktu": now.isoformat(timespec="seconds")})
    else:
        if sender.state.running and sender.state.bypass:
            sender.stop()
        db.delete_setting("bypass_sesi")
    events.publish("bypass_berubah", aktif=sender.bypass_aktif())
    return {"bypass": sender.bypass_aktif(), "kondisi": _kondisi()}


@router.post("/send/stop")
def send_stop(_=Depends(wa_blast)) -> dict[str, Any]:
    return sender.stop()


@router.get("/antrean")
def antrean(_=Depends(wa_blast)) -> dict[str, Any]:
    try:
        items = sender.antrean()
    except NotAllowed as e:
        raise HTTPException(400, str(e)) from e
    ringkas: dict[str, int] = {}
    for i in items:
        ringkas[i.status] = ringkas.get(i.status, 0) + 1
    return {
        "ringkasan": ringkas,
        "items": [
            {"baris": i.baris, "nama_fasil": i.nama_fasil, "status": i.status, "keterangan": i.keterangan,
             "waktu": i.waktu, "bisa_dikirim": i.bisa_dikirim}
            for i in items
        ],
    }


@router.post("/chat/refresh")
def chat_refresh_now(_=Depends(wa_blast)) -> dict[str, Any]:
    return chat_refresh.refresh_once()


@router.get("/events")
async def stream(request: Request, _=Depends(wa_blast)):
    async def gen():
        last = events.last_id()
        yield {"event": "halo", "data": json.dumps(sender.snapshot())}
        while not await request.is_disconnected():
            for e in events.since(last):
                last = e["id"]
                yield {"event": e["type"], "id": str(e["id"]), "data": json.dumps(e["data"])}
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen(), ping=15)
