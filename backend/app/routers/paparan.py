"""Paparan PIC: data 6 slide, pratinjau di aplikasi, dan pembuatan Google Slides."""

import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import google_auth, komunikasi, paparan
from .deps import require_access
from .lkb import _jalan

router = APIRouter(prefix="/api/paparan")

SEGAR_DETIK = 300
_simpan: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def _data(paksa: bool = False) -> dict[str, Any]:
    saya = komunikasi.petugas_saya()
    if not saya:
        raise HTTPException(400, "Nama petugas belum dipilih.")
    with _lock:
        ada = _simpan.get(saya)
    if ada and not paksa and time.time() - ada[0] < SEGAR_DETIK:
        return ada[1]
    d = _jalan(paparan.hitung)
    with _lock:
        _simpan[saya] = (time.time(), d)
    return d


def _izin() -> dict[str, Any]:
    st = paparan.izin_state
    return {"punya": paparan.punya_izin(), "status": st.status, "error": st.error}


@router.get("")
def ambil(paksa: bool = False, _=Depends(require_access)) -> dict[str, Any]:
    d = _data(paksa)
    return {
        "pic": d["pic"], "week": d["week"], "cutoff": d["cutoff"], "tanggal": d["tanggal"], "dibuat": d["dibuat"],
        "daftar": [{"kunci": k, "judul": j, "aktif": k not in paparan.BAWAAN_MATI} for k, j in paparan.SLIDE],
        "langkah": paparan.langkah_awal(d),
        "catatan": paparan.catatan_awal(d),
        "slides": paparan.susun(d),
        "jumlah_masalah": len(d["masalah"]),
        "izin": _izin(),
    }


@router.get("/izin")
def izin(_=Depends(require_access)) -> dict[str, Any]:
    return _izin()


@router.post("/izin")
def minta_izin(_=Depends(require_access)) -> dict[str, Any]:
    paparan.minta_izin(google_auth.current_email() or "")
    return _izin()


class SlidesIn(BaseModel):
    urutan: list[str] = Field(default_factory=list, max_length=12)
    langkah: list[str] = Field(default_factory=list, max_length=30)
    catatan: dict[str, str] = Field(default_factory=dict)
    ubahan: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


@router.post("/slides")
def buat(body: SlidesIn, _=Depends(require_access)) -> dict[str, Any]:
    if not body.urutan:
        raise HTTPException(400, "Pilih minimal satu slide.")
    if not paparan.punya_izin():
        raise HTTPException(428, "Belum ada izin Google Slides.")
    d = _data()
    langkah = [" ".join(x.split())[:300] for x in body.langkah if x.strip()]
    catatan = {k: v[:3000] for k, v in body.catatan.items()}
    slides = paparan.terapkan_ubahan(paparan.susun(d, body.urutan, langkah, catatan), body.ubahan)
    try:
        return paparan.buat_slides(d, slides)
    except paparan.SlidesError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Google Slides tidak bisa dibuat: {e}") from e
