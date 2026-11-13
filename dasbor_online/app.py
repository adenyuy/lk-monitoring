"""API dashboard online. Memakai ulang modul backend/app (lk_baru, komunikasi, todo, cutoff_baru, dashboard)
dengan akses Sheet lewat service account HANYA-BACA. Tidak ada endpoint yang menulis ke Sheet atau WhatsApp.

Env (diisi di Vercel, bukan di repo):
  GOOGLE_SA_JSON        isi key JSON service account (boleh base64)
  LKM_LK2_SHEET_ID      ID Sheet LK Monitoring Pelaporan
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET   OAuth client tipe Web application
  LKM_SESI_RAHASIA      string acak panjang untuk menandatangani cookie
  LKM_IZIN_EMAIL        email/domain yang boleh masuk, dipisah koma (mis. "a@gmail.com, @kantor.go.id")
  LKM_ADMIN_EMAIL       email admin, dipisah koma: hanya mereka yang melihat Ranking PIC
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

from app import google_auth, komunikasi, lk_baru, ranking, schedule, todo  # noqa: E402
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
def saya(email: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    return {"email": email, "admin": _admin(email)}


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
def dash(pic: str = Query("", max_length=120), bimtek: str = Query("", max_length=60), paksa: bool = False,
         email: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    target = dashboard.target(pic or dashboard.NASIONAL, bimtek)
    if paksa:
        k = normalize_petugas(target)
        if time.time() - _paksa_terakhir.get(k, 0) < JEDA_PAKSA:
            paksa = False
        else:
            _paksa_terakhir[k] = time.time()
    out = dict(_jalan(dashboard.ambil, target, paksa))
    out["pilihan_pic"] = _pilihan_pic()
    out["admin"] = _admin(email)
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


def _admin(email: str) -> bool:
    return auth.admin(email)


@app.get("/api/dashboard/ranking")
@app.get("/api/ranking")
def ranking_(bimtek: str = Query("", max_length=60), email: str = Depends(auth.wajib_login)) -> dict[str, Any]:
    if not _admin(email):
        raise HTTPException(403, "Ranking PIC hanya untuk admin.")
    return _jalan(ranking.ambil, bimtek)
