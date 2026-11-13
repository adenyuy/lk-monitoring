"""LK Monitoring Pelaporan (format baru): tab WEEK n, Log Komunikasi, Log Progres.

Tata letak WEEK n (judul 3 baris, data mulai baris 4):
  baris 1  kelompok besar (DATA SEKOLAH, DETAIL & KONTAK, KOMPONEN MONITORING, SESI ... · DIISI PETUGAS)
  baris 2  nama komponen / nama pasangan isian
  baris 3  judul kolom (identitas, komponen, lalu Kendala | Tindak Lanjut per komponen per sesi)
Kolom dicari lewat judul, bukan huruf, supaya admin boleh menyisipkan kolom.

Alamat sheet tidak disimpan di repo: LKM_LK2_SHEET_ID, `lk2` di sheets.json, atau baris `lk_monitoring`
di tab Pengaturan sheet Akses (dipasang admin sekali untuk seluruh tim).
"""

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from . import config, paths
from .sheets import cache, clean_petugas, col_letter, daftar_nomor, gspread_client, normalize_petugas

log = logging.getLogger(__name__)

PREFIX_WEEK = "WEEK "
BARIS_DATA = 4
TAB_LOG_KOM = "Log Komunikasi"
TAB_LOG_PROGRES = "Log Progres"
TAB_PENGATURAN = "Pengaturan"
KUNCI_PENGATURAN = "lk_monitoring"
CACHE_DETIK = 300

IDENTITAS = {
    "PIC": "petugas", "NPSN": "npsn", "Nama Sekolah": "nama", "Angkatan": "angkatan", "Provinsi": "provinsi",
    "Kab/Kota": "kab", "Nama Kepala Sekolah": "kepsek", "No HP Kepala Sekolah": "hp_kepsek", "PTN": "ptn",
    "Koordinator": "koor", "No HP Koordinator": "hp_koor", "Fasilitator": "fasil", "No HP Fasilitator": "hp_fasil",
    "Bimtek Pelaporan": "bimtek",
}
# Kolom identitas yang boleh tidak ada (WEEK lama dibuat sebelum kolomnya ada)
IDENTITAS_OPSIONAL = {"bimtek"}
JUDUL_BIMTEK = "Bimtek Pelaporan"


@dataclass(frozen=True)
class Komponen:
    kode: str
    judul: str          # judul kolom komponen di baris 3
    pasangan: str       # nama pasangan Kendala/Tindak Lanjut di baris 2
    label: str          # nama pendek untuk tampilan
    tahap: str          # pendahuluan | berkala | l50 | l100
    pelaku: str         # sekolah (mengirim/mengunggah) | fasil (mereviu)
    tunggu: str = ""    # judul kolom waktu tunggu reviu (hari)
    alias: tuple[str, ...] = ()  # judul lain yang pernah dipakai di LK (baris 2 / 3)

    def cocok(self, h: str) -> bool:
        """Judul kolom komponen di baris 3 (boleh judul lama/alternatif)."""
        return _kunci(h) in {_kunci(x) for x in (self.judul, *self.alias)}

    def cocok_pasangan(self, h: str) -> bool:
        """Nama pasangan Kendala/Tindak Lanjut di baris 2."""
        return _kunci(h) in {_kunci(x) for x in (self.pasangan, self.judul, *self.alias)}


def _kunci(v: Any) -> str:
    """Pembanding judul: abaikan huruf besar/kecil, spasi ganda, dan spasi di tepi."""
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().casefold()


_IDENTITAS_KUNCI = {_kunci(j): f for j, f in IDENTITAS.items()}


def komponen_dari_judul(h: str) -> "Komponen | None":
    return next((k for k in KOMPONEN if k.cocok(h)), None)


