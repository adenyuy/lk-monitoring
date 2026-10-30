"""Tarik data cutoff (CSV/Excel dari aplikasi) ke LK. Port dari legacy/tarik.py.

  Mingguan (Baseline) : progres, submit, reviu baseline di sheet WEEK n
  Harian              : progres, submit, reviu terbaru + Prioritas di sheet WEEK n
  Waktu tunggu        : kolom Waktu Tunggu di sheet WEEK n, dari file tanggal kirim laporan 50% (NPSN, Tanggal Kirim)
Huruf kolom WEEK dibaca dari judul baris 2 (lihat _kolom).

Kolom file cutoff (urutan tetap):
  A NPSN | B Nama Sekolah | C Jenis Laporan | D Periode Ke | E Capaian (%) | F Sudah Submit | G Sudah Review | ...

Setiap tarikan dicatat di tab tersembunyi 'Log Tarik Data' di LK supaya riwayatnya terlihat oleh semua admin.
"""

import io
import json
import logging
import re
import secrets
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from . import config, db, schedule
from .sheets import cache, col_number, gspread_client, kolom_lk, lk_tab

log = logging.getLogger(__name__)
WEEK_FIRST_ROW = config.LK_FIRST_ROW
MODE_LABEL = {"mingguan": "Mingguan (Baseline)", "harian": "Harian", "waktu_tunggu": "Waktu Tunggu"}
LOG_TAB = "Log Tarik Data"
LOG_JUDUL = ["Waktu", "Jenis", "Week", "File", "Sekolah", "Oleh"]
CUT_NPSN, CUT_JENIS, CUT_CAPAIAN, CUT_SUBMIT, CUT_REVIU = 0, 2, 4, 5, 6
JENIS_PROGRES = ("laporan mingguan", "laporan bulanan")  # progres = capaian tertinggi dari keduanya
JENIS_50 = "laporan 50%"
PRIO_LABEL = ("Prioritas 1", "Prioritas 2", "Prioritas 3", "Selesai")
RENCANA_DETIK = 30 * 60


class CutoffError(Exception):
    pass


# ---------- baca & olah file ----------

def baca(data: bytes, nama_file: str, min_kolom: int = CUT_REVIU + 1) -> pd.DataFrame:
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
    if df is None or df.shape[1] < min_kolom:
        raise CutoffError(f"Format file tidak sesuai: butuh minimal {min_kolom} kolom, "
                          f"ketemu {0 if df is None else df.shape[1]}.")
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
        if j in JENIS_PROGRES:
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


EXCEL_NOL = datetime(1899, 12, 30)


def ke_serial(v: Any) -> float | None:
    """Tanggal kirim -> nomor seri tanggal Sheets (rumus Waktu Tunggu memakai INT() atasnya)."""
    s = str(v).strip()
    if not s:
        return None
    try:
        n = float(s.replace(",", "."))
        return n if 20000 < n < 80000 else None  # sudah berupa nomor seri
    except ValueError:
        pass
    iso = re.match(r"^\d{4}-\d{2}-\d{2}", s)
    t = pd.to_datetime(s, errors="coerce", dayfirst=not iso)
    if pd.isna(t):
        return None
    t = t.tz_localize(None) if t.tzinfo else t
    return round((t.to_pydatetime() - EXCEL_NOL).total_seconds() / 86400, 8)


def _angka(v: Any) -> Any:
    s = key_npsn(v)
    return int(s) if s.isdigit() else s


