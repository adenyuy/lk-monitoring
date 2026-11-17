"""Tarik Cutoff (LK format baru): hanya untuk akun dengan fitur 'cutoff' di sheet Akses."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .. import bimtek_lap, cutoff_baru, db, google_auth, komunikasi, lk_baru, pic_baru, schedule
from .deps import require_feature
from .lkb import _jalan

router = APIRouter(prefix="/api/cutoff")
admin = require_feature("cutoff")
MAKS_BYTE = 60 * 1024 * 1024


@router.get("")
def info(_=Depends(admin)) -> dict[str, Any]:
    weeks = _jalan(lk_baru.daftar_week, True)
    return {
        "weeks": weeks,
        "week_aktif": weeks[-1] if weeks else None,
        "senin_baru": cutoff_baru.senin_berikutnya().isoformat(),
        "riwayat": cutoff_baru.riwayat(),
        **_log_cutoff(),
        "status": cutoff_baru.status(),
        "kolom_wajib": list(cutoff_baru.WAJIB),
        "cutoff_terakhir": _cutoff_terakhir(),
    }


def _log_cutoff() -> dict[str, Any]:
    try:
        log = cutoff_baru.log_cutoff()
    except Exception:
        log = []
    return {"log_cutoff": log, "minggu": cutoff_baru.status_minggu(log, schedule.now().date())}


def _cutoff_terakhir() -> str:
    try:
        return komunikasi.label_cutoff()
    except Exception:
        return ""


@router.post("/cek")
async def cek(file: UploadFile = File(...), week: int = Form(...), _=Depends(admin)) -> dict[str, Any]:
    data = await file.read()
    if len(data) > MAKS_BYTE:
        raise HTTPException(400, "File terlalu besar (maks 60 MB).")
    try:
        r = cutoff_baru.siapkan(data, file.filename or "cutoff.csv", week)
    except cutoff_baru.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    except lk_baru.LkError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Gagal membaca file atau LK: {e}") from e
    return {"token": r.token, "file": r.nama_file, "week": r.week, **r.ringkasan}


class TulisReq(BaseModel):
    token: str


@router.post("/tulis")
def tulis(req: TulisReq, _=Depends(admin)) -> dict[str, Any]:
    try:
        cutoff_baru.mulai_tulis(req.token, google_auth.current_email() or "")
    except cutoff_baru.CutoffError as e:
        raise HTTPException(400, str(e)) from e
    return cutoff_baru.status()


@router.get("/status")
def status(_=Depends(admin)) -> dict[str, Any]:
    return cutoff_baru.status()


class WeekReq(BaseModel):
    senin: date


@router.post("/week-baru")
def week_baru(req: WeekReq, _=Depends(admin)) -> dict[str, Any]:
    try:
        return cutoff_baru.buat_week(req.senin)
    except (cutoff_baru.CutoffError, lk_baru.LkError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"WEEK baru gagal dibuat: {e}") from e


# ---------- PIC sekolah baru dari sheet pembagian ----------

class PicReq(BaseModel):
    link: str
    ganti_beda: bool = False


def _pic(fn, req: PicReq) -> dict[str, Any]:
    try:
        return fn(req.link.strip(), req.ganti_beda)
    except (pic_baru.PicError, lk_baru.LkError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Sheet pembagian atau LK tidak bisa dibaca: {e}") from e


@router.get("/pic")
def pic_info(_=Depends(admin)) -> dict[str, Any]:
    return _jalan(pic_baru.ringkas)


@router.post("/pic/cek")
def pic_cek(req: PicReq, _=Depends(admin)) -> dict[str, Any]:
    r = _pic(pic_baru.rencana, req)
    db.set_setting(pic_baru.KUNCI_LINK, req.link.strip())
    return {k: v for k, v in r.items() if k not in ("isi", "beda")} | {
        "isi": [{k: x[k] for k in ("npsn", "nama", "pic")} for x in r["isi"][:200]],
        "beda": [{k: x[k] for k in ("npsn", "nama", "pic", "pic_lama")} for x in r["beda"][:200]],
        "jml_isi": len(r["isi"]), "jml_beda": len(r["beda"]),
    }


@router.post("/pic/isi")
def pic_isi(req: PicReq, _=Depends(admin)) -> dict[str, Any]:
    return _pic(pic_baru.tulis, req)


# ---------- Bimtek Pelaporan dari sheet daftar bimtek ----------

def _bimtek(fn, req: PicReq) -> dict[str, Any]:
    try:
        return fn(req.link.strip(), req.ganti_beda)
    except (bimtek_lap.BimtekLapError, lk_baru.LkError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Sheet daftar bimtek atau LK tidak bisa dibaca: {e}") from e


@router.get("/bimtek")
def bimtek_info(_=Depends(admin)) -> dict[str, Any]:
    return _jalan(bimtek_lap.ringkas)


@router.post("/bimtek/cek")
def bimtek_cek(req: PicReq, _=Depends(admin)) -> dict[str, Any]:
    r = _bimtek(bimtek_lap.rencana, req)
    db.set_setting(bimtek_lap.KUNCI_LINK, req.link.strip())
    return _ringkas_cek(r)


def _ringkas_cek(r: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in r.items() if k not in ("isi", "beda", "tanpa")} | {
        "beda": [{k: x[k] for k in ("npsn", "nama", "bimtek", "bimtek_lama")} for x in r["beda"][:200]],
        "tanpa": r["tanpa"][:200],
        "jml_isi": len(r["isi"]), "jml_beda": len(r["beda"]), "jml_tanpa": len(r["tanpa"]),
    }


@router.post("/bimtek/isi")
def bimtek_isi(req: PicReq, _=Depends(admin)) -> dict[str, Any]:
    return _bimtek(bimtek_lap.tulis, req)


def _bimtek_file(fn, data: bytes, nama: str, ganti_beda: bool) -> dict[str, Any]:
    try:
        return fn(data, nama, ganti_beda)
    except (bimtek_lap.BimtekLapError, lk_baru.LkError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"File atau LK tidak bisa dibaca: {e}") from e


@router.post("/bimtek/cek-file")
async def bimtek_cek_file(file: UploadFile = File(...), ganti_beda: bool = Form(False),
                          _=Depends(admin)) -> dict[str, Any]:
    r = await run_in_threadpool(_bimtek_file, bimtek_lap.rencana_file, await file.read(),
                                file.filename or "bimtek.csv", ganti_beda)
    return _ringkas_cek(r)


@router.post("/bimtek/isi-file")
async def bimtek_isi_file(file: UploadFile = File(...), ganti_beda: bool = Form(False),
                          _=Depends(admin)) -> dict[str, Any]:
    return await run_in_threadpool(_bimtek_file, bimtek_lap.tulis_file, await file.read(),
                                   file.filename or "bimtek.csv", ganti_beda)
