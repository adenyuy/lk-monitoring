"""Baca sheet Broadcast dan LK.

Fungsi `parse_*` murni (tanpa jaringan) supaya mudah dites.
Fungsi `read_*` memanggil Google Sheets dan memakai cache singkat.
"""

import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import config
from .google_auth import gspread_client


# ---------- helper ----------

def normalize_petugas(name: str) -> str:
    """'*Sari Petugas* ' -> 'sari petugas' (untuk dicocokkan persis)."""
    return re.sub(r"\s+", " ", str(name).replace("*", "")).strip().casefold()


def clean_petugas(name: str) -> str:
    """'*Sari Petugas*' -> 'Sari Petugas' (untuk ditampilkan)."""
    return re.sub(r"\s+", " ", str(name).replace("*", "")).strip()


def normalize_nomor(raw: str) -> str:
    """Ambil nomor dari 'https://wa.me/62857...' / '0857-…' / '+62 857…' -> '62857…'. '' bila tidak valid."""
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits if digits.startswith("62") and 10 <= len(digits) <= 15 else ""


def nomor_key(nomor: str) -> str:
    """9 digit terakhir, untuk mencocokkan nomor antar-sheet yang formatnya beda."""
    digits = re.sub(r"\D", "", str(nomor))
    return digits[-9:] if len(digits) >= 9 else ""


def message_hash(text: str) -> str:
    """Hash isi pesan untuk anti-dobel. Spasi di ujung & beda line ending diabaikan."""
    norm = str(text).replace("\r\n", "\n").strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def _col(header: list[str], *names: str) -> int:
    lowered = [str(h).strip().casefold() for h in header]
    for n in names:
        if n.casefold() in lowered:
            return lowered.index(n.casefold())
    raise ValueError(f"Kolom {names[0]!r} tidak ditemukan. Header: {header}")


def _cell(row: list[Any], i: int) -> str:
    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""


# ---------- Broadcast ----------

@dataclass(frozen=True)
class BroadcastRow:
    baris: int  # nomor baris di sheet (untuk urutan & laporan)
    petugas: str
    nama_fasil: str
    nomor: str  # '' bila tidak valid
    nomor_asli: str
    pesan: str
    hash_pesan: str


def parse_broadcast(values: list[list[Any]]) -> list[BroadcastRow]:
    if not values:
        return []
    header = values[0]
    i_fasil = _col(header, "Nama Fasil")
    i_nomor = _col(header, "Nomor HP")
    i_pesan = _col(header, "Pesan")
    i_petugas = _col(header, "Nama Petugas")
    rows = []
    for n, r in enumerate(values[1:], start=2):
        petugas = clean_petugas(_cell(r, i_petugas))
        if not petugas:
            continue
        pesan = _cell(r, i_pesan)
        nomor_asli = _cell(r, i_nomor)
        rows.append(
            BroadcastRow(
                baris=n,
                petugas=petugas,
                nama_fasil=_cell(r, i_fasil),
                nomor=normalize_nomor(nomor_asli),
                nomor_asli=nomor_asli,
                pesan=pesan,
                hash_pesan=message_hash(pesan) if pesan else "",
            )
        )
    return rows


def filter_petugas(rows: list[BroadcastRow], petugas: str) -> list[BroadcastRow]:
    target = normalize_petugas(petugas)
    return [r for r in rows if normalize_petugas(r.petugas) == target]


def petugas_summary(rows: list[BroadcastRow]) -> list[dict[str, Any]]:
    """[{nama, jumlah_fasil}] urut nama. Nama yang beda hanya karena '*'/spasi digabung."""
    count: dict[str, int] = defaultdict(int)
    display: dict[str, str] = {}
    for r in rows:
        key = normalize_petugas(r.petugas)
        count[key] += 1
        display.setdefault(key, r.petugas)
    return sorted(
        ({"nama": display[k], "jumlah_fasil": v} for k, v in count.items()),
        key=lambda x: x["nama"].casefold(),
    )


# ---------- LK WEEK n ----------
# Kolom LK TIDAK dipatok ke huruf: dibaca dari judul di baris 2 (admin bisa menyisipkan/memindah kolom).
ISIAN_KEYS = ("a1", "a2", "b1", "b2", "c1", "c2")

