"""Daftar akses pengguna dari sheet Akses (milik admin).

Kolom: email | nama_petugas | fitur   (fitur dipisah koma: wa_blast, cutoff)
"""

from dataclasses import dataclass
from typing import Any

from . import config
from .google_auth import gspread_client
from .sheets import cache, clean_petugas


class AccessError(Exception):
    """Pesan error-nya ditampilkan langsung ke pengguna."""


@dataclass(frozen=True)
class Access:
    email: str
    nama_petugas: str
    fitur: tuple[str, ...]

    def has(self, feature: str) -> bool:
        return feature in self.fitur


def parse_access(values: list[list[Any]]) -> dict[str, Access]:
    if not values:
        return {}
    header = [str(h).strip().casefold() for h in values[0]]
    try:
        i_email = header.index("email")
        i_nama = header.index("nama_petugas")
        i_fitur = header.index("fitur")
    except ValueError as e:
        raise AccessError("Sheet Akses harus punya kolom: email, nama_petugas, fitur.") from e

    out = {}
    for r in values[1:]:
        cell = lambda i: str(r[i]).strip() if i < len(r) else ""  # noqa: E731
        email = cell(i_email).casefold()
        if not email:
            continue
        fitur = tuple(
            f for f in (x.strip().casefold() for x in cell(i_fitur).split(",")) if f in config.FEATURES
        )
        out[email] = Access(email=email, nama_petugas=clean_petugas(cell(i_nama)), fitur=fitur)
    return out


def read_access(refresh: bool = False) -> dict[str, Access]:
    if not config.ACCESS_SHEET_ID:
        raise AccessError(
            "Sheet Akses belum diatur. Admin perlu mengisi ACCESS_SHEET_ID di backend/app/config.py."
        )

    def load() -> dict[str, Access]:
        ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
        values = ss.values_get(f"'{config.ACCESS_TAB}'!A1:C").get("values", [])
        return parse_access(values)

    return cache.get("access", config.ACCESS_CACHE_SECONDS, load, refresh)


def access_for(email: str, refresh: bool = False) -> Access:
    acc = read_access(refresh).get(email.casefold())
    if acc is None:
        raise AccessError(f"Akun {email} belum terdaftar. Hubungi admin untuk didaftarkan.")
    if not acc.fitur:
        raise AccessError(f"Akun {email} terdaftar tapi belum diberi fitur apa pun. Hubungi admin.")
    return acc
