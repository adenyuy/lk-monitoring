"""Tarik data cutoff (CSV/Excel dari aplikasi) ke sheet WEEK n di LK. Port dari legacy/tarik.py.

  Mingguan (Baseline) : isi J, K, L
  Harian              : isi M, N, O + Prioritas (H)

Kolom file cutoff (urutan tetap):
  A NPSN | B Nama Sekolah | C Jenis Laporan | D Periode Ke | E Capaian (%) | F Sudah Submit | G Sudah Review | ...
"""

import io
import json
import re
import secrets
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import config, db, schedule
from .sheets import cache, gspread_client, lk_tab

WEEK_FIRST_ROW = config.LK_FIRST_ROW
COL_NPSN = "C"
COL_PRIORITAS = "H"
KOLOM = {
    "mingguan": {"mulai": "J", "akhir": "L", "label": "Mingguan (Baseline)"},
    "harian": {"mulai": "M", "akhir": "O", "label": "Harian"},
}
CUT_NPSN, CUT_JENIS, CUT_CAPAIAN, CUT_SUBMIT, CUT_REVIU = 0, 2, 4, 5, 6
JENIS_MINGGUAN = "laporan mingguan"
JENIS_50 = "laporan 50%"
PRIO_LABEL = ("Prioritas 1", "Prioritas 2", "Prioritas 3", "Selesai")
RENCANA_DETIK = 30 * 60


class CutoffError(Exception):
    pass


# ---------- baca & olah file ----------

def baca(data: bytes, nama_file: str) -> pd.DataFrame:
    """Semua kolom dibaca sebagai teks supaya '13.12' tidak berubah jadi tanggal."""
    ext = nama_file.lower().rsplit(".", 1)[-1] if "." in nama_file else ""
    df = None
    if ext == "csv":
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, sep=None,
                                 engine="python", encoding=enc)
                break
            except UnicodeDecodeError:
                continue
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)
    else:
        raise CutoffError("File harus CSV atau Excel (.csv, .xlsx, .xls).")
    if df is None or df.shape[1] < CUT_REVIU + 1:
        raise CutoffError(f"Format file tidak sesuai: butuh minimal 7 kolom (A–G), ketemu {0 if df is None else df.shape[1]}.")
    return df


def header_aneh(df: pd.DataFrame) -> str:
    header = [str(c).strip().lower() for c in df.columns[: CUT_REVIU + 1]]
    if "npsn" not in header[CUT_NPSN] or "jenis" not in header[CUT_JENIS]:
        return "Judul kolom tidak seperti biasa: " + ", ".join(header) + ". Pastikan urutannya NPSN, Nama, Jenis, Periode, Capaian, Submit, Review."
    return ""


def ke_capaian(v: str) -> float | None:
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)  # '13.12' yang terlanjur jadi tanggal 2026-12-13
    if m:
        return int(m.group(3)) + int(m.group(2)) / 100
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def key_npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", str(v).strip())


def ya_tidak(v: Any) -> str:
    return "Ya" if str(v).strip().lower() == "ya" else "Tidak"


def olah(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, tuple[str, str]]]:
    progress: dict[str, float] = {}
    lap50: dict[str, tuple[str, str]] = {}
    cols = df.columns
    for npsn, jenis, capaian, submit, reviu in zip(
        df[cols[CUT_NPSN]], df[cols[CUT_JENIS]], df[cols[CUT_CAPAIAN]], df[cols[CUT_SUBMIT]], df[cols[CUT_REVIU]]
    ):
        k = key_npsn(npsn)
        if not k:
            continue
        j = str(jenis).strip().lower()
        if j == JENIS_MINGGUAN:
            v = ke_capaian(capaian)
            if v is not None and (k not in progress or v > progress[k]):
                progress[k] = v
        elif j == JENIS_50:
            lap50[k] = (ya_tidak(submit), ya_tidak(reviu))
    return progress, lap50


