"""Halaman Rekap: posisi sekolah binaan petugas (prioritas, chat, isian LK) per fasil."""

from collections import Counter
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import bimtek, db, schedule, store, tahap
from ..sheets import filter_petugas, nomor_key, nomor_lk, normalize_petugas, read_broadcast, read_lk
from ..wa.status import mask
from .deps import require_feature

from ..sheets import week_aktif  # noqa: E402

router = APIRouter(prefix="/api")
wa_blast = require_feature("wa_blast")

PRIO = {"prioritas 1": "p1", "prioritas 2": "p2", "prioritas 3": "p3", "selesai": "selesai"}


def _status_chat(k: dict | None, manual: dict) -> str:
    """Status kontak minggu ini: belum | gagal | terkirim | dibaca | dibalas"""
    k = k or {}
    nilai = lambda kode: manual.get(kode, {}).get("nilai")  # noqa: E731
    if nilai("dibalas") or (k.get("dibalas") and nilai("dibalas") is None):
        return "dibalas"
    if nilai("dibaca") or (k.get("dibaca") and nilai("dibaca") is None):
        return "dibaca"
    if nilai("terkirim") or (k.get("terkirim") and nilai("terkirim") is None):
        return "terkirim"
    return "gagal" if k.get("gagal") else "belum"


def _tahap_kini(t: list[dict[str, Any]], perlu: int, k: dict | None) -> str:
    """Posisi fasil di papan tahap minggu ini: tahap terjauh yang sudah tercapai."""
    if not perlu:
        return "selesai"
    capai = [x["kode"] for x in t if x["selesai"]]
    if not capai:
        return "gagal" if (k or {}).get("gagal") else "belum"
    urut = [x["kode"] for x in t]
    return max(capai, key=urut.index)


def _alur(rows: list[dict[str, Any]], k: str) -> dict[str, int]:
    """Fasil yang punya sekolah prioritas k (semua = punya sekolah yang belum selesai), dan kemajuannya minggu ini."""
    f = [r for r in rows if (r["isian_perlu"] > 0 if k == "semua" else r[k] > 0)]
    return {
        "fasil": len(f),
        "sekolah": sum(r["isian_perlu"] if k == "semua" else r[k] for r in f),
        "dihubungi": sum(1 for r in f if r["chat"] in ("terkirim", "dibaca", "dibalas")),
        "membalas": sum(1 for r in f if r["chat"] == "dibalas"),
        "lk_lengkap": sum(1 for r in f if r["isian_perlu"] and r["isian_lengkap"] >= r["isian_perlu"]),
    }


