"""
Tarik data cutoff (CSV/Excel dari aplikasi) ke sheet WEEK di Google Sheets.

  Mingguan (Baseline) : isi J, K, L
  Harian              : isi M, N, O + Prioritas (H)

Kolom file cutoff (urutan tetap, sama seperti sheet CUTOFF):
  A NPSN | B Nama Sekolah | C Jenis Laporan | D Periode Ke | E Capaian (%) | F Sudah Submit | G Sudah Review | ...

Cara pakai:
  python tarik.py                                  # mode tanya-jawab (dipakai tarik.bat)
  python tarik.py --mode harian --week 1           # pakai file terbaru di folder data/
  python tarik.py --mode mingguan --week 1 --file "data/cutoff.xlsx"
  python tarik.py --cek-koneksi                    # cuma cek login & akses sheet
  python tarik.py ... --dry-run                    # hitung saja, tidak menulis ke sheet
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import gspread
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ---------- Pengaturan ----------
BASE = Path(__file__).resolve().parent
SPREADSHEET_ID = "ID_SHEET_LK"
CREDENTIALS_FILE = BASE / "credentials.json"
TOKEN_FILE = BASE / "token.json"
DATA_DIR = BASE / "data"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

WEEK_PREFIX = "WEEK "
WEEK_FIRST_ROW = 3
COL_NPSN = "C"
COL_PRIORITAS = "H"
KOLOM = {
    "mingguan": {"mulai": "J", "akhir": "L", "label": "Mingguan (Baseline)"},  # J progress, K submit, L reviu
    "harian":   {"mulai": "M", "akhir": "O", "label": "Harian"},               # M progress, N submit, O reviu
}

# Posisi kolom di file cutoff (0 = A)
CUT_NPSN, CUT_JENIS, CUT_CAPAIAN, CUT_SUBMIT, CUT_REVIU = 0, 2, 4, 5, 6
JENIS_MINGGUAN = "laporan mingguan"
JENIS_50 = "laporan 50%"


# ---------- Login Google ----------
def login() -> gspread.Client:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds or not creds.valid:
            if not CREDENTIALS_FILE.exists():
                sys.exit(f"File {CREDENTIALS_FILE.name} tidak ada di folder {BASE}.")
            print("Browser akan terbuka untuk login Google (cukup sekali)...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return gspread.authorize(creds)


# ---------- Baca file cutoff ----------
def cari_file_terbaru(wajib: bool = True) -> Path | None:
    files = [p for p in DATA_DIR.glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    files = [p for p in files if not p.name.startswith("~$")]  # file sementara Excel
    if not files:
        if not wajib:
            return None
        sys.exit(f"Tidak ada file CSV/Excel di folder {DATA_DIR}. Taruh file cutoff di situ dulu.")
    return max(files, key=lambda p: p.stat().st_mtime)


def baca_cutoff(path: Path) -> pd.DataFrame:
    # Semua dibaca sebagai teks supaya "13.12" tidak berubah jadi tanggal
    if path.suffix.lower() == ".csv":
        df = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(path, dtype=str, keep_default_na=False, sep=None, engine="python", encoding=enc)
                break
            except UnicodeDecodeError:
                continue
    else:
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    if df is None or df.shape[1] < CUT_REVIU + 1:
        sys.exit(f"Format file tidak sesuai: butuh minimal 7 kolom (A-G), ketemu {0 if df is None else df.shape[1]}.")

    header = [str(c).strip().lower() for c in df.columns[: CUT_REVIU + 1]]
    if "npsn" not in header[CUT_NPSN] or "jenis" not in header[CUT_JENIS]:
        print(f"PERINGATAN: header kolom tidak seperti biasa: {header}")
    return df


def ke_capaian(v: str):
    s = str(v).strip()
    if not s:
        return None
    # Tanggal dari Excel (kalau di sumber sudah kebaca tanggal): 2026-12-13 -> 13.12
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return int(m.group(3)) + int(m.group(2)) / 100
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def key_npsn(v) -> str:
    return re.sub(r"\.0+$", "", str(v).strip())


def ya_tidak(v) -> str:
    return "Ya" if str(v).strip().lower() == "ya" else "Tidak"


def olah(df: pd.DataFrame):
    progress, lap50 = {}, {}
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


def prioritas(p, submit, reviu) -> str:
    """
    Prioritas 1: belum submit laporan 50% (progres di bawah atau sudah 50%)
    Prioritas 2: sudah submit, tapi progres fisik belum 50%
    Prioritas 3: sudah submit, progres sudah 50%, belum direviu
    Selesai    : sudah submit, progres sudah 50%, sudah direviu
    """
    if submit != "Ya":
        return "Prioritas 1"
    if p is None or p < 50:
        return "Prioritas 2"
    if reviu != "Ya":
        return "Prioritas 3"
    return "Selesai"


# ---------- Tulis ke Google Sheets ----------
def col_index(letter: str) -> int:
    n = 0
    for ch in letter:
        n = n * 26 + ord(ch) - 64
    return n - 1  # 0-based


def jalankan(mode: str, week_no: str, file: Path, dry_run: bool, tanya: bool, spreadsheet_id: str = SPREADSHEET_ID):
    kol = KOLOM[mode]
    nama_sheet = WEEK_PREFIX + week_no if week_no.isdigit() else week_no

    t0 = time.time()
    print(f"\nMembaca {file.name} ...")
    df = baca_cutoff(file)
    progress, lap50 = olah(df)
    print(f"  {len(df):,} baris | {len(progress):,} sekolah punya Laporan Mingguan | "
          f"{len(lap50):,} sekolah punya Laporan 50%  ({time.time() - t0:.1f} dtk)")

    print("\nMenghubungkan ke Google Sheets ...")
    gc = login()
    ss = gc.open_by_key(spreadsheet_id)
    print(f'  File: "{ss.title}"')
    try:
        ws = ss.worksheet(nama_sheet)
    except gspread.WorksheetNotFound:
        sys.exit(f'Sheet "{nama_sheet}" tidak ditemukan. Buat dulu sheet-nya, lalu jalankan lagi.')

    npsn_rows = ws.get(f"{COL_NPSN}{WEEK_FIRST_ROW}:{COL_NPSN}", major_dimension="COLUMNS")
    npsn_list = [key_npsn(v) for v in (npsn_rows[0] if npsn_rows else [])]
    while npsn_list and not npsn_list[-1]:
        npsn_list.pop()
    n = len(npsn_list)
    if n == 0:
        sys.exit(f'Tidak ada NPSN di kolom {COL_NPSN} sheet "{nama_sheet}".')

    blok, prio = [], []
    for k in npsn_list:
        if not k:
            blok.append(["", "", ""]); prio.append([""])
            continue
        p = progress.get(k)
        sub, rev = lap50.get(k, ("Tidak", "Tidak"))
        blok.append(["" if p is None else round(p / 100, 6), sub, rev])  # kolom progress berformat persen
        prio.append([prioritas(p, sub, rev)])

    # Ringkasan
    tidak_ketemu = sum(1 for k in npsn_list if k and k not in progress)
    print(f'  "{nama_sheet}": {n:,} sekolah, {tidak_ketemu:,} tanpa Laporan Mingguan')
    if mode == "harian":
        hitung = pd.Series([x[0] for x in prio if x[0]]).value_counts()
        for label in ["Prioritas 1", "Prioritas 2", "Prioritas 3", "Selesai"]:
            print(f"    {label:<12}: {int(hitung.get(label, 0)):,}")
    if "10307082" in npsn_list:
        i = npsn_list.index("10307082")
        print(f"  Contoh 10307082 -> {blok[i]}" + (f" {prio[i][0]}" if mode == "harian" else ""))

    kolom_ditulis = f"{kol['mulai']}-{kol['akhir']}" + (f" dan {COL_PRIORITAS}" if mode == "harian" else "")
    if dry_run:
        print("\n[dry-run] Tidak ada yang ditulis ke sheet.")
        return
    if tanya:
        ok = input(f'\nTulis ke "{nama_sheet}" kolom {kolom_ditulis}? Isi lama akan ditimpa. (y/n): ')
        if ok.strip().lower() not in ("y", "ya", "yes"):
            print("Dibatalkan.")
            return

    t1 = time.time()
    akhir = WEEK_FIRST_ROW + n - 1
    data = [{"range": f"'{nama_sheet}'!{kol['mulai']}{WEEK_FIRST_ROW}:{kol['akhir']}{akhir}", "values": blok}]
    if mode == "harian":
        data.append({"range": f"'{nama_sheet}'!{COL_PRIORITAS}{WEEK_FIRST_ROW}:{COL_PRIORITAS}{akhir}", "values": prio})
    ss.values_batch_update({"valueInputOption": "RAW", "data": data})

    # Format persen di kolom progress + catatan waktu update sebagai note di header
    waktu = datetime.now().strftime("%d %b %Y %H:%M")
    ci = col_index(kol["mulai"])
    ss.batch_update({"requests": [{
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": WEEK_FIRST_ROW - 1, "endRowIndex": akhir,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }, {
        "updateCells": {
            "range": {
                "sheetId": ws.id,
                "startRowIndex": WEEK_FIRST_ROW - 2, "endRowIndex": WEEK_FIRST_ROW - 1,
                "startColumnIndex": col_index(kol["mulai"]), "endColumnIndex": col_index(kol["mulai"]) + 1,
            },
            "rows": [{"values": [{"note": f"Update terakhir ({kol['label']}): {waktu}\nsumber: {file.name}"}]}],
            "fields": "note",
        }
    }]})
    print(f'\nSelesai: {n:,} sekolah ditulis ke "{nama_sheet}" kolom {kolom_ditulis} ({time.time() - t1:.1f} dtk).')


# ---------- Mode tanya-jawab ----------
def pilih_file() -> Path | None:
    """Buka jendela 'pilih file' Windows, mulai dari folder Downloads.
    Return None kalau jendela tidak bisa dibuka; keluar kalau user menekan Cancel."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    downloads = Path.home() / "Downloads"
    awal = downloads if downloads.exists() else BASE
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # supaya jendela muncul di depan
    path = filedialog.askopenfilename(
        title="Pilih file cutoff dari aplikasi",
        initialdir=str(awal),
        filetypes=[("File cutoff", "*.xlsx *.xls *.csv"), ("Semua file", "*.*")],
    )
    root.destroy()
    if not path:
        sys.exit("Dibatalkan: tidak ada file yang dipilih.")
    return Path(path)



