"""LK Eskalasi: catat permasalahan sekolah binaan yang perlu dijawab tim terkait."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import aktivitas, db, eskalasi, schedule
from ..wa import actions
from . import chat
from ..access import Access
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
    try:
        eskalasi.sheet_id()
    except eskalasi.LinkBelumAda:
        return {"perlu_link": True, "opsi": None, "eskalasi": []}
    return {"perlu_link": False, "opsi": _jalan(eskalasi.opsi),
            "eskalasi": _jalan(eskalasi.daftar, pilih) if pilih else []}


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