@router.get("/rekap")
def rekap(_=Depends(wa_blast)) -> dict[str, Any]:
    petugas = db.get_setting("nama_petugas") or ""
    week = week_aktif()
    try:
        bc = filter_petugas(read_broadcast(), petugas)
        lk = [s for s in read_lk(week) if normalize_petugas(s.petugas) == normalize_petugas(petugas)]
    except Exception as e:
        raise HTTPException(502, f"Sheet Broadcast/LK tidak bisa dibaca: {e}") from e

    blok = tahap.blok_hari_ini()
    bc_by_key = {nomor_key(r.nomor): r for r in bc if r.nomor}

    # Kelompokkan sekolah per fasil (kunci = 9 digit terakhir nomor pertama di LK)
    fasil: dict[str, dict[str, Any]] = {}
    for s in lk:
        nomors = nomor_lk(s)
        key = nomor_key(nomors[0]) if nomors else f"nama:{s.fasil}"
        f = fasil.setdefault(key, {"nama": s.fasil, "nomor": nomors[0] if nomors else "", "sekolah": []})
        f["sekolah"].append(s)
    for key, r in bc_by_key.items():  # fasil Broadcast yang tidak ada di LK tetap tampil
        fasil.setdefault(key, {"nama": r.nama_fasil, "nomor": r.nomor, "sekolah": []})

    kontak = tahap.kontak_minggu()
    manual = store.tahap_all()
    from .. import aktivitas
    terakhir = aktivitas.terakhir_sejak(tahap.senin_iso())
    perlu_balas = {x["nomor"] for x in store.perlu_dibalas(tahap.senin_iso())}
    bt = bimtek.peta()

    rows = []
    for key, f in fasil.items():
        bcr = bc_by_key.get(key)
        nomor = bcr.nomor if bcr else f["nomor"]
        sekolah = f["sekolah"]
        prio = Counter(PRIO.get(s.prioritas.strip().lower(), "lain") for s in sekolah)
        perlu = [s for s in sekolah if tahap.perlu_isian(s)]
        man = tahap.manual_minggu(manual.get(nomor, {}))
        t = tahap.hitung(nomor, sekolah, kontak.get(nomor), man, blok)
        rows.append({
            "nama": bcr.nama_fasil if bcr else f["nama"],
            "nomor": nomor,
            "nomor_tersamar": mask(nomor),
            "di_broadcast": bcr is not None,
            "sekolah": len(sekolah),
            "p1": prio["p1"], "p2": prio["p2"], "p3": prio["p3"], "selesai": prio["selesai"],
            "p1_progres_50": sum(1 for s in sekolah if PRIO.get(s.prioritas.strip().lower()) == "p1"
                                 and s.progres is not None and s.progres >= 50),
            "chat": _status_chat(kontak.get(nomor), man),
            "isian_lengkap": sum(1 for s in perlu if tahap.sekolah_lengkap(s, blok)),
            "isian_perlu": len(perlu),
            "tahap": [x["selesai"] for x in t],
            "tahap_kini": _tahap_kini(t, len(perlu), kontak.get(nomor)),
            "terakhir": terakhir.get(nomor, {}).get("waktu", ""),
            "terakhir_label": terakhir.get(nomor, {}).get("label", ""),
            "perlu_balas": nomor in perlu_balas,
            "bimtek": sum(1 for s in sekolah if bimtek.tanda(s, bt)),
        })
    rows.sort(key=lambda r: (-r["p1"], r["nama"].casefold()))

    prio_all = Counter(PRIO.get(s.prioritas.strip().lower(), "lain") for s in lk)
    perlu_all = [s for s in lk if tahap.perlu_isian(s)]
    dihubungi = {r["nomor"] for r in rows if r["chat"] in ("terkirim", "dibaca", "dibalas")}
    p1_rows = [r for r in rows if r["p1"]]
    kom = Counter((s.komunikasi or "Belum diisi") for s in perlu_all)
    luar = [r for r in rows if not r["di_broadcast"]]

    return {
        "tanggal_panjang": schedule.tanggal_panjang(schedule.now().date()),
        "week": week,
        "blok": {"no": blok, "label": tahap.BLOK_LABEL[blok], "kolom": tahap.blok_kolom_label(blok)},
        "sekolah": {"total": len(lk), "p1": prio_all["p1"], "p2": prio_all["p2"], "p3": prio_all["p3"],
                    "selesai": prio_all["selesai"]},
        "fasil_total": len(rows),
        "p1": {
            "sekolah": prio_all["p1"],
            "fasil": len(p1_rows),
            "fasil_dihubungi": sum(1 for r in p1_rows if r["nomor"] in dihubungi),
            "fasil_membalas": sum(1 for r in p1_rows if r["chat"] == "dibalas"),
            "fasil_lk_lengkap": sum(1 for r in p1_rows if r["isian_perlu"] and r["isian_lengkap"] >= r["isian_perlu"]),
            "sekolah_dihubungi": sum(r["p1"] for r in p1_rows if r["nomor"] in dihubungi),
        },
        "isian": {
            "perlu": len(perlu_all),
            "blok": [
                {"no": b, "label": tahap.BLOK_LABEL[b], "kolom": tahap.blok_kolom_label(b),
                 "lengkap": sum(1 for s in perlu_all if tahap.sekolah_lengkap(s, b))}
                for b in (1, 2)
            ],
            "komunikasi": [{"label": k, "jumlah": v} for k, v in kom.most_common()],
        },
        "alur": {
            k: _alur(rows, k) for k in ("semua", "p1", "p2", "p3")
        },
        "luar_broadcast": {
            "fasil": len(luar),
            "sekolah": sum(r["sekolah"] for r in luar),
            "perlu": sum(r["isian_perlu"] for r in luar),
            "p1_sekolah": sum(r["p1"] for r in luar),
            "p1_progres_50": sum(r["p1_progres_50"] for r in luar),
            "dihubungi": sum(1 for r in luar if r["chat"] in ("terkirim", "dibaca", "dibalas")),
        },
        "bimtek": {
            **({k: v for k, v in (bimtek.info() or {}).items() if k != "sekolah"}),
            "ada": bool(bt),
            "fasil": sum(1 for r in rows if r["bimtek"]),
            "sekolah": sum(r["bimtek"] for r in rows),
        },
        "fasil": rows,
    }


@router.get("/perubahan")
def daftar_perubahan(batas: int = 50, tanggal: str | None = None, _=Depends(wa_blast)) -> dict[str, Any]:
    from .. import perubahan

    if tanggal:
        try:
            date.fromisoformat(tanggal)
        except ValueError as e:
            raise HTTPException(400, "Format tanggal YYYY-MM-DD.") from e
    return {"items": perubahan.daftar(max(1, min(batas, 200)), tanggal)}


@router.get("/perubahan/kalender")
def kalender_perubahan(bulan: str | None = None, _=Depends(wa_blast)) -> dict[str, Any]:
    """`bulan` = YYYY-MM (bawaan: bulan ini)."""
    from .. import perubahan

    try:
        awal = date.fromisoformat(f"{bulan}-01") if bulan else schedule.now().date().replace(day=1)
    except ValueError as e:
        raise HTTPException(400, "Format bulan YYYY-MM.") from e
    return perubahan.kalender(awal)
