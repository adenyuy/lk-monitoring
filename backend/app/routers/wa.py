"""Status & koneksi WhatsApp Web (dipakai layar setup dan header)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..wa import status as wa_status
from ..wa.browser import worker
from .deps import require_login


def _sibuk() -> bool:
    from ..blast import sibuk

    return sibuk()


router = APIRouter(prefix="/api/wa")


def _snapshot() -> dict[str, Any]:
    try:
        snap = worker.call(wa_status.snapshot, timeout=20)
    except Exception as e:
        return {"state": "error", "nomor": "", "nomor_tersamar": "", "error": str(e)}
    if snap["state"] == "logged_in":
        if not db.get_setting("wa_terhubung", False):
            from .. import chat_refresh

            chat_refresh.trigger()  # baru pertama tertaut: langsung pindai chat fasil
        db.set_setting("wa_terhubung", True)
        db.set_setting("wa_nomor", snap["nomor"])
    snap.pop("nomor", None)  # nomor lengkap tidak dikirim ke UI
    return snap


@router.get("/status")
def wa_get_status(_: str = Depends(require_login)) -> dict[str, Any]:
    return _snapshot()


@router.post("/open/{nomor}")
def wa_open_chat(nomor: str, _: str = Depends(require_login)) -> dict[str, Any]:
    """Buka chat fasil di jendela WhatsApp app (tanpa mengisi pesan) untuk dibalas manual."""
    from ..sender import sender  # hindari import melingkar
    from ..sheets import normalize_nomor
    from ..wa import actions

    if _sibuk():
        raise HTTPException(409, "Pengiriman sedang berjalan. Buka chat setelah sesi selesai atau tekan Berhenti.")
    n = normalize_nomor(nomor)
    if not n:
        raise HTTPException(400, "Nomor tidak valid.")

    def run(b):
        b.open()
        res = actions.open_chat(b, n)
        b.page.bring_to_front()
        return res

    try:
        res = worker.call(run, timeout=90)
    except Exception as e:
        raise HTTPException(500, f"Chat tidak bisa dibuka: {e}") from e
    if not res.ok:
        raise HTTPException(400, "Nomor ini tidak terdaftar di WhatsApp." if res.alasan == "nomor_tidak_terdaftar"
                            else "Chat tidak terbuka. Coba lagi.")
    return {"ok": True}


@router.post("/connect")
def wa_connect(_: str = Depends(require_login)) -> dict[str, Any]:
    """Buka Chrome WhatsApp Web. UI lalu memantau /api/wa/status sampai 'logged_in'."""
    try:
        worker.call(lambda b: b.open(), timeout=90)
    except Exception as e:
        raise HTTPException(
            500,
            f"Chrome tidak bisa dibuka: {e}. Pastikan Google Chrome terpasang dan jendela WhatsApp app sebelumnya sudah ditutup.",
        ) from e
    return _snapshot()


@router.post("/keluar")
def wa_keluar(_: str = Depends(require_login)) -> dict[str, Any]:
    """Keluar dari nomor WhatsApp yang tertaut supaya bisa scan QR dengan nomor lain.
    Dicoba lewat menu WhatsApp Web; bila gagal, sesi WhatsApp di aplikasi ini dihapus."""
    import shutil
    import time

    from .. import paths

    if _sibuk():
        raise HTTPException(409, "Pengiriman sedang berjalan. Hentikan dulu sebelum mengganti WhatsApp.")

    def run(b) -> str:
        if b.is_open and wa_status.state(b.page) == "logged_in" and wa_status.keluar_lewat_menu(b.page):
            return "menu"
        b.close()
        time.sleep(1.5)  # beri waktu Chrome melepas file profil
        if paths.CHROME_PROFILE_DIR.exists():
            shutil.rmtree(paths.CHROME_PROFILE_DIR, ignore_errors=True)
        paths.ensure_dirs()
        return "profil"

    try:
        cara = worker.call(run, timeout=90)
    except Exception as e:
        raise HTTPException(500, f"WhatsApp tidak bisa dikeluarkan: {e}") from e
    db.delete_setting("wa_terhubung")
    db.delete_setting("wa_nomor")
    return {"cara": cara, **_snapshot()}
