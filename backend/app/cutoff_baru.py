"""Tarik Cutoff ke LK format baru (WEEK n), dari export aplikasi per sekolah (CSV/Excel, berjudul).

Alur: siapkan(file) -> ringkasan perubahan untuk dicek admin -> tulis(token):
  1. identitas & komponen WEEK n diperbarui per NPSN (Kendala/TL petugas tidak disentuh); sekolah baru ditambahkan
  2. baris diurutkan per PIC lalu nama sekolah (supaya data tiap petugas terbaca cepat)
  3. keterangan otomatis Kendala/TL ditulis ulang sesuai to-do terbaru
  4. Log Progres (nasional) dan Log Progres PIC mendapat kolom/baris cutoff baru
Nomor HP yang rusak di export (notasi ilmiah Excel) tidak menimpa nomor yang sudah ada di LK.
"""

import io
import logging
import re
import secrets
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from . import lk_baru, schedule, todo
from .lk_baru import BARIS_DATA, KOMPONEN, Sekolah, komponen_dari_judul
from .sheets import cache, clean_petugas, col_letter

log = logging.getLogger(__name__)
TAB_PIC = "Log Progres PIC"
TAB_LOG = "Log Tarik Data"
RENCANA_DETIK = 30 * 60

WAJIB = ("NPSN", "Nama Sekolah", "Pendahuluan - Status Kirim", "Capaian Progres (%)", "Mingguan Terkirim",
         "Mingguan Due", "Bulanan Terkirim", "Bulanan Due", "Laporan 50% - Status Kirim",
         "Laporan 100% - Status Kirim")
KIRIM = {"Sudah Dikirim": "Sudah", "Belum Dikirim": "Belum", "Belum Due": "Belum Due"}
REVIU_LP = {"Disetujui": "Sudah", "Revisi": "Revisi", "Belum Direviu": "Belum", "Belum Dikirim": "-"}
REVIU_LAP = {"Selesai (TTD Koordinator)": "Sudah", "Disetujui Fasil, belum TTD Koordinator": "Belum TTD Koor",
             "Dikembalikan": "Dikembalikan", "Belum Direviu": "Belum", "Belum Dikirim": "-", "Belum Due": "Belum Due"}
KETERANGAN_BARU = (todo.SELESAI, todo.DUE, todo.KOSONG, todo.BERJALAN, todo.TANPA_DATA,
                   "Menunggu Lap. Pendahuluan", "Menunggu progres 50%", "Menunggu Lap. 50%", "Menunggu progres 100%")


class CutoffError(Exception):
    pass


# ---------- baca file ----------

def baca(data: bytes, nama_file: str) -> pd.DataFrame:
    ext = nama_file.lower().rsplit(".", 1)[-1] if "." in nama_file else ""
    df = None
    if ext == "csv":
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, sep=None, engine="python",
                                 encoding=enc)
                break
            except UnicodeDecodeError:
                continue
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)
    else:
        raise CutoffError("File harus CSV atau Excel (.csv, .xlsx, .xls).")
    if df is None:
        raise CutoffError("File tidak bisa dibaca.")
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    hilang = [c for c in WAJIB if c not in df.columns]
    if hilang:
        raise CutoffError("Kolom berikut tidak ada di file: " + ", ".join(hilang)
                          + ". Pastikan file-nya export per sekolah (bukan per laporan).")
    return df


def hp(v: Any) -> str:
    v = str(v or "").strip()
    if not v or "E+" in v.upper():
        return ""
    d = re.sub(r"\D", "", v)
    if d.startswith("62"):
        d = "0" + d[2:]
    elif d.startswith("8"):
        d = "0" + d
    return d if 9 <= len(d) <= 14 else ""


def angka(v: Any, bagi: float = 1) -> Any:
    try:
        return round(float(str(v).replace(",", ".")) / bagi, 4 if bagi > 1 else 1)
    except ValueError:
        return ""


def rasio(a: Any, b: Any) -> str:
    a, b = str(a).strip(), str(b).strip()
    if a == "Belum Due" or b == "Belum Due":
        return "Belum Due"
    if b == "0":
        return "-"
    return f"{a}/{b}" if a and b else ""


def npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", str(v).strip())


