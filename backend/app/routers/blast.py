"""Blast: penerima (fasil, koordinator, kepala sekolah binaan), pengiriman dengan jeda & istirahat."""

import logging
import re
from collections import Counter
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import blast, db, kom_siklus, komunikasi, lk_baru, schedule, todo
from ..sheets import daftar_nomor, normalize_petugas
from ..wa.browser import worker
from ..wa.status import mask
from .deps import require_feature
from .lkb import _konteks, blok_hari_ini

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/blast")
wa_blast = require_feature("wa_blast")
MAKS_PESAN = 4000


def _terakhir_blast(nomor: set[str]) -> dict[str, str]:
    """{nomor: 'HH.MM'} blast terkirim terakhir hari ini."""
    hari = schedule.now().date().isoformat()
    out: dict[str, str] = {}
    for r in db.query("SELECT nomor, waktu FROM sends WHERE coba = 0 AND status = 'terkirim' "
                      "AND hash_pesan LIKE 'blast:%' AND substr(waktu, 1, 10) = ?", (hari,)):
        if r["nomor"] in nomor:
            out[r["nomor"]] = r["waktu"][11:16].replace(":", ".")
    return out


def _chat_hari_ini(nomor: set[str]) -> dict[str, str]:
    """{nomor: 'HH.MM'} chat keluar terakhir hari ini: kiriman aplikasi apa pun (blast, broadcast, balasan) atau
    chat yang terdeteksi di WhatsApp (mis. dikirim lewat HP)."""
    hari = schedule.now().date().isoformat()
    out: dict[str, str] = {}
    for r in db.query("SELECT nomor, waktu FROM sends WHERE coba = 0 AND status = 'terkirim' AND substr(waktu, 1, 10) = ? "
                      "UNION ALL SELECT nomor, waktu FROM aktivitas WHERE jenis IN ('balas', 'blast') "
                      "AND substr(waktu, 1, 10) = ?", (hari, hari)):
        if r["nomor"] in nomor:
            j = r["waktu"][11:16].replace(":", ".")
            out[r["nomor"]] = max(out.get(r["nomor"], ""), j)
    # Chat lewat HP: dari pendengar (jam tepat) atau terbaca di chat WA Web (jam tidak diketahui)
    try:
        from .. import kom_siklus
        from ..wa import pendengar

        pendengar._db()
        kom_siklus._db()
        for r in db.query("SELECT nomor, waktu FROM neo_pesan WHERE keluar = 1 AND substr(waktu, 1, 10) = ?", (hari,)):
            if r["nomor"] in nomor:
                out[r["nomor"]] = max(out.get(r["nomor"], ""), r["waktu"][11:16].replace(":", "."))
        for r in db.query("SELECT nomor FROM kom_mulai WHERE tanggal = ?", (hari,)):
            if r["nomor"] in nomor and r["nomor"] not in out:
                out[r["nomor"]] = "lewat HP"
    except Exception:
        log.exception("Chat lewat HP hari ini tidak terbaca")
    return out


def _todo_json(r: todo.Rencana, pelaku: str | None = None) -> list[dict[str, Any]]:
    # posisi: komponen papan LK (lp, lp_rev, mg, ...) supaya pesan bisa dipersempit ke satu komponen
    return [{"kode": t.kode, "judul": t.judul, "detail": t.detail, "pelaku": t.pelaku, "tunggu": t.tunggu,
             "posisi": komunikasi.posisi_todo(t.kode)}
            for t in r.todo if pelaku is None or t.pelaku == pelaku]


