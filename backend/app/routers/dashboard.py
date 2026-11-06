"""Dashboard: distribusi binaan, capaian komponen, tren per cutoff, dan frekuensi komunikasi.

Semua angka dihitung dari isi komponen LK dan Log Komunikasi (bukan dari to-do; to-do hanya dipakai di halaman LK).
Hasil hitungan disimpan dan dihitung ulang di latar tiap 10 menit, jadi halaman langsung terbuka.
Petugas melihat datanya sendiri. Admin bisa memilih PIC lain atau "semua" (nasional).
"""

import logging
import threading
import time
from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import cutoff_baru, komunikasi, lk_baru, schedule, todo
from ..access import Access
from ..sheets import normalize_petugas
from .deps import require_access
from .lkb import _jalan

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard")

SEGAR_DETIK = 600          # hitung ulang di latar bila hasil lebih tua dari ini
DIPANTAU_DETIK = 3 * 3600  # dashboard yang dibuka dalam 3 jam terakhir ikut dihitung ulang berkala
NASIONAL = "__semua__"

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


def _capaian(st: list[dict[str, todo.Status]]) -> list[dict[str, Any]]:
    out = []
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


def _progres(st: list[dict[str, todo.Status]]) -> dict[str, Any]:
    p = [x["progres"].persen for x in st if x["progres"].persen is not None]
    ember = [("0–24%", 0, 25), ("25–49%", 25, 50), ("50–74%", 50, 75), ("75–99%", 75, 100), ("100%", 100, 101)]
    return {"rata": round(sum(p) / len(p), 1) if p else None, "ada": len(p),
            "sebaran": [{"nama": n, "jumlah": sum(1 for v in p if a <= v < b)} for n, a, b in ember]}


def _reviu(sekolah: list[lk_baru.Sekolah], st: list[dict[str, todo.Status]]) -> dict[str, Any]:
    """Waktu tunggu reviu dari kolom LK, hanya untuk komponen reviu yang belum selesai."""
    per: dict[str, list[float]] = defaultdict(list)
    for s, x in zip(sekolah, st):
        for kode, hari in s.tunggu.items():
            if hari and x.get(kode) and x[kode].status == "belum":
                per[kode].append(hari)
    semua = [v for xs in per.values() for v in xs]
    return {"rata": round(sum(semua) / len(semua), 1) if semua else None,
            "lewat3": sum(1 for v in semua if v > 3), "menunggu": len(semua),
            "komponen": [{"label": lk_baru.KOMP[k].label, "menunggu": len(v), "rata": round(sum(v) / len(v), 1),
                          "lewat3": sum(1 for x in v if x > 3)} for k, v in per.items()]}


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


def _komunikasi(fasil: dict[str, komunikasi.Fasil], logkom: lk_baru.LogKom) -> dict[str, Any]:
    tanggal = sorted(logkom.tanggal)
    hari = schedule.now().date().isoformat()
    tampil = [d for d in tanggal if d <= hari][-10:] or tanggal[:5]
    per_hari = []
    total: Counter[str] = Counter()
    kode_f = {k: komunikasi.kode_fasil(f, logkom) for k, f in fasil.items()}
    for d in tampil:
        c: Counter[str] = Counter()
        for k in fasil:
            c[kode_f[k].get(d, "") or "-"] += 1
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


def _tabel_fasil(fasil: dict[str, komunikasi.Fasil], status: dict[str, dict[str, todo.Status]],
                 logkom: lk_baru.LogKom) -> list[dict[str, Any]]:
    hari = schedule.now().date().isoformat()
    out = []
    for f in fasil.values():
        st = [status[s.npsn] for s in f.sekolah]
        belum = sum(1 for x in st for v in x.values() if v.status == "belum")
        lengkap = sum(1 for x in st if not any(v.status == "belum" for v in x.values()))
        p = [x["progres"].persen for x in st if x["progres"].persen is not None]
        kode = komunikasi.kode_fasil(f, logkom)
        c = Counter(kode.values())
        tunggu = [h for s in f.sekolah for k, h in s.tunggu.items() if h and status[s.npsn][k].status == "belum"]
        out.append({"nama": f.nama, "ptn": f.ptn, "sekolah": len(f.sekolah), "lengkap": lengkap, "belum": belum,
                    "progres": round(sum(p) / len(p), 1) if p else None,
                    "terhubung": c["T"] + c["TP"], "lambat": c["T1"] + c["T2"],
                    "tidak": c["R"] + c["C"] + c["N"], "telepon": c["TP"],
                    "hari_tercatat": len(kode), "kode_hari_ini": kode.get(hari, ""),
                    "tunggu_maks": max(tunggu) if tunggu else None})
    out.sort(key=lambda x: (-x["belum"], x["nama"]))
    return out


