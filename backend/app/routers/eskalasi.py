"""LK Eskalasi: petugas mencatat permasalahan, PIC Eskalasi (fitur `eskalasi`) memantau dan mengisi Kode Tema."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import aktivitas, db, eskalasi, schedule
from ..wa import actions
from . import chat
from ..access import Access
from ..sheets import normalize_petugas
from .deps import require_access, require_feature

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


def _saya(acc: Access) -> str:
    from .. import komunikasi

    return komunikasi.petugas_saya() or acc.nama_petugas or acc.email.split("@")[0]


def _pic(acc: Access) -> bool:
    return acc.admin or acc.has("eskalasi")


def _keluar(m: dict[str, Any], saya: str, pic: bool) -> dict[str, Any]:
    return {**m, "boleh_ubah": eskalasi.boleh_ubah(m, saya, pic),
            "milik_saya": bool(saya) and normalize_petugas(m["petugas"]) == normalize_petugas(saya)}


@router.get("")
def daftar(npsn: str = Query("", max_length=4000), semua: bool = False, paksa: bool = False,
           acc: Access = Depends(require_access)) -> dict[str, Any]:
    """`npsn` = masalah sekolah-sekolah ini saja; `semua` = seluruh LK Eskalasi (halaman FAQ & Eskalasi)."""
    try:
        eskalasi.sheet_id()
    except eskalasi.LinkBelumAda:
        return {"perlu_link": True, "opsi": None, "masalah": [], "faq": [], "saya": {}}
    saya, pic = _saya(acc), _pic(acc)
    if paksa:
        eskalasi.cache.drop("esk_opsi")
        eskalasi.cache.drop("esk_faq")
    pilih = [x for x in npsn.split(",") if x.strip()]
    masalah = (_jalan(eskalasi.semua, paksa) if semua else _jalan(eskalasi.daftar, pilih) if pilih else [])
    return {"perlu_link": False, "opsi": _jalan(eskalasi.opsi), "faq": _jalan(eskalasi.faq_resmi) if semua else [],
            "masalah": [_keluar(m, saya, pic) for m in masalah],
            "saya": {"nama": saya, "pic": pic, "admin": acc.admin}}


@router.get("/sekolah/{npsn}")
def sekolah(npsn: str, _=Depends(require_access)) -> dict[str, Any]:
    """Isi otomatis dari NPSN: Nama Sekolah, Fasilitator, Petugas Monitoring, PTN (WEEK aktif LK, lalu Master Data)."""
    s = _jalan(eskalasi.sekolah, npsn)
    if not s:
        raise HTTPException(404, f"NPSN {npsn} tidak ditemukan di LK maupun Master Data.")
    return s


class LinkReq(BaseModel):
    link: str = Field(min_length=10, max_length=500)


@router.post("/link")
def pasang_link(req: LinkReq, acc: Access = Depends(wa_blast)) -> dict[str, Any]:
    """Admin memasang untuk seluruh tim; petugas lain hanya untuk laptopnya sendiri."""
    untuk_tim = acc.admin
    _jalan(eskalasi.pasang_link, req.link, untuk_tim)
    return {"ok": True, "untuk_tim": untuk_tim}


@router.get("/kontak")
def kontak(_=Depends(wa_blast)) -> dict[str, Any]:
    """Teman petugas dari tab Kontak PIC sheet Broadcast, tanpa diri sendiri."""
    saya = normalize_petugas(db.get_setting("nama_petugas") or "")
    try:
        semua = eskalasi.kontak_pic()
    except Exception as e:
        raise HTTPException(502, f"Tab Kontak PIC di sheet Broadcast tidak bisa dibaca: {e}") from e
    return {"kontak": [k for k in semua if normalize_petugas(k["nama"]) != saya]}


class CatatReq(BaseModel):
    sumber: str = Field(min_length=1, max_length=60)
    npsn: list[str] = Field(default_factory=list, max_length=eskalasi.MAKS_SEKOLAH)
    topik: str = Field("", max_length=200)
    keterangan: str = Field(min_length=1, max_length=MAKS_TEKS)
    permasalahan: str = Field(min_length=1, max_length=200)
    tingkat: str = Field("", max_length=100)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    tgl_awal: str = Field("", max_length=10)
    agregasi: str = Field("Ya", max_length=10)
    tim: list[str] = Field(default_factory=list, max_length=20)
    jawaban: str = Field("", max_length=MAKS_TEKS)
    status: str = Field("", max_length=100)
    pengisi: str = Field("", max_length=100)


@router.post("")
def catat(req: CatatReq, acc: Access = Depends(require_access)) -> dict[str, Any]:
    saya = _saya(acc)
    hasil = _jalan(eskalasi.catat, req.model_dump(exclude={"npsn"}), req.npsn, saya)
    for fasil in dict.fromkeys(h["fasil"] for h in hasil if h["fasil"]):
        sekolah_fasil = [h["nama"] for h in hasil if h["fasil"] == fasil]
        aktivitas.catat(f"nama:{fasil}", "lk", f"Eskalasi ke {', '.join(req.tim)}: {req.permasalahan} untuk "
                        + ", ".join(sekolah_fasil[:4]) + (f", +{len(sekolah_fasil) - 4} lagi" if len(sekolah_fasil) > 4 else ""),
                        fasil)
    return {"ditulis": hasil}


class UbahReq(BaseModel):
    sumber: str | None = Field(None, max_length=60)
    topik: str | None = Field(None, max_length=200)
    keterangan: str | None = Field(None, max_length=MAKS_TEKS)
    permasalahan: str | None = Field(None, max_length=200)
    tingkat: str | None = Field(None, max_length=100)
    evidence: list[str] | None = Field(None, max_length=10)
    tgl_awal: str | None = Field(None, max_length=10)
    agregasi: str | None = Field(None, max_length=10)
    tim: list[str] | None = Field(None, max_length=20)
    jawaban: str | None = Field(None, max_length=MAKS_TEKS)
    status: str | None = Field(None, max_length=100)
    tgl_selesai: str | None = Field(None, max_length=10)
    pengisi: str | None = Field(None, max_length=100)
    kode_tema: str | None = Field(None, max_length=20)
    status_eskalasi: str | None = Field(None, max_length=40)
    # baris yang dilihat pengguna: ID Masalah di sheet bisa bergeser, jadi baris dicocokkan lewat sidik
    baris: int | None = Field(None, ge=1)
    sidik: str | None = Field(None, max_length=300)


@router.post("/{mid}/ubah")
def ubah(mid: str, req: UbahReq, acc: Access = Depends(require_access)) -> dict[str, Any]:
    saya, pic = _saya(acc), _pic(acc)
    m = _jalan(eskalasi.ubah, mid, req.model_dump(exclude_unset=True, exclude={"baris", "sidik"}), saya, pic,
               req.baris, req.sidik)
    return {"masalah": _keluar(m, saya, pic)}


# ---------- chat teman PIC (dibaca & dibalas di panel aplikasi, bukan di WhatsApp Web) ----------

def _nomor_teman(nomor: str) -> dict[str, str]:
    from ..sheets import normalize_nomor

    n = normalize_nomor(nomor)
    try:
        teman = next((k for k in eskalasi.kontak_pic() if k["nomor"] == n), None)
    except Exception as e:
        raise HTTPException(502, f"Tab Kontak PIC di sheet Broadcast tidak bisa dibaca: {e}") from e
    if not teman:
        raise HTTPException(403, "Nomor ini tidak ada di Kontak PIC.")
    return teman


def _percakapan(rows) -> dict[str, Any]:
    return {"pesan": [{"keluar": r.out, "teks": r.text, "waktu": r.waktu, "status": r.status, "kutipan": r.kutipan}
                      for r in rows if r.text][-40:],
            "dibaca_pada": schedule.now().strftime("%H.%M")}


@router.post("/teman/{nomor}/baca")
def baca_teman(nomor: str, _=Depends(wa_blast)) -> dict[str, Any]:
    t = _nomor_teman(nomor)
    chat._siap()
    _, rows = chat._jalan(lambda b: actions.read_thread(b, t["nomor"]), timeout=90)
    return _percakapan(rows)


class KirimTemanReq(BaseModel):
    pesan: str = Field(min_length=1, max_length=chat.MAKS_BALASAN)
    fasil: str = ""  # nomor fasil yang ditanyakan, untuk riwayat


@router.post("/teman/{nomor}/kirim")
def kirim_teman(nomor: str, req: KirimTemanReq, _=Depends(wa_blast)) -> dict[str, Any]:
    t = _nomor_teman(nomor)
    teks = req.pesan.strip()
    if not teks:
        raise HTTPException(400, "Pesan masih kosong.")
    chat._siap()

    def run(b):
        res = actions.reply(b, t["nomor"], teks)
        if res.status != "terkirim":
            return res, None
        b.page.wait_for_timeout(800)
        return res, actions.read_thread(b, t["nomor"])

    res, thread = chat._jalan(run, timeout=120)
    if res.status != "terkirim":
        raise HTTPException(502, f"Pesan belum terkirim: {res.keterangan}")
    if req.fasil:
        from ..sheets import normalize_nomor
        aktivitas.catat(normalize_nomor(req.fasil), "lk", f"Ditanyakan ke teman PIC {t['nama']}")
    return _percakapan(thread[1])
