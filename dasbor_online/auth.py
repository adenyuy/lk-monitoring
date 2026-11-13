"""Login Google untuk dashboard online.

Alur: /api/auth/masuk -> Google -> /api/auth/kembali -> cookie sesi bertanda tangan (HMAC).
Email dicek ke daftar izin (LKM_IZIN_EMAIL) saat masuk DAN di setiap permintaan, jadi menghapus email
dari daftar langsung mencabut akses tanpa menunggu sesi habis.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GRequest
from google.oauth2 import id_token

COOKIE_SESI = "lkm_sesi"
COOKIE_STATE = "lkm_state"
UMUR_SESI = 7 * 24 * 3600
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _env(nama: str) -> str:
    v = os.environ.get(nama, "").strip()
    if not v:
        raise HTTPException(500, f"Konfigurasi server belum lengkap ({nama}).")
    return v


def daftar_izin() -> list[str]:
    """'a@x.com, @kantor.go.id' -> ['a@x.com', '@kantor.go.id']. Entri '@domain' mengizinkan satu domain."""
    return [x.strip().lower() for x in os.environ.get("LKM_IZIN_EMAIL", "").split(",") if x.strip()]


def diizinkan(email: str) -> bool:
    email = email.lower()
    for x in daftar_izin():
        if email == x or (x.startswith("@") and email.endswith(x)):
            return True
    return False


def admin(email: str) -> bool:
    """Admin dashboard online = email di LKM_ADMIN_EMAIL (persis, dipisah koma)."""
    daftar = {x.strip().lower() for x in os.environ.get("LKM_ADMIN_EMAIL", "").split(",") if x.strip()}
    return email.lower() in daftar


def _tanda(data: str) -> str:
    kunci = _env("LKM_SESI_RAHASIA").encode()
    return base64.urlsafe_b64encode(hmac.new(kunci, data.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def buat_sesi(email: str) -> str:
    data = base64.urlsafe_b64encode(f"{email}|{int(time.time()) + UMUR_SESI}".encode()).decode().rstrip("=")
    return f"{data}.{_tanda(data)}"


def baca_sesi(nilai: str | None) -> str | None:
    if not nilai or "." not in nilai:
        return None
    data, tanda = nilai.rsplit(".", 1)
    if not hmac.compare_digest(tanda, _tanda(data)):
        return None
    try:
        email, exp = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode().rsplit("|", 1)
    except (ValueError, UnicodeDecodeError):
        return None
    if int(exp) < time.time() or not diizinkan(email):
        return None
    return email


def wajib_login(request: Request) -> str:
    """Dependency FastAPI: email pengguna, atau 401."""
    email = baca_sesi(request.cookies.get(COOKIE_SESI))
    if not email:
        raise HTTPException(401, "Silakan masuk dulu.")
    return email


def _base_url(request: Request) -> str:
    tetap = os.environ.get("LKM_URL", "").rstrip("/")
    if tetap:
        return tetap
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


def _aman(request: Request) -> bool:
    return _base_url(request).startswith("https://")


def masuk(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    q = urlencode({
        "client_id": _env("GOOGLE_CLIENT_ID"),
        "redirect_uri": f"{_base_url(request)}/api/auth/kembali",
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "prompt": "select_account",
    })
    r = RedirectResponse(f"{AUTH_URL}?{q}", status_code=302)
    r.set_cookie(COOKIE_STATE, state, max_age=600, httponly=True, secure=_aman(request), samesite="lax")
    return r


def _gagal(pesan: str) -> RedirectResponse:
    r = RedirectResponse(f"/masuk/?{urlencode({'galat': pesan})}", status_code=302)
    r.delete_cookie(COOKIE_STATE)
    return r


def kembali(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    if error:
        return _gagal("Login dibatalkan.")
    if not code or not state or not hmac.compare_digest(state, request.cookies.get(COOKIE_STATE, "")):
        return _gagal("Sesi login kedaluwarsa. Coba lagi.")
    client_id = _env("GOOGLE_CLIENT_ID")
    resp = requests.post(TOKEN_URL, data={
        "code": code, "client_id": client_id, "client_secret": _env("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": f"{_base_url(request)}/api/auth/kembali", "grant_type": "authorization_code",
    }, timeout=20)
    if not resp.ok:
        return _gagal("Google menolak login. Coba lagi.")
    try:
        info = id_token.verify_oauth2_token(resp.json()["id_token"], GRequest(), client_id)
    except (KeyError, ValueError):
        return _gagal("Token Google tidak valid.")
    email = str(info.get("email", "")).lower()
    if not email or not info.get("email_verified"):
        return _gagal("Email Google belum terverifikasi.")
    if not diizinkan(email):
        return _gagal(f"{email} belum diberi akses. Hubungi admin LK Monitoring.")
    r = RedirectResponse("/dashboard/", status_code=302)
    r.delete_cookie(COOKIE_STATE)
    r.set_cookie(COOKIE_SESI, buat_sesi(email), max_age=UMUR_SESI, httponly=True, secure=_aman(request),
                 samesite="lax")
    return r
