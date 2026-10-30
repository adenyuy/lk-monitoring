"""LK Eskalasi: permasalahan sekolah yang perlu dijawab tim terkait, dicatat di spreadsheet LK Eskalasi milik tim.

Tab "LK Eskalasi" berisi satu baris per sekolah (judul di baris 4). Permasalahan pertama sebuah sekolah ditulis di
baris sekolah itu; permasalahan berikutnya ditambahkan sebagai baris baru di bawah tabel (data sekolah disalin),
sesuai petunjuk di sheet. Tanggal awal diisi aplikasi karena skrip onEdit sheet tidak jalan untuk tulisan lewat API.

Alamat sheet: LKM_ESKALASI_SHEET_ID, `eskalasi` di sheets.json, atau tab "Pengaturan" di sheet Akses
(baris `lk_eskalasi` | link), supaya admin cukup memasangnya sekali untuk semua anggota tim.
"""

import json
import os
import re
import threading
from datetime import date
from typing import Any

from . import config, paths, schedule
from .sheets import cache, col_letter, col_number, gspread_client

TAB = "LK Eskalasi"
TAB_PILIHAN = "Daftar Pilihan"
TAB_PENGATURAN = "Pengaturan"
BARIS_JUDUL = 4
TIM = ("Tim Monitoring", "Tim Aplikasi", "Tim Substansi", "PMO", "Tim Penyaluran", "Tim Regulasi")
JUDUL = {
    "no.": "no", "npsn": "npsn", "nama sekolah": "nama", "fasilitator": "fasil", "petugas monitoring": "petugas",
    "keterangan permasalahan": "keterangan", "permasalahan": "permasalahan",
    "tanggal awal permasalahan": "tgl_awal", "tanggal permasalahan selesai": "tgl_selesai",
    "status tindak lanjut": "status",
}
EXCEL_NOL = date(1899, 12, 30)
_lock = threading.Lock()


class EskalasiError(Exception):
    """Pesannya ditampilkan langsung ke pengguna."""


def key_npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", str(v).strip())


