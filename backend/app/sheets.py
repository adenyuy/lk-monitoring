"""Baca sheet Broadcast dan LK.

Fungsi `parse_*` murni (tanpa jaringan) supaya mudah dites.
Fungsi `read_*` memanggil Google Sheets dan memakai cache singkat.
"""

import hashlib
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
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
# Range dibaca: B..O mulai baris LK_FIRST_ROW. Indeks relatif terhadap kolom B.
_B, _C, _D, _E, _F, _G, _H = 0, 1, 2, 3, 4, 5, 6
_J, _K, _L, _M, _N, _O = 8, 9, 10, 11, 12, 13


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
    progres: float | None  # 0..100, harian (M) bila ada, selain itu baseline (J)
    submit: str
    reviu: str
    nomor_keys: list[str] = field(default_factory=list)


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


def parse_lk(values: list[list[Any]], first_row: int = config.LK_FIRST_ROW) -> list[Sekolah]:
    out = []
    for n, r in enumerate(values, start=first_row):
        npsn = re.sub(r"\.0+$", "", _cell(r, _C))
        if not npsn:
            continue
        nomor_raw = _cell(r, _G)
        keys = [k for k in (nomor_key(p) for p in re.split(r"[,/;]", nomor_raw)) if k]
        harian = _progres(r[_M]) if _M < len(r) else None
        baseline = _progres(r[_J]) if _J < len(r) else None
        out.append(
            Sekolah(
                baris=n,
                petugas=clean_petugas(_cell(r, _B)),
                npsn=npsn,
                nama=_cell(r, _D),
                kab_kota=_cell(r, _E),
                fasil=_cell(r, _F),
                nomor_fasil=nomor_raw,
                prioritas=_cell(r, _H),
                progres=harian if harian is not None else baseline,
                submit=_cell(r, _N) or _cell(r, _K),
                reviu=_cell(r, _O) or _cell(r, _L),
                nomor_keys=keys,
            )
        )
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


cache = _Cache()


def read_broadcast(refresh: bool = False) -> list[BroadcastRow]:
    def load() -> list[BroadcastRow]:
        ss = gspread_client().open_by_key(config.BROADCAST_SHEET_ID)
        values = ss.values_get(f"'{config.BROADCAST_TAB}'!A1:E").get("values", [])
        return parse_broadcast(values)

    return cache.get("broadcast", config.BROADCAST_CACHE_SECONDS, load, refresh)


def read_lk(week: str, refresh: bool = False) -> list[Sekolah]:
    tab = f"{config.LK_WEEK_PREFIX}{week}" if str(week).isdigit() else str(week)

    def load() -> list[Sekolah]:
        ss = gspread_client().open_by_key(config.LK_SHEET_ID)
        rng = f"'{tab}'!B{config.LK_FIRST_ROW}:O"
        values = ss.values_get(rng, params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
        return parse_lk(values)

    return cache.get(f"lk:{tab}", config.LK_CACHE_SECONDS, load, refresh)
