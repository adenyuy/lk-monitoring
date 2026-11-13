"""Kolom "Bimtek Pelaporan" di LK (mis. "Bimtek Lap 1"), diisi dari sheet daftar bimtek.

Sekolah peserta bimtek pelaporan (diundang offline untuk mendorong dokumen) dibagi per kelompok. Daftarnya berkolom
NPSN dan Tag (atau "Bimtek Pelaporan"), dari link Google Sheet ATAU file CSV/Excel yang diunggah. Seperti PIC sekolah
baru: admin memasukkannya di halaman Tarik Cutoff, aplikasi mencocokkan per NPSN lalu hanya menulis kolom Bimtek
Pelaporan di tab WEEK aktif. Bawaannya hanya sel yang kosong; nilai yang berbeda diganti hanya bila diminta. Setiap
cutoff, sekolah baru ikut diisi dari sumber terakhir (link dibaca ulang; isi file disimpan di laptop).

Bila tab WEEK belum punya kolomnya, kolom disisipkan di bagian Informasi Sekolah (setelah Angkatan). Aplikasi
mencari kolom lewat judul, jadi kolom yang disisipkan tidak menggeser apa pun. Fitur ini kelanjutan bimtek.py lama
(penanda percepatan laporan 50%) tetapi terpisah.
"""

import csv
import io
import json
import logging
import re
from collections import Counter
from typing import Any

from . import db, lk_baru, paths
from .google_auth import gspread_client, id_sheet
from .sheets import cache, col_letter

log = logging.getLogger(__name__)

KUNCI_LINK = "link_bimtek_pelaporan"
KUNCI_SUMBER = "sumber_bimtek_pelaporan"  # "link" | "file"
MAKS_BYTE = 20 * 1024 * 1024
_JUDUL_NPSN = ("npsn",)
_JUDUL_TAG = ("bimtek pelaporan", "bimtek", "tag")


class BimtekLapError(ValueError):
    """Pesannya untuk pengguna."""


def _rapi(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def _npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", _rapi(v))


def urut(nama: str) -> tuple[int, str]:
    """'Bimtek Lap 2' sebelum 'Bimtek Lap 10'."""
    m = re.search(r"(\d+)", nama)
    return (int(m.group(1)) if m else 10**6, nama.casefold())


def cari_kolom(baris: list[list[Any]]) -> tuple[int, int, int] | None:
    """(indeks baris judul, kolom NPSN, kolom Tag) dari beberapa baris teratas sebuah tab."""
    for i, r in enumerate(baris):
        judul = [_rapi(x).casefold() for x in r]
        n = next((j for j, h in enumerate(judul) if h in _JUDUL_NPSN), None)
        if n is None:
            continue
        for kunci in _JUDUL_TAG:
            a = next((j for j, h in enumerate(judul) if h == kunci), None)
            if a is not None:
                return i, n, a
    return None


def peta_dari_nilai(nilai: list[list[Any]], kn: int, kt: int) -> dict[str, str]:
    """{npsn: tag} dari baris data (kolom mulai min(kn, kt))."""
    a0 = min(kn, kt)
    lebar = max(kn, kt) - a0 + 1
    out: dict[str, str] = {}
    for r in nilai:
        r = list(r) + [""] * (lebar - len(r))
        n, tag = _npsn(r[kn - a0]), _rapi(r[kt - a0])
        if n and tag:
            out[n] = tag
    return out


def baca_daftar(link: str) -> tuple[str, str, dict[str, str]]:
    """(judul file, nama tab, {npsn: kelompok bimtek}) dari tab terlengkap di sheet daftar bimtek."""
    sid = id_sheet(link)
    if not sid:
        raise BimtekLapError("Link sheet tidak valid. Salin link Google Sheets-nya dari address bar.")
    try:
        ss = gspread_client().open_by_key(sid)
    except Exception as e:
        raise BimtekLapError("Sheet tidak bisa dibuka. Pastikan akun Google kamu punya akses ke sheet itu.") from e
    terbaik: tuple[str, dict[str, str]] | None = None
    for w in ss.worksheets():
        try:
            atas = w.get_values("A1:Z6")
        except Exception:
            continue
        pos = cari_kolom(atas)
        if not pos:
            continue
        i, kn, kt = pos
        nilai = w.get_values(f"{col_letter(min(kn, kt))}{i + 2}:{col_letter(max(kn, kt))}")
        peta = peta_dari_nilai(nilai, kn, kt)
        if peta and (terbaik is None or len(peta) > len(terbaik[1])):
            terbaik = (w.title, peta)
    if not terbaik:
        raise BimtekLapError("Tidak ada tab dengan kolom NPSN dan Tag (atau Bimtek Pelaporan) di sheet ini.")
    return ss.title, terbaik[0], terbaik[1]


def _tabel_terbaik(nama: str, tabel: list[tuple[str, list[list[Any]]]]) -> tuple[str, str, dict[str, str]]:
    terbaik: tuple[str, dict[str, str]] | None = None
    for judul, baris in tabel:
        pos = cari_kolom(baris[:6])
        if not pos:
            continue
        i, kn, kt = pos
        a0 = min(kn, kt)
        peta = peta_dari_nilai([list(r)[a0:] for r in baris[i + 1:]], kn, kt)
        if peta and (terbaik is None or len(peta) > len(terbaik[1])):
            terbaik = (judul, peta)
    if not terbaik:
        raise BimtekLapError("File tidak punya kolom NPSN dan Tag (atau Bimtek Pelaporan) di baris judul.")
    return nama, terbaik[0], terbaik[1]


def _bisa(data: bytes, enc: str) -> bool:
    try:
        data.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def baca_file(data: bytes, nama: str) -> tuple[str, str, dict[str, str]]:
    """(nama file, nama sheet/"CSV", {npsn: kelompok}) dari CSV (pemisah ; , atau tab) atau Excel (.xlsx)."""
    if len(data) > MAKS_BYTE:
        raise BimtekLapError("File terlalu besar (maks 20 MB).")
    low = nama.lower()
    if low.endswith((".xlsx", ".xlsm")):
        import openpyxl

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            raise BimtekLapError(f"File Excel tidak bisa dibuka: {e}") from e
        return _tabel_terbaik(nama, [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)])
                                     for ws in wb.worksheets])
    if not low.endswith((".csv", ".txt", ".tsv")):
        raise BimtekLapError("File harus CSV atau Excel (.xlsx).")
    enc = "utf-8-sig" if _bisa(data, "utf-8-sig") else "cp1252"
    teks = data.decode(enc, errors="replace")
    contoh = teks[:4096]
    pisah = max((";", ",", "\t"), key=contoh.count)
    return _tabel_terbaik(nama, [("CSV", list(csv.reader(io.StringIO(teks), delimiter=pisah)))])


