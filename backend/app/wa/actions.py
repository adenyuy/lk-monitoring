"""Aksi di WhatsApp Web: buka chat, kirim, cek terkirim, baca chat.

Semua fungsi menerima `Browser` dan harus dipanggil lewat `worker.call(...)`.
"""

import time
from dataclasses import dataclass, field
from urllib.parse import quote

from playwright.sync_api import Page

from . import selectors as S
from .browser import Browser
from .status import first_visible, state


class NotLoggedIn(Exception):
    """WhatsApp Web logout / meminta scan QR. Pengiriman harus berhenti total."""


@dataclass
class OpenResult:
    ok: bool
    alasan: str = ""  # diisi bila ok=False: 'nomor_tidak_terdaftar' | 'timeout' | 'teks_tidak_terisi'


@dataclass
class SendResult:
    status: str  # 'terkirim' | 'gagal'
    keterangan: str = ""


@dataclass
class ChatInfo:
    status: str  # 'belum_ada' | 'terkirim' | 'dibaca' | 'dibalas'
    pesan_keluar_terakhir: str = ""
    balasan: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(str(s).split()).casefold()


def _popup_text(page: Page) -> str:
    sel = first_visible(page, S.POPUP)
    if not sel:
        return ""
    try:
        return _norm(page.inner_text(sel))
    except Exception:
        return ""


def _compose(page: Page):
    sel = first_visible(page, S.COMPOSE)
    return page.query_selector(sel) if sel else None


def open_chat(b: Browser, nomor: str, teks: str = "", timeout: float = 45) -> OpenResult:
    """Buka chat ke `nomor` (format 62…) dengan `teks` terisi di kotak pesan (belum dikirim)."""
    page = b.page
    url = f"{S.WA_URL}send?phone={nomor}"
    if teks:
        url += f"&text={quote(teks)}"
    page.goto(url, wait_until="domcontentloaded")

    expect = _norm(teks)[:40]
    end = time.time() + timeout
    while time.time() < end:
        page.wait_for_timeout(700)
        if state(page) == "qr":
            raise NotLoggedIn("WhatsApp Web meminta scan QR ulang.")
        popup = _popup_text(page)
        if popup and any(t in popup for t in S.INVALID_NUMBER_TEXT):
            return OpenResult(False, "nomor_tidak_terdaftar")
        box = _compose(page)
        if box is not None:
            if not expect:
                return OpenResult(True)
            # Teks dari URL kadang baru muncul sesaat setelah kotak pesan siap.
            if expect in _norm(box.inner_text()):
                return OpenResult(True)
    box = _compose(page)
    if box is not None and expect:
        return OpenResult(False, "teks_tidak_terisi")
    return OpenResult(False, "timeout")


def clear_draft(b: Browser) -> None:
    """Hapus teks di kotak pesan (dipakai setelah mode coba agar tidak jadi draft)."""
    box = _compose(b.page)
    if box is None:
        return
    box.click()
    b.page.keyboard.press("Control+A")
    b.page.keyboard.press("Delete")


_ROWS_JS = """
([rowSels, textSels, tailOut, tailIn]) => {
  let rows = [];
  for (const s of rowSels) { rows = [...document.querySelectorAll(s)]; if (rows.length) break; }
  return rows.map(r => {
    let text = '';
    for (const s of textSels) { const el = r.querySelector(s); if (el) { text = el.innerText; break; } }
    const labels = [...r.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label') || '');
    const titles = [...r.querySelectorAll('svg title')].map(t => t.textContent || '');
    const icons = [...r.querySelectorAll('[data-icon]')].map(e => e.getAttribute('data-icon') || '');
    return {
      id: r.getAttribute('data-id') || '',
      text: text || '',
      labels, titles, icons,
      tailOut: !!r.querySelector(tailOut),
      tailIn: !!r.querySelector(tailIn),
    };
  });
}
"""


@dataclass
class Row:
    id: str
    out: bool
    status: str  # pending | sent | delivered | read | '' (pesan masuk)
    text: str


def _status_of(raw: dict) -> str:
    hay = " ".join(raw["labels"] + raw["titles"] + raw["icons"]).casefold()
    for name, keys in S.STATUS_KEYWORDS:
        if any(k in hay for k in keys):
            return name
    return ""


def _is_out(raw: dict, status: str) -> bool:
    if raw["tailOut"]:
        return True
    if raw["tailIn"]:
        return False
    labels = [_norm(x) for x in raw["labels"]]
    if any(lbl in S.OUT_SENDER_LABELS for lbl in labels):
        return True
    # Pesan lanjutan tanpa "ekor": pesan keluar selalu punya ikon status.
    return bool(status)


def rows(page: Page) -> list[Row]:
    raw = page.evaluate(_ROWS_JS, [list(S.MESSAGE_ROW), list(S.MESSAGE_TEXT), S.TAIL_OUT, S.TAIL_IN])
    out = []
    for r in raw:
        st = _status_of(r)
        is_out = _is_out(r, st)
        out.append(Row(r["id"], is_out, st if is_out else "", r["text"].strip()))
    return out


def send(b: Browser, timeout: float = 30) -> SendResult:
    """Tekan kirim pada chat yang sedang terbuka, lalu pastikan pesan tidak lagi berikon jam."""
    page = b.page
    before_ids = {r.id for r in rows(page)}
    btn_sel = first_visible(page, S.SEND_BUTTON)
    if btn_sel:
        page.click(btn_sel)
    else:
        box = _compose(page)
        if box is None:
            return SendResult("gagal", "Kotak pesan tidak ditemukan.")
        box.press("Enter")

    end = time.time() + timeout
    new_out: list[Row] = []
    while time.time() < end:
        page.wait_for_timeout(700)
        new_out = [r for r in rows(page) if r.out and r.id not in before_ids]
        if new_out and new_out[-1].status in ("sent", "delivered", "read"):
            return SendResult("terkirim")
    if new_out:
        return SendResult("gagal", "Pesan masih menunggu (ikon jam) setelah 30 detik.")
    return SendResult("gagal", "Pesan tidak muncul di chat setelah menekan kirim.")


def read_chat(b: Browser, nomor: str) -> ChatInfo:
    """Status pesan keluar terakhir + pesan masuk setelahnya, di chat `nomor`."""
    res = open_chat(b, nomor)
    if not res.ok:
        return ChatInfo("belum_ada")
    b.page.wait_for_timeout(1500)  # beri waktu riwayat chat dimuat

    all_rows = rows(b.page)
    last_out = max((i for i, r in enumerate(all_rows) if r.out), default=-1)
    if last_out < 0:
        return ChatInfo("belum_ada")
    balasan = [r.text for r in all_rows[last_out + 1 :] if not r.out and r.text]
    if balasan:
        status = "dibalas"
    else:
        status = "dibaca" if all_rows[last_out].status == "read" else "terkirim"
    return ChatInfo(status, all_rows[last_out].text, balasan)
