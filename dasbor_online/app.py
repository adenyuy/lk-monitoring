"""API dashboard online. Memakai ulang modul backend/app (lk_baru, komunikasi, todo, cutoff_baru, dashboard)
dengan akses Sheet lewat service account HANYA-BACA. Tidak ada endpoint yang menulis ke Sheet atau WhatsApp.

Env (diisi di Vercel, bukan di repo):
  GOOGLE_SA_JSON        isi key JSON service account (boleh base64)
  LKM_LK2_SHEET_ID      ID Sheet LK Monitoring Pelaporan
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET   OAuth client tipe Web application
  LKM_SESI_RAHASIA      string acak panjang untuk menandatangani cookie
  LKM_IZIN_EMAIL        email/domain yang boleh masuk, dipisah koma (mis. "a@gmail.com, @kantor.go.id")
"""

import base64
from datetime import date, timedelta
import json
import os
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

# backend/app dipakai sebagai paket "app"; data lokal (SQLite kosong) di folder sementara
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "backend"))
os.environ.setdefault("LKM_DATA_DIR", str(Path(tempfile.gettempdir()) / "lkm-online"))

from fastapi import Depends, FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from google.oauth2 import service_account  # noqa: E402

from app import google_auth, komunikasi, lk_baru, schedule, todo  # noqa: E402
from app.routers import dashboard  # noqa: E402
from app.routers.lkb import _jalan  # noqa: E402
from app.sheets import normalize_petugas  # noqa: E402

from . import auth  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_kred: service_account.Credentials | None = None
_kred_lock = threading.Lock()


def _kredensial() -> service_account.Credentials:
    """Ganti login Google pengguna (token.json di laptop) dengan service account hanya-baca."""
    global _kred
    with _kred_lock:
        if _kred is None:
            mentah = os.environ.get("GOOGLE_SA_JSON", "").strip()
            if not mentah:
                raise HTTPException(500, "Konfigurasi server belum lengkap (GOOGLE_SA_JSON).")
            if not mentah.startswith("{"):
                mentah = base64.b64decode(mentah).decode()
            _kred = service_account.Credentials.from_service_account_info(json.loads(mentah), scopes=SCOPES)
        return _kred


# gspread_client() memanggil fungsi ini. LKM_ONLINE_LOKAL=1: uji di laptop memakai token Google di LKM_DATA_DIR.
if os.environ.get("LKM_ONLINE_LOKAL") != "1":
    google_auth.credentials = _kredensial

