"""Kirim WA Blast: status, antrean, mulai/stop, pembaruan chat, aliran peristiwa (SSE)."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import events
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


class StartIn(BaseModel):
    coba: bool = False


@router.post("/send/start")
def send_start(body: StartIn, _=Depends(wa_blast)) -> dict[str, Any]:
    try:
        return sender.start(coba=body.coba)
    except NotAllowed as e:
        raise HTTPException(409, str(e)) from e


@router.post("/send/stop")
def send_stop(_=Depends(wa_blast)) -> dict[str, Any]:
    return sender.stop()


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


# ---------- Undangan WAG ----------