def _penerima(jenis: str) -> list[dict[str, Any]]:
    k = _konteks()
    rencana, hari, blok = k["rencana"], k["hari"], k["blok"]
    out: list[dict[str, Any]] = []
    if jenis == "fasil":
        for f in k["fasil"].values():
            r = komunikasi.ringkasan_fasil(f, rencana, k["logkom"], hari, blok, k["tag"], k["delta"])
            out.append({
                "kunci": f.kunci, "nama": f.nama, "nomor": f.nomor, "tersamar": mask(f.nomor) if f.nomor else "",
                "kelompok": r["kelompok"], "tag": r["tag"], "ptn": f.ptn, "koor": f.koor,
                "angkatan": sorted({s.angkatan for s in f.sekolah if s.angkatan}),
                "kab": sorted({s.kab for s in f.sekolah if s.kab}),
                "jumlah_sekolah": len(f.sekolah), "perlu": r["perlu"], "posisi": r["posisi"],
                "sekolah": [{"nama": s.nama, "npsn": s.npsn, "kab": s.kab, "angkatan": s.angkatan,
                             "tahap": rencana[s.npsn].tahap, "todo": _todo_json(rencana[s.npsn])}
                            for s in sorted(f.sekolah, key=lambda s: s.nama) if rencana[s.npsn].todo],
            })
    elif jenis == "koor":
        per: dict[str, dict[str, Any]] = {}
        ringkas = {f.kunci: komunikasi.ringkasan_fasil(f, rencana, k["logkom"], hari, blok, k["tag"], k["delta"])
                   for f in k["fasil"].values()}
        from .. import tahap as _tahap

        chat = komunikasi.peta_chat(_tahap.senin_iso())
        kom = {kunci: komunikasi.status_kom(r, chat.get(r["nomor"]) if r["nomor"] else None)
               for kunci, r in ringkas.items()}
        for f in k["fasil"].values():
            nomor = daftar_nomor(f.hp_koor)
            if not f.koor:
                continue
            kunci = "koor:" + normalize_petugas(f.koor)
            x = per.setdefault(kunci, {"kunci": kunci, "nama": f.koor, "nomor": nomor[0] if nomor else "",
                                       "ptn": f.ptn, "fasil": [], "kab": set(), "angkatan": set()})
            if not x["nomor"] and nomor:
                x["nomor"] = nomor[0]
            r = ringkas[f.kunci]
            x["fasil"].append({"nama": f.nama, "kelompok": r["kelompok"], "sekolah": len(f.sekolah),
                               "perlu": r["perlu"], "todo": r["todo"], "todo_fasil": r["todo_fasil"],
                               "posisi": r["posisi"],
                               "belum_ditelepon": r["belum_ditelepon"], "tanpa_progres": r["tanpa_progres"],
                               # sulit: tidak sampai / hanya dibaca (Log Komunikasi) atau chat minggu ini hanya dibaca
                               "sulit": r["perlu"] > 0 and (r["kelompok"] in ("perlu_telepon", "dibaca")
                                                            or r["belum_ditelepon"] or kom[f.kunci] in ("telepon", "dibaca"))})
            x["kab"].update(s.kab for s in f.sekolah if s.kab)
            x["angkatan"].update(s.angkatan for s in f.sekolah if s.angkatan)
        for x in per.values():
            x["tersamar"] = mask(x["nomor"]) if x["nomor"] else ""
            x["kab"], x["angkatan"] = sorted(x["kab"]), sorted(x["angkatan"])
            x["fasil"].sort(key=lambda f: f["nama"])
            x["jumlah_sekolah"] = sum(f["sekolah"] for f in x["fasil"])
            x["perlu"] = sum(f["perlu"] for f in x["fasil"])
            x["posisi"] = dict(sum((Counter(f["posisi"]) for f in x["fasil"]), Counter()))
            x["kelompok"] = "perlu_telepon" if any(f["sulit"] for f in x["fasil"]) else "terhubung"
            x["tag"] = []
            out.append(x)
    elif jenis == "sekolah":
        for s in k["sekolah"]:
            nomor = daftar_nomor(s.hp_kepsek)
            r = rencana[s.npsn]
            out.append({
                "kunci": s.npsn, "nama": s.nama, "kepsek": s.kepsek, "nomor": nomor[0] if nomor else "",
                "tersamar": mask(nomor[0]) if nomor else "", "fasil": s.fasil, "ptn": s.ptn, "koor": s.koor,
                "kelompok": "beres" if not r.todo else r.tahap, "tag": [], "angkatan": [s.angkatan] if s.angkatan else [],
                "kab": [s.kab] if s.kab else [], "jumlah_sekolah": 1, "perlu": 1 if r.todo else 0,
                "todo": _todo_json(r, "sekolah"), "tahap": r.tahap,
                "posisi": {k: 1 for k in {komunikasi.posisi_todo(x.kode) for x in r.todo} if k},
            })
    else:
        raise HTTPException(400, "Jenis penerima tidak dikenal.")
    nomor = {x["nomor"] for x in out if x["nomor"]}
    terakhir = _terakhir_blast(nomor)
    hari_ini = _chat_hari_ini(nomor)
    tgl = schedule.now().date()
    put = kom_siklus.putaran(tgl)
    for x in out:
        x["terakhir_blast"] = terakhir.get(x["nomor"], "")
        x["chat_hari_ini"] = hari_ini.get(x["nomor"], "")
        # status chat di putaran blast terakhir: dibalas | dibaca | terkirim | '' (tidak ikut putaran / belum di-chat)
        x["chat"] = kom_siklus.status_sekarang(x["nomor"], tgl, put) if x["nomor"] else ""
        if x["chat"] not in ("dibalas", "dibaca", "terkirim"):
            x["chat"] = "terkirim" if x["chat_hari_ini"] else ""
        x["punya_nomor"] = bool(x.pop("nomor"))
    out.sort(key=lambda x: x["nama"].casefold())
    return out


