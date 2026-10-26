"""Health, setup credentials, login/logout, /me, pengaturan, daftar petugas."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import config, db, google_auth, sheets
from ..access import AccessError, access_for
from .deps import require_access, require_login

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": config.VERSION}


# ---------- setup ----------

@router.post("/setup/credentials")
async def upload_credentials(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if len(raw) > 64_000:
        raise HTTPException(400, "File terlalu besar untuk credentials.json.")
    try:
        google_auth.save_credentials(raw)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


# ---------- auth ----------

@router.post("/auth/login")
def login() -> dict[str, Any]:
    try:
        st = google_auth.start_login()
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    return {"status": st.status}


@router.post("/auth/logout")
def logout() -> dict[str, Any]:
    """Keluar dari akun Google. Persiapan diulang supaya akun baru memilih nama petugasnya sendiri."""
    from ..sender import sender  # hindari import melingkar

    if sender.state.running:
        raise HTTPException(409, "Pengiriman sedang berjalan. Tekan Berhenti dan tunggu selesai sebelum keluar.")
    google_auth.logout()
    db.set_setting("setup_selesai", False)
    sheets.cache.clear()
    return {"ok": True}


# ---------- me ----------

def _settings() -> dict[str, Any]:
    return {
        "nama_petugas": db.get_setting("nama_petugas"),
        "batas_harian": db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT),
        "kirim_akhir_pekan": db.get_setting("kirim_akhir_pekan", False),
        "week": db.get_setting("week", "1"),
        "wa_terhubung": db.get_setting("wa_terhubung", False),
        "setup_selesai": db.get_setting("setup_selesai", False),
    }


@router.get("/me")
def me() -> dict[str, Any]:
    """Satu endpoint untuk menentukan layar mana yang ditampilkan UI."""
    out: dict[str, Any] = {
        "version": config.VERSION,
        "api_rev": config.API_REV,
        "needs_credentials": not google_auth.has_credentials(),
        "login": {"status": google_auth.login_state.status, "error": google_auth.login_state.error},
        "logged_in": False,
        "email": None,
        "access": None,
        "access_error": None,
        "settings": _settings(),
    }
    if not google_auth.is_logged_in():
        return out
    out["logged_in"] = True
    out["email"] = google_auth.current_email()
    if out["email"]:
        try:
            acc = access_for(out["email"])
            out["access"] = {"nama_petugas": acc.nama_petugas, "fitur": list(acc.fitur)}
        except AccessError as e:
            out["access_error"] = str(e)
        except Exception as e:  # mis. sheet Akses tidak bisa dibuka
            out["access_error"] = f"Sheet Akses tidak bisa dibaca: {e}"
    return out


# ---------- settings ----------

class SettingsIn(BaseModel):
    nama_petugas: str | None = None
    batas_harian: int | None = Field(None, ge=config.BATAS_HARIAN_MIN, le=config.BATAS_HARIAN_MAX)
    kirim_akhir_pekan: bool | None = None
    week: str | None = Field(None, pattern=r"^\d{1,2}$")
    setup_selesai: bool | None = None


@router.get("/settings")
def get_settings(_: str = Depends(require_login)) -> dict[str, Any]:
    return _settings()


@router.post("/settings")
def save_settings(body: SettingsIn, _: str = Depends(require_login)) -> dict[str, Any]:
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "nama_petugas":
            value = sheets.clean_petugas(value)
            if not value:
                raise HTTPException(400, "Nama petugas tidak boleh kosong.")
        db.set_setting(key, value)
    return _settings()


# ---------- petugas ----------

@router.get("/petugas")
def petugas(refresh: bool = False, acc=Depends(require_access)) -> dict[str, Any]:
    try:
        rows = sheets.read_broadcast(refresh=refresh)
    except Exception as e:
        raise HTTPException(502, f"Sheet Broadcast tidak bisa dibaca: {e}") from e
    return {
        "petugas": sheets.petugas_summary(rows),
        "dari_akses": acc.nama_petugas,
    }
