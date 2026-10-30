"""LK Eskalasi: catat permasalahan sekolah binaan yang perlu dijawab tim terkait."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import aktivitas, db, eskalasi
from ..sheets import nomor_lk, normalize_petugas, read_lk, week_aktif
from .deps import require_feature

router = APIRouter(prefix="/api/eskalasi")
wa_blast = require_feature("wa_blast")
MAKS_TEKS = 2000


def _jalan(fn, *args):
    try:
        return fn(*args)
    except eskalasi.EskalasiError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"LK Eskalasi tidak bisa dibuka: {e}") from e


@router.get("")
def daftar(npsn: str = Query("", max_length=4000), _=Depends(wa_blast)) -> dict[str, Any]:
    pilih = [x for x in npsn.split(",") if x.strip()]
    return {"opsi": _jalan(eskalasi.opsi), "eskalasi": _jalan(eskalasi.daftar, pilih) if pilih else []}


class CatatReq(BaseModel):
    npsn: list[str] = Field(min_length=1, max_length=100)
    keterangan: str = Field(min_length=1, max_length=MAKS_TEKS)
    permasalahan: str = Field("", max_length=200)
    tim: list[str] = Field(min_length=1, max_length=10)


@router.post("")
def catat(req: CatatReq, _=Depends(wa_blast)) -> dict[str, Any]:
    petugas = normalize_petugas(db.get_setting("nama_petugas") or "")
    try:
        semua = read_lk(week_aktif())
    except Exception as e:
        raise HTTPException(502, f"LK tidak bisa dibaca: {e}") from e
    milik = {s.npsn: s for s in semua if normalize_petugas(s.petugas) == petugas}
    for x in req.npsn:
        if x not in milik:
            raise HTTPException(403, f"NPSN {x} bukan sekolah binaan petugas ini.")
    cadangan = {x: {"nama": milik[x].nama, "fasil": milik[x].fasil, "petugas": milik[x].petugas} for x in req.npsn}
    hasil = _jalan(eskalasi.catat, req.npsn, req.keterangan, req.permasalahan, req.tim, cadangan)

    sekolah = [milik[d["npsn"]] for d in hasil["ditulis"]]
    nomors = nomor_lk(sekolah[0]) if sekolah else []
    nama = ", ".join(s.nama for s in sekolah[:4]) + (f", +{len(sekolah) - 4} lagi" if len(sekolah) > 4 else "")
    aktivitas.catat(nomors[0] if nomors else f"nama:{sekolah[0].fasil}", "lk",
                    f"Eskalasi ke {', '.join(req.tim)}: {req.permasalahan or 'tanpa kelompok'} untuk {nama}",
                    sekolah[0].fasil)
    return hasil