def olah(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """{npsn: {judul kolom WEEK: nilai}} dari export."""
    def g(r: dict, k: str) -> str:
        return str(r.get(k, "") or "").strip()

    out: dict[str, dict[str, Any]] = {}
    for r in df.to_dict("records"):
        n = npsn(r.get("NPSN", ""))
        if not n:
            continue
        x: dict[str, Any] = {
            "Nama Sekolah": g(r, "Nama Sekolah"),
            "Angkatan": g(r, "Angkatan").replace("Angkatan", "").strip(),
            "Provinsi": g(r, "Provinsi"), "Kab/Kota": g(r, "Kab/Kota"),
            "Nama Kepala Sekolah": g(r, "Nama Kepala Sekolah"), "No HP Kepala Sekolah": hp(g(r, "No HP Kepala Sekolah")),
            "PTN": g(r, "PTN"), "Koordinator": g(r, "Koordinator"), "Fasilitator": g(r, "Fasilitator"),
            "No HP Fasilitator": hp(g(r, "No HP Fasilitator")), "No HP Koordinator": hp(g(r, "No HP Koordinator")),
            "Status Laporan Pendahuluan": KIRIM.get(g(r, "Pendahuluan - Status Kirim"), g(r, "Pendahuluan - Status Kirim")),
            "Waktu Tunggu Reviu Laporan Pendahuluan": angka(g(r, "Hari Verif Pendahuluan")),
            "Reviu Laporan Pendahuluan": REVIU_LP.get(g(r, "Pendahuluan - Status Reviu"), g(r, "Pendahuluan - Status Reviu")),
            "Progres Fisik (%)": angka(g(r, "Capaian Progres (%)"), 100),
            "Laporan Mingguan (jumlah/target)": rasio(g(r, "Mingguan Terkirim"), g(r, "Mingguan Due")),
            "Waktu Tunggu Reviu Laporan Mingguan": angka(g(r, "Rata2 Hari Verif Mingguan")),
            "Reviu Laporan Mingguan (direviu/submit)": rasio(g(r, "Mingguan Sudah Direviu"), g(r, "Mingguan Terkirim")),
            "Laporan Bulanan (jumlah/target)": rasio(g(r, "Bulanan Terkirim"), g(r, "Bulanan Due")),
            "Waktu Tunggu Reviu Laporan Bulanan": angka(g(r, "Rata2 Hari Verif Bulanan")),
            "Reviu Laporan Bulanan (direviu/submit)": rasio(g(r, "Bulanan Sudah Direviu"), g(r, "Bulanan Terkirim")),
            "Status Unggah Laporan 50%": KIRIM.get(g(r, "Laporan 50% - Status Kirim"), g(r, "Laporan 50% - Status Kirim")),
            "Waktu Tunggu Reviu Laporan 50%": angka(g(r, "Hari Verif 50%")),
            "Reviu Laporan 50%": REVIU_LAP.get(g(r, "Laporan 50% - Status Reviu"), g(r, "Laporan 50% - Status Reviu")),
            "Status Unggah Laporan 100%": KIRIM.get(g(r, "Laporan 100% - Status Kirim"), g(r, "Laporan 100% - Status Kirim")),
            "Waktu Tunggu Reviu Laporan 100%": angka(g(r, "Hari Verif 100%")),
            "Reviu Laporan 100%": REVIU_LAP.get(g(r, "Laporan 100% - Status Reviu"), g(r, "Laporan 100% - Status Reviu")),
        }
        # BKU / BPP: diisi hanya bila export sudah punya kolomnya
        for k in ("BKU", "BPP"):
            for nama in (f"{k} - Status Kirim", k):
                if nama in r:
                    x[k] = KIRIM.get(g(r, nama), g(r, nama))
                    break
        out[n] = x
    return out


# ---------- rencana ----------

@dataclass
class Rencana:
    token: str
    week: int
    nama_file: str
    dibuat: float
    judul: list[str]                      # judul baris 3 kolom A..terakhir komponen
    baris: list[list[Any]]                # isi baru A4.. (identitas + komponen), urut seperti di sheet
    tambah: list[list[Any]]               # sekolah baru (belum ada di WEEK)
    ringkasan: dict[str, Any] = field(default_factory=dict)


_rencana: dict[str, Rencana] = {}
_lock = threading.Lock()
_status: dict[str, Any] = {"jalan": False, "langkah": "", "persen": 0, "hasil": None, "error": ""}

NOMOR_TETAP = ("No HP Fasilitator", "No HP Koordinator", "No HP Kepala Sekolah")
IDENTITAS_ISI = ("Nama Sekolah", "Angkatan", "Provinsi", "Kab/Kota", "Nama Kepala Sekolah", "PTN", "Koordinator",
                 "Fasilitator")


def _sama(a: Any, b: Any) -> bool:
    """Bandingkan nilai sel lama dan baru (0.5 == '0.5', 4 == 4.0)."""
    if str(a).strip() == str(b).strip():
        return True
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def siapkan(data: bytes, nama_file: str, week: int) -> Rencana:
    df = baca(data, nama_file)
    baru = olah(df)
    if not baru:
        raise CutoffError("File tidak berisi NPSN.")
    t = lk_baru.tata(week, refresh=True)
    akhir = max(t.komponen.values()) + 1
    for i in t.tunggu.values():
        akhir = max(akhir, i + 1)
    tab = lk_baru.tab_week(week)
    ss = lk_baru._ss()
    judul = ss.values_get(f"'{tab}'!A3:{col_letter(akhir - 1)}3").get("values", [[]])[0]
    judul += [""] * (akhir - len(judul))
    # Judul komponen di LK bisa saja nama alternatif (mis. "Submit Laporan Pendahuluan"); pakai nama baku agar cocok
    # dengan kunci hasil export.
    judul = [k.judul if (k := komponen_dari_judul(h)) else h for h in judul]
    lama = ss.values_get(f"'{tab}'!A{BARIS_DATA}:{col_letter(akhir - 1)}",
                         params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
    i_npsn = t.identitas["npsn"]
    out, ada = [], set()
    berubah = Counter()
    naik = Counter()
    for r in lama:
        r = list(r) + [""] * (akhir - len(r))
        n = npsn(r[i_npsn])
        x = baru.get(n)
        if n:
            ada.add(n)
        if x:
            for j, h in enumerate(judul):
                if h not in x or h in ("PIC", "NPSN"):
                    continue
                v = x[h]
                if h in NOMOR_TETAP and (not v or str(r[j]).strip()):
                    continue  # nomor di LK (dari MASTER / Penugasan) lebih bisa dipercaya; export hanya mengisi yang kosong
                if h in IDENTITAS_ISI and not v:
                    continue  # export kosong (mis. sekolah baru): data yang sudah ada tidak dihapus
                if not _sama(r[j], v):
                    berubah[h] += 1
                    k = komponen_dari_judul(h)
                    if k and todo.status(k.kode, v).status == "selesai" and todo.status(k.kode, r[j]).status != "selesai":
                        naik[k.label] += 1
                r[j] = v
        out.append(r)
    tambah = []
    for n, x in baru.items():
        if n in ada:
            continue
        r: list[Any] = [""] * akhir
        r[i_npsn] = n
        for j, h in enumerate(judul):
            if h in x:
                r[j] = x[h]
        tambah.append(r)
    hilang = len([n for n in ada if n not in baru])
    rc = Rencana(token=secrets.token_urlsafe(12), week=week, nama_file=nama_file, dibuat=time.time(), judul=judul,
                 baris=out, tambah=tambah)
    rc.ringkasan = {
        "sekolah_file": len(baru), "sekolah_lk": len(ada), "cocok": len(ada & set(baru)), "baru": len(tambah),
        "tidak_di_file": hilang,
        "berubah": [{"kolom": k, "jumlah": v} for k, v in berubah.most_common()],
        "naik_selesai": [{"komponen": k, "jumlah": v} for k, v in naik.most_common()],
        "bku_bpp": any(k in df.columns for k in ("BKU", "BPP", "BKU - Status Kirim", "BPP - Status Kirim")),
        "tab": lk_baru.tab_week(week),
    }
    with _lock:
        for k in [k for k, v in _rencana.items() if time.time() - v.dibuat > RENCANA_DETIK]:
            _rencana.pop(k, None)
        _rencana[rc.token] = rc
    return rc


def status() -> dict[str, Any]:
    return dict(_status)


def mulai_tulis(token: str, oleh: str) -> None:
    with _lock:
        rc = _rencana.get(token)
        if not rc:
            raise CutoffError("Rencana sudah kedaluwarsa. Unggah file lagi.")
        if _status["jalan"]:
            raise CutoffError("Penulisan cutoff lain masih berjalan.")
        _status.update(jalan=True, langkah="Mulai", persen=0, hasil=None, error="")
    threading.Thread(target=_tulis_aman, args=(rc, oleh), name="cutoff-baru", daemon=True).start()


def _tulis_aman(rc: Rencana, oleh: str) -> None:
    try:
        hasil = tulis(rc, oleh)
        _status.update(hasil=hasil, persen=100, langkah="Selesai")
        with _lock:
            _rencana.pop(rc.token, None)
    except Exception as e:
        log.exception("Tulis cutoff gagal")
        _status.update(error=str(e))
    finally:
        _status["jalan"] = False


def _langkah(teks: str, persen: int) -> None:
    _status.update(langkah=teks, persen=persen)


def tulis(rc: Rencana, oleh: str) -> dict[str, Any]:
    ss = lk_baru._ss()
    tab = lk_baru.tab_week(rc.week)
    w = ss.worksheet(tab)
    akhir = col_letter(len(rc.judul) - 1)

    _langkah("Memperbarui data sekolah", 10)
    for i in range(0, len(rc.baris), 4000):
        ss.values_update(f"'{tab}'!A{BARIS_DATA + i}:{akhir}{BARIS_DATA + i + len(rc.baris[i:i + 4000]) - 1}",
                         params={"valueInputOption": "RAW"}, body={"values": rc.baris[i:i + 4000]})
    if rc.tambah:
        _langkah(f"Menambahkan {len(rc.tambah)} sekolah baru", 25)
        mulai = BARIS_DATA + len(rc.baris)
        perlu = mulai + len(rc.tambah) + 5
        if w.row_count < perlu:
            w.resize(rows=perlu)
        sid = w.id
        ss.batch_update({"requests": [{"copyPaste": {
            "source": {"sheetId": sid, "startRowIndex": BARIS_DATA - 1, "endRowIndex": BARIS_DATA,
                       "startColumnIndex": 0, "endColumnIndex": w.col_count},
            "destination": {"sheetId": sid, "startRowIndex": mulai - 1, "endRowIndex": mulai - 1 + len(rc.tambah),
                            "startColumnIndex": 0, "endColumnIndex": w.col_count},
            "pasteType": t}} for t in ("PASTE_FORMAT", "PASTE_DATA_VALIDATION")]})
        ss.values_update(f"'{tab}'!A{mulai}:{akhir}{mulai + len(rc.tambah) - 1}", params={"valueInputOption": "RAW"},
                         body={"values": rc.tambah})

    _langkah("Mengurutkan per PIC", 40)
    t = lk_baru.tata(rc.week, refresh=True)
    total = len(rc.baris) + len(rc.tambah)
    ss.batch_update({"requests": [{"sortRange": {
        "range": {"sheetId": w.id, "startRowIndex": BARIS_DATA - 1, "endRowIndex": BARIS_DATA - 1 + total,
                  "startColumnIndex": 0, "endColumnIndex": w.col_count},
        "sortSpecs": [{"dimensionIndex": t.identitas["petugas"], "sortOrder": "ASCENDING"},
                      {"dimensionIndex": t.identitas["nama"], "sortOrder": "ASCENDING"}]}}]})
    cache.clear()

    _langkah("Menulis keterangan otomatis Kendala/Tindak Lanjut", 55)
    siapkan_format(rc.week)
    semua = lk_baru.baca_semua(rc.week, refresh=True)
    n_ket = tulis_keterangan(rc.week, semua)

    _langkah("Mengisi Log Progres", 80)
    label = catat_log_progres(semua)
    catat_log_pic(semua, label)
    _catat_tarik(ss, rc, oleh, total)
    cache.clear()
    return {"tab": tab, "sekolah": total, "baru": len(rc.tambah), "keterangan": n_ket, "cutoff": label}


# ---------- keterangan otomatis ----------

def tulis_keterangan(week: int, semua: list[Sekolah]) -> int:
    """Tulis ulang keterangan otomatis di semua kolom Kendala/TL (per kolom, sekali tulis)."""
    t = lk_baru.tata(week)
    tab = lk_baru.tab_week(week)
    rencana = {s.baris: todo.rencana(s) for s in semua}
    if not semua:
        return 0
    awal, akhir = min(s.baris for s in semua), max(s.baris for s in semua)
    per_baris = {s.baris: s for s in semua}
    data, n = [], 0
    for blok, cols in t.isian.items():
        for kode, (a, c) in cols.items():
            for col, pos in ((a, 0), (c, 1)):
                kolom, ubah = [], False
                for b in range(awal, akhir + 1):
                    s = per_baris.get(b)
                    if not s:
                        kolom.append([""])
                        continue
                    cur = s.isian.get(blok, {}).get(kode, ("", ""))[pos]
                    if not cur or todo.otomatis(cur):
                        baru = rencana[b].keterangan(kode)
                        if baru != cur:
                            ubah, n = True, n + 1
                        cur = baru
                    kolom.append([cur])
                if ubah:
                    data.append({"range": f"'{tab}'!{col_letter(col)}{awal}:{col_letter(col)}{akhir}",
                                 "values": kolom})
    ss = lk_baru._ss()
    for i in range(0, len(data), 6):
        ss.values_batch_update({"valueInputOption": "RAW", "data": data[i:i + 6]})
    return n


def siapkan_format(week: int) -> None:
    """Sekali per tab: keterangan baru masuk daftar dropdown Kendala, dan diberi warna abu-abu miring."""
    ss = lk_baru._ss()
    tab = lk_baru.tab_week(week)
    w = ss.worksheet(tab)
    t = lk_baru.tata(week)
    a0 = min(a for cols in t.isian.values() for a, _ in cols.values())
    a1 = max(c for cols in t.isian.values() for _, c in cols.values())
    meta = ss.fetch_sheet_metadata(params={
        "ranges": f"'{tab}'!{col_letter(a0)}{BARIS_DATA}:{col_letter(a1)}{BARIS_DATA}",
        "fields": "sheets(conditionalFormats,data(rowData(values(dataValidation))))"})
    sh = meta["sheets"][0]
    vals = sh["data"][0]["rowData"][0]["values"]
    req = []
    for cols in t.isian.values():
        for a, _ in cols.values():
            dv = (vals[a - a0] or {}).get("dataValidation")
            if not dv:
                continue
            pilihan = [x.get("userEnteredValue", "") for x in dv["condition"].get("values", [])]
            tambah = [k for k in KETERANGAN_BARU if k not in pilihan]
            if not tambah:
                continue
            dv["condition"]["values"] = [{"userEnteredValue": p} for p in pilihan + tambah]
            req.append({"setDataValidation": {"range": {"sheetId": w.id, "startRowIndex": BARIS_DATA - 1,
                                                        "endRowIndex": w.row_count, "startColumnIndex": a,
                                                        "endColumnIndex": a + 1}, "rule": dv}})
    sudah = any("Menunggu " in str(r) for r in sh.get("conditionalFormats", []))
    if not sudah:
        rng = [{"sheetId": w.id, "startRowIndex": BARIS_DATA - 1, "endRowIndex": w.row_count,
                "startColumnIndex": a0, "endColumnIndex": a1 + 1}]
        abu = {"backgroundColor": {"red": 0.933, "green": 0.941, "blue": 0.957},
               "textFormat": {"foregroundColor": {"red": 0.54, "green": 0.576, "blue": 0.65}, "italic": True}}
        for cond in ({"type": "TEXT_STARTS_WITH", "values": [{"userEnteredValue": "Menunggu "}]},
                     {"type": "TEXT_EQ", "values": [{"userEnteredValue": todo.BERJALAN}]},
                     {"type": "TEXT_EQ", "values": [{"userEnteredValue": todo.TANPA_DATA}]}):
            req.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": rng, "booleanRule": {"condition": cond, "format": abu}}}})
    if req:
        ss.batch_update({"requests": req})


# ---------- Log Progres ----------

def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _pct(a: float, b: float) -> str:
    return f"{_fmt(a)} / {_fmt(b)} ({str(round(a / b * 100, 1)).replace('.', ',')}%)" if b else "-"


def metrik(semua: list[Sekolah]) -> list[str]:
    """Nilai Log Progres, urut sesuai baris di tab Log Progres."""
    st = [todo.semua_status(s) for s in semua]

    def kirim(k: str, rev: str) -> tuple[str, str]:
        due = sum(1 for x in st if x[k].status in ("selesai", "belum"))
        sudah = sum(1 for x in st if x[k].status == "selesai")
        return _pct(sudah, due), _pct(sum(1 for x in st if x[rev].status == "selesai"), sudah)

    def rata(k: str) -> str:
        v = [s.tunggu[k] for s in semua if k in s.tunggu]
        return (str(round(sum(v) / len(v), 1)).replace(".", ",") + " hari") if v else "-"

    def jumlah(k: str) -> str:
        a = sum(x[k].rasio[0] for x in st if x[k].rasio)
        b = sum(x[k].rasio[1] for x in st if x[k].rasio)
        return _pct(a, b)

    prog = [x["progres"].persen for x in st if x["progres"].persen is not None]
    total = len(semua)
    lp, lp_r = kirim("lp", "lp_rev")
    l50, l50_r = kirim("l50", "l50_rev")
    l100, l100_r = kirim("l100", "l100_rev")
    bku = sum(1 for x in st if x["bku"].status == "selesai")
    bpp = sum(1 for x in st if x["bpp"].status == "selesai")
    return [_fmt(total), lp, rata("lp_rev"), lp_r,
            (str(round(sum(prog) / len(prog), 1)).replace(".", ",") + "%") if prog else "-",
            _pct(sum(1 for p in prog if p >= 50), total), _pct(sum(1 for p in prog if p >= 100), total),
            jumlah("mg"), rata("mg_rev"), jumlah("mg_rev"), jumlah("bl"), rata("bl_rev"), jumlah("bl_rev"),
            _pct(bku, total) if bku else "-", _pct(bpp, total) if bpp else "-",
            l50, rata("l50_rev"), l50_r, l100, rata("l100_rev"), l100_r]


def catat_log_progres(semua: list[Sekolah], tanggal: date | None = None) -> str:
    """Isi kolom Cutoff berikutnya di Log Progres; kolom bertanggal sama ditimpa. Mengembalikan labelnya."""
    tgl = (tanggal or schedule.now().date()).strftime("%d/%m")
    ss = lk_baru._ss()
    tab = lk_baru.TAB_LOG_PROGRES
    h2 = ss.values_get(f"'{tab}'!A2:AZ2").get("values", [[]])[0]
    kol = [i for i, x in enumerate(h2) if str(x).startswith("Cutoff")]
    terisi = [i for i in kol if "(" in str(h2[i])]
    if terisi and str(h2[terisi[-1]]).endswith(f"({tgl})"):
        c = terisi[-1]
    else:
        kosong = [i for i in kol if "(" not in str(h2[i])]
        if kosong:
            c = kosong[0]
        else:  # semua kolom terpakai: tambah kolom di kanan
            c = (kol[-1] + 1) if kol else 2
            w = ss.worksheet(tab)
            if w.col_count <= c:
                w.add_cols(c - w.col_count + 4)
    nomor = (kol.index(c) + 1) if c in kol else len(kol) + 1
    label = f"Cutoff {nomor} ({tgl})"
    nilai = metrik(semua)
    L = col_letter(c)
    ss.values_update(f"'{tab}'!{L}2:{L}{2 + len(nilai)}", params={"valueInputOption": "RAW"},
                     body={"values": [[label]] + [[v] for v in nilai]})
    cache.drop("lk2_cutoff_label")
    return label


JUDUL_PIC = ["Cutoff", "PIC", "Sekolah", "Fasil", "Lap. Pendahuluan terkirim (%)", "Lap. Pendahuluan direviu (%)",
             "Progres fisik rata-rata (%)", "Lap. Mingguan lengkap (%)", "Reviu Mingguan (%)",
             "Lap. Bulanan lengkap (%)", "Reviu Bulanan (%)", "Lap. 50% terunggah (%)", "Reviu Lap. 50% (%)",
             "Lap. 100% terunggah (%)", "Sekolah tanpa to-do", "Waktu tunggu reviu rata-rata (hari)"]


def _baris_pic(label: str, pic: str, xs: list[Sekolah]) -> list[Any]:
    st = [todo.semua_status(s) for s in xs]

    def p_kirim(k: str) -> Any:
        due = sum(1 for x in st if x[k].status in ("selesai", "belum"))
        return round(sum(1 for x in st if x[k].status == "selesai") / due * 100, 1) if due else ""

    def p_reviu(rev: str, kirim: str) -> Any:
        sudah = sum(1 for x in st if x[kirim].status == "selesai")
        return round(sum(1 for x in st if x[rev].status == "selesai") / sudah * 100, 1) if sudah else ""

    def p_rasio(k: str) -> Any:
        a = sum(x[k].rasio[0] for x in st if x[k].rasio)
        b = sum(x[k].rasio[1] for x in st if x[k].rasio)
        return round(a / b * 100, 1) if b else ""

    prog = [x["progres"].persen for x in st if x["progres"].persen is not None]
    tunggu = [v for s in xs for v in s.tunggu.values()]
    fasil = {s.fasil for s in xs if s.fasil}
    return [label, pic, len(xs), len(fasil), p_kirim("lp"), p_reviu("lp_rev", "lp"),
            round(sum(prog) / len(prog), 1) if prog else "", p_rasio("mg"), p_rasio("mg_rev"), p_rasio("bl"),
            p_rasio("bl_rev"), p_kirim("l50"), p_reviu("l50_rev", "l50"), p_kirim("l100"),
            sum(1 for s in xs if not todo.rencana(s).todo),
            round(sum(tunggu) / len(tunggu), 1) if tunggu else ""]


def catat_log_pic(semua: list[Sekolah], label: str) -> None:
    """Tab Log Progres PIC: satu baris per PIC per cutoff (baris cutoff yang sama diganti)."""
    ss = lk_baru._ss()
    judul = [w.title for w in ss.worksheets()]
    if TAB_PIC not in judul:
        w = ss.add_worksheet(TAB_PIC, rows=500, cols=len(JUDUL_PIC))
        ss.values_update(f"'{TAB_PIC}'!A1", params={"valueInputOption": "RAW"}, body={"values": [JUDUL_PIC]})
        ss.batch_update({"requests": [
            {"repeatCell": {"range": {"sheetId": w.id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                                           "backgroundColor": {"red": 0.137, "green": 0.275, "blue": 0.627},
                                                           "wrapStrategy": "WRAP"}},
                            "fields": "userEnteredFormat"}},
            {"repeatCell": {"range": {"sheetId": w.id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": {
                                "red": 1, "green": 1, "blue": 1}}}}, "fields": "userEnteredFormat.textFormat"}},
            {"updateSheetProperties": {"properties": {"sheetId": w.id, "gridProperties": {"frozenRowCount": 1}},
                                       "fields": "gridProperties.frozenRowCount"}}]})
    lama = ss.values_get(f"'{TAB_PIC}'!A2:{col_letter(len(JUDUL_PIC) - 1)}").get("values", [])
    sisa = [r for r in lama if r and r[0] != label]
    per: dict[str, list[Sekolah]] = defaultdict(list)
    for s in semua:
        per[clean_petugas(s.petugas) or "(tanpa PIC)"].append(s)
    baru = [_baris_pic(label, p, xs) for p, xs in sorted(per.items(), key=lambda x: x[0].casefold())]
    semua_baris = sisa + baru
    w = ss.worksheet(TAB_PIC)
    if w.row_count < len(semua_baris) + 2:
        w.add_rows(len(semua_baris) + 50 - w.row_count)
    ss.values_batch_clear(body={"ranges": [f"'{TAB_PIC}'!A2:{col_letter(len(JUDUL_PIC) - 1)}"]})
    ss.values_update(f"'{TAB_PIC}'!A2", params={"valueInputOption": "RAW"}, body={"values": semua_baris})


