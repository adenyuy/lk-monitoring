"""Forum tanya jawab tim (semua petugas boleh bertanya, menjawab, dan langsung tampil)."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import forum, google_auth, komunikasi, lk_baru, paparan
from ..access import Access
from .deps import require_access

router = APIRouter(prefix="/api/forum")


def _jalan(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except forum.ForumError as e:
        raise HTTPException(400, str(e)) from e
    except lk_baru.LinkBelumAda as e:
        raise HTTPException(428, str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Forum tidak bisa dibuka: {e}") from e


def _nama(acc: Access) -> str:
    return komunikasi.petugas_saya() or acc.nama_petugas or acc.email.split("@")[0]


def _izin() -> dict[str, Any]:
    st = paparan.izin_state
    return {"punya": paparan.punya_izin(), "status": st.status, "error": st.error}


@router.get("")
def daftar(paksa: bool = False, acc: Access = Depends(require_access)) -> dict[str, Any]:
    d = _jalan(forum.baca, paksa)
    return {"items": forum.ringkas(d, acc.email), "topik": forum.topik(d), "admin": acc.admin}


@router.get("/izin")
def izin(_=Depends(require_access)) -> dict[str, Any]:
    return _izin()


@router.post("/izin")
def minta_izin(_=Depends(require_access)) -> dict[str, Any]:
    paparan.minta_izin(google_auth.current_email() or "")
    return _izin()


@router.post("/foto")
async def foto(file: UploadFile = File(...), _=Depends(require_access)) -> dict[str, Any]:
    if not paparan.punya_izin():
        raise HTTPException(428, "Belum ada izin Google Drive.")
    isi = await file.read(forum.MAKS_BYTE + 1)
    fid = _jalan(forum.unggah_foto, isi, file.content_type or "", file.filename or "")
    return {"id": fid}


class TanyaIn(BaseModel):
    judul: str = Field(max_length=400)
    isi: str = Field(default="", max_length=16000)
    topik: str = Field(default="", max_length=80)
    foto: list[str] = Field(default_factory=list, max_length=8)
    jawaban: str = Field(default="", max_length=16000)
    foto_jawaban: list[str] = Field(default_factory=list, max_length=8)


@router.post("/tanya")
def tanya(body: TanyaIn, acc: Access = Depends(require_access)) -> dict[str, Any]:
    tid = _jalan(forum.buat_tanya, acc.email, _nama(acc), body.judul, body.isi, body.topik, body.foto,
                 body.jawaban, body.foto_jawaban)
    return {"id": tid}


class JawabIn(BaseModel):
    isi: str = Field(max_length=16000)
    foto: list[str] = Field(default_factory=list, max_length=8)


@router.post("/{tid}/jawab")
def jawab(tid: str, body: JawabIn, acc: Access = Depends(require_access)) -> dict[str, Any]:
    return {"id": _jalan(forum.buat_jawab, acc.email, _nama(acc), tid, body.isi, body.foto)}


class UbahIn(BaseModel):
    judul: str | None = Field(default=None, max_length=400)
    isi: str | None = Field(default=None, max_length=16000)
    topik: str | None = Field(default=None, max_length=80)
    foto: list[str] | None = Field(default=None, max_length=8)


@router.post("/{pid}/ubah")
def ubah(pid: str, body: UbahIn, acc: Access = Depends(require_access)) -> dict[str, Any]:
    _jalan(forum.ubah, acc.email, acc.admin, pid, body.judul, body.isi, body.topik, body.foto)
    return {"ok": True}


@router.post("/{pid}/hapus")
def hapus(pid: str, acc: Access = Depends(require_access)) -> dict[str, Any]:
    _jalan(forum.hapus, acc.email, acc.admin, pid)
    return {"ok": True}


class SolusiIn(BaseModel):
    jawaban: str = Field(default="", max_length=40)


@router.post("/{tid}/solusi")
def solusi(tid: str, body: SolusiIn, acc: Access = Depends(require_access)) -> dict[str, Any]:
    _jalan(forum.pilih_solusi, acc.email, acc.admin, tid, body.jawaban)
    return {"ok": True}


@router.get("/{tid}")
def detail(tid: str, acc: Access = Depends(require_access)) -> dict[str, Any]:
    return _jalan(forum.detail, tid, acc.email, acc.admin)