def olah_raw(df: pd.DataFrame) -> tuple[list[list], int]:
    """File Raw Reviu 50% -> baris [NPSN, serial tanggal kirim, kiriman ke-], dan jumlah baris tanpa tanggal.
    Kolom dicari dari judulnya; bila tidak ketemu dipakai urutan A, B, C."""
    judul = [str(c).strip().lower() for c in df.columns]

    def cari(*kata: str, cadangan: int) -> int:
        return next((i for i, j in enumerate(judul) if any(k in j for k in kata)), cadangan)

    i_npsn, i_tgl, i_ke = cari("npsn", cadangan=0), cari("tanggal", "kirim", cadangan=1), cari("kiriman ke", cadangan=2)
    cols = df.columns
    baris, tanpa_tgl = [], 0
    for _, r in df.iterrows():
        npsn = key_npsn(r[cols[i_npsn]])
        if not npsn:
            continue
        tgl = ke_serial(r[cols[i_tgl]])
        if tgl is None:
            tanpa_tgl += 1
            continue
        ke = _angka(r[cols[i_ke]]) if i_ke < len(cols) else ""
        baris.append([_angka(npsn), tgl, ke])
    return baris, tanpa_tgl


def _kolom_tunggu(ss, tab: str) -> str:
    """Huruf kolom 'Waktu Tunggu' dari judul baris 2."""
    from .sheets import col_letter

    judul = (ss.values_get(f"'{tab}'!A{WEEK_FIRST_ROW - 1}:BZ{WEEK_FIRST_ROW - 1}").get("values") or [[]])[0]
    for i, j in enumerate(judul):
        if " ".join(str(j).lower().split()) == "waktu tunggu":
            return col_letter(i)
    raise CutoffError(f'Kolom berjudul "Waktu Tunggu" tidak ada di baris {WEEK_FIRST_ROW - 1} sheet "{tab}".')


def hari_tunggu(submit: Any, reviu: Any, serial: float | None, hari_ini: date) -> int | str:
    """Sama dengan rumus LK =IF(AND(P="Ya",Q="Tidak"),IFERROR(TODAY()-INT(tanggal kirim),""),""):
    selisih hari kalender (jam diabaikan) bila sudah submit dan belum direviu, selain itu kosong."""
    if str(submit).strip().lower() != "ya" or str(reviu).strip().lower() != "tidak" or serial is None:
        return ""
    return (hari_ini - (EXCEL_NOL + timedelta(days=int(serial))).date()).days