def prioritas(p: float | None, submit: str, reviu: str) -> str:
    if submit != "Ya":
        return "Prioritas 1"
    if p is None or p < 50:
        return "Prioritas 2"
    if reviu != "Ya":
        return "Prioritas 3"
    return "Selesai"


def bangun(npsn_list: list[str], progress: dict, lap50: dict) -> tuple[list[list], list[list]]:
    blok, prio = [], []
    for k in npsn_list:
        if not k:
            blok.append(["", "", ""])
            prio.append([""])
            continue
        p = progress.get(k)
        sub, rev = lap50.get(k, ("Tidak", "Tidak"))
        blok.append(["" if p is None else round(p / 100, 6), sub, rev])  # kolom progres berformat persen
        prio.append([prioritas(p, sub, rev)])
    return blok, prio


def col_index(letter: str) -> int:
    n = 0
    for ch in letter:
        n = n * 26 + ord(ch) - 64
    return n - 1


# ---------- rencana (cek dulu) lalu tulis ----------

@dataclass
class Rencana:
    token: str
    mode: str
    week: str
    tab: str
    nama_file: str
    n: int
    blok: list[list]
    prio: list[list]
    ringkasan: dict[str, Any] = field(default_factory=dict)
    dibuat: float = field(default_factory=time.time)


_rencana: dict[str, Rencana] = {}
_lock = threading.Lock()


def _bandingkan(lama: list[list], baru: list[list]) -> int:
    def norm(v):
        if v in ("", None):
            return ""
        if isinstance(v, (int, float)):
            return round(float(v), 4)
        return str(v).strip()
    berubah = 0
    for i, b in enumerate(baru):
        a = lama[i] if i < len(lama) else []
        a = list(a) + [""] * (len(b) - len(a))
        if any(norm(x) != norm(y) for x, y in zip(a, b)):
            berubah += 1
    return berubah


