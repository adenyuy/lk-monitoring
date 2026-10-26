"""Isi kolom LK (status komunikasi, alasan, tindak lanjut) langsung dari aplikasi."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import aktivitas, db, tahap
from ..sheets import (
    BLOK_KOLOM, ISIAN_KEYS, KOMUNIKASI_KOLOM, LkWriteError, normalize_petugas, read_lk, read_validasi, write_isian,
)
from .deps import require_feature

from ..sheets import nomor_lk, week_aktif  # noqa: E402

router = APIRouter(prefix="/api/lk")
wa_blast = require_feature("wa_blast")

BLOK_LABEL = {1: "Senin–Rabu", 2: "Rabu–Jumat"}
# Kolom alasan memakai dropdown dari tab validasi; tindak lanjut teks bebas.
OPSI_UNTUK = {"a1": "alasan_progres", "b1": "alasan_submit", "c1": "alasan_reviu"}
MAKS_TEKS = 500


def blok_default() -> int:
    return tahap.blok_hari_ini()


def _opsi() -> dict[str, list[str]]:
    try:
        return read_validasi()
    except Exception as e:
        raise HTTPException(502, f"Tab validasi di LK tidak bisa dibaca: {e}") from e


@router.get("/opsi")
def opsi(_=Depends(wa_blast)) -> dict[str, Any]:
    return {
        "opsi": _opsi(),
        "blok_default": blok_default(),
        "blok_kolom": tahap.BLOK_KOLOM_LABEL[blok_default()],
        "blok": [{"no": b, "label": BLOK_LABEL[b]} for b in BLOK_KOLOM],
    }


class Isian(BaseModel):
    npsn: str = Field(min_length=1, max_length=20)
    komunikasi: str | None = Field(None, max_length=MAKS_TEKS)
    isian: dict[str, str] = Field(default_factory=dict)


class IsiReq(BaseModel):
    blok: int | None = Field(None, ge=1, le=2)  # kosong = otomatis dari hari
    sekolah: list[Isian] = Field(min_length=1, max_length=100)


@router.post("/isi")
def isi(req: IsiReq, _=Depends(wa_blast)) -> dict[str, Any]:
    petugas = normalize_petugas(db.get_setting("nama_petugas") or "")
    week = week_aktif()
    try:
        semua = read_lk(week)
    except Exception as e:
        raise HTTPException(502, f"LK tidak bisa dibaca: {e}") from e
    milik = {s.npsn: s for s in semua if normalize_petugas(s.petugas) == petugas}
    opsi_lk = _opsi()
    blok = req.blok or blok_default()

    perubahan = []
    for it in req.sekolah:
        s = milik.get(it.npsn)
        if not s:
            raise HTTPException(403, f"NPSN {it.npsn} bukan sekolah binaan petugas ini di LK WEEK {week}.")
        sel: dict[str, str] = {}
        if it.komunikasi is not None:
            v = it.komunikasi.strip()
            if v and v not in opsi_lk["komunikasi"]:
                raise HTTPException(400, f"Status komunikasi '{v}' tidak ada di pilihan.")
            sel[KOMUNIKASI_KOLOM] = v
        for k, v in it.isian.items():
            if k not in ISIAN_KEYS:
                raise HTTPException(400, f"Kolom isian '{k}' tidak dikenal.")
            v = v.strip()
            if len(v) > MAKS_TEKS:
                raise HTTPException(400, f"Isian terlalu panjang (maks {MAKS_TEKS} karakter).")
            if k in OPSI_UNTUK and v and v not in opsi_lk[OPSI_UNTUK[k]]:
                raise HTTPException(400, f"Alasan '{v}' tidak ada di pilihan.")
            sel[BLOK_KOLOM[blok][ISIAN_KEYS.index(k)]] = v
        if sel:
            perubahan.append((s, sel, it))

    try:
        write_isian(week, [(s, sel) for s, sel, _ in perubahan])
    except LkWriteError as e:
        raise HTTPException(409, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Gagal menulis ke LK: {e}") from e

    # Perbarui cache supaya tampilan langsung sesuai tanpa membaca ulang seluruh LK
    for s, _, it in perubahan:
        if it.komunikasi is not None:
            s.komunikasi = it.komunikasi.strip()
        for k, v in it.isian.items():
            s.isian.setdefault(blok, {})[k] = v.strip()

    # Riwayat per fasil: satu catatan per fasil yang sekolahnya diisi
    per_fasil: dict[str, list] = {}
    for s, _, it in perubahan:
        nomors = nomor_lk(s)
        per_fasil.setdefault(nomors[0] if nomors else f"nama:{s.fasil}", []).append((s, it))
    for nomor, isi in per_fasil.items():
        kom = {it.komunikasi.strip() for _, it in isi if it.komunikasi}
        teks = f"Sesi {BLOK_LABEL[blok]}: {len(isi)} sekolah disimpan ({', '.join(s.nama for s, _ in isi[:4])}"
        teks += f", +{len(isi) - 4} lagi)" if len(isi) > 4 else ")"
        if kom:
            teks += f". Status komunikasi: {', '.join(sorted(kom))}"
        aktivitas.catat(nomor, "lk", teks, isi[0][0].fasil)
    return {"disimpan": len(perubahan), "blok": blok}