KOMPONEN: tuple[Komponen, ...] = (
    Komponen("lp", "Status Laporan Pendahuluan", "Status Laporan Pendahuluan", "Lap. Pendahuluan", "pendahuluan",
             "sekolah", alias=("Submit Laporan Pendahuluan", "Laporan Pendahuluan")),
    Komponen("lp_rev", "Reviu Laporan Pendahuluan", "Reviu Laporan Pendahuluan", "Reviu Lap. Pendahuluan",
             "pendahuluan", "fasil", "Waktu Tunggu Reviu Laporan Pendahuluan"),
    Komponen("progres", "Progres Fisik (%)", "Progres Fisik (%)", "Progres fisik", "berkala", "sekolah"),
    Komponen("mg", "Laporan Mingguan (jumlah/target)", "Laporan Mingguan (jumlah/target)", "Lap. Mingguan",
             "berkala", "sekolah"),
    Komponen("mg_rev", "Reviu Laporan Mingguan (direviu/submit)", "Reviu Laporan Mingguan", "Reviu Lap. Mingguan",
             "berkala", "fasil", "Waktu Tunggu Reviu Laporan Mingguan"),
    Komponen("bl", "Laporan Bulanan (jumlah/target)", "Laporan Bulanan (jumlah/target)", "Lap. Bulanan",
             "berkala", "sekolah"),
    Komponen("bl_rev", "Reviu Laporan Bulanan (direviu/submit)", "Reviu Laporan Bulanan", "Reviu Lap. Bulanan",
             "berkala", "fasil", "Waktu Tunggu Reviu Laporan Bulanan"),
    Komponen("bku", "BKU", "BKU", "BKU", "berkala", "sekolah"),
    Komponen("bpp", "BPP", "BPP", "BPP", "berkala", "sekolah"),
    Komponen("l50", "Status Unggah Laporan 50%", "Status Unggah Laporan 50%", "Lap. 50%", "l50", "sekolah"),
    Komponen("l50_rev", "Reviu Laporan 50%", "Reviu Laporan 50%", "Reviu Lap. 50%", "l50", "fasil",
             "Waktu Tunggu Reviu Laporan 50%"),
    Komponen("l100", "Status Unggah Laporan 100%", "Status Unggah Laporan 100%", "Lap. 100%", "l100", "sekolah"),
    Komponen("l100_rev", "Reviu Laporan 100%", "Reviu Laporan 100%", "Reviu Lap. 100%", "l100", "fasil",
             "Waktu Tunggu Reviu Laporan 100%"),
)
KOMP = {k.kode: k for k in KOMPONEN}
# Sesi isian bila judul "SESI ..." di baris 1 tidak menyebut hari: (hari pertama, hari terakhir, label), Senin = 0.
SESI_BAWAAN = {1: (0, 2, "Senin–Rabu"), 2: (3, 5, "Kamis–Sabtu")}
_HARI = {"senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "sabtu": 5, "minggu": 6}


def rentang_hari(judul: str) -> tuple[int, int, str] | None:
    """'SESI SENIN – RABU · DIISI PETUGAS' -> (0, 2, 'Senin–Rabu'). None bila tidak ada nama hari."""
    kata = [k for k in re.findall(r"[a-z']+", judul.lower().replace("'", "")) if k in _HARI]
    if not kata:
        return None
    a, b = _HARI[kata[0]], _HARI[kata[-1]]
    label = kata[0].title() if a == b else f"{kata[0].title()}–{kata[-1].title()}"
    return a, max(a, b), label


class LkError(Exception):
    """Pesannya ditampilkan langsung ke pengguna."""


class LinkBelumAda(LkError):
    pass


# ---------- alamat sheet ----------

def _id_dari(nilai: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", nilai or "")
    return m.group(1) if m else (nilai or "").strip()


def _sheets_json() -> dict[str, Any]:
    f = paths.DATA_DIR / "sheets.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (ValueError, OSError):
        return {}


def sheet_id() -> str:
    env = os.environ.get("LKM_LK2_SHEET_ID")
    if env:
        return env
    lokal = _sheets_json().get("lk2")
    if lokal:
        return _id_dari(str(lokal))

    def load() -> str:
        try:
            ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
            baris = ss.values_get(f"'{TAB_PENGATURAN}'!A1:B50").get("values", [])
        except Exception:
            return ""
        for r in baris:
            if len(r) > 1 and str(r[0]).strip().casefold() == KUNCI_PENGATURAN:
                return _id_dari(str(r[1]))
        return ""

    sid = cache.get("lk2_id", 600, load)
    if not sid:
        raise LinkBelumAda("Link LK Monitoring belum dipasang. Admin cukup memasangnya sekali di halaman Admin.")
    return sid


def pasang_link(link: str, untuk_tim: bool) -> str:
    """Simpan link LK di laptop ini; admin juga menulisnya ke tab Pengaturan sheet Akses untuk seluruh tim."""
    sid = _id_dari(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", sid):
        raise LkError("Itu bukan link Google Sheets. Salin link dari address bar sheet LK.")
    try:
        judul = [w.title for w in gspread_client().open_by_key(sid).worksheets()]
    except Exception as e:
        raise LkError(f"Sheet tidak bisa dibuka dengan akun ini: {e}") from e
    if not any(re.fullmatch(r"WEEK \d+", t) for t in judul):
        raise LkError("Sheet ini tidak punya tab WEEK. Pastikan link-nya LK Monitoring Pelaporan.")
    data = _sheets_json()
    data["lk2"] = sid
    paths.ensure_dirs()
    (paths.DATA_DIR / "sheets.json").write_text(json.dumps(data), encoding="utf-8")
    if untuk_tim:
        ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
        if TAB_PENGATURAN not in [w.title for w in ss.worksheets()]:
            ss.add_worksheet(TAB_PENGATURAN, rows=20, cols=3)
            ss.values_update(f"'{TAB_PENGATURAN}'!A1:C1", params={"valueInputOption": "RAW"},
                             body={"values": [["kunci", "nilai", "keterangan"]]})
        baris = ss.values_get(f"'{TAB_PENGATURAN}'!A1:A50").get("values", [])
        n = next((i + 1 for i, r in enumerate(baris) if r and str(r[0]).strip().casefold() == KUNCI_PENGATURAN),
                 len(baris) + 1)
        ss.values_update(f"'{TAB_PENGATURAN}'!A{n}:C{n}", params={"valueInputOption": "RAW"},
                         body={"values": [[KUNCI_PENGATURAN, f"https://docs.google.com/spreadsheets/d/{sid}/edit",
                                           "LK Monitoring Pelaporan (WEEK n, Log Komunikasi, Log Progres)"]]})
    cache.clear()
    return sid


def _ss():
    return gspread_client().open_by_key(sheet_id())


# ---------- WEEK ----------

def daftar_week(refresh: bool = False) -> list[int]:
    def load() -> list[int]:
        out = []
        for w in _ss().worksheets():
            m = re.fullmatch(r"WEEK (\d+)", w.title.strip())
            if m:
                out.append(int(m.group(1)))
        return sorted(out)

    return cache.get("lk2_weeks", CACHE_DETIK, load, refresh)


def week_aktif() -> int:
    weeks = daftar_week()
    if not weeks:
        raise LkError("LK belum punya tab WEEK.")
    return weeks[-1]


def tab_week(week: int) -> str:
    return f"{PREFIX_WEEK}{week}"


@dataclass(frozen=True)
class Tata:
    """Posisi kolom (indeks 0) di tab WEEK, hasil membaca judul."""
    identitas: dict[str, int]
    komponen: dict[str, int]
    tunggu: dict[str, int]
    isian: dict[int, dict[str, tuple[int, int]]]  # {blok: {kode: (kolom Kendala, kolom Tindak Lanjut)}}
    lebar: int
    sesi: dict[int, tuple[int, int, str]] = field(default_factory=dict)  # {blok: (hari awal, hari akhir, label)}

    @property
    def kolom_terakhir(self) -> str:
        return col_letter(self.lebar - 1)


def _rapi(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def parse_tata(r1: list[Any], r2: list[Any], r3: list[Any]) -> Tata:
    n = max(len(r1), len(r2), len(r3))
    r1, r2, r3 = ([_rapi(x) for x in r] + [""] * (n - len(r)) for r in (r1, r2, r3))
    ident: dict[str, int] = {}
    komp: dict[str, int] = {}
    tunggu: dict[str, int] = {}
    sesi = [i for i, x in enumerate(r1) if x.upper().startswith("SESI")]
    awal_isian = sesi[0] if sesi else n
    for i in range(awal_isian):
        h = r3[i]
        f = _IDENTITAS_KUNCI.get(_kunci(h))
        if f and f not in ident:
            ident[f] = i
        for k in KOMPONEN:
            if k.cocok(h) and k.kode not in komp:
                komp[k.kode] = i
            if k.tunggu and _kunci(h) == _kunci(k.tunggu) and k.kode not in tunggu:
                tunggu[k.kode] = i
    hilang = [j for j, f in IDENTITAS.items() if f not in ident and f not in IDENTITAS_OPSIONAL]
    hilang += [k.judul for k in KOMPONEN if k.kode not in komp]
    if len(sesi) < 2:
        hilang.append("judul SESI di baris 1 (dua sesi)")
    isian: dict[int, dict[str, tuple[int, int]]] = {}
    for b, mulai in enumerate(sesi[:2], start=1):
        akhir = sesi[b] if b < len(sesi) else n
        isian[b] = {}
        for k in KOMPONEN:
            j = next((j for j in range(mulai, akhir) if k.cocok_pasangan(r2[j]) and _kunci(r3[j]) == "kendala"), None)
            if j is None or j + 1 >= n or _kunci(r3[j + 1]) != "tindak lanjut":
                hilang.append(f"Kendala/Tindak Lanjut {k.pasangan} (sesi {b})")
                continue
            isian[b][k.kode] = (j, j + 1)
    if hilang:
        raise LkError("Judul kolom LK tidak ketemu: " + "; ".join(hilang[:6])
                      + ". Kemungkinan judulnya diganti; samakan lagi judulnya atau kabari pengembang.")
    lebar = max(max(c) for b in isian.values() for c in b.values()) + 1
    hari = {b: rentang_hari(r1[i]) or SESI_BAWAAN[b] for b, i in enumerate(sesi[:2], start=1)}
    return Tata(ident, komp, tunggu, isian, lebar, hari)


def tata(week: int, refresh: bool = False) -> Tata:
    def load() -> Tata:
        got = _ss().values_get(f"'{tab_week(week)}'!A1:EZ3").get("values", [])
        got += [[]] * (3 - len(got))
        return parse_tata(*got[:3])

    return cache.get(f"lk2_tata:{week}", CACHE_DETIK, load, refresh)


# ---------- sesi isian (mengikuti judul SESI di tab WEEK aktif) ----------

def sesi_hari() -> dict[int, tuple[int, int, str]]:
    try:
        return tata(week_aktif()).sesi or SESI_BAWAAN
    except Exception:  # noqa: BLE001 - LK tidak terbaca: pakai pembagian bawaan
        return SESI_BAWAAN


def blok_untuk(hari: date, sesi: dict[int, tuple[int, int, str]] | None = None) -> int:
    """Sesi untuk tanggal `hari`: sesi yang rentang harinya memuat hari itu; hari sesudah sesi terakhir (mis. Sabtu,
    Minggu) ikut sesi yang paling akhir dimulai."""
    sesi = sesi or sesi_hari()
    wd = hari.weekday()
    for b, (a, z, _) in sorted(sesi.items()):
        if a <= wd <= z:
            return b
    mulai = [b for b, (a, _, _) in sorted(sesi.items()) if a <= wd]
    return mulai[-1] if mulai else min(sesi)


def label_blok(blok: int, sesi: dict[int, tuple[int, int, str]] | None = None) -> str:
    return (sesi or sesi_hari()).get(blok, SESI_BAWAAN.get(blok, (0, 0, f"Sesi {blok}")))[2]


def rentang_blok(hari: date, sesi: dict[int, tuple[int, int, str]] | None = None) -> tuple[date, date]:
    """Tanggal pertama dan terakhir sesi yang memuat `hari` (sesi terakhir berlanjut sampai Minggu)."""
    sesi = sesi or sesi_hari()
    blok = blok_untuk(hari, sesi)
    senin = hari - timedelta(days=hari.weekday())
    urut = sorted(sesi)
    awal = sesi[blok][0]
    lanjut = [sesi[b][0] for b in urut if b > blok]
    akhir = lanjut[0] - 1 if lanjut else 6
    return senin + timedelta(days=awal), senin + timedelta(days=max(awal, akhir))


@dataclass
class Sekolah:
    baris: int
    petugas: str
    npsn: str
    nama: str
    angkatan: str
    provinsi: str
    kab: str
    kepsek: str
    hp_kepsek: str
    ptn: str
    koor: str
    hp_koor: str
    fasil: str
    hp_fasil: str
    bimtek: str = ""                                           # kelompok Bimtek Pelaporan (mis. "Bimtek Lap 1")
    nilai: dict[str, Any] = field(default_factory=dict)       # nilai komponen apa adanya
    tunggu: dict[str, float] = field(default_factory=dict)    # waktu tunggu reviu (hari)
    isian: dict[int, dict[str, tuple[str, str]]] = field(default_factory=dict)

    def nomor_fasil(self) -> list[str]:
        return daftar_nomor(self.hp_fasil)


def _sel(r: list[Any], i: int) -> Any:
    return r[i] if i < len(r) and r[i] is not None else ""


def _teks(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def parse_baris(values: list[list[Any]], t: Tata, baris_awal: list[int]) -> list[Sekolah]:
    """`values[i]` adalah baris sheet `baris_awal[i]` (kolom A ke kanan)."""
    out = []
    for n, r in zip(baris_awal, values):
        npsn = re.sub(r"\.0+$", "", _teks(_sel(r, t.identitas["npsn"])))
        if not npsn:
            continue
        idn = {f: _teks(_sel(r, i)) for f, i in t.identitas.items()}
        idn["npsn"] = npsn
        idn["petugas"] = clean_petugas(idn["petugas"])
        nilai = {k: _sel(r, i) for k, i in t.komponen.items()}
        tunggu = {}
        for k, i in t.tunggu.items():
            v = _sel(r, i)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                tunggu[k] = float(v)
        isian = {b: {k: (_teks(_sel(r, a)), _teks(_sel(r, c))) for k, (a, c) in cols.items()}
                 for b, cols in t.isian.items()}
        out.append(Sekolah(baris=n, **idn, nilai=nilai, tunggu=tunggu, isian=isian))
    return out


def _runs(baris: list[int]) -> list[tuple[int, int]]:
    """[4,5,6,9,10] -> [(4,6),(9,10)]"""
    out: list[tuple[int, int]] = []
    for b in sorted(baris):
        if out and b == out[-1][1] + 1:
            out[-1] = (out[-1][0], b)
        else:
            out.append((b, b))
    return out


def pic_kolom(week: int, refresh: bool = False) -> list[str]:
    """Isi kolom PIC (baris 4 ke bawah)."""
    t = tata(week)

    def load() -> list[str]:
        c = col_letter(t.identitas["petugas"])
        got = _ss().values_get(f"'{tab_week(week)}'!{c}{BARIS_DATA}:{c}").get("values", [])
        return [clean_petugas(r[0]) if r else "" for r in got]

    return cache.get(f"lk2_pic:{week}", CACHE_DETIK, load, refresh)


def daftar_petugas() -> list[dict[str, Any]]:
    hit: dict[str, list] = {}
    for p in pic_kolom(week_aktif()):
        if p:
            k = normalize_petugas(p)
            hit.setdefault(k, [p, 0])[1] += 1
    return sorted(({"nama": v[0], "jumlah_sekolah": v[1]} for v in hit.values()), key=lambda x: x["nama"].casefold())


def baca_petugas(petugas: str, week: int | None = None, refresh: bool = False) -> list[Sekolah]:
    """Sekolah binaan satu petugas (hanya baris miliknya yang diambil dari sheet)."""
    week = week or week_aktif()
    target = normalize_petugas(petugas)

    def load() -> list[Sekolah]:
        t = tata(week, refresh=True)
        pic = pic_kolom(week, refresh=True)
        baris = [BARIS_DATA + i for i, p in enumerate(pic) if p and normalize_petugas(p) == target]
        if not baris:
            return []
        runs = _runs(baris)
        rng = [f"'{tab_week(week)}'!A{a}:{t.kolom_terakhir}{b}" for a, b in runs]
        out: list[Sekolah] = []
        for i in range(0, len(rng), 200):
            got = _ss().values_batch_get(rng[i:i + 200], params={"valueRenderOption": "UNFORMATTED_VALUE"})
            for (a, b), vr in zip(runs[i:i + 200], got.get("valueRanges", [])):
                vals = vr.get("values", [])
                vals += [[]] * (b - a + 1 - len(vals))
                out += parse_baris(vals, t, list(range(a, b + 1)))
        return out

    return cache.get(f"lk2_petugas:{week}:{target}", CACHE_DETIK, load, refresh)


def baca_semua(week: int | None = None, refresh: bool = False) -> list[Sekolah]:
    """Seluruh sekolah (untuk admin / dashboard nasional / cutoff)."""
    week = week or week_aktif()

    def load() -> list[Sekolah]:
        t = tata(week, refresh=True)
        got = _ss().values_get(f"'{tab_week(week)}'!A{BARIS_DATA}:{t.kolom_terakhir}",
                               params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
        return parse_baris(got, t, list(range(BARIS_DATA, BARIS_DATA + len(got))))

    return cache.get(f"lk2_semua:{week}", 600, load, refresh)


def opsi_kendala(week: int | None = None) -> dict[str, list[str]]:
    """Pilihan dropdown Kendala per komponen (dari validasi data baris pertama), tanpa keterangan otomatis."""
    from .todo import OTOMATIS, otomatis

    week = week or week_aktif()
    t = tata(week)

    def load() -> dict[str, list[str]]:
        cols = t.isian[1]
        awal = min(a for a, _ in cols.values())
        akhir = max(c for _, c in cols.values())
        rng = f"'{tab_week(week)}'!{col_letter(awal)}{BARIS_DATA}:{col_letter(akhir)}{BARIS_DATA}"
        meta = _ss().fetch_sheet_metadata(params={"ranges": rng,
                                                  "fields": "sheets(data(rowData(values(dataValidation))))"})
        vals = (((meta.get("sheets") or [{}])[0].get("data") or [{}])[0].get("rowData") or [{}])[0].get("values", [])
        out = {}
        for k, (a, _) in cols.items():
            v = vals[a - awal] if a - awal < len(vals) else {}
            dv = (v or {}).get("dataValidation") or {}
            pilihan = [str(x.get("userEnteredValue", "")).strip() for x in dv.get("condition", {}).get("values", [])]
            out[k] = [p for p in pilihan if p and p not in OTOMATIS and not otomatis(p)]
        return out

    return cache.get(f"lk2_opsi:{week}", 1800, load)


def tulis_isian(week: int, isi: list[tuple[Sekolah, int, str, str, str]], hanya_tl: bool = False) -> None:
    """Tulis Kendala/Tindak Lanjut. `isi` = [(sekolah, blok, kode komponen, kendala, tindak lanjut)].
    `hanya_tl`: hanya kolom Tindak Lanjut yang ditulis (Kendala di sheet tidak disentuh).
    Baris dicek lewat NPSN dulu supaya tidak menulis ke sekolah lain bila urutan sheet berubah."""
    if not isi:
        return
    t = tata(week)
    tab = tab_week(week)
    ss = _ss()
    c_npsn = col_letter(t.identitas["npsn"])
    unik = {s.baris: s for s, *_ in isi}
    cek = ss.values_batch_get([f"'{tab}'!{c_npsn}{b}" for b in unik],
                              params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("valueRanges", [])
    for (b, s), vr in zip(unik.items(), cek):
        got = re.sub(r"\.0+$", "", _teks((vr.get("values") or [[""]])[0][0]))
        if got != s.npsn:
            cache.clear()
            raise LkError(f"Baris {b} di {tab} sekarang berisi NPSN {got or '(kosong)'}, bukan {s.npsn}. "
                          "Urutan sheet berubah. Muat ulang lalu isi lagi.")
    data = []
    for s, blok, kode, kendala, tl in isi:
        a, c = t.isian[blok][kode]
        if hanya_tl:
            data.append({"range": f"'{tab}'!{col_letter(c)}{s.baris}", "values": [[tl]]})
        else:
            data.append({"range": f"'{tab}'!{col_letter(a)}{s.baris}:{col_letter(c)}{s.baris}",
                         "values": [[kendala, tl]]})
    ss.values_batch_update({"valueInputOption": "RAW", "data": data})
    try:  # warna sel ditulis aplikasi (bukan conditional formatting): teks otomatis abu-abu -> isian petugas
        from .warna_lk import warnai_isian

        warnai_isian(week, isi, hanya_tl)
    except Exception:  # noqa: BLE001 - isian sudah tersimpan; warna menyusul saat cutoff berikutnya
        log.warning("Gagal mewarnai isian", exc_info=True)
    # Perbarui objek sekolah yang ada di cache supaya tampilan langsung benar tanpa membaca ulang sheet.
    for s, blok, kode, kendala, tl in isi:
        lama = s.isian.setdefault(blok, {}).get(kode, ("", ""))
        s.isian[blok][kode] = (lama[0] if hanya_tl else kendala, tl)


# ---------- Log Komunikasi ----------

KODE_KOMUNIKASI = {
    # T/T1/T2 hanya bila fasil SUDAH MEMBALAS. Pesan diterima tapi tidak dibalas = C2 (atau R bila sudah dibaca).
    "T": "Membalas dengan Kendala / Tindak lanjut (respon baik)",
    "T1": "Sudah membalas, belum ada Kendala / Tindak lanjut",
    "T2": "Sudah membalas, tapi lambat (3+ hari kerja)",
    "TP": "Terhubung melalui telepon",
    "R": "Dibaca (centang biru), tidak membalas",
    "C": "Centang satu (belum diterima)",
    "C2": "Centang dua (diterima), belum dibaca, tidak membalas",
    "N": "Nomor tidak terhubung WhatsApp",
}
_RE_TGL = re.compile(r"(\d{1,2})/(\d{1,2})")
_lock_kom = threading.Lock()
_cek_kom_terakhir = 0.0


@dataclass
class LogKom:
    tanggal: dict[str, int]                 # 'YYYY-MM-DD' -> indeks kolom
    baris: dict[str, int]                   # npsn -> nomor baris
    kode: dict[str, dict[str, str]]         # npsn -> {tanggal: kode}


def _tahun_untuk(bulan: int, hari: int, acuan: date) -> date:
    """'09/11' tanpa tahun -> tanggal terdekat dengan acuan."""
    calon = [date(acuan.year + d, bulan, hari) for d in (-1, 0, 1)]
    return min(calon, key=lambda x: abs((x - acuan).days))


def parse_log_kom(values: list[list[Any]], acuan: date) -> LogKom:
    """values mulai baris 2 (judul hari) kolom A."""
    if not values:
        return LogKom({}, {}, {})
    judul = values[0]
    tgl: dict[str, int] = {}
    for i, h in enumerate(judul):
        if i < 4:
            continue
        m = _RE_TGL.search(str(h))
        if not m:
            continue
        try:
            tgl[_tahun_untuk(int(m.group(2)), int(m.group(1)), acuan).isoformat()] = i
        except ValueError:
            continue
    baris, kode = {}, {}
    for n, r in enumerate(values[1:], start=3):
        npsn = re.sub(r"\.0+$", "", _teks(_sel(r, 1)))
        if not npsn:
            continue
        baris[npsn] = n
        kode[npsn] = {d: _teks(_sel(r, i)).upper() for d, i in tgl.items() if _teks(_sel(r, i))}
    return LogKom(tgl, baris, kode)


def baca_log_kom(refresh: bool = False) -> LogKom:
    from . import schedule

    def load() -> LogKom:
        got = _ss().values_get(f"'{TAB_LOG_KOM}'!A2:ZZ").get("values", [])
        return parse_log_kom(got, schedule.now().date())

    return cache.get("lk2_logkom", 120, load, refresh)


def _baris_kom_cocok(lk: LogKom, npsn: list[str]) -> bool:
    """Cek cepat: baris Log Komunikasi di cache masih berisi NPSN yang sama."""
    baris = [(n, lk.baris[n]) for n in npsn if n in lk.baris]
    if not baris:
        return False
    # Satu permintaan untuk seluruh kolom NPSN. (Dulu satu rentang per sekolah: dengan banyak sekolah sekaligus
    # alamat permintaannya terlalu panjang dan Google menolak dengan 400.)
    kolom = _ss().values_get(f"'{TAB_LOG_KOM}'!B1:B{max(b for _, b in baris)}",
                             params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
    for n, b in baris:
        isi = kolom[b - 1][0] if b - 1 < len(kolom) and kolom[b - 1] else ""
        if re.sub(r"\.0+$", "", _teks(isi)) != n:
            return False
    return True


def pastikan_kode_dropdown(kode: str) -> bool:
    """Pastikan `kode` ada di dropdown kolom tanggal Log Komunikasi (menambahkannya bila perlu).
    False bila dropdown tidak bisa diubah (mis. sumbernya rentang sel, bukan daftar)."""
    kunci = f"lk2_dropdown_{kode}"
    if cache.get(kunci, 3600, lambda: None):
        return True
    try:
        lk = baca_log_kom()
        if not lk.tanggal:
            return False
        kolom = sorted(set(lk.tanggal.values()))
        ss = _ss()
        meta = ss.fetch_sheet_metadata(params={
            "ranges": f"'{TAB_LOG_KOM}'!{col_letter(kolom[-1])}3", "includeGridData": "true",
            "fields": "sheets(properties(sheetId,gridProperties(rowCount)),data(rowData(values(dataValidation))))"})
        sh = meta["sheets"][0]
        sel = (((sh.get("data") or [{}])[0].get("rowData") or [{}])[0].get("values") or [{}])[0]
        aturan = sel.get("dataValidation")
        if not aturan:
            cache.get(kunci, 3600, lambda: True, refresh=True)
            return True  # tanpa dropdown: nilai apa pun boleh
        kondisi = aturan.get("condition", {})
        if kondisi.get("type") != "ONE_OF_LIST":
            log.warning("Dropdown Log Komunikasi bukan daftar (%s); kode %s tidak ditambahkan", kondisi.get("type"), kode)
            return False
        nilai = [v.get("userEnteredValue", "") for v in kondisi.get("values", [])]
        if kode not in nilai:
            aturan = {**aturan, "condition": {**kondisi, "values": [{"userEnteredValue": v} for v in [*nilai, kode]]}}
            sid, baris = sh["properties"]["sheetId"], sh["properties"]["gridProperties"]["rowCount"]
            runs: list[list[int]] = []
            for c in kolom:
                if runs and runs[-1][1] == c:
                    runs[-1][1] = c + 1
                else:
                    runs.append([c, c + 1])
            ss.batch_update({"requests": [{"setDataValidation": {
                "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": baris, "startColumnIndex": a,
                          "endColumnIndex": b}, "rule": aturan}} for a, b in runs]})
            log.info("Kode %s ditambahkan ke dropdown Log Komunikasi", kode)
        cache.get(kunci, 3600, lambda: True, refresh=True)
        return True
    except Exception:
        log.exception("Dropdown Log Komunikasi tidak bisa diperiksa")
        return False


# Legenda kode di kanan tab Log Komunikasi (judul "Kode" | "Arti" di baris 2) dan warnanya (conditional formatting).
LEGENDA_C2 = ("C2", "Centang dua (diterima), belum dibaca")
WARNA_C2 = {"red": 0.878, "green": 0.878, "blue": 0.937}  # abu-abu lembayung, beda dari C (merah muda) dan R (jingga)


def susun_legenda(baris: list[list[str]], kode: str, arti: str, setelah: str) -> list[list[str]] | None:
    """Daftar [kode, arti] baru dengan `kode` disisipkan setelah baris `setelah` (atau sebelum '(kosong)' / di akhir).
    None bila kode sudah ada."""
    rapi = [[_teks(r[0]) if r else "", _teks(r[1]) if len(r) > 1 else ""] for r in baris]
    while rapi and not any(rapi[-1]):
        rapi.pop()
    if any(r[0].upper() == kode.upper() for r in rapi):
        return None
    i = next((j + 1 for j, r in enumerate(rapi) if r[0].upper() == setelah.upper()), None)
    if i is None:
        i = next((j for j, r in enumerate(rapi) if r[0].startswith("(")), len(rapi))
    return rapi[:i] + [[kode, arti]] + rapi[i:]


def pastikan_legenda_c2() -> bool:
    """Tambahkan C2 ke legenda Kode/Arti dan beri warna lewat conditional formatting (sekali; aman diulang)."""
    kunci = "lk2_legenda_c2"
    if cache.get(kunci, 3600, lambda: None):
        return True
    try:
        ss = _ss()
        judul = (ss.values_get(f"'{TAB_LOG_KOM}'!A2:ZZ2").get("values") or [[]])[0]
        k = next((i for i, x in enumerate(judul) if _kunci(x) == "kode" and i + 1 < len(judul)
                  and _kunci(judul[i + 1]) == "arti"), None)
        meta = ss.fetch_sheet_metadata({"fields": "sheets(properties(title,sheetId),conditionalFormats)"})
        sh = next(x for x in meta["sheets"] if x["properties"]["title"] == TAB_LOG_KOM)
        sid = sh["properties"]["sheetId"]
        req: list[dict[str, Any]] = []
        if k is not None:
            a, b = col_letter(k), col_letter(k + 1)
            lama = ss.values_get(f"'{TAB_LOG_KOM}'!{a}3:{b}30").get("values", [])
            baru = susun_legenda(lama, *LEGENDA_C2, setelah="C")
            if baru:
                fmt = ss.fetch_sheet_metadata({"ranges": f"'{TAB_LOG_KOM}'!{a}3:{a}30", "includeGridData": True,
                                               "fields": "sheets(data(rowData(values(effectiveFormat(backgroundColor)))))"})
                rows = (fmt["sheets"][0]["data"][0].get("rowData") or [])
                warna = {}
                for r, x in zip(lama, rows):
                    if r and r[0]:
                        bg = ((x.get("values") or [{}])[0].get("effectiveFormat") or {}).get("backgroundColor")
                        if bg:
                            warna[_teks(r[0])] = bg
                warna[LEGENDA_C2[0]] = WARNA_C2
                n_lama = sum(1 for r in lama if r and any(_teks(x) for x in r))
                if n_lama:  # baris baru di bawah legenda: salin format baris terakhir (tebal, rata tengah, garis)
                    req.append({"copyPaste": {
                        "source": {"sheetId": sid, "startRowIndex": 1 + n_lama, "endRowIndex": 2 + n_lama,
                                   "startColumnIndex": k, "endColumnIndex": k + 2},
                        "destination": {"sheetId": sid, "startRowIndex": 2 + n_lama, "endRowIndex": 2 + len(baru),
                                        "startColumnIndex": k, "endColumnIndex": k + 2},
                        "pasteType": "PASTE_FORMAT"}})
                req.append({"updateCells": {
                    "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 2 + len(baru),
                              "startColumnIndex": k, "endColumnIndex": k + 2},
                    "rows": [{"values": [
                        {"userEnteredValue": {"stringValue": kd}, "userEnteredFormat": {
                            "backgroundColor": warna.get(kd, {"red": 1, "green": 1, "blue": 1})}},
                        {"userEnteredValue": {"stringValue": arti}}]} for kd, arti in baru],
                    "fields": "userEnteredValue,userEnteredFormat.backgroundColor"}})
        aturan = sh.get("conditionalFormats", [])
        ada_c2 = any(((r.get("booleanRule") or {}).get("condition") or {}).get("values", [{}])[0].get("userEnteredValue")
                     == "C2" for r in aturan)
        contoh = next((r for r in aturan if ((r.get("booleanRule") or {}).get("condition") or {}).get("values", [{}])[0]
                       .get("userEnteredValue") == "C"), None)
        if not ada_c2 and contoh:
            req.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": contoh["ranges"],
                "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "C2"}]},
                                "format": {"backgroundColor": WARNA_C2}}}}})
        if req:
            ss.batch_update({"requests": req})
            log.info("Legenda/warna C2 ditambahkan di Log Komunikasi")
        cache.get(kunci, 3600, lambda: True, refresh=True)
        return True
    except Exception:
        log.exception("Legenda C2 Log Komunikasi tidak bisa ditambahkan")
        return False


def tulis_log_kom(tanggal: str, npsn_kode: dict[str, str]) -> int:
    """Tulis kode komunikasi satu hari untuk beberapa sekolah. Mengembalikan jumlah sel yang ditulis."""
    if not npsn_kode:
        return 0
    with _lock_kom:
        lk = baca_log_kom()
        global _cek_kom_terakhir
        # Cek baris NPSN cukup sekali tiap 2 menit (sinkron menulis banyak tanggal berturut-turut)
        if tanggal not in lk.tanggal or (time.time() - _cek_kom_terakhir > 120
                                         and not _baris_kom_cocok(lk, list(npsn_kode))):
            lk = baca_log_kom(refresh=True)
        _cek_kom_terakhir = time.time()
        if tanggal not in lk.tanggal:
            from .cutoff_baru import pastikan_tanggal_log

            try:  # kolom tanggal belum ada: buat dulu (Senin–Sabtu)
                if pastikan_tanggal_log(date.fromisoformat(tanggal)):
                    lk = baca_log_kom(refresh=True)
            except Exception:
                log.exception("Kolom tanggal Log Komunikasi gagal dibuat")
        if tanggal not in lk.tanggal:
            raise LkError(f"Tab {TAB_LOG_KOM} belum punya kolom untuk tanggal {tanggal}. "
                          "Kolom tanggal dibuat otomatis untuk Senin–Sabtu.")
        c = col_letter(lk.tanggal[tanggal])
        data = []
        for npsn, k in npsn_kode.items():
            n = lk.baris.get(npsn)
            if n:
                data.append({"range": f"'{TAB_LOG_KOM}'!{c}{n}", "values": [[k]]})
                lk.kode.setdefault(npsn, {})[tanggal] = k
        if data:
            _ss().values_batch_update({"valueInputOption": "RAW", "data": data})
        return len(data)