# Judul kolom (dinormalkan: huruf kecil, spasi tunggal) -> nama field
JUDUL_KOLOM = {
    "nama pic": "petugas",
    "npsn": "npsn",
    "nama sekolah": "nama",
    "kab/kota": "kab",
    "fasilitator": "fasil",
    "no fasil": "nomor",
    "prioritas": "prioritas",
    "status komunikasi": "komunikasi",
    "% progress fisik baseline": "progres_base",
    "status submit 50% baseline": "submit_base",
    "status reviu 50% baseline": "reviu_base",
    "% progress fisik": "progres",
    "status submit 50%": "submit",
    "status reviu 50%": "reviu",
}
# "A1. Alasan ...", "A.2. Tindak Lanjut", "C2. Tindak Lanjut": kemunculan pertama = sesi Senin–Rabu, kedua = Rabu–Jumat
_RE_ISIAN = re.compile(r"^([abc])\.?\s*([12])\.")


class LkKolomError(Exception):
    pass


def col_letter(i: int) -> str:
    """0 -> 'A', 26 -> 'AA'."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def col_number(letter: str) -> int:
    """'A' -> 0, 'AA' -> 26."""
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


@dataclass(frozen=True)
class LkKolom:
    """Huruf kolom tiap isian LK, hasil deteksi judul baris 2."""
    petugas: str
    npsn: str
    nama: str
    kab: str
    fasil: str
    nomor: str
    prioritas: str
    komunikasi: str
    progres_base: str
    submit_base: str
    reviu_base: str
    progres: str
    submit: str
    reviu: str
    blok: dict[int, tuple[str, ...]]  # {1: (a1..c2), 2: (a1..c2)}

    @property
    def terakhir(self) -> str:
        semua = [getattr(self, f) for f in set(JUDUL_KOLOM.values())] + [c for cols in self.blok.values() for c in cols]
        return col_letter(max(col_number(c) for c in semua))

    def ringkas(self) -> dict[str, Any]:
        return {
            **{f: getattr(self, f) for f in sorted(set(JUDUL_KOLOM.values()))},
            "blok": {b: f"{cols[0]}–{cols[-1]}" for b, cols in self.blok.items()},
        }


def _judul(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().lower()


def parse_kolom(header: list[Any]) -> LkKolom:
    """Baris judul LK (mulai kolom A) -> LkKolom. Gagal bila ada judul yang tidak ketemu."""
    pos: dict[str, str] = {}
    isian: dict[str, list[str]] = {k: [] for k in ISIAN_KEYS}
    for i, v in enumerate(header):
        h = _judul(v)
        f = JUDUL_KOLOM.get(h)
        if f and f not in pos:
            pos[f] = col_letter(i)
            continue
        m = _RE_ISIAN.match(h)
        if m:
            isian[m.group(1) + m.group(2)].append(col_letter(i))
    hilang = [j for j, f in JUDUL_KOLOM.items() if f not in pos]
    hilang += [f"{k.upper()} (sesi {n})" for k, cols in isian.items() for n in (1, 2) if len(cols) < n]
    if hilang:
        raise LkKolomError("Judul kolom LK tidak ketemu di baris 2: " + ", ".join(hilang)
                           + ". Kemungkinan judulnya diganti; samakan lagi judulnya atau kabari pengembang.")
    blok = {n: tuple(isian[k][n - 1] for k in ISIAN_KEYS) for n in (1, 2)}
    return LkKolom(**pos, blok=blok)


@dataclass
class Sekolah:
    baris: int
    petugas: str
    npsn: str
    nama: str
    kab_kota: str
    fasil: str
    nomor_fasil: str
    prioritas: str
    progres: float | None  # 0..100, harian bila ada, selain itu baseline
    submit: str
    reviu: str
    nomor_keys: list[str] = field(default_factory=list)
    komunikasi: str = ""
    isian: dict[int, dict[str, str]] = field(default_factory=dict)  # {blok: {a1..c2: nilai}}


def _progres(v: Any) -> float | None:
    """Sel persen: 0.2239 (unformatted) -> 22.39. Teks '22.39%' juga diterima."""
    if v in ("", None):
        return None
    if isinstance(v, (int, float)):
        return round(float(v) * 100, 2) if float(v) <= 1.0 else float(v)
    s = str(v).strip().replace("%", "").replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return None
    return f


def parse_lk(values: list[list[Any]], kol: LkKolom, first_row: int = config.LK_FIRST_ROW) -> list[Sekolah]:
    """Baris data LK (mulai kolom A) -> Sekolah, memakai posisi kolom hasil `parse_kolom`."""
    i = {f: col_number(getattr(kol, f)) for f in set(JUDUL_KOLOM.values())}
    out = []
    for n, r in enumerate(values, start=first_row):
        npsn = re.sub(r"\.0+$", "", _cell(r, i["npsn"]))
        if not npsn:
            continue
        nomor_raw = _cell(r, i["nomor"])
        keys = [k for k in (nomor_key(p) for p in re.split(r"[,/;]", nomor_raw)) if k]
        harian = _progres(r[i["progres"]]) if i["progres"] < len(r) else None
        baseline = _progres(r[i["progres_base"]]) if i["progres_base"] < len(r) else None
        out.append(
            Sekolah(
                baris=n,
                petugas=clean_petugas(_cell(r, i["petugas"])),
                npsn=npsn,
                nama=_cell(r, i["nama"]),
                kab_kota=_cell(r, i["kab"]),
                fasil=_cell(r, i["fasil"]),
                nomor_fasil=nomor_raw,
                prioritas=_cell(r, i["prioritas"]),
                progres=harian if harian is not None else baseline,
                submit=_cell(r, i["submit"]) or _cell(r, i["submit_base"]),
                reviu=_cell(r, i["reviu"]) or _cell(r, i["reviu_base"]),
                nomor_keys=keys,
                komunikasi=_cell(r, i["komunikasi"]),
                isian={
                    b: {k: _cell(r, col_number(col)) for k, col in zip(ISIAN_KEYS, cols)}
                    for b, cols in kol.blok.items()
                },
            )
        )
    return out


def parse_validasi(values: list[list[Any]]) -> dict[str, list[str]]:
    """Tab 'validasi' (baris 1 = judul): A komunikasi, B alasan progres, C alasan submit, D alasan reviu."""
    keys = ("komunikasi", "alasan_progres", "alasan_submit", "alasan_reviu")
    out: dict[str, list[str]] = {k: [] for k in keys}
    for r in values[1:]:
        for i, k in enumerate(keys):
            v = _cell(r, i)
            if v:
                out[k].append(v)
    return out


def sekolah_per_fasil(sekolah: list[Sekolah], petugas: str) -> dict[str, list[Sekolah]]:
    """{nomor_key: [Sekolah]} untuk sekolah milik petugas."""
    target = normalize_petugas(petugas)
    out: dict[str, list[Sekolah]] = defaultdict(list)
    for s in sekolah:
        if normalize_petugas(s.petugas) != target:
            continue
        for k in s.nomor_keys:
            out[k].append(s)
    return dict(out)


# ---------- baca dari Google (dengan cache) ----------

class _Cache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: int, loader: Callable[[], Any], refresh: bool = False) -> Any:
        with self._lock:
            hit = self._data.get(key)
            if hit and not refresh and time.time() - hit[0] < ttl:
                return hit[1]
        value = loader()
        with self._lock:
            self._data[key] = (time.time(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def drop(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


cache = _Cache()


def read_broadcast(refresh: bool = False) -> list[BroadcastRow]:
    # KHUSUS DEVELOP: LKM_BROADCAST_FILE = file JSON [[header...], [baris...], ...] sebagai
    # pengganti sheet Broadcast, supaya uji kirim tidak pernah menyentuh fasilitator sungguhan.
    override = os.environ.get("LKM_BROADCAST_FILE")
    if override:
        return parse_broadcast(json.loads(Path(override).read_text(encoding="utf-8")))

    def load() -> list[BroadcastRow]:
        ss = gspread_client().open_by_key(config.BROADCAST_SHEET_ID)
        values = ss.values_get(f"'{config.BROADCAST_TAB}'!A1:E").get("values", [])
        rows = parse_broadcast(values)
        from . import perubahan  # hindari import melingkar

        perubahan.catat_broadcast(rows)
        return rows

    return cache.get("broadcast", config.BROADCAST_CACHE_SECONDS, load, refresh)


def read_lk(week: str, refresh: bool = False) -> list[Sekolah]:
    tab = f"{config.LK_WEEK_PREFIX}{week}" if str(week).isdigit() else str(week)

    def load() -> list[Sekolah]:
        kol = kolom_lk(week, refresh=True)
        ss = gspread_client().open_by_key(config.LK_SHEET_ID)
        rng = f"'{tab}'!A{config.LK_FIRST_ROW}:{kol.terakhir}"
        values = ss.values_get(rng, params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
        data = parse_lk(values, kol)
        from . import perubahan  # hindari import melingkar

        perubahan.catat_lk(tab, data)
        return data

    return cache.get(f"lk:{tab}", config.LK_CACHE_SECONDS, load, refresh)


def kolom_lk(week: str, refresh: bool = False) -> LkKolom:
    """Posisi kolom LK WEEK n dari judul baris 2 (cache 5 menit; `refresh` untuk sebelum menulis)."""
    tab = lk_tab(week)

    def load() -> LkKolom:
        ss = gspread_client().open_by_key(config.LK_SHEET_ID)
        r = config.LK_FIRST_ROW - 1
        header = (ss.values_get(f"'{tab}'!A{r}:BZ{r}").get("values") or [[]])[0]
        return parse_kolom(header)

    return cache.get(f"lkkol:{tab}", 300, load, refresh)


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


def week_aktif() -> str:
    """WEEK yang dipakai: tab 'WEEK n' terbaru di LK (admin membuatnya tiap minggu).

    Bila LK tidak terbaca, pakai WEEK terakhir yang tersimpan. Saat pindah WEEK, dicatat di log perubahan.
    """
    from . import db, perubahan  # hindari import melingkar

    simpan = str(db.get_setting("week", "1") or "1")
    try:
        weeks = daftar_week()
    except Exception:
        return simpan
    if not weeks:
        return simpan
    baru = weeks[-1]
    if baru != simpan:
        db.set_setting("week", baru)
        perubahan.catat_pindah_week(simpan, baru)
    return baru


def lk_tab(week: str) -> str:
    return f"{config.LK_WEEK_PREFIX}{week}" if str(week).isdigit() else str(week)


def read_validasi(refresh: bool = False) -> dict[str, list[str]]:
    def load() -> dict[str, list[str]]:
        ss = gspread_client().open_by_key(config.LK_SHEET_ID)
        return parse_validasi(ss.values_get("'validasi'!A1:D").get("values", []))

    return cache.get("validasi", config.LK_CACHE_SECONDS, load, refresh)


class LkWriteError(Exception):
    pass


def _npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", str(v if v is not None else "").strip())


def write_isian(week: str, perubahan: list[tuple["Sekolah", dict[str, str]]], kol: LkKolom | None = None) -> None:
    """Tulis sel isian LK. `perubahan` = [(sekolah, {kolom: nilai})], huruf kolom dari `kol` (deteksi judul terbaru).
    Baris dicek dulu lewat NPSN supaya tidak menulis ke sekolah lain bila urutan sheet sudah berubah."""
    if not perubahan:
        return
    tab = lk_tab(week)
    kol = kol or kolom_lk(week, refresh=True)
    ss = gspread_client().open_by_key(config.LK_SHEET_ID)
    cek = ss.values_batch_get([f"'{tab}'!{kol.npsn}{s.baris}" for s, _ in perubahan],
                              params={"valueRenderOption": "UNFORMATTED_VALUE"})
    for (s, _), vr in zip(perubahan, cek.get("valueRanges", [])):
        got = _npsn((vr.get("values") or [[""]])[0][0])
        if got != s.npsn:
            cache.clear()
            raise LkWriteError(
                f"Baris {s.baris} di {tab} sekarang berisi NPSN {got or '(kosong)'}, bukan {s.npsn}. "
                "Urutan sheet berubah. Muat ulang lalu isi lagi."
            )
    data = [
        {"range": f"'{tab}'!{kolom}{s.baris}", "values": [[nilai]]}
        for s, sel in perubahan for kolom, nilai in sel.items()
    ]
    ss.values_batch_update({"valueInputOption": "RAW", "data": data})


def nomor_lk(s: "Sekolah") -> list[str]:
    """Nomor fasil (format 62…) dari sel No Fasil di LK; bisa lebih dari satu."""
    return [n for n in (normalize_nomor(p) for p in re.split(r"[,/;]", s.nomor_fasil)) if n]


def nomor_milik() -> set[str]:
    """Semua nomor fasil petugas ini: dari sheet Broadcast dan dari LK."""
    from . import db  # hindari import melingkar saat modul dimuat

    petugas = db.get_setting("nama_petugas") or ""
    out = {r.nomor for r in filter_petugas(read_broadcast(), petugas) if r.nomor}
    try:
        lk = read_lk(week_aktif())
        for s in lk:
            if normalize_petugas(s.petugas) == normalize_petugas(petugas):
                out.update(nomor_lk(s))
    except Exception:
        pass  # LK tidak terbaca: cukup nomor dari Broadcast
    return out