def siapkan_waktu_tunggu(data: bytes, nama_file: str, week: str) -> "Rencana":
    df = baca(data, nama_file, min_kolom=2)
    baris, tanpa_tgl = olah_raw(df)
    if not baris:
        raise CutoffError("Tidak ada baris dengan NPSN dan Tanggal Kirim yang terbaca di file ini.")
    tgl: dict[str, float] = {}
    for npsn, serial, _ in baris:  # seperti XLOOKUP: baris pertama per NPSN yang dipakai
        tgl.setdefault(key_npsn(npsn), serial)
    tab = lk_tab(week)
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    try:
        ws = ss.worksheet(tab)
    except Exception as e:
        raise CutoffError(f'Sheet "{tab}" tidak ditemukan di LK.') from e
    try:
        lk = kolom_lk(week, refresh=True)
    except Exception as e:
        raise CutoffError(f"Judul kolom LK tidak terbaca: {e}") from e
    kol = {"tunggu": _kolom_tunggu(ss, tab), "npsn": lk.npsn, "submit": lk.submit, "reviu": lk.reviu}
    got = ss.values_batch_get([f"'{tab}'!{kol[k]}{WEEK_FIRST_ROW}:{kol[k]}" for k in ("npsn", "submit", "reviu")],
                              params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("valueRanges", [])
    kolom_isi = [[(r[0] if r else "") for r in g.get("values", [])] for g in got]
    npsn_list = [key_npsn(v) for v in kolom_isi[0]]
    while npsn_list and not npsn_list[-1]:
        npsn_list.pop()
    if not npsn_list:
        raise CutoffError(f'Tidak ada NPSN di kolom {kol["npsn"]} sheet "{tab}".')

    def sel(i: int, j: int) -> str:
        return str(kolom_isi[i][j]).strip() if j < len(kolom_isi[i]) else ""

    hari_ini = schedule.now().date()
    nilai, menunggu, menunggu_ada = [], 0, 0
    for j, npsn in enumerate(npsn_list):
        nilai.append([hari_tunggu(sel(1, j), sel(2, j), tgl.get(npsn), hari_ini)])
        if hari_tunggu(sel(1, j), sel(2, j), 0, hari_ini) != "":
            menunggu += 1
            menunggu_ada += npsn in tgl
    r = Rencana(
        token=secrets.token_urlsafe(16), mode="waktu_tunggu", week=str(week), tab=tab, nama_file=nama_file,
        n=len(npsn_list), blok=nilai, prio=[], kol=kol,
        ringkasan={
            "baris_file": int(len(df)),
            "baris_valid": len(baris),
            "tanpa_tanggal": tanpa_tgl,
            "sekolah_file": len(tgl),
            "sekolah_sheet": len(npsn_list),
            "sekolah_cocok": sum(1 for k in npsn_list if k in tgl),
            "menunggu_lk": menunggu,
            "menunggu_ada": menunggu_ada,
            "kolom": kol["tunggu"],
            "peringatan": "" if "npsn" in str(df.columns[0]).lower() else
            "Judul kolom pertama bukan NPSN. Pastikan file berisi NPSN, Tanggal Kirim, Kiriman Ke-.",
        },
    )
    r.ringkasan["sheet_id"] = ws.id
    _simpan_rencana(r)
    return r


def _tulis_waktu_tunggu(r: "Rencana") -> datetime:
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    try:
        lk = kolom_lk(r.week, refresh=True)
        kol = {"tunggu": _kolom_tunggu(ss, r.tab), "npsn": lk.npsn, "submit": lk.submit, "reviu": lk.reviu}
    except CutoffError:
        raise
    except Exception as e:
        raise CutoffError(f"Judul kolom LK tidak terbaca: {e}") from e
    if kol != r.kol:
        raise CutoffError("Kolom LK berubah sejak file dicek (ada kolom disisipkan/dipindah). Cek file lagi.")
    akhir = WEEK_FIRST_ROW + r.n - 1
    k = kol["tunggu"]
    ss.values_batch_update({"valueInputOption": "RAW", "data": [
        {"range": f"'{r.tab}'!{k}{WEEK_FIRST_ROW}:{k}{akhir}", "values": r.blok},
    ]})
    now = schedule.now()
    sid = r.ringkasan["sheet_id"]
    ci = col_index(k)
    ss.batch_update({"requests": [{
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": WEEK_FIRST_ROW - 1, "endRowIndex": akhir,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }, {
        "updateCells": {
            "range": {"sheetId": sid, "startRowIndex": WEEK_FIRST_ROW - 2, "endRowIndex": WEEK_FIRST_ROW - 1,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "rows": [{"values": [{"note": _catatan("Waktu Tunggu", now, r.nama_file)}]}],
            "fields": "note",
        }
    }]})
    return now


def _catatan(label: str, now: datetime, file: str) -> str:
    return (f"Update terakhir ({label}): {now.strftime('%d %b %Y %H:%M')}\n"
            f"sumber: {file}\noleh: {db.get_setting('nama_petugas') or ''}")


def col_index(letter: str) -> int:
    return col_number(letter)


def _kolom(week: str, mode: str) -> dict[str, str]:
    """Kolom tujuan tarikan, dari judul LK terbaru (bukan huruf tetap: admin bisa menyisipkan kolom).
    Progres, submit, dan reviu harus berdampingan karena ditulis sebagai satu blok."""
    try:
        kol = kolom_lk(week, refresh=True)
    except Exception as e:
        raise CutoffError(f"Judul kolom LK tidak terbaca: {e}") from e
    cols = ((kol.progres_base, kol.submit_base, kol.reviu_base) if mode == "mingguan"
            else (kol.progres, kol.submit, kol.reviu))
    n = [col_number(c) for c in cols]
    if n != list(range(n[0], n[0] + 3)):
        raise CutoffError(f"Kolom progres, submit, dan reviu {MODE_LABEL[mode].lower()} di LK tidak berdampingan "
                          f"({', '.join(cols)}). Rapikan urutannya dulu.")
    return {"mulai": cols[0], "akhir": cols[2], "label": MODE_LABEL[mode], "npsn": kol.npsn,
            "prioritas": kol.prioritas}


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
    kol: dict[str, str] = field(default_factory=dict)  # kolom tujuan saat dicek (lihat _kolom)
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
    if mode == "waktu_tunggu":
        return siapkan_waktu_tunggu(data, nama_file, week)
    if mode not in MODE_LABEL:
        raise CutoffError("Mode harus harian, mingguan, atau waktu_tunggu.")
    df = baca(data, nama_file)
    progress, lap50 = olah(df)
    tab = lk_tab(week)
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    try:
        ws = ss.worksheet(tab)
    except Exception as e:
        raise CutoffError(f'Sheet "{tab}" tidak ditemukan di LK. Buat dulu sheet-nya.') from e
    kol = _kolom(week, mode)
    rng = [f"'{tab}'!{kol['npsn']}{WEEK_FIRST_ROW}:{kol['npsn']}",
           f"'{tab}'!{kol['mulai']}{WEEK_FIRST_ROW}:{kol['akhir']}"]
    if mode == "harian":
        rng.append(f"'{tab}'!{kol['prioritas']}{WEEK_FIRST_ROW}:{kol['prioritas']}")
    got = ss.values_batch_get(rng, params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("valueRanges", [])
    npsn_list = [key_npsn(r[0]) if r else "" for r in got[0].get("values", [])]
    while npsn_list and not npsn_list[-1]:
        npsn_list.pop()
    if not npsn_list:
        raise CutoffError(f'Tidak ada NPSN di kolom {kol["npsn"]} sheet "{tab}".')
    blok, prio = bangun(npsn_list, progress, lap50)

    berubah = _bandingkan(got[1].get("values", []), blok)
    if mode == "harian":
        lama_p = got[2].get("values", [])
        berubah_p = _bandingkan(lama_p, prio)
        sebelum = Counter((r[0] if r else "") for r in lama_p)
    else:
        berubah_p, sebelum = 0, Counter()
    sesudah = Counter(p[0] for p in prio if p[0])
    kolom = f"{kol['mulai']}–{kol['akhir']}" + (f" dan {kol['prioritas']}" if mode == "harian" else "")

    r = Rencana(
        token=secrets.token_urlsafe(16), mode=mode, week=str(week), tab=tab, nama_file=nama_file,
        n=len(npsn_list), blok=blok, prio=prio, kol=kol,
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
    _simpan_rencana(r)
    return r


def _simpan_rencana(r: Rencana) -> None:
    with _lock:
        now = time.time()
        for t in [t for t, x in _rencana.items() if now - x.dibuat > RENCANA_DETIK]:
            del _rencana[t]
        _rencana[r.token] = r


def tulis(token: str) -> dict[str, Any]:
    with _lock:
        r = _rencana.pop(token, None)
    if r is None or time.time() - r.dibuat > RENCANA_DETIK:
        raise CutoffError("Hasil cek sudah kedaluwarsa. Cek file lagi.")
    if r.mode == "waktu_tunggu":
        return _selesai(r, r.ringkasan["kolom"], _tulis_waktu_tunggu(r))
    kol = _kolom(r.week, r.mode)
    if kol != r.kol:
        raise CutoffError("Kolom LK berubah sejak file dicek (ada kolom disisipkan/dipindah). Cek file lagi.")
    akhir = WEEK_FIRST_ROW + r.n - 1
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    data = [{"range": f"'{r.tab}'!{kol['mulai']}{WEEK_FIRST_ROW}:{kol['akhir']}{akhir}", "values": r.blok}]
    if r.mode == "harian":
        data.append({"range": f"'{r.tab}'!{kol['prioritas']}{WEEK_FIRST_ROW}:{kol['prioritas']}{akhir}", "values": r.prio})
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
            "rows": [{"values": [{"note": _catatan(kol["label"], now, r.nama_file)}]}],
            "fields": "note",
        }
    }]})
    return _selesai(r, r.ringkasan["kolom"], now)


