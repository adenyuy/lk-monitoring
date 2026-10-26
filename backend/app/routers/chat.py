"""Baca percakapan dan balas fasil langsung dari aplikasi (lewat jendela WhatsApp app)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import aktivitas, events, schedule, store, tagging
from ..sender import sender
from ..sheets import normalize_nomor, nomor_milik
from ..wa import actions
from ..wa.browser import worker
from .deps import require_feature

router = APIRouter(prefix="/api/chat")
wa_blast = require_feature("wa_blast")
MAKS_BALASAN = 2000


def _nomor_fasil(nomor: str) -> str:
    """Hanya nomor fasil milik petugas ini (dari sheet Broadcast) yang boleh dibaca/dibalas."""
    n = normalize_nomor(nomor)
    if not n:
        raise HTTPException(400, "Nomor tidak valid.")
    try:
        milik = nomor_milik()
    except Exception as e:
        raise HTTPException(502, f"Sheet Broadcast/LK tidak bisa dibaca: {e}") from e
    if n not in milik:
        raise HTTPException(403, "Nomor ini bukan fasil petugas ini.")
    return n


def _siap() -> None:
    if sender.state.running:
        raise HTTPException(409, "Pengiriman sedang berjalan. Chat bisa dibaca dan dibalas setelah sesi selesai atau setelah menekan Berhenti.")
    if not worker.browser_open():
        raise HTTPException(409, "WhatsApp belum dibuka. Tekan Buka WhatsApp dulu.")


def _hasil(nomor: str, info: actions.ChatInfo, rows: list[actions.Row]) -> dict[str, Any]:
    if info.status in ("dibaca", "dibalas") or info.centang in ("delivered", "read"):
        manual = store.tahap_all().get(nomor, {}).get("terkirim", {}).get("nilai")
        if manual or any(x["status"] == "terkirim" and not x["coba"] for x in store.sends_real() if x["nomor"] == nomor):
            tagging.tandai(nomor, "hijau")
    if info.status != "belum_ada":
        balasan = info.balasan[-1] if info.balasan else ""
        store.save_chat_status(nomor, info.status, balasan, schedule.now().isoformat(timespec="seconds"))
        events.publish("chat_diperbarui", jumlah=1)
    return {
        "status": info.status,
        "dibaca_pada": schedule.now().strftime("%H.%M"),
        "pesan": [{"keluar": r.out, "teks": r.text, "waktu": r.waktu, "status": r.status} for r in rows if r.text][-40:],
    }


def _jalan(fn, timeout: float):
    try:
        return worker.call(fn, timeout=timeout)
    except actions.NotLoggedIn as e:
        raise HTTPException(409, "WhatsApp Web minta scan QR ulang.") from e
    except Exception as e:
        raise HTTPException(500, f"WhatsApp tidak bisa dibaca: {e}") from e


@router.post("/{nomor}/baca")
def baca(nomor: str, _=Depends(wa_blast)) -> dict[str, Any]:
    n = _nomor_fasil(nomor)
    _siap()
    info, rows = _jalan(lambda b: actions.read_thread(b, n), timeout=90)
    return _hasil(n, info, rows)


class BalasReq(BaseModel):
    pesan: str = Field(min_length=1, max_length=MAKS_BALASAN)
    jenis: str = ""  # 'tanya_lk' bila dari template pertanyaan isian LK


@router.post("/{nomor}/balas")
def balas(nomor: str, req: BalasReq, _=Depends(wa_blast)) -> dict[str, Any]:
    n = _nomor_fasil(nomor)
    teks = req.pesan.strip()
    if not teks:
        raise HTTPException(400, "Balasan masih kosong.")
    _siap()

    def run(b):
        res = actions.reply(b, n, teks)
        if res.status != "terkirim":
            return res, None
        b.page.wait_for_timeout(800)
        return res, actions.read_thread(b, n)

    res, thread = _jalan(run, timeout=120)
    if res.status != "terkirim":
        raise HTTPException(502, f"Balasan belum terkirim: {res.keterangan}")
    if req.jenis == "tanya_lk":
        store.set_tahap(n, "ditanya", True, "template", schedule.now().isoformat(timespec="seconds"))
    ringkas = " ".join(teks.split())
    ringkas = ringkas if len(ringkas) <= 90 else ringkas[:89] + "…"
    aktivitas.catat(n, "balas", ("Tanya isian LK: " if req.jenis == "tanya_lk" else "Pesan: ") + ringkas)
    info, rows = thread
    return _hasil(n, info, rows)
