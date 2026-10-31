"""Dependency bersama: wajib login, wajib punya fitur."""

from fastapi import HTTPException

from .. import google_auth
from ..access import Access, AccessError, access_for


def require_login() -> str:
    if not google_auth.is_logged_in():
        raise HTTPException(401, "Belum masuk ke akun Google.")
    email = google_auth.current_email()
    if not email:
        raise HTTPException(401, "Email akun belum diketahui. Silakan masuk ulang.")
    return email


def require_access() -> Access:
    email = require_login()
    try:
        return access_for(email)
    except AccessError as e:
        raise HTTPException(403, str(e)) from e


def require_admin() -> Access:
    acc = require_access()
    if not acc.admin:
        raise HTTPException(403, "Halaman ini khusus admin (catatan \"admin\" di sheet Akses).")
    return acc


def require_feature(feature: str):
    def dep() -> Access:
        acc = require_access()
        if not acc.has(feature):
            raise HTTPException(403, "Akunmu tidak punya akses ke fitur ini.")
        return acc

    return dep
