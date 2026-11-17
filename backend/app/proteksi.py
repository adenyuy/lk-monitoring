"""Proteksi "hanya peringatan" untuk baris judul LK (tab WEEK n dan Log Komunikasi).

Judul kolom dipakai aplikasi untuk mencari kolom (mis. 'Sen 09/11'). Bila tertimpa (pernah: 'Sen 09/11' jadi 'T1'),
aplikasi menganggap kolomnya hilang dan membuat kolom baru, sehingga data terbelah dua. Dengan proteksi ini
Google Sheets menampilkan peringatan sebelum judul diubah; aplikasi (lewat API) tetap bisa menulis.
"""

import logging
import threading

from . import lk_baru

log = logging.getLogger(__name__)

KETERANGAN = "lkm-judul: judul kolom dipakai aplikasi LK Monitoring, jangan diubah"
_sudah: set[int] = set()
_lock = threading.Lock()


def baris_judul(judul_tab: str) -> int:
    """Jumlah baris judul yang dilindungi, 0 bila tab ini tidak dilindungi."""
    if judul_tab == lk_baru.TAB_LOG_KOM:
        return 2
    if judul_tab.startswith(lk_baru.PREFIX_WEEK) and judul_tab[len(lk_baru.PREFIX_WEEK):].strip().isdigit():
        return lk_baru.BARIS_DATA - 1
    return 0


def rencana(sheets: list[dict]) -> list[dict]:
    """Permintaan addProtectedRange untuk tab yang belum punya proteksi judul dari aplikasi."""
    req = []
    for sh in sheets:
        p = sh["properties"]
        n = baris_judul(p["title"])
        if not n or any(r.get("description") == KETERANGAN for r in sh.get("protectedRanges", [])):
            continue
        req.append({"addProtectedRange": {"protectedRange": {
            "range": {"sheetId": p["sheetId"], "startRowIndex": 0, "endRowIndex": n},
            "description": KETERANGAN, "warningOnly": True}}})
    return req


def pastikan(ss=None) -> int:
    """Pasang proteksi judul yang belum ada (sekali per tab per jalannya aplikasi). Jumlah proteksi baru."""
    with _lock:
        ss = ss or lk_baru._ss()
        meta = ss.fetch_sheet_metadata(params={
            "fields": "sheets(properties(sheetId,title),protectedRanges(description))"})
        sheets = [s for s in meta.get("sheets", []) if s["properties"]["sheetId"] not in _sudah]
        req = rencana(sheets)
        if req:
            ss.batch_update({"requests": req})
            log.info("Proteksi judul dipasang di %d tab", len(req))
        _sudah.update(s["properties"]["sheetId"] for s in sheets if baris_judul(s["properties"]["title"]))
        return len(req)