def _hitung(target: str) -> dict[str, Any]:
    nasional = target == NASIONAL
    sekolah = lk_baru.baca_semua() if nasional else lk_baru.baca_petugas(target)
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    status = {s.npsn: todo.semua_status(s) for s in sekolah}
    st = [status[s.npsn] for s in sekolah]
    fasil = komunikasi.kelompokkan(sekolah)
    lengkap = sum(1 for x in st if not any(v.status == "belum" for v in x.values()))
    return {
        "pic": "Nasional" if nasional else target,
        "nasional": nasional,
        "week": lk_baru.week_aktif(),
        "cutoff": komunikasi.label_cutoff(),
        "dibuat": schedule.now().strftime("%d/%m %H.%M"),
        "distribusi": _distribusi(sekolah),
        "capaian": _capaian(st),
        "progres": _progres(st),
        "reviu": _reviu(sekolah, st),
        "lengkap": lengkap,
        "komunikasi": _komunikasi(fasil, logkom),
        "tren": _tren(None if nasional else target),
        "fasil": [] if nasional else _tabel_fasil(fasil, status, logkom),
    }


# ---------- simpanan hasil & hitung ulang di latar ----------

_hasil: dict[str, tuple[float, dict[str, Any]]] = {}
_dibuka: dict[str, float] = {}
_jalan_hitung: set[str] = set()
_lock = threading.Lock()
_loop_mulai = False


def _kunci(target: str) -> str:
    return target if target == NASIONAL else normalize_petugas(target)


def _hitung_simpan(target: str) -> dict[str, Any]:
    k = _kunci(target)
    try:
        data = _hitung(target)
        with _lock:
            _hasil[k] = (time.time(), data)
        return data
    finally:
        with _lock:
            _jalan_hitung.discard(k)


def _latar(target: str) -> None:
    k = _kunci(target)
    with _lock:
        if k in _jalan_hitung:
            return
        _jalan_hitung.add(k)

    def run() -> None:
        try:
            _hitung_simpan(target)
        except Exception:
            log.exception("Dashboard %s gagal dihitung ulang", target)

    threading.Thread(target=run, name=f"dashboard-{k[:20]}", daemon=True).start()


def _loop() -> None:
    while True:
        time.sleep(SEGAR_DETIK)
        batas = time.time() - DIPANTAU_DETIK
        with _lock:
            target = [t for t, w in _dibuka.items() if w >= batas]
        for t in target:
            try:
                with _lock:
                    if _kunci(t) in _jalan_hitung:
                        continue
                    _jalan_hitung.add(_kunci(t))
                _hitung_simpan(t)
            except Exception:
                log.exception("Dashboard %s gagal dihitung ulang", t)


def mulai_latar() -> None:
    """Hitung dashboard petugas ini saat aplikasi dibuka, lalu ulang tiap 10 menit."""
    global _loop_mulai
    with _lock:
        if _loop_mulai:
            return
        _loop_mulai = True
    threading.Thread(target=_loop, name="dashboard-loop", daemon=True).start()
    saya = komunikasi.petugas_saya()
    if saya:
        _dibuka.setdefault(saya, time.time())
        _latar(saya)


def ambil(target: str, paksa: bool = False) -> dict[str, Any]:
    k = _kunci(target)
    with _lock:
        _dibuka[target] = time.time()
        ada = _hasil.get(k)
        sedang = k in _jalan_hitung
    if ada and not paksa:
        umur = time.time() - ada[0]
        if umur > SEGAR_DETIK:
            _latar(target)
        return {**ada[1], "umur_detik": int(umur), "menghitung": sedang or umur > SEGAR_DETIK}
    if sedang and not paksa:
        # hitungan pertama sedang berjalan di latar; tunggu sebentar
        for _ in range(120):
            time.sleep(0.5)
            with _lock:
                ada = _hasil.get(k)
            if ada:
                return {**ada[1], "umur_detik": int(time.time() - ada[0]), "menghitung": False}
    with _lock:
        _jalan_hitung.add(k)
    data = _hitung_simpan(target)
    return {**data, "umur_detik": 0, "menghitung": False}


@router.get("")
def dashboard(pic: str = Query("", max_length=120), paksa: bool = False,
              acc: Access = Depends(require_access)) -> dict[str, Any]:
    saya = komunikasi.petugas_saya()
    if pic and normalize_petugas(pic) != normalize_petugas(saya) and not acc.admin:
        raise HTTPException(403, "Hanya admin yang bisa melihat dashboard PIC lain.")
    target = pic or saya
    if not target:
        raise HTTPException(400, "Nama petugas belum dipilih.")
    out = dict(_jalan(ambil, target, paksa))
    if acc.admin:
        try:
            out["pilihan_pic"] = [p["nama"] for p in lk_baru.daftar_petugas()]
        except Exception:
            out["pilihan_pic"] = []
    return out
