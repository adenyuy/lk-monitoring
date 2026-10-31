"""Status login WhatsApp Web."""

import json
import re
import time
from typing import Iterable

from playwright.sync_api import Page

from . import selectors as S
from .browser import Browser


def first_visible(page: Page, sels: Iterable[str]) -> str | None:
    """Selektor pertama yang elemennya ada & tampil, atau None."""
    for sel in sels:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return sel
        except Exception:
            continue
    return None


def state(page: Page) -> str:
    """'logged_in' | 'qr' | 'loading'"""
    if first_visible(page, S.LOGGED_IN):
        return "logged_in"
    if first_visible(page, S.QR):
        return "qr"
    return "loading"


def account_number(page: Page) -> str:
    """Nomor akun yang login dari localStorage WhatsApp Web, '' bila tidak ketemu."""
    for key in S.LOCALSTORAGE_WID_KEYS:
        try:
            raw = page.evaluate("k => window.localStorage.getItem(k)", key)
        except Exception:
            continue
        if raw:
            try:
                raw = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                pass
            m = re.match(r"\D*(\d{8,15})", str(raw))
            if m:
                return m.group(1)
    return ""


def mask(nomor: str) -> str:
    """'6281234567890' -> '0812•••7890'"""
    if not nomor:
        return ""
    local = "0" + nomor[2:] if nomor.startswith("62") else nomor
    return f"{local[:4]}•••{local[-4:]}" if len(local) > 8 else local


def snapshot(b: Browser) -> dict:
    if not b.is_open:
        return {"state": "closed", "nomor": "", "nomor_tersamar": ""}
    st = state(b.page)
    nomor = account_number(b.page) if st == "logged_in" else ""
    return {"state": st, "nomor": nomor, "nomor_tersamar": mask(nomor)}


def wait_logged_in(b: Browser, timeout: float = 180) -> dict:
    """Tunggu sampai login (mis. setelah scan QR). Return snapshot terakhir."""
    end = time.time() + timeout
    snap = snapshot(b)
    while time.time() < end and snap["state"] not in ("logged_in", "closed"):
        b.page.wait_for_timeout(1500)
        snap = snapshot(b)
    return snap