app = FastAPI(title="LK Monitoring – Dashboard online", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def _tanpa_cache(request: Request, call_next):
    r = await call_next(request)
    r.headers["Cache-Control"] = "private, no-store"
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "same-origin"
    return r


@app.exception_handler(HTTPException)
async def _galat(_: Request, e: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": e.detail}, status_code=e.status_code)


# ---------- login ----------

@app.get("/api/auth/masuk")
def masuk(request: Request) -> RedirectResponse:
    return auth.masuk(request)


@app.get("/api/auth/kembali")
def kembali(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    return auth.kembali(request, code, state, error)


@app.get("/api/auth/saya")
def saya(email: str = Depends(auth.wajib_login)) -> dict[str, str]:
    return {"email": email}


@app.post("/api/auth/keluar")
def keluar() -> JSONResponse:
    r = JSONResponse({"ok": True})
    r.delete_cookie(auth.COOKIE_SESI)
    return r


# ---------- dashboard ----------

_paksa_terakhir: dict[str, float] = {}
JEDA_PAKSA = 120  # "Hitung ulang" paling cepat tiap 2 menit per PIC, supaya kuota baca Google aman


def _pilihan_pic() -> list[str]:
    try:
        return [p["nama"] for p in lk_baru.daftar_petugas()]
    except Exception:
        return []


@app.get("/api/dashboard")
def dash(pic: str = Query("", max_length=120), paksa: bool = False,
         _: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    target = pic or dashboard.NASIONAL
    if paksa:
        k = normalize_petugas(target)
        if time.time() - _paksa_terakhir.get(k, 0) < JEDA_PAKSA:
            paksa = False
        else:
            _paksa_terakhir[k] = time.time()
    out = dict(_jalan(dashboard.ambil, target, paksa))
    out["pilihan_pic"] = _pilihan_pic()
    return out


@app.get("/api/dashboard/log-progres")
def log_progres(_: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    from app import cutoff_baru

    return _jalan(cutoff_baru.baca_log_progres)


# ---------- log pengisian (dari Sheet) ----------

HARI_LOG = 10


def _log(pic: str) -> dict[str, Any]:
    sekolah = lk_baru.baca_semua()
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    hari_ini = schedule.now().date().isoformat()
    tanggal = [d for d in sorted(logkom.tanggal) if d <= hari_ini][-HARI_LOG:]

    per_pic: dict[str, tuple[str, list[lk_baru.Sekolah]]] = {}
    for s in sekolah:
        if not s.petugas:
            continue
        per_pic.setdefault(normalize_petugas(s.petugas), (s.petugas, []))[1].append(s)

    def manusia(v: Any) -> str:
        """Isian petugas saja; keterangan otomatis dari aplikasi (Selesai, Due, Menunggu reviu, ...) diabaikan."""
        t = str(v or "").strip()
        return "" if todo.otomatis(t) or "tidak ada kendala" in t.casefold() else t

    def kendala(daftar: list[lk_baru.Sekolah]) -> list[dict[str, Any]]:
        out = []
        for s in daftar:
            for sesi, isi in s.isian.items():
                for kode, (k, tl) in isi.items():
                    k, tl = manusia(k), manusia(tl)
                    if k or tl:
                        out.append({"npsn": s.npsn, "sekolah": s.nama, "fasil": s.fasil, "ptn": s.ptn,
                                    "pic": s.petugas, "komponen": lk_baru.KOMP[kode].label, "sesi": sesi,
                                    "kendala": k, "tindak_lanjut": tl})
        out.sort(key=lambda x: (-x["sesi"], x["sekolah"]))
        return out

    ringkas = []
    for _, (nama, daftar) in sorted(per_pic.items(), key=lambda x: x[1][0].casefold()):
        fasil = komunikasi.kelompokkan(daftar)
        kode = {k: komunikasi.kode_fasil(f, logkom) for k, f in fasil.items()}
        terisi = [sum(1 for k in fasil if kode[k].get(d)) for d in tanggal]
        diisi = sorted({d for x in kode.values() for d in x if d <= hari_ini})
        jml_kendala = sum(1 for s in daftar for isi in s.isian.values() for k, _tl in isi.values() if manusia(k))
        ringkas.append({"nama": nama, "sekolah": len(daftar), "fasil": len(fasil), "terisi": terisi,
                        "terakhir": diisi[-1] if diisi else None, "kendala": jml_kendala})

    out: dict[str, Any] = {"tanggal": tanggal, "hari_ini": hari_ini, "week": lk_baru.week_aktif(),
                           "pic": ringkas, "kode": komunikasi.kode_label(), "dibuat": schedule.now().strftime("%d/%m %H.%M")}
    semua = kendala(sekolah)
    out["kendala_teratas"] = [{"kendala": k, "jumlah": n}
                              for k, n in Counter(x["kendala"] for x in semua if x["kendala"]).most_common(8)]
    if pic:
        nama, daftar = per_pic.get(normalize_petugas(pic), (pic, []))
        fasil = komunikasi.kelompokkan(daftar)
        out["detail"] = {
            "nama": nama,
            "fasil": sorted(({"nama": f.nama, "ptn": f.ptn, "sekolah": len(f.sekolah),
                              "kode": {d: c for d, c in komunikasi.kode_fasil(f, logkom).items() if d in tanggal}}
                             for f in fasil.values()), key=lambda x: x["nama"].casefold()),
            "kendala": kendala(daftar),
        }
    else:
        out["kendala_terbaru"] = semua[:60]
    return out


_log_simpan: dict[str, tuple[float, dict[str, Any]]] = {}


@app.get("/api/log-online")
def log_online(pic: str = Query("", max_length=120), _: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    k = normalize_petugas(pic) if pic else ""
    ada = _log_simpan.get(k)
    if ada and time.time() - ada[0] < 300:
        return ada[1]
    d = _jalan(_log, pic)
    _log_simpan[k] = (time.time(), d)
    return d


# ---------- ranking PIC ----------

HARI_RANKING = 6  # Log Komunikasi: hari kerja terakhir (kolom = hari terakhir, detail = per hari)


def _ranking() -> dict[str, Any]:
    """Per PIC: komponen sudah diisi / yang seharusnya (sudah due), per komponen dan total, plus pengisian
    Log Komunikasi. Satu kali baca data nasional untuk semua PIC."""
    sekolah = lk_baru.baca_semua()
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    hari_ini = schedule.now().date().isoformat()
    # Hari = hari kerja WEEK aktif sampai hari ini, supaya filter hari berlaku juga untuk isian Kendala/TL
    # (isian per sesi di tab WEEK aktif; isian minggu lalu ada di tab WEEK sebelumnya)
    hari_d = schedule.now().date()
    senin = (hari_d - timedelta(days=hari_d.weekday())).isoformat()
    tanggal = [d for d in sorted(logkom.tanggal) if senin <= d <= hari_ini]
    sesi = lk_baru.sesi_hari()
    blok_urut = sorted(sesi)
    blok_hari = [lk_baru.blok_untuk(date.fromisoformat(d), sesi) for d in tanggal]

    per_pic: dict[str, tuple[str, list[lk_baru.Sekolah]]] = {}
    for s in sekolah:
        if s.petugas:
            per_pic.setdefault(normalize_petugas(s.petugas), (s.petugas, []))[1].append(s)

    # komponen yang punya kolom Kendala/TL di WEEK ini
    berkolom = {kode for s in sekolah[:50] for isi in s.isian.values() for kode in isi}

    def diisi(v: Any) -> bool:
        """Isian petugas (termasuk 'Tidak ada kendala'); keterangan otomatis aplikasi tidak dihitung."""
        t = str(v or "").strip()
        return bool(t) and not todo.otomatis(t)

    def kom_terakhir(x: dict[str, str]) -> str:
        """Kode terakhir dalam HARI_RANKING hari kerja terakhir ('' = belum ada)."""
        return next((x[d] for d in reversed(tanggal) if x.get(d)), "")

    def rinci_fasil(fasil: dict[str, Any], kode_f: dict[str, dict[str, str]], st_by: dict[int, Any]) -> list[dict[str, Any]]:
        """Per fasil, untuk filter gabungan di halaman: kode Log Komunikasi per hari (urut `tanggal`) dan per
        komponen [belum, selesai, harus, kendala terisi semua sesi, TL semua sesi, lalu kendala & TL per sesi
        (urut `blok_urut`)] dari sekolah binaannya. Isian dihitung dari sekolah yang belum."""
        out = []
        for key, f in fasil.items():
            k: dict[str, list[int]] = {}
            for kp in lk_baru.KOMPONEN:
                b = sel = 0
                isi = [0] * (2 + 2 * len(blok_urut))
                for sk in f.sekolah:
                    stt = st_by[id(sk)][kp.kode].status
                    if stt == "selesai":
                        sel += 1
                    elif stt == "belum":
                        b += 1
                        per = [sk.isian.get(bl, {}).get(kp.kode, ("", "")) for bl in blok_urut]
                        isi[0] += any(diisi(x[0]) for x in per)
                        isi[1] += any(diisi(x[1]) for x in per)
                        for j, x in enumerate(per):
                            isi[2 + 2 * j] += diisi(x[0])
                            isi[3 + 2 * j] += diisi(x[1])
                if sel + b:
                    k[kp.kode] = [b, sel, sel + b, *isi]
            out.append({"n": f.nama, "s": len(f.sekolah), "h": [kode_f[key].get(d, "") for d in tanggal], "k": k})
        out.sort(key=lambda x: x["n"].casefold())
        return out

    def hitung(nama: str, daftar: list[lk_baru.Sekolah], rinci: bool = True) -> dict[str, Any]:
        st = [todo.semua_status(s) for s in daftar]
        # Komunikasi dihitung per FASIL (menghubungi fasil = semua sekolahnya); kode fasil per hari = kode
        # terbanyak di antara sekolahnya hari itu
        fasil = komunikasi.kelompokkan(daftar)
        kode_f = {k: komunikasi.kode_fasil(f, logkom) for k, f in fasil.items()}
        akhir_f = {k: kom_terakhir(x) or "-" for k, x in kode_f.items()}
        semua_fasil_belum: set[str] = set()
        komp = []
        tot_a = tot_b = 0
        tot_belum = tot_k = tot_tl = 0
        for k in lk_baru.KOMPONEN:
            a = sum(1 for x in st if x[k.kode].status == "selesai")
            belum = [s for s, x in zip(daftar, st) if x[k.kode].status == "belum"]
            b = a + len(belum)
            tot_a += a
            tot_b += b
            # sekolah yang belum: Kendala/TL sudah diisi petugas (sesi mana pun di WEEK ini) dan komunikasinya
            ada = k.kode in berkolom
            n_k = sum(1 for s in belum if any(diisi(i.get(k.kode, ("", ""))[0]) for i in s.isian.values())) if ada else None
            n_tl = sum(1 for s in belum if any(diisi(i.get(k.kode, ("", ""))[1]) for i in s.isian.values())) if ada else None
            fasil_belum = {komunikasi.kunci_fasil(s) for s in belum}
            semua_fasil_belum |= fasil_belum
            kom = Counter(akhir_f[f] for f in fasil_belum)
            if ada:
                tot_belum += len(belum)
                tot_k += n_k or 0
                tot_tl += n_tl or 0
            komp.append({"kode": k.kode, "label": k.label, "selesai": a, "harus": b,
                         "persen": round(a / b * 100, 1) if b else None,
                         "belum": len(belum), "fasil_belum": len(fasil_belum), "kendala": n_k, "tl": n_tl,
                         "kom": dict(kom)})
        tot_kom = Counter(akhir_f[f] for f in semua_fasil_belum)
        log_hari = []
        for d in tanggal:
            c = Counter(x.get(d, "") for x in kode_f.values())
            kosong = c.pop("", 0)
            log_hari.append({"tanggal": d, "isi": len(kode_f) - kosong, "slot": len(kode_f), "kode": dict(c)})
        akhir = log_hari[-1] if log_hari else {"isi": 0, "slot": 0, "kode": {}}
        isi, slot, log_kode = akhir["isi"], akhir["slot"], akhir["kode"]
        p = [x["progres"].persen for x in st if x["progres"].persen is not None]
        return {"nama": nama, "sekolah": len(daftar), "fasil": len(fasil),
                "selesai": tot_a, "harus": tot_b, "persen": round(tot_a / tot_b * 100, 1) if tot_b else None,
                "komponen": komp,
                "belum": tot_belum, "kendala": tot_k, "tl": tot_tl, "kom": dict(tot_kom),
                "log_isi": isi, "log_slot": slot, "log_persen": round(isi / slot * 100, 1) if slot else None,
                "log_kode": dict(log_kode), "log_hari": log_hari,
                "rinci": rinci_fasil(fasil, kode_f, {id(sk): x for sk, x in zip(daftar, st)}) if rinci else [],
                "progres": round(sum(p) / len(p), 1) if p else None}

    pic = [hitung(n, d) for n, d in per_pic.values()]
    pic.sort(key=lambda x: (-(x["persen"] or 0), x["nama"].casefold()))
    for i, x in enumerate(pic, 1):
        x["peringkat"] = i
    return {"pic": pic, "nasional": hitung("Nasional", sekolah, rinci=False), "hari_log": tanggal,
            "komponen": [{"kode": k.kode, "label": k.label} for k in lk_baru.KOMPONEN],
            "kode_kom": komunikasi.kode_label(), "berkolom": sorted(berkolom),
            "blok": [{"blok": b, "label": lk_baru.label_blok(b, sesi)} for b in blok_urut], "blok_hari": blok_hari,
            "dibuat": schedule.now().strftime("%d/%m %H.%M")}


_rank_simpan: tuple[float, dict[str, Any]] | None = None
_rank_lock = threading.Lock()


@app.get("/api/ranking")
def ranking(_: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    global _rank_simpan
    with _rank_lock:
        if _rank_simpan and time.time() - _rank_simpan[0] < 600:
            return _rank_simpan[1]
        d = _jalan(_ranking)
        _rank_simpan = (time.time(), d)
        return d