def _berkas_simpan():
    return paths.DATA_DIR / "bimtek_pelaporan.json"


def simpan_file(nama: str, tab: str, peta: dict[str, str]) -> None:
    """Isi file terakhir disimpan supaya cutoff berikutnya bisa mengisi sekolah baru tanpa unggah ulang."""
    _berkas_simpan().write_text(json.dumps({"nama": nama, "tab": tab, "peta": peta}), encoding="utf-8")
    db.set_setting(KUNCI_SUMBER, "file")


def file_tersimpan() -> tuple[str, str, dict[str, str]] | None:
    try:
        x = json.loads(_berkas_simpan().read_text(encoding="utf-8"))
        return x["nama"], x["tab"], dict(x["peta"])
    except (OSError, ValueError, KeyError):
        return None


# ---------- kolom di tab WEEK ----------

def ada_kolom(week: int) -> bool:
    return "bimtek" in lk_baru.tata(week).identitas


def pastikan_kolom(week: int) -> bool:
    """Sisipkan kolom Bimtek Pelaporan setelah Angkatan bila belum ada. True bila baru disisipkan."""
    t = lk_baru.tata(week, refresh=True)
    if "bimtek" in t.identitas:
        return False
    ss = lk_baru._ss()
    tab = lk_baru.tab_week(week)
    w = ss.worksheet(tab)
    j = t.identitas["angkatan"] + 1
    ss.batch_update({"requests": [{"insertDimension": {
        "range": {"sheetId": w.id, "dimension": "COLUMNS", "startIndex": j, "endIndex": j + 1},
        "inheritFromBefore": True}}]})
    ss.values_update(f"'{tab}'!{col_letter(j)}3", params={"valueInputOption": "RAW"},
                     body={"values": [[lk_baru.JUDUL_BIMTEK]]})
    cache.clear()
    log.info("Kolom %s disisipkan di %s kolom %s", lk_baru.JUDUL_BIMTEK, tab, col_letter(j))
    return True


# ---------- rencana & tulis ----------

