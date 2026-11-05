"""Dashboard: distribusi binaan, capaian komponen, tren per cutoff, dan frekuensi komunikasi.

Petugas melihat datanya sendiri. Admin bisa memilih PIC lain atau "semua" (nasional).
"""

from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import cutoff_baru, komunikasi, lk_baru, schedule, todo
from ..access import Access
from ..sheets import normalize_petugas
from .deps import require_access
from .lkb import _jalan, blok_hari_ini

router = APIRouter(prefix="/api/dashboard")

KOLOM_TREN = {
    "lp": "Lap. Pendahuluan terkirim (%)", "lp_rev": "Lap. Pendahuluan direviu (%)",
    "progres": "Progres fisik rata-rata (%)", "mg": "Lap. Mingguan lengkap (%)", "mg_rev": "Reviu Mingguan (%)",
    "bl": "Lap. Bulanan lengkap (%)", "bl_rev": "Reviu Bulanan (%)", "l50": "Lap. 50% terunggah (%)",
    "l50_rev": "Reviu Lap. 50% (%)", "l100": "Lap. 100% terunggah (%)",
}


def _angka(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _capaian(sekolah: list[lk_baru.Sekolah]) -> list[dict[str, Any]]:
    out = []
    st = [todo.semua_status(s) for s in sekolah]
    for k in lk_baru.KOMPONEN:
        c = Counter(x[k.kode].status for x in st)
        a = sum(x[k.kode].rasio[0] for x in st if x[k.kode].rasio)
        b = sum(x[k.kode].rasio[1] for x in st if x[k.kode].rasio)
        relevan = c["selesai"] + c["belum"]
        out.append({"kode": k.kode, "label": k.label, "tahap": k.tahap, "pelaku": k.pelaku,
                    "selesai": c["selesai"], "belum": c["belum"], "due": c["due"], "kosong": c["kosong"],
                    "tanpa_data": c["tanpa_data"], "relevan": relevan,
                    "persen": round(c["selesai"] / relevan * 100, 1) if relevan else None,
                    "rasio": [a, b] if b else None})
    return out


def _distribusi(sekolah: list[lk_baru.Sekolah]) -> dict[str, Any]:
    def top(f, n=8):
        c = Counter(f(s) or "(kosong)" for s in sekolah)
        return [{"nama": k, "jumlah": v} for k, v in c.most_common(n)]

    fasil = {komunikasi.kunci_fasil(s) for s in sekolah}
    koor = {normalize_petugas(s.koor) for s in sekolah if s.koor}
    per_fasil = Counter(komunikasi.kunci_fasil(s) for s in sekolah)
    return {
        "sekolah": len(sekolah), "fasil": len(fasil), "koor": len(koor),
        "jml_ptn": len({s.ptn for s in sekolah if s.ptn}), "jml_kab": len({s.kab for s in sekolah if s.kab}),
        "rata_sekolah_per_fasil": round(len(sekolah) / len(fasil), 1) if fasil else 0,
        "maks_sekolah_per_fasil": max(per_fasil.values()) if per_fasil else 0,
        "angkatan": [{"nama": f"Angkatan {k}" if k != "(kosong)" else k, "jumlah": v}
                     for k, v in sorted(Counter(s.angkatan or "(kosong)" for s in sekolah).items())],
        "provinsi": top(lambda s: s.provinsi.replace("Prov. ", "")),
        "kab": top(lambda s: s.kab),
        "ptn": top(lambda s: s.ptn),
        "tanpa_hp_fasil": sum(1 for s in sekolah if not s.nomor_fasil()),
    }


def _komunikasi(sekolah: list[lk_baru.Sekolah], logkom: lk_baru.LogKom) -> dict[str, Any]:
    fasil = komunikasi.kelompokkan(sekolah)
    tanggal = sorted(logkom.tanggal)
    hari = schedule.now().date().isoformat()
    tampil = [d for d in tanggal if d <= hari][-10:] or tanggal[:5]
    per_hari = []
    total = Counter()
    for d in tampil:
        c = Counter()
        for f in fasil.values():
            k = komunikasi.kode_fasil(f, logkom).get(d, "")
            c[k or "-"] += 1
        total.update({k: v for k, v in c.items() if k != "-"})
        per_hari.append({"tanggal": d, "kode": dict(c), "tercatat": sum(v for k, v in c.items() if k != "-"),
                         "fasil": len(fasil)})
    return {"hari": per_hari, "total": dict(total), "kode": komunikasi.kode_label()}


def _tren(pic: str | None) -> dict[str, Any]:
    rows = cutoff_baru.baca_log_pic()
    cut = list(dict.fromkeys(r["Cutoff"] for r in rows if r.get("Cutoff")))
    per: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if pic and normalize_petugas(str(r.get("PIC", ""))) != normalize_petugas(pic):
            continue
        for kode, kol in KOLOM_TREN.items():
            v = _angka(r.get(kol))
            if v is not None:
                per[r["Cutoff"]][kode].append(v)
    seri = []
    for kode, kol in KOLOM_TREN.items():
        seri.append({"kode": kode, "label": kol.replace(" (%)", ""),
                     "nilai": [round(sum(per[c][kode]) / len(per[c][kode]), 1) if per[c][kode] else None for c in cut]})
    nasional = {}
    if cut:
        akhir = [r for r in rows if r.get("Cutoff") == cut[-1]]
        for kode, kol in KOLOM_TREN.items():
            v = [x for x in (_angka(r.get(kol)) for r in akhir) if x is not None]
            nasional[kode] = round(sum(v) / len(v), 1) if v else None
    return {"cutoff": cut, "seri": seri, "rata_pic": nasional}


@router.get("")
def dashboard(pic: str = Query("", max_length=120), acc: Access = Depends(require_access)) -> dict[str, Any]:
    saya = komunikasi.petugas_saya()
    if pic and normalize_petugas(pic) != normalize_petugas(saya) and not acc.admin:
        raise HTTPException(403, "Hanya admin yang bisa melihat dashboard PIC lain.")
    target = pic or saya
    nasional = target == "__semua__"
    if nasional:
        sekolah = _jalan(lk_baru.baca_semua)
    else:
        sekolah = _jalan(lk_baru.baca_petugas, target)
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    rencana = {s.npsn: todo.rencana(s) for s in sekolah}
    blok = blok_hari_ini()
    tahap = Counter(r.tahap for r in rencana.values())
    fokus = Counter(r.fokus.judul for r in rencana.values() if r.fokus)
    perlu = [s for s in sekolah if rencana[s.npsn].todo]
    pelaku = Counter(t.pelaku for r in rencana.values() for t in r.todo)
    tunggu = [t.tunggu for r in rencana.values() for t in r.todo if t.tunggu]
    fasil_tabel = []
    if not nasional:
        fasil = komunikasi.kelompokkan(sekolah)
        hari = schedule.now().date().isoformat()
        for f in fasil.values():
            r = komunikasi.ringkasan_fasil(f, rencana, logkom, hari, blok, {}, {})
            kode = komunikasi.kode_fasil(f, logkom)
            c = Counter(kode.values())
            fasil_tabel.append({"nama": f.nama, "sekolah": r["sekolah"], "perlu": r["perlu"], "lengkap": r["lengkap"],
                                "todo": r["todo"], "todo_fasil": r["todo_fasil"], "kelompok": r["kelompok"],
                                "terhubung": c["T"] + c["TP"], "lambat": c["T1"] + c["T2"],
                                "tidak": c["R"] + c["C"] + c["N"], "telepon": c["TP"],
                                "hari_tercatat": len(kode), "tunggu_maks": r["tunggu_maks"]})
        fasil_tabel.sort(key=lambda x: (-x["todo"], x["nama"]))
    out = {
        "pic": "Nasional" if nasional else target,
        "nasional": nasional,
        "week": _jalan(lk_baru.week_aktif),
        "cutoff": komunikasi.label_cutoff(),
        "dibuat": schedule.now().strftime("%d/%m %H.%M"),
        "distribusi": _distribusi(sekolah),
        "capaian": _capaian(sekolah),
        "tahap": [{"kode": t, "jumlah": tahap.get(t, 0)} for t in ("pendahuluan", "berkala", "l50", "l100", "selesai")],
        "fokus": [{"judul": j, "jumlah": v} for j, v in fokus.most_common(8)],
        "todo": {"sekolah_perlu": len(perlu), "sekolah_beres": len(sekolah) - len(perlu),
                 "item": sum(pelaku.values()), "oleh_sekolah": pelaku["sekolah"], "oleh_fasil": pelaku["fasil"],
                 "lengkap": sum(1 for s in perlu if todo.lengkap(s, rencana[s.npsn], blok)),
                 "tunggu_rata": round(sum(tunggu) / len(tunggu), 1) if tunggu else None,
                 "tunggu_lewat3": sum(1 for x in tunggu if x > 3)},
        "komunikasi": _komunikasi(sekolah, logkom),
        "tren": _tren(None if nasional else target),
        "fasil": fasil_tabel,
    }
    if acc.admin:
        try:
            out["pilihan_pic"] = [p["nama"] for p in lk_baru.daftar_petugas()]
        except Exception:
            out["pilihan_pic"] = []
    return out