@router.get("/penerima")
def penerima(jenis: Literal["fasil", "koor", "sekolah"] = "fasil", _=Depends(wa_blast)) -> dict[str, Any]:
    daftar = _penerima(jenis)
    return {
        "jenis": jenis, "penerima": daftar,
        "petugas": komunikasi.petugas_saya(),
        "blok": blok_hari_ini(),
        "jumlah_tanpa_nomor": sum(1 for x in daftar if not x["punya_nomor"]),
        "tag": sorted({t for x in daftar for t in x["tag"]}, key=str.casefold),
        "kelompok": [{"kode": a, "label": b} for a, b, _ in komunikasi.KELOMPOK],
        "komponen": [{"kode": a, "label": b} for a, b, _ in komunikasi.POSISI],
        "angkatan": sorted({a for x in daftar for a in x["angkatan"]}),
        "kab": [k for k, _ in Counter(k for x in daftar for k in x["kab"]).most_common()],
    }


@router.get("/state")
def state(_=Depends(wa_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.snapshot(), "aturan": asdict(blast.aturan_tersimpan()),
            "wa_terbuka": worker.browser_open(), "wa_otomatis": komunikasi.wa_otomatis(),
            "jam_kirim": blast.mesin.di_jam_kirim(), "template": db.get_setting("blast_template_saya") or []}


class AturanIn(BaseModel):
    jeda_min: int = Field(20, ge=5, le=600)
    jeda_max: int = Field(45, ge=5, le=900)
    istirahat_setiap: int = Field(20, ge=0, le=200)
    istirahat_menit: int = Field(5, ge=1, le=60)


class Kirim(BaseModel):
    kunci: str = Field(min_length=1, max_length=200)
    pesan: str = Field(min_length=1, max_length=MAKS_PESAN)


class StartReq(BaseModel):
    jenis: Literal["fasil", "koor", "sekolah"]
    judul: str = Field("Blast", max_length=80)
    coba: bool = False
    aturan: AturanIn
    kirim: list[Kirim] = Field(min_length=1, max_length=1000)


def _nomor_penerima(jenis: str) -> dict[str, tuple[str, str]]:
    """{kunci: (nomor, nama)} dari LK, supaya nomor tidak pernah datang dari tampilan."""
    sekolah = komunikasi.sekolah_saya()
    out: dict[str, tuple[str, str]] = {}
    for s in sekolah:
        if jenis == "fasil":
            n = s.nomor_fasil()
            if n:
                out.setdefault(komunikasi.kunci_fasil(s), (n[0], s.fasil))
        elif jenis == "koor" and s.koor:
            n = daftar_nomor(s.hp_koor)
            k = "koor:" + normalize_petugas(s.koor)
            if n and k not in out:
                out[k] = (n[0], s.koor)
        elif jenis == "sekolah":
            n = daftar_nomor(s.hp_kepsek)
            if n:
                out[s.npsn] = (n[0], s.kepsek or f"Kepala {s.nama}")
    return out


@router.post("/start")
def start(req: StartReq, _=Depends(wa_blast)) -> dict[str, Any]:
    if not komunikasi.wa_otomatis():
        raise HTTPException(400, "WhatsApp otomatis sedang dimatikan. Nyalakan dulu di halaman LK untuk memakai Blast.")
    try:
        peta = _nomor_penerima(req.jenis)
    except lk_baru.LkError as e:
        raise HTTPException(400, str(e)) from e
    daftar, dilewati = [], []
    sudah = set()
    for x in req.kirim:
        nomor, nama = peta.get(x.kunci, ("", ""))
        if not nomor:
            dilewati.append(x.kunci)
            continue
        if nomor in sudah:
            continue
        sudah.add(nomor)
        teks = x.pesan.replace("\r\n", "\n").strip()
        if re.search(r"\{[a-z_]+\}", teks.replace("{salam}", "")):
            raise HTTPException(400, f"Pesan untuk {nama} masih berisi variabel yang belum terisi.")
        daftar.append(blast.Penerima(nomor=nomor, nama=nama, pesan=teks, jenis=req.jenis, kunci=x.kunci))
    try:
        snap = blast.mesin.start(daftar, blast.Aturan(**req.aturan.model_dump()), req.judul, req.coba)
    except blast.BlastError as e:
        raise HTTPException(400, str(e)) from e
    return {"state": snap, "dilewati": len(dilewati)}


class JedaReq(BaseModel):
    aktif: bool


@router.post("/jeda")
def jeda(req: JedaReq, _=Depends(wa_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.jeda(req.aktif)}


@router.post("/stop")
def stop(_=Depends(wa_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.stop()}


@router.get("/bc")
def template_bc(refresh: bool = False, _=Depends(wa_blast)) -> dict[str, Any]:
    """Template dari tab "BC - ..." sheet Draft Broadcast: pesan siap kirim per penerima milik petugas ini."""
    from .. import bc_draft

    if not bc_draft.sheet_id():
        return {"ada_link": False, "template": [], "error": ""}
    try:
        fasil = komunikasi.fasil_saya()
        kunci_nama = {
            "fasil": {normalize_petugas(f.nama): f.kunci for f in fasil.values() if f.nama},
            "koor": {normalize_petugas(f.koor): "koor:" + normalize_petugas(f.koor) for f in fasil.values() if f.koor},
        }
        return {"ada_link": True, "template": bc_draft.template(komunikasi.petugas_saya(), kunci_nama, refresh),
                "error": ""}
    except (bc_draft.BcError, lk_baru.LkError) as e:
        return {"ada_link": True, "template": [], "error": str(e)}


class TemplateSaya(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    judul: str = Field(min_length=1, max_length=60)
    jenis: Literal["fasil", "koor", "sekolah"]
    teks: str = Field(min_length=1, max_length=MAKS_PESAN)


class TemplateReq(BaseModel):
    template: list[TemplateSaya] = Field(default_factory=list, max_length=30)


@router.post("/template")
def simpan_template(req: TemplateReq, _=Depends(wa_blast)) -> dict[str, Any]:
    db.set_setting("blast_template_saya", [t.model_dump() for t in req.template])
    return {"template": db.get_setting("blast_template_saya")}