def baca_log_pic() -> list[dict[str, Any]]:
    def load() -> list[dict[str, Any]]:
        try:
            v = lk_baru._ss().values_get(f"'{TAB_PIC}'!A1:{col_letter(len(JUDUL_PIC) - 1)}",
                                         params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
        except Exception:
            return []
        if not v:
            return []
        h = v[0]
        return [dict(zip(h, list(r) + [""] * (len(h) - len(r)))) for r in v[1:] if r]

    return cache.get("lk2_logpic", 600, load)


def baca_log_progres() -> dict[str, Any]:
    def load() -> dict[str, Any]:
        v = lk_baru._ss().values_get(f"'{lk_baru.TAB_LOG_PROGRES}'!A2:AZ30").get("values", [])
        if not v:
            return {"cutoff": [], "baris": []}
        h = v[0]
        kol = [i for i, x in enumerate(h) if str(x).startswith("Cutoff") and "(" in str(x)]
        baris, kel = [], ""
        for r in v[1:]:
            if len(r) < 2 or not str(r[1]).strip():
                continue
            kel = str(r[0]).strip() or kel
            baris.append({"kelompok": kel, "komponen": str(r[1]),
                          "nilai": [str(r[i]) if i < len(r) else "" for i in kol]})
        return {"cutoff": [str(h[i]) for i in kol], "baris": baris}

    return cache.get("lk2_logprogres", 600, load)


def _catat_tarik(ss, rc: Rencana, oleh: str, total: int) -> None:
    judul = [w.title for w in ss.worksheets()]
    if TAB_LOG not in judul:
        w = ss.add_worksheet(TAB_LOG, rows=200, cols=6)
        ss.values_update(f"'{TAB_LOG}'!A1", params={"valueInputOption": "RAW"},
                         body={"values": [["Waktu", "Week", "File", "Sekolah", "Baru", "Oleh"]]})
        ss.batch_update({"requests": [{"updateSheetProperties": {"properties": {"sheetId": w.id, "hidden": True},
                                                                 "fields": "hidden"}}]})
    ss.values_append(f"'{TAB_LOG}'!A1", params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                     body={"values": [[schedule.now().strftime("%Y-%m-%d %H:%M"), f"WEEK {rc.week}", rc.nama_file,
                                       total, len(rc.tambah), oleh]]})


def riwayat() -> list[dict[str, Any]]:
    try:
        v = lk_baru._ss().values_get(f"'{TAB_LOG}'!A2:F").get("values", [])
    except Exception:
        return []
    out = [{"waktu": r[0], "week": r[1] if len(r) > 1 else "", "file": r[2] if len(r) > 2 else "",
            "sekolah": r[3] if len(r) > 3 else "", "baru": r[4] if len(r) > 4 else "", "oleh": r[5] if len(r) > 5 else ""}
           for r in v if r]
    return list(reversed(out))[:30]


# ---------- WEEK baru ----------

HARI = ("Sen", "Sel", "Rab", "Kam", "Jum")
BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def buat_week(senin: date) -> dict[str, Any]:
    """Salin WEEK terakhir jadi WEEK n+1 (isian petugas dikosongkan, keterangan otomatis ditulis ulang),
    dan tambahkan 5 kolom tanggal (Senin–Jumat) di Log Komunikasi."""
    if senin.weekday() != 0:
        raise CutoffError("Tanggal awal WEEK harus hari Senin.")
    ss = lk_baru._ss()
    n = lk_baru.week_aktif()
    lama = ss.worksheet(lk_baru.tab_week(n))
    baru_nama = lk_baru.tab_week(n + 1)
    if baru_nama in [w.title for w in ss.worksheets()]:
        raise CutoffError(f"{baru_nama} sudah ada.")
    ss.batch_update({"requests": [{"duplicateSheet": {"sourceSheetId": lama.id, "insertSheetIndex": 0,
                                                      "newSheetName": baru_nama}}]})
    cache.clear()
    t = lk_baru.tata(n + 1, refresh=True)
    a0 = min(a for cols in t.isian.values() for a, _ in cols.values())
    a1 = max(c for cols in t.isian.values() for _, c in cols.values())
    w = ss.worksheet(baru_nama)
    ss.values_batch_clear(body={"ranges": [f"'{baru_nama}'!{col_letter(a0)}{BARIS_DATA}:{col_letter(a1)}{w.row_count}"]})
    cache.clear()
    semua = lk_baru.baca_semua(n + 1, refresh=True)
    tulis_keterangan(n + 1, semua)
    tanggal = _tambah_tanggal_log(ss, n + 1, senin)
    cache.clear()
    return {"tab": baru_nama, "tanggal": tanggal}


def _tambah_tanggal_log(ss, week: int, senin: date) -> list[str]:
    tab = lk_baru.TAB_LOG_KOM
    w = ss.worksheet(tab)
    h2 = ss.values_get(f"'{tab}'!A2:AZ2").get("values", [[]])[0]
    tgl = [i for i, x in enumerate(h2) if i >= 4 and re.search(r"\d{1,2}/\d{1,2}", str(x))]
    if not tgl:
        raise CutoffError("Kolom tanggal di Log Komunikasi tidak ketemu.")
    akhir = tgl[-1]
    hari = [senin + timedelta(days=i) for i in range(5)]
    if any(f"{d:%d/%m}" in str(x) for x in h2 for d in hari):
        return [d.isoformat() for d in hari]
    ss.batch_update({"requests": [
        {"insertDimension": {"range": {"sheetId": w.id, "dimension": "COLUMNS", "startIndex": akhir + 1,
                                       "endIndex": akhir + 6}, "inheritFromBefore": True}},
        {"copyPaste": {"source": {"sheetId": w.id, "startRowIndex": 0, "endRowIndex": w.row_count,
                                  "startColumnIndex": akhir - 4, "endColumnIndex": akhir + 1},
                       "destination": {"sheetId": w.id, "startRowIndex": 0, "endRowIndex": w.row_count,
                                       "startColumnIndex": akhir + 1, "endColumnIndex": akhir + 6},
                       "pasteType": "PASTE_FORMAT"}},
        {"copyPaste": {"source": {"sheetId": w.id, "startRowIndex": 2, "endRowIndex": w.row_count,
                                  "startColumnIndex": akhir - 4, "endColumnIndex": akhir + 1},
                       "destination": {"sheetId": w.id, "startRowIndex": 2, "endRowIndex": w.row_count,
                                       "startColumnIndex": akhir + 1, "endColumnIndex": akhir + 6},
                       "pasteType": "PASTE_DATA_VALIDATION"}},
    ]})
    jumat = hari[-1]
    judul = f"WEEK {week} · {senin.day}–{jumat.day} {BULAN[jumat.month - 1]} {jumat.year}"
    L0, L1 = col_letter(akhir + 1), col_letter(akhir + 5)
    ss.values_batch_update({"valueInputOption": "RAW", "data": [
        {"range": f"'{tab}'!{L0}1", "values": [[judul]]},
        {"range": f"'{tab}'!{L0}2:{L1}2", "values": [[f"{HARI[i]} {d:%d/%m}" for i, d in enumerate(hari)]]},
    ]})
    return [d.isoformat() for d in hari]


def senin_berikutnya() -> date:
    """Usulan Senin untuk WEEK baru: Senin setelah tanggal terakhir di Log Komunikasi."""
    try:
        lk = lk_baru.baca_log_kom(refresh=True)
        if lk.tanggal:
            akhir = date.fromisoformat(max(lk.tanggal))
            return akhir + timedelta(days=7 - akhir.weekday())
    except Exception:
        pass
    d = schedule.now().date()
    return d + timedelta(days=7 - d.weekday())