def tanya_interaktif(file_awal: Path | None = None):
    print("=" * 50)
    print(" Tarik Data Cutoff -> LK Monitoring")
    print("=" * 50)
    if file_awal:
        print(f' File cutoff: "{file_awal.name}"')
        print("-" * 50)
    print(" 1. Harian   (M, N, O + Prioritas)")
    print(" 2. Mingguan (Baseline J, K, L)")
    pilih = input("Pilih [1/2]: ").strip()
    mode = {"1": "harian", "2": "mingguan"}.get(pilih)
    if not mode:
        sys.exit("Pilihan tidak valid.")

    week = input("Week berapa? (contoh: 1): ").strip()
    if not week:
        sys.exit("Week belum diisi.")

    if file_awal:
        file = file_awal
    else:
        print("Pilih file cutoff di jendela yang muncul...")
        file = pilih_file()
        if file is None:
            path = input("Jendela pilih file tidak bisa dibuka. Drag & drop file ke sini, lalu Enter: ")
            file = Path(path.strip().strip('"')) if path.strip() else None
        if file is None:
            sys.exit("Tidak ada file yang dipilih.")
        print(f'File cutoff: "{file.name}"')
    if not file or not file.exists():
        sys.exit(f"File tidak ditemukan: {file}")
    return mode, week, file


