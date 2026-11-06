"""Blast admin: kirim pesan dari nomor WhatsApp admin ke seluruh koordinator, fasil, atau kepala sekolah (nasional).

Hanya untuk akun dengan fitur 'blast_admin' di sheet Akses. Penerima dipilih lewat filter (PIC, PTN, provinsi,
angkatan); pesan dirakit di sini dari template, jadi nomor dan isi tidak pernah datang dari tampilan. Memakai mesin
kirim Blast yang sama (jeda acak, istirahat, berhenti bila 2 gagal beruntun atau di luar jam kirim). Bila berhenti di
tengah jalan, Mulai lagi dengan pesan yang sama melewati penerima yang sudah menerimanya.
"""

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import blast, db, komunikasi, lk_baru
from ..sheets import daftar_nomor, message_hash, normalize_petugas
from ..wa.browser import worker
from .deps import require_feature
from .lkb import _jalan

router = APIRouter(prefix="/api/blast-admin")
admin_blast = require_feature("blast_admin")
MAKS_PESAN = 4000
KONFIRMASI = "risiko ditanggung sendiri"
Jenis = Literal["koor", "fasil", "sekolah"]

VARIABEL = {
    "koor": [("{salam}", "Salam sesuai jam"), ("{nama}", "Nama koordinator"), ("{ptn}", "PTN"),
             ("{jumlah_fasil}", "Jumlah fasil binaan"), ("{jumlah_sekolah}", "Jumlah sekolah binaan")],
    "fasil": [("{salam}", "Salam sesuai jam"), ("{nama}", "Nama fasil"), ("{ptn}", "PTN"),
              ("{koor}", "Nama koordinator"), ("{pic}", "Nama PIC"), ("{jumlah_sekolah}", "Jumlah sekolah binaan")],
    "sekolah": [("{salam}", "Salam sesuai jam"), ("{nama}", "Nama kepala sekolah"), ("{sekolah}", "Nama sekolah"),
                ("{fasil}", "Nama fasil"), ("{ptn}", "PTN"), ("{pic}", "Nama PIC")],
}


@dataclass
class Target:
    kunci: str
    nama: str
    nomor: str
    nilai: dict[str, str]
    pic: set[str] = field(default_factory=set)
    ptn: set[str] = field(default_factory=set)
    provinsi: set[str] = field(default_factory=set)
    angkatan: set[str] = field(default_factory=set)


def _prov(v: str) -> str:
    return v.replace("Prov. ", "").strip()


def _ikut(t: Target, s: lk_baru.Sekolah) -> None:
    if s.petugas.strip():
        t.pic.add(s.petugas.strip())
    if s.ptn:
        t.ptn.add(s.ptn)
    if s.provinsi:
        t.provinsi.add(_prov(s.provinsi))
    if s.angkatan:
        t.angkatan.add(s.angkatan)


def target(jenis: str, sekolah: list[lk_baru.Sekolah]) -> list[Target]:
    out: dict[str, Target] = {}
    if jenis == "sekolah":
        for s in sekolah:
            n = daftar_nomor(s.hp_kepsek)
            t = out.setdefault(s.npsn, Target(s.npsn, s.kepsek or f"Kepala {s.nama}", n[0] if n else "", {
                "nama": s.kepsek or "Bapak/Ibu Kepala Sekolah", "sekolah": s.nama, "fasil": s.fasil, "ptn": s.ptn,
                "pic": s.petugas.strip()}))
            _ikut(t, s)
    elif jenis == "fasil":
        for f in komunikasi.kelompokkan(sekolah).values():
            pic = sorted({s.petugas.strip() for s in f.sekolah if s.petugas.strip()})
            t = out[f.kunci] = Target(f.kunci, f.nama, f.nomor, {
                "nama": f.nama, "ptn": f.ptn, "koor": f.koor, "pic": ", ".join(pic),
                "jumlah_sekolah": str(len(f.sekolah))})
            for s in f.sekolah:
                _ikut(t, s)
    elif jenis == "koor":
        fasil: dict[str, set[str]] = {}
        jml: Counter[str] = Counter()
        for s in sekolah:
            if not s.koor:
                continue
            k = "koor:" + normalize_petugas(s.koor)
            n = daftar_nomor(s.hp_koor)
            t = out.get(k)
            if not t:
                t = out[k] = Target(k, s.koor, n[0] if n else "", {"nama": s.koor, "ptn": s.ptn})
            elif not t.nomor and n:
                t.nomor = n[0]
            fasil.setdefault(k, set()).add(komunikasi.kunci_fasil(s))
            jml[k] += 1
            _ikut(t, s)
        for k, t in out.items():
            t.nilai["jumlah_fasil"] = str(len(fasil.get(k, ())))
            t.nilai["jumlah_sekolah"] = str(jml[k])
    else:
        raise HTTPException(400, "Jenis penerima tidak dikenal.")
    return sorted(out.values(), key=lambda t: t.nama.casefold())