def bandingkan(sekolah: list[lk_baru.Sekolah], peta: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """isi = kolom kosong & ada di sheet; beda = nilai di LK berbeda; tanpa = kosong & tidak ada di sheet."""
    isi, beda, tanpa = [], [], []
    for s in sekolah:
        baru = peta.get(s.npsn, "")
        lama = s.bimtek.strip()
        if not lama:
            if baru:
                isi.append({"npsn": s.npsn, "nama": s.nama, "baris": s.baris, "bimtek": baru})
        elif baru and baru.casefold() != lama.casefold():
            beda.append({"npsn": s.npsn, "nama": s.nama, "baris": s.baris, "bimtek": baru, "bimtek_lama": lama})
    di_lk = {s.npsn for s in sekolah}
    for n in peta:
        if n not in di_lk:
            tanpa.append({"npsn": n, "bimtek": peta[n]})
    return {"isi": isi, "beda": beda, "tanpa": tanpa}


def rencana(link: str, ganti_beda: bool = False, week: int | None = None) -> dict[str, Any]:
    """Bandingkan kolom Bimtek Pelaporan di LK WEEK aktif dengan sheet, tanpa menulis apa pun."""
    return rencana_dari(baca_daftar(link), ganti_beda, week)


def rencana_file(data: bytes, nama: str, ganti_beda: bool = False) -> dict[str, Any]:
    return rencana_dari(baca_file(data, nama), ganti_beda)


def rencana_dari(sumber: tuple[str, str, dict[str, str]], ganti_beda: bool = False,
                 week: int | None = None) -> dict[str, Any]:
    judul, tab, peta = sumber
    week = week or lk_baru.week_aktif()
    sekolah = lk_baru.baca_semua(week, refresh=True)
    b = bandingkan(sekolah, peta)
    tulis_ = b["isi"] + (b["beda"] if ganti_beda else [])
    return {
        "file": judul, "tab": tab, "week": week, "lk_tab": lk_baru.tab_week(week), "sheet_sekolah": len(peta),
        "ada_kolom": ada_kolom(week), **b,
        # sekolah peserta di sheet yang tidak ada di LK (mis. belum masuk cutoff) -> hanya diinfokan
        "per_bimtek": [{"bimtek": k, "jumlah": v}
                       for k, v in sorted(Counter(peta.values()).items(), key=lambda x: urut(x[0]))],
        "akan_ditulis": len(tulis_),
    }


def tulis(link: str, ganti_beda: bool = False, week: int | None = None) -> dict[str, Any]:
    out = tulis_dari(baca_daftar(link), ganti_beda, week)
    db.set_setting(KUNCI_LINK, link)
    db.set_setting(KUNCI_SUMBER, "link")
    return out


def tulis_file(data: bytes, nama: str, ganti_beda: bool = False) -> dict[str, Any]:
    sumber = baca_file(data, nama)
    out = tulis_dari(sumber, ganti_beda)
    simpan_file(*sumber)
    return out


def tulis_dari(sumber: tuple[str, str, dict[str, str]], ganti_beda: bool = False,
               week: int | None = None) -> dict[str, Any]:
    week = week or lk_baru.week_aktif()
    kolom_baru = pastikan_kolom(week)
    rc = rencana_dari(sumber, ganti_beda, week)
    data = rc["isi"] + (rc["beda"] if ganti_beda else [])
    if data:
        t = lk_baru.tata(week, refresh=True)
        kol = col_letter(t.identitas["bimtek"])
        ss = lk_baru._ss()
        isi = [{"range": f"'{rc['lk_tab']}'!{kol}{x['baris']}", "values": [[x["bimtek"]]]} for x in data]
        for i in range(0, len(isi), 500):
            ss.values_batch_update({"valueInputOption": "RAW", "data": isi[i:i + 500]})
        cache.clear()
    return {"ditulis": len(data), "diisi": len(rc["isi"]), "diganti": len(rc["beda"]) if ganti_beda else 0,
            "tanpa": len(rc["tanpa"]), "lk_tab": rc["lk_tab"], "kolom_baru": kolom_baru}


def isi_otomatis(week: int) -> dict[str, Any] | None:
    """Saat cutoff: isi sekolah yang kolomnya kosong dari sumber terakhir (link atau file). None bila belum ada."""
    if sumber_terakhir() == "file":
        sumber = file_tersimpan()
        return tulis_dari(sumber, False, week) if sumber else None
    link = db.get_setting(KUNCI_LINK, "") or ""
    if not link:
        return None
    return tulis_dari(baca_daftar(link), False, week)


def sumber_terakhir() -> str:
    """'link', 'file', atau '' (belum pernah)."""
    s = db.get_setting(KUNCI_SUMBER, "") or ""
    return s or ("link" if db.get_setting(KUNCI_LINK, "") else "")


def ringkas() -> dict[str, Any]:
    """Untuk kartu di halaman Tarik Cutoff."""
    week = lk_baru.week_aktif()
    sekolah = lk_baru.baca_semua(week)
    per = Counter(s.bimtek for s in sekolah if s.bimtek)
    return {"ada_kolom": ada_kolom(week), "terisi": sum(per.values()), "sekolah": len(sekolah),
            "per_bimtek": [{"bimtek": k, "jumlah": v} for k, v in sorted(per.items(), key=lambda x: urut(x[0]))],
            "link": db.get_setting(KUNCI_LINK, "") or "", "sumber": sumber_terakhir(),
            "file": f[0] if (f := file_tersimpan()) else ""}


def pilihan(sekolah: list[lk_baru.Sekolah]) -> list[str]:
    return sorted({s.bimtek for s in sekolah if s.bimtek}, key=urut)


def cocok(s: lk_baru.Sekolah, bimtek: str) -> bool:
    """Filter: '' = semua, '-' = bukan peserta, selain itu nama kelompok."""
    if not bimtek:
        return True
    if bimtek == "-":
        return not s.bimtek
    return s.bimtek.casefold() == bimtek.casefold()