def siapkan(data: bytes, nama_file: str, mode: str, week: str) -> Rencana:
    if mode not in KOLOM:
        raise CutoffError("Mode harus harian atau mingguan.")
    df = baca(data, nama_file)
    progress, lap50 = olah(df)
    tab = lk_tab(week)
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    try:
        ws = ss.worksheet(tab)
    except Exception as e:
        raise CutoffError(f'Sheet "{tab}" tidak ditemukan di LK. Buat dulu sheet-nya.') from e
    kol = KOLOM[mode]
    rng = [f"'{tab}'!{COL_NPSN}{WEEK_FIRST_ROW}:{COL_NPSN}",
           f"'{tab}'!{kol['mulai']}{WEEK_FIRST_ROW}:{kol['akhir']}"]
    if mode == "harian":
        rng.append(f"'{tab}'!{COL_PRIORITAS}{WEEK_FIRST_ROW}:{COL_PRIORITAS}")
    got = ss.values_batch_get(rng, params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("valueRanges", [])
    npsn_list = [key_npsn(r[0]) if r else "" for r in got[0].get("values", [])]
    while npsn_list and not npsn_list[-1]:
        npsn_list.pop()
    if not npsn_list:
        raise CutoffError(f'Tidak ada NPSN di kolom {COL_NPSN} sheet "{tab}".')
    blok, prio = bangun(npsn_list, progress, lap50)

    berubah = _bandingkan(got[1].get("values", []), blok)
    if mode == "harian":
        lama_p = got[2].get("values", [])
        berubah_p = _bandingkan(lama_p, prio)
        sebelum = Counter((r[0] if r else "") for r in lama_p)
    else:
        berubah_p, sebelum = 0, Counter()
    sesudah = Counter(p[0] for p in prio if p[0])
    kolom = f"{kol['mulai']}–{kol['akhir']}" + (f" dan {COL_PRIORITAS}" if mode == "harian" else "")

    r = Rencana(
        token=secrets.token_urlsafe(16), mode=mode, week=str(week), tab=tab, nama_file=nama_file,
        n=len(npsn_list), blok=blok, prio=prio,
        ringkasan={
            "baris_file": int(len(df)),
            "sekolah_mingguan": len(progress),
            "sekolah_lap50": len(lap50),
            "sekolah_sheet": len(npsn_list),
            "tanpa_mingguan": sum(1 for k in npsn_list if k and k not in progress),
            "berubah": berubah,
            "prioritas_berubah": berubah_p,
            "prioritas": [{"label": p, "sebelum": sebelum.get(p, 0), "sesudah": sesudah.get(p, 0)} for p in PRIO_LABEL]
            if mode == "harian" else [],
            "kolom": kolom,
            "peringatan": header_aneh(df),
        },
    )
    r.ringkasan["sheet_id"] = ws.id
    with _lock:
        now = time.time()
        for t in [t for t, x in _rencana.items() if now - x.dibuat > RENCANA_DETIK]:
            del _rencana[t]
        _rencana[r.token] = r
    return r


def tulis(token: str) -> dict[str, Any]:
    with _lock:
        r = _rencana.pop(token, None)
    if r is None or time.time() - r.dibuat > RENCANA_DETIK:
        raise CutoffError("Hasil cek sudah kedaluwarsa. Cek file lagi.")
    kol = KOLOM[r.mode]
    akhir = WEEK_FIRST_ROW + r.n - 1
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    data = [{"range": f"'{r.tab}'!{kol['mulai']}{WEEK_FIRST_ROW}:{kol['akhir']}{akhir}", "values": r.blok}]
    if r.mode == "harian":
        data.append({"range": f"'{r.tab}'!{COL_PRIORITAS}{WEEK_FIRST_ROW}:{COL_PRIORITAS}{akhir}", "values": r.prio})
    ss.values_batch_update({"valueInputOption": "RAW", "data": data})

    now = schedule.now()
    sid = r.ringkasan["sheet_id"]
    ci = col_index(kol["mulai"])
    ss.batch_update({"requests": [{
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": WEEK_FIRST_ROW - 1, "endRowIndex": akhir,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }, {
        "updateCells": {
            "range": {"sheetId": sid, "startRowIndex": WEEK_FIRST_ROW - 2, "endRowIndex": WEEK_FIRST_ROW - 1,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "rows": [{"values": [{"note": f"Update terakhir ({kol['label']}): {now.strftime('%d %b %Y %H:%M')}\n"
                                          f"sumber: {r.nama_file}\noleh: {db.get_setting('nama_petugas') or ''}"}]}],
            "fields": "note",
        }
    }]})
    cache.clear()  # LK berubah: baca ulang di layar lain

    ringkas = {k: v for k, v in r.ringkasan.items() if k != "sheet_id"}
    with db.tx() as c:
        c.execute(
            "INSERT INTO cutoff_runs(waktu, file, mode, week, sekolah, ringkasan) VALUES(?,?,?,?,?,?)",
            (now.isoformat(timespec="seconds"), r.nama_file, r.mode, r.week, r.n, json.dumps(ringkas)),
        )
    return {"sekolah": r.n, "tab": r.tab, "kolom": r.ringkasan["kolom"], "waktu": now.strftime("%H.%M")}


def riwayat() -> list[dict[str, Any]]:
    return [dict(r) for r in db.query("SELECT waktu, file, mode, week, sekolah FROM cutoff_runs ORDER BY waktu")]


def daftar_week() -> list[str]:
    """Nomor WEEK yang ada di LK, mis. ['1', '2']."""
    def load():
        ss = gspread_client().open_by_key(config.LK_SHEET_ID)
        out = []
        for w in ss.worksheets():
            m = re.fullmatch(rf"{re.escape(config.LK_WEEK_PREFIX)}(\d+)", w.title.strip())
            if m:
                out.append(m.group(1))
        return sorted(out, key=int)
    return cache.get("lk_weeks", 300, load)