def main():
    ap = argparse.ArgumentParser(description="Tarik data cutoff ke sheet WEEK.")
    ap.add_argument("--mode", choices=["harian", "mingguan"])
    ap.add_argument("--week", help="nomor week, misal 1 (sheet 'WEEK 1')")
    ap.add_argument("--file", help="path file CSV/Excel cutoff (default: terbaru di folder data/)")
    ap.add_argument("--dry-run", action="store_true", help="hitung saja, tidak menulis ke sheet")
    ap.add_argument("--cek-koneksi", action="store_true", help="cek login & akses sheet saja")
    ap.add_argument("--spreadsheet", default=SPREADSHEET_ID, help="ID spreadsheet tujuan (default: LK utama)")
    args = ap.parse_args()

    if args.cek_koneksi:
        ss = login().open_by_key(args.spreadsheet)
        print(f'Terhubung ke "{ss.title}". Sheet: {[w.title for w in ss.worksheets()]}')
        return

    if args.mode and args.week:
        file = Path(args.file) if args.file else cari_file_terbaru()
        if not file.exists():
            sys.exit(f"File tidak ditemukan: {file}")
        jalankan(args.mode, args.week, file, args.dry_run, tanya=False, spreadsheet_id=args.spreadsheet)
    else:
        mode, week, file = tanya_interaktif(Path(args.file) if args.file else None)
        jalankan(mode, week, file, args.dry_run, tanya=True, spreadsheet_id=args.spreadsheet)


if __name__ == "__main__":
    main()