class Saring(BaseModel):
    pic: list[str] = Field(default_factory=list, max_length=100)
    ptn: list[str] = Field(default_factory=list, max_length=100)
    provinsi: list[str] = Field(default_factory=list, max_length=100)
    angkatan: list[str] = Field(default_factory=list, max_length=20)


def saring(ts: list[Target], f: Saring) -> list[Target]:
    def cocok(nilai: set[str], pilih: list[str]) -> bool:
        return not pilih or bool(nilai & set(pilih))

    return [t for t in ts if cocok(t.pic, f.pic) and cocok(t.ptn, f.ptn) and cocok(t.provinsi, f.provinsi)
            and cocok(t.angkatan, f.angkatan)]


def rakit(teks: str, t: Target) -> str:
    """Isi variabel kecuali {salam} (diisi saat dikirim sesuai jam)."""
    out = teks.replace("\r\n", "\n").strip()
    for k, v in t.nilai.items():
        out = out.replace("{" + k + "}", v or "")
    return out


def _sisa_variabel(teks: str) -> list[str]:
    return sorted(set(re.findall(r"\{[a-z_]+\}", teks.replace("{salam}", ""))))


def _sudah_terkirim(nomor_hash: list[tuple[str, str]]) -> set[str]:
    """Nomor yang sudah menerima pesan yang sama persis (untuk melanjutkan blast yang terhenti)."""
    if not nomor_hash:
        return set()
    hs = {h for _, h in nomor_hash}
    sudah = set()
    for r in db.query("SELECT nomor, hash_pesan FROM sends WHERE coba = 0 AND status = 'terkirim' "
                      "AND hash_pesan LIKE 'blast:%'"):
        if r["hash_pesan"] in hs:
            sudah.add((r["nomor"], r["hash_pesan"]))
    return {n for n, h in nomor_hash if (n, h) in sudah}


def _semua() -> list[lk_baru.Sekolah]:
    return _jalan(lk_baru.baca_semua)


@router.get("/opsi")
def opsi(_=Depends(admin_blast)) -> dict[str, Any]:
    sekolah = _semua()
    jumlah = {j: len(target(j, sekolah)) for j in ("koor", "fasil", "sekolah")}
    return {
        "jumlah": jumlah,
        "pic": sorted({s.petugas.strip() for s in sekolah if s.petugas.strip()}, key=str.casefold),
        "ptn": sorted({s.ptn for s in sekolah if s.ptn}, key=str.casefold),
        "provinsi": sorted({_prov(s.provinsi) for s in sekolah if s.provinsi}, key=str.casefold),
        "angkatan": sorted({s.angkatan for s in sekolah if s.angkatan}),
        "variabel": {j: [{"kode": k, "arti": a} for k, a in v] for j, v in VARIABEL.items()},
        "konfirmasi": KONFIRMASI,
    }


class HitungReq(BaseModel):
    jenis: Jenis
    saring: Saring = Field(default_factory=Saring)
    pesan: str = Field("", max_length=MAKS_PESAN)


