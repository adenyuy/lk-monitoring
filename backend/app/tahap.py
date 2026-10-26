"""Tahap komunikasi dengan fasil dan kelengkapan isian LK.

Dipakai panel fasil dan halaman Rekap supaya hitungannya sama.
"""

from typing import Any

from . import schedule
from .sheets import Sekolah

TAHAP = (
    ("terkirim", "Broadcast terkirim"),
    ("dibaca", "Dibaca"),
    ("dibalas", "Fasil membalas"),
    ("ditanya", "Isian LK ditanyakan"),
    ("lk_lengkap", "Isian LK lengkap"),
)
BLOK_LABEL = {1: "Senin–Rabu", 2: "Rabu–Jumat"}
BLOK_KOLOM_LABEL = {1: "P–U", 2: "V–AA"}


def blok_hari_ini() -> int:
    """Senin–Selasa isi blok 1 (P–U), Rabu dan seterusnya blok 2 (V–AA)."""
    return 1 if schedule.now().weekday() <= 1 else 2


def grup_relevan(s: Sekolah) -> list[str]:
    """Alasan yang perlu diisi: a = progres < 50%, b = belum submit, c = sudah submit tapi belum direviu."""
    out = []
    if s.progres is None or s.progres < 50:
        out.append("a")
    if s.submit != "Ya":
        out.append("b")
    elif s.reviu != "Ya":
        out.append("c")
    return out


def sekolah_lengkap(s: Sekolah, blok: int) -> bool:
    """Lengkap bila status komunikasi terisi dan semua alasan yang relevan terisi di blok itu."""
    if s.prioritas.strip().lower() == "selesai":
        return True
    isi = s.isian.get(blok, {})
    return bool(s.komunikasi) and all(isi.get(f"{g}1") for g in grup_relevan(s))


def perlu_isian(s: Sekolah) -> bool:
    return s.prioritas.strip().lower() != "selesai"


def hitung(nomor: str, sekolah: list[Sekolah], sends: list[dict], chat: dict | None,
           manual: dict[str, dict], blok: int) -> list[dict[str, Any]]:
    """Status tiap tahap untuk satu fasil. Centang manual menimpa deteksi otomatis."""
    terkirim = any(x["status"] == "terkirim" and not x["coba"] for x in sends)
    st = (chat or {}).get("status", "")
    perlu = [x for x in sekolah if perlu_isian(x)]
    auto = {
        "terkirim": terkirim,
        "dibaca": st in ("dibaca", "dibalas"),
        "dibalas": st == "dibalas",
        "ditanya": False,
        "lk_lengkap": bool(perlu) and all(sekolah_lengkap(x, blok) for x in perlu),
    }
    out = []
    for kode, label in TAHAP:
        m = manual.get(kode)
        if m is not None and kode != "lk_lengkap":
            out.append({"kode": kode, "label": label, "selesai": m["nilai"], "sumber": m["sumber"], "waktu": m["waktu"]})
        else:
            out.append({"kode": kode, "label": label, "selesai": auto[kode], "sumber": "otomatis", "waktu": ""})
    return out
