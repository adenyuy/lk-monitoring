"""Kirim WA Blast: status, antrean, mulai/stop, pembaruan chat, aliran peristiwa (SSE)."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import chat_refresh, events, store
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


# ---------- Undangan WAG ----------

class UndanganIn(BaseModel):
    aktif: bool
    link: str = ""
    tim: str = ""
    teks: str = ""


def _undangan() -> dict[str, Any]:
    from .. import schedule, undangan_wag
    from ..sheets import filter_petugas

    p = undangan_wag.pengaturan()
    out = p.as_dict()
    out["ringkasan"] = None
    out["contoh"] = ""
    out["nama_contoh"] = "Nama Fasilitator"
    try:
        petugas, _, _ = sender._settings()
        rows = filter_petugas(sender.load_rows(), petugas)
    except Exception:  # nama petugas belum dipilih / Broadcast tak terbaca: pengaturan tetap bisa diubah
        return out
    if p.link:
        items = undangan_wag.build(undangan_wag.penerima(rows, petugas, sender.load_lk()), store.sends_real(), p)
        out["ringkasan"] = undangan_wag.ringkasan(items)
    nama = next((r.nama_fasil for r in rows if r.nomor), "Nama Fasilitator")
    out["nama_contoh"] = nama
    contoh = undangan_wag.susun(p if p.link else undangan_wag.Pengaturan(link="https://chat.whatsapp.com/…",
                                                                         tim=p.tim, teks=p.teks), nama)
    out["contoh"] = undangan_wag.isi_salam(contoh, schedule.now())
    return out


@router.get("/undangan-wag")
def undangan_get(_=Depends(wa_blast)) -> dict[str, Any]:
    return _undangan()


@router.post("/undangan-wag")
def undangan_set(body: UndanganIn, _=Depends(wa_blast)) -> dict[str, Any]:
    from .. import undangan_wag

    if sender.state.running:
        raise HTTPException(409, "Tunggu pengiriman yang sedang berjalan selesai, atau hentikan dulu.")
    try:
        undangan_wag.simpan(aktif=body.aktif, link=body.link, tim=body.tim, teks=body.teks)
    except undangan_wag.UndanganError as e:
        raise HTTPException(400, str(e)) from e
    events.publish("undangan_berubah", aktif=undangan_wag.pengaturan().aktif)
    return _undangan()