@router.post("/hitung")
def hitung(req: HitungReq, _=Depends(admin_blast)) -> dict[str, Any]:
    ts = saring(target(req.jenis, _semua()), req.saring)
    ada = [t for t in ts if t.nomor]
    unik = {t.nomor for t in ada}
    out: dict[str, Any] = {"jumlah": len(ts), "punya_nomor": len(ada), "tanpa_nomor": len(ts) - len(ada),
                           "nomor_unik": len(unik), "contoh_nama": [t.nama for t in ada[:6]]}
    if req.pesan.strip() and ada:
        out["contoh"] = [{"nama": t.nama, "pesan": rakit(req.pesan, t)} for t in ada[:3]]
        out["sisa_variabel"] = _sisa_variabel(rakit(req.pesan, ada[0]))
        hs = [(t.nomor, blast.AWALAN + message_hash(rakit(req.pesan, t))) for t in ada]
        out["sudah_terkirim"] = len(_sudah_terkirim(hs))
    return out


class AturanIn(BaseModel):
    jeda_min: int = Field(20, ge=5, le=600)
    jeda_max: int = Field(45, ge=5, le=900)
    istirahat_setiap: int = Field(20, ge=0, le=200)
    istirahat_menit: int = Field(5, ge=1, le=60)


class StartReq(HitungReq):
    judul: str = Field("Blast admin", max_length=80)
    coba: bool = False
    lewati_terkirim: bool = True
    aturan: AturanIn = Field(default_factory=AturanIn)
    konfirmasi: str = ""


@router.post("/start")
def start(req: StartReq, _=Depends(admin_blast)) -> dict[str, Any]:
    if not req.pesan.strip():
        raise HTTPException(400, "Pesan masih kosong.")
    if not req.coba and req.konfirmasi.strip().casefold() != KONFIRMASI:
        raise HTTPException(400, f'Ketik "{KONFIRMASI}" untuk mulai mengirim.')
    if not komunikasi.wa_otomatis():
        raise HTTPException(400, "WhatsApp otomatis sedang dimatikan. Nyalakan dulu di halaman LK untuk memakai Blast.")
    ts = [t for t in saring(target(req.jenis, _semua()), req.saring) if t.nomor]
    daftar, sudah = [], set()
    for t in ts:
        if t.nomor in sudah:
            continue
        sudah.add(t.nomor)
        teks = rakit(req.pesan, t)
        sisa = _sisa_variabel(teks)
        if sisa:
            raise HTTPException(400, f"Variabel {', '.join(sisa)} tidak dikenal untuk penerima ini.")
        daftar.append(blast.Penerima(nomor=t.nomor, nama=t.nama, pesan=teks, jenis=req.jenis, kunci=t.kunci))
    dilewati = 0
    if req.lewati_terkirim and not req.coba:
        lewat = _sudah_terkirim([(p.nomor, blast.AWALAN + message_hash(p.pesan)) for p in daftar])
        dilewati = len(lewat)
        daftar = [p for p in daftar if p.nomor not in lewat]
    if not daftar:
        raise HTTPException(400, "Tidak ada penerima yang perlu dikirimi (semua tanpa nomor atau sudah menerima pesan ini).")
    try:
        snap = blast.mesin.start(daftar, blast.Aturan(**req.aturan.model_dump()), req.judul, req.coba)
    except blast.BlastError as e:
        raise HTTPException(400, str(e)) from e
    return {"state": snap, "dilewati": dilewati, "jumlah": len(daftar)}


@router.get("/state")
def state(_=Depends(admin_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.snapshot(), "aturan": asdict(blast.aturan_tersimpan()),
            "wa_terbuka": worker.browser_open(), "wa_otomatis": komunikasi.wa_otomatis(),
            "jam_kirim": blast.mesin.di_jam_kirim()}


class JedaReq(BaseModel):
    aktif: bool


@router.post("/jeda")
def jeda(req: JedaReq, _=Depends(admin_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.jeda(req.aktif)}


@router.post("/stop")
def stop(_=Depends(admin_blast)) -> dict[str, Any]:
    return {"state": blast.mesin.stop()}
