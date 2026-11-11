"""Template blast dari sheet "Draft Broadcast Tim Monitoring": setiap tab berawalan "BC - " jadi satu template.

Isi tab dibuat rumus di sheet: satu baris per PIC + fasilitator (atau koordinator untuk tab koordinator) dengan pesan
siap kirim yang sudah berisi daftar sekolah masing-masing. Aplikasi hanya mengambil baris milik petugas ini dan
mencocokkan nama penerimanya dengan LK; nomor tetap diambil dari LK (tidak dari sheet ini).

Alamat sheet tidak disimpan di repo: LKM_BC_SHEET_ID, `bc` di sheets.json, atau baris `draft_broadcast` di tab
Pengaturan sheet Akses (berlaku untuk seluruh tim).
"""

import logging
import os
import re
from typing import Any

from . import config, lk_baru
from .google_auth import gspread_client
from .sheets import cache, normalize_petugas

log = logging.getLogger(__name__)

AWALAN_TAB = "BC -"
KUNCI_PENGATURAN = "draft_broadcast"
CACHE_DETIK = 300


class BcError(Exception):
    pass


def sheet_id() -> str:
    env = os.environ.get("LKM_BC_SHEET_ID")
    if env:
        return env
    lokal = lk_baru._sheets_json().get("bc")
    if lokal:
        return lk_baru._id_dari(str(lokal))

    def load() -> str:
        try:
            ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
            baris = ss.values_get(f"'{lk_baru.TAB_PENGATURAN}'!A1:B50").get("values", [])
        except Exception:
            return ""
        for r in baris:
            if len(r) > 1 and str(r[0]).strip().casefold() == KUNCI_PENGATURAN:
                return lk_baru._id_dari(str(r[1]))
        return ""

    return cache.get("bc_id", 600, load)


def tab_bc(judul: str) -> bool:
    return judul.strip().upper().startswith(AWALAN_TAB)


def _salam(teks: str) -> str:
    """Sapaan di sheet dihitung saat sheet dibuka; ganti dengan {salam} supaya sesuai jam kirim."""
    return re.sub(r"(?i)\bselamat\s+(pagi|siang|sore|malam)\b", "Selamat {salam}", teks, count=1)


def _kolom(header: list[Any], *cari: str, kecuali: tuple[str, ...] = ()) -> int | None:
    for c in cari:
        for i, h in enumerate(header):
            t = str(h).strip().casefold()
            if c in t and not any(x in t for x in kecuali):
                return i
    return None


def parse_tab(judul: str, values: list[list[Any]], petugas: str) -> dict[str, Any] | None:
    """Satu tab BC -> {judul, jenis, pesan: [(nama, teks)]} untuk baris milik `petugas`. None bila formatnya lain."""
    baris_h = next((i for i, r in enumerate(values) if r and str(r[0]).strip().casefold().startswith("pic")), None)
    if baris_h is None:
        return None
    h = values[baris_h]
    i_nama = _kolom(h, "nama fasilitator")
    jenis = "fasil"
    if i_nama is None:
        i_nama, jenis = _kolom(h, "koordinator"), "koor"
    i_pesan = _kolom(h, "siap salin", "bc ", kecuali=("link", "whatsapp"))
    if i_nama is None or i_pesan is None:
        return None
    saya = normalize_petugas(petugas)
    pesan: list[tuple[str, str]] = []
    for r in values[baris_h + 1:]:
        if len(r) <= max(i_nama, i_pesan) or normalize_petugas(r[0]) != saya:
            continue
        nama, teks = str(r[i_nama]).strip(), str(r[i_pesan]).replace("\r\n", "\n").strip()
        if nama and teks:
            pesan.append((nama, _salam(teks)))
    judul_tpl = re.sub(r"(?i)^bc\s*-\s*", "", judul.strip())
    return {"tab": judul.strip(), "judul": f"BC {judul_tpl.title()}", "jenis": jenis, "pesan": pesan}


def baca(petugas: str, refresh: bool = False) -> list[dict[str, Any]]:
    """Semua tab BC untuk `petugas`."""
    sid = sheet_id()
    if not sid:
        raise BcError("Link sheet Draft Broadcast belum dipasang.")

    def load() -> list[dict[str, Any]]:
        try:
            ss = gspread_client().open_by_key(sid)
            tabs = [w.title for w in ss.worksheets() if tab_bc(w.title)]
            if not tabs:
                return []
            got = ss.values_batch_get([f"'{t}'!A1:F" for t in tabs]).get("valueRanges", [])
        except Exception as e:
            raise BcError(f"Sheet Draft Broadcast tidak terbaca: {e}") from e
        out = []
        for t, vr in zip(tabs, got):
            x = parse_tab(t, vr.get("values", []), petugas)
            if x is None:
                log.warning("Tab %s tidak berformat BC (kolom PIC / nama / pesan tidak ditemukan)", t)
                continue
            out.append(x)
        return out

    return cache.get(f"bc:{normalize_petugas(petugas)}", CACHE_DETIK, load, refresh)


def template(petugas: str, kunci_nama: dict[str, dict[str, str]], refresh: bool = False) -> list[dict[str, Any]]:
    """Template per tab: pesan dipetakan ke kunci penerima Blast. `kunci_nama` = {jenis: {nama ternormalisasi: kunci}}."""
    out = []
    for x in baca(petugas, refresh):
        peta = kunci_nama.get(x["jenis"], {})
        per: dict[str, str] = {}
        tanpa: list[str] = []
        for nama, teks in x["pesan"]:
            k = peta.get(normalize_petugas(nama))
            if k:
                per.setdefault(k, teks)
            else:
                tanpa.append(nama)
        out.append({"kode": "bc:" + x["tab"], "judul": x["judul"], "tab": x["tab"], "jenis": x["jenis"],
                    "per": per, "tanpa_cocok": tanpa})
    return out