def _id_dari(nilai: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", nilai)
    return m.group(1) if m else nilai.strip()


def sheet_id() -> str:
    env = os.environ.get("LKM_ESKALASI_SHEET_ID")
    if env:
        return env
    f = paths.DATA_DIR / "sheets.json"
    try:
        lokal = json.loads(f.read_text(encoding="utf-8")).get("eskalasi") if f.exists() else ""
    except (ValueError, OSError):
        lokal = ""
    if lokal:
        return _id_dari(str(lokal))

    def load() -> str:
        ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
        try:
            baris = ss.values_get(f"'{TAB_PENGATURAN}'!A1:B50").get("values", [])
        except Exception:
            return ""
        for r in baris:
            if len(r) > 1 and str(r[0]).strip().casefold() == "lk_eskalasi":
                return _id_dari(str(r[1]))
        return ""

    sid = cache.get("eskalasi_id", 600, load)
    if not sid:
        raise EskalasiError('Link LK Eskalasi belum dipasang admin. Tambahkan baris "lk_eskalasi" berisi link sheet '
                            'di tab Pengaturan pada sheet Akses.')
    return sid


def _ss():
    return gspread_client().open_by_key(sheet_id())


def parse_judul(header: list[Any]) -> dict[str, str]:
    """Baris judul -> {field: huruf kolom}; tim tujuan disimpan sebagai 'tim:<nama>'."""
    pos: dict[str, str] = {}
    for i, v in enumerate(header):
        h = " ".join(str(v).lower().split())
        f = JUDUL.get(h) or next((f"tim:{t}" for t in TIM if t.lower() == h), None)
        if f and f not in pos:
            pos[f] = col_letter(i)
    hilang = [j for j, f in JUDUL.items() if f not in pos]
    if hilang:
        raise EskalasiError(f"Judul kolom LK Eskalasi tidak ketemu di baris {BARIS_JUDUL}: {', '.join(hilang)}.")
    return pos


def tanggal(v: Any) -> str:
    """Serial tanggal Sheets -> 'YYYY-MM-DD' (kosong bila bukan tanggal)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        return date.fromordinal(EXCEL_NOL.toordinal() + int(v)).isoformat()
    return str(v or "")


def _baca() -> tuple[dict[str, str], list[dict[str, Any]]]:
    ss = _ss()
    try:
        got = ss.values_get(f"'{TAB}'!A{BARIS_JUDUL}:Z", params={"valueRenderOption": "UNFORMATTED_VALUE"})
    except Exception as e:
        raise EskalasiError(f'Tab "{TAB}" di LK Eskalasi tidak bisa dibaca: {e}') from e
    nilai = got.get("values", [])
    if not nilai:
        raise EskalasiError(f'Tab "{TAB}" kosong.')
    kol = parse_judul(nilai[0])
    idx = {f: col_number(k) for f, k in kol.items()}
    baris = []
    for n, r in enumerate(nilai[1:], start=BARIS_JUDUL + 1):
        def sel(f: str) -> Any:
            i = idx[f]
            return r[i] if i < len(r) else ""
        npsn = key_npsn(sel("npsn"))
        if not npsn:
            continue
        baris.append({
            "baris": n, "no": sel("no"), "npsn": npsn, "nama": str(sel("nama")), "fasil": str(sel("fasil")),
            "petugas": str(sel("petugas")), "keterangan": str(sel("keterangan")).strip(),
            "permasalahan": str(sel("permasalahan")).strip(), "tgl_awal": tanggal(sel("tgl_awal")),
            "tgl_selesai": tanggal(sel("tgl_selesai")), "status": str(sel("status")).strip(),
            "tim": [t for t in TIM if f"tim:{t}" in idx and sel(f"tim:{t}") is True],
        })
    return kol, baris


def _terisi(b: dict[str, Any]) -> bool:
    return bool(b["keterangan"] or b["permasalahan"] or b["tim"])


def opsi() -> dict[str, Any]:
    def load() -> dict[str, Any]:
        got = _ss().values_batch_get([f"'{TAB_PILIHAN}'!A2:A", f"'{TAB_PILIHAN}'!C2:C"]).get("valueRanges", [])
        col = [[str(r[0]).strip() for r in g.get("values", []) if r and str(r[0]).strip()] for g in got]
        col += [[]] * (2 - len(col))
        return {"permasalahan": col[0], "status": col[1], "tim": list(TIM)}

    return cache.get("eskalasi_opsi", 300, load)


def daftar(npsn: list[str]) -> list[dict[str, Any]]:
    """Eskalasi yang sudah tercatat untuk sekolah-sekolah ini, terbaru dulu."""
    mau = {key_npsn(x) for x in npsn}
    _, baris = cache.get("eskalasi_baris", 60, _baca)
    isi = [b for b in baris if b["npsn"] in mau and _terisi(b)]
    return sorted(isi, key=lambda b: (b["tgl_awal"], b["baris"]), reverse=True)


def catat(npsn: list[str], keterangan: str, permasalahan: str, tim: list[str],
          cadangan: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Tulis satu permasalahan untuk beberapa sekolah. `cadangan` = data sekolah dari LK bila NPSN belum ada
    di LK Eskalasi ({npsn: {nama, fasil, petugas}})."""
    keterangan = keterangan.strip()
    if not keterangan:
        raise EskalasiError("Keterangan permasalahan wajib diisi.")
    tim = [t for t in TIM if t in tim]
    if not tim:
        raise EskalasiError("Pilih minimal satu tim tujuan eskalasi.")
    pilihan = opsi()
    if permasalahan and permasalahan not in pilihan["permasalahan"]:
        raise EskalasiError(f'Permasalahan "{permasalahan}" tidak ada di daftar pilihan LK Eskalasi.')
    status = pilihan["status"][0] if pilihan["status"] else ""
    hari = (schedule.now().date() - EXCEL_NOL).days

    with _lock:
        cache.clear()
        kol, baris = _baca()
        ss = _ss()
        data, tambah, ditulis, dilewati = [], [], [], []
        no_maks = max((int(b["no"]) for b in baris if isinstance(b["no"], (int, float))), default=0)
        lebar = max(col_number(k) for k in kol.values()) + 1
        for x in dict.fromkeys(key_npsn(v) for v in npsn):
            punya = [b for b in baris if b["npsn"] == x]
            kosong = next((b for b in punya if not _terisi(b)), None)
            isi = {"keterangan": keterangan, "permasalahan": permasalahan, "tgl_awal": hari, "status": status,
                   **{f"tim:{t}": t in tim for t in TIM}}
            if kosong:
                for f, v in isi.items():
                    if f in kol:
                        data.append({"range": f"'{TAB}'!{kol[f]}{kosong['baris']}", "values": [[v]]})
                ditulis.append({"npsn": x, "nama": kosong["nama"], "baris": kosong["baris"], "baru": False})
                continue
            asal = punya[0] if punya else (cadangan or {}).get(x)
            if not asal:
                dilewati.append(x)
                continue
            no_maks += 1
            row: list[Any] = [""] * lebar
            for f, v in {"no": no_maks, "npsn": x, "nama": asal.get("nama", ""), "fasil": asal.get("fasil", ""),
                         "petugas": asal.get("petugas", ""), **isi}.items():
                if f in kol:
                    row[col_number(kol[f])] = v
            tambah.append(row)
            ditulis.append({"npsn": x, "nama": asal.get("nama", ""), "baris": None, "baru": True})
        if not ditulis:
            raise EskalasiError("Sekolah yang dipilih tidak ditemukan di LK Eskalasi.")
        if data:
            ss.values_batch_update({"valueInputOption": "RAW", "data": data})
        if tambah:
            ss.values_append(f"'{TAB}'!A{BARIS_JUDUL}:{col_letter(lebar - 1)}",
                             params={"valueInputOption": "RAW", "insertDataOption": "OVERWRITE"},
                             body={"values": tambah})
        cache.clear()
    return {"ditulis": ditulis, "dilewati": dilewati}