def _selesai(r: Rencana, kolom: str, now: datetime) -> dict[str, Any]:
    cache.clear()  # LK berubah: baca ulang di layar lain
    waktu = now.isoformat(timespec="seconds")
    ringkas = {k: v for k, v in r.ringkasan.items() if k != "sheet_id"}
    with db.tx() as c:
        c.execute(
            "INSERT INTO cutoff_runs(waktu, file, mode, week, sekolah, ringkasan) VALUES(?,?,?,?,?,?)",
            (waktu, r.nama_file, r.mode, r.week, r.n, json.dumps(ringkas)),
        )
    catat_bersama([waktu, r.mode, r.week, r.nama_file, r.n, db.get_setting("nama_petugas") or ""])
    return {"sekolah": r.n, "tab": r.tab, "kolom": kolom, "waktu": now.strftime("%H.%M")}


def riwayat() -> list[dict[str, Any]]:
    """Tarikan dari laptop ini."""
    return [dict(r) for r in db.query("SELECT waktu, file, mode, week, sekolah FROM cutoff_runs ORDER BY waktu")]


# ---------- riwayat bersama (semua admin) ----------

def _tambah_log(ss, baris: list[list]) -> None:
    if LOG_TAB not in [w.title for w in ss.worksheets()]:
        ws = ss.add_worksheet(LOG_TAB, rows=200, cols=len(LOG_JUDUL))
        ss.batch_update({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": ws.id, "hidden": True}, "fields": "hidden"}}]})
        ss.values_update(f"'{LOG_TAB}'!A1", params={"valueInputOption": "RAW"}, body={"values": [LOG_JUDUL]})
    ss.values_append(f"'{LOG_TAB}'!A:F", params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                     body={"values": baris})
    cache.clear()


def catat_bersama(baris: list) -> None:
    """Tambahkan satu baris ke tab tersembunyi 'Log Tarik Data'. Tidak pernah menggagalkan tarikan."""
    try:
        _tambah_log(gspread_client().open_by_key(config.LK_SHEET_ID), [baris])
    except Exception:
        log.exception("Gagal mencatat riwayat tarik ke LK")


def _baca_log(ss) -> list[dict[str, Any]]:
    if LOG_TAB not in [w.title for w in ss.worksheets()]:
        return []
    out = []
    for r in ss.values_get(f"'{LOG_TAB}'!A2:F").get("values", []):
        r = list(r) + [""] * (6 - len(r))
        if r[0]:
            out.append({"waktu": r[0], "mode": r[1], "week": r[2], "file": r[3],
                        "sekolah": int(r[4]) if str(r[4]).isdigit() else 0, "oleh": r[5]})
    return out


def _kunci(r: dict[str, Any]) -> tuple:
    return (r["mode"], str(r["week"]), r["waktu"][:16])


def susulkan_riwayat() -> int:
    """Sekali per laptop: kirim riwayat tarik lokal (dari sebelum ada log bersama) ke 'Log Tarik Data',
    supaya tarikan lama dari laptop ini ikut terlihat di aplikasi admin lain."""
    if db.get_setting("cutoff_log_disusulkan"):
        return 0
    try:
        lokal = riwayat()
        if lokal:
            ss = gspread_client().open_by_key(config.LK_SHEET_ID)
            ada = {_kunci(r) for r in _baca_log(ss)}
            petugas = db.get_setting("nama_petugas") or ""
            baru = [[r["waktu"], r["mode"], r["week"], r["file"], r["sekolah"], petugas]
                    for r in lokal if _kunci(r) not in ada]
            if baru:
                _tambah_log(ss, baru)
        else:
            baru = []
        db.set_setting("cutoff_log_disusulkan", schedule.now().isoformat(timespec="seconds"))
        return len(baru)
    except Exception:
        log.exception("Gagal menyusulkan riwayat tarik ke LK")
        return 0


_RE_CATATAN = re.compile(r"Update terakhir \((.+?)\): (\d{1,2} \w{3} \d{4} \d{1,2}:\d{2})(?:\nsumber: (.*))?(?:\noleh: (.*))?")
_MODE_DARI_LABEL = {v: k for k, v in MODE_LABEL.items()}


def dari_catatan(note: str, week: str) -> dict[str, Any] | None:
    """Catatan 'Update terakhir (...)' di judul kolom -> satu tarikan. Dipakai untuk tarikan yang belum masuk log."""
    m = _RE_CATATAN.search(note or "")
    if not m or m.group(1) not in _MODE_DARI_LABEL:
        return None
    try:
        t = datetime.strptime(m.group(2), "%d %b %Y %H:%M").replace(tzinfo=schedule.now().tzinfo)
    except ValueError:
        return None
    mode = _MODE_DARI_LABEL[m.group(1)]
    return {"waktu": t.isoformat(timespec="seconds"), "mode": mode, "week": "" if mode == "waktu_tunggu" else week,
            "file": (m.group(3) or "").strip(), "sekolah": 0, "oleh": (m.group(4) or "").strip()}


def _baca_bersama() -> list[dict[str, Any]]:
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    judul = [w.title for w in ss.worksheets()]
    out = _baca_log(ss)
    # Catatan di judul kolom: tarikan terakhir per jenis, juga dari versi aplikasi yang belum mencatat log
    weeks = [t for t in judul if t.upper().startswith(config.LK_WEEK_PREFIX.upper())]
    ranges = [f"'{t}'!A{WEEK_FIRST_ROW - 1}:BZ{WEEK_FIRST_ROW - 1}" for t in weeks]
    if ranges:
        meta = ss.fetch_sheet_metadata(params={"ranges": ranges, "fields": "sheets(properties.title,data.rowData.values.note)"})
        for sh in meta.get("sheets", []):
            tab = sh["properties"]["title"]
            week = tab[len(config.LK_WEEK_PREFIX):].strip() if tab in weeks else ""
            for d in sh.get("data", []):
                for row in d.get("rowData", []):
                    for v in row.get("values", []):
                        x = dari_catatan(v.get("note", ""), week)
                        if x:
                            out.append(x)
    return out


def riwayat_semua() -> list[dict[str, Any]]:
    """Riwayat tarik dari semua admin (log bersama + catatan di LK), digabung dengan riwayat laptop ini."""
    try:
        bersama = cache.get("cutoff_riwayat", 60, _baca_bersama)
    except Exception:
        log.exception("Riwayat tarik bersama tidak terbaca")
        bersama = []
    gabung: dict[tuple, dict[str, Any]] = {}
    petugas = db.get_setting("nama_petugas") or ""
    lokal = [{**r, "oleh": petugas} for r in riwayat()]
    for r in bersama + lokal:  # tarikan yang sama (menit yang sama) digabung, isian kosong dilengkapi
        k = _kunci(r)
        gabung[k] = {**gabung.get(k, {}), **{a: b for a, b in r.items() if b not in ("", 0, None)}}
    return sorted(({"file": "", "sekolah": 0, "oleh": "", "week": "", **v} for v in gabung.values()),
                  key=lambda r: r["waktu"])


def daftar_week() -> list[str]:
    """Nomor WEEK yang ada di LK, mis. ['1', '2']."""
    from .sheets import daftar_week as dw

    return dw()
