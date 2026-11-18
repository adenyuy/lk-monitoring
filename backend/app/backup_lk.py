"""Backup tab WEEK di LK ke Google Drive sebagai CSV, otomatis setiap ada cutoff baru.

Susunan di folder Drive yang dipilih admin:

    <folder backup>/
      WEEK 5/
        WEEK 5 - Mingguan - 2026-11-16 0912.csv     <- cutoff pertama minggu itu (biasanya Senin)
        Sesi 1/  WEEK 5 - Sesi 1 - 2026-11-18 0930.csv  <- cutoff hari terakhir sesi (Rabu)
        Sesi 2/  WEEK 5 - Sesi 2 - 2026-11-21 0930.csv  <- cutoff hari terakhir sesi (Sabtu; Minggu ikut)

Satu file per slot: cutoff kedua di hari yang sama (atau backup manual) menimpa isi file slot itu.
Isinya tab WEEK apa adanya (export CSV Google Sheets, termasuk 3 baris judul) pada saat backup diambil.

Izin Drive terpisah dari login utama (token_backup.json, scope `drive` penuh, karena folder tujuan dibuat lewat
Drive, bukan oleh aplikasi). Diatur di satu laptop saja (akun pemilik folder backup). Laptop itu memeriksa tab Log Tarik Data
setiap 15 menit, jadi cutoff yang ditarik petugas lain di laptop lain juga ikut di-backup selama laptop ini menyala.
Gagal backup tidak pernah menggagalkan cutoff.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import db, lk_baru, paths, schedule
from .sheets import cache

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN = paths.DATA_DIR / "token_backup.json"
SET_FOLDER = "backup_folder"          # {"id": ..., "nama": ...}
SET_OTOMATIS = "backup_otomatis"      # bool, bawaan True
SET_TERAKHIR = "backup_cutoff_terakhir"  # "YYYY-mm-dd HH:MM|WEEK n" baris Log Tarik terakhir yang sudah di-backup

DRIVE = "https://www.googleapis.com/drive/v3/files"
UNGGAH = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
UMUM = {"supportsAllDrives": "true"}
JEDA_CEK = 15 * 60
TUJUAN = ("otomatis", "mingguan", "sesi1", "sesi2")


class BackupError(Exception):
    pass


# ---------- izin Google Drive ----------

@dataclass
class IzinState:
    status: str = "idle"  # idle | running | done | error
    error: str = ""


izin_state = IzinState()
_izin_lock = threading.Lock()


def _creds() -> Credentials | None:
    if not TOKEN.exists():
        return None
    try:
        c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    except (ValueError, json.JSONDecodeError):
        return None
    if not c.valid:
        if not (c.expired and c.refresh_token):
            return None
        try:
            c.refresh(Request())
            TOKEN.write_text(c.to_json(), encoding="utf-8")
        except RefreshError:
            return None
    return c


def punya_izin() -> bool:
    return _creds() is not None


def _jalan_izin(email: str) -> None:
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(paths.CREDENTIALS_FILE), SCOPES)
        c = flow.run_local_server(port=0, open_browser=True, authorization_prompt_message="",
                                  success_message="Izin Google Drive untuk backup diberikan. Tutup tab ini dan kembali "
                                                  "ke LK Monitoring.",
                                  login_hint=email or None)
        paths.ensure_dirs()
        TOKEN.write_text(c.to_json(), encoding="utf-8")
        izin_state.status, izin_state.error = "done", ""
        picu()
    except Exception as e:  # noqa: BLE001
        izin_state.status, izin_state.error = "error", f"Izin gagal: {e}"


def minta_izin(email: str) -> IzinState:
    with _izin_lock:
        if izin_state.status != "running":
            izin_state.status, izin_state.error = "running", ""
            threading.Thread(target=_jalan_izin, args=(email,), name="izin-backup", daemon=True).start()
    return izin_state


def cabut_izin() -> None:
    if TOKEN.exists():
        TOKEN.unlink()
    izin_state.status, izin_state.error = "idle", ""
    _lupakan()


# ---------- Drive ----------

def _sesi() -> AuthorizedSession:
    c = _creds()
    if c is None:
        raise BackupError("Belum ada izin Google Drive untuk backup. Klik \"Beri izin Google Drive\" dulu.")
    return AuthorizedSession(c)


def _panggil(sesi: AuthorizedSession, method: str, url: str, timeout: float = 60, **kw) -> dict:
    r = sesi.request(method, url, timeout=timeout, **kw)
    if r.status_code >= 400:
        teks = r.text[:400]
        if r.status_code == 401:
            cabut_izin()
            raise BackupError("Izin Google Drive kedaluwarsa. Beri izin lagi.")
        if "SERVICE_DISABLED" in teks or "has not been used" in teks or "is disabled" in teks:
            raise BackupError("Google Drive API belum diaktifkan di project Google Cloud aplikasi ini "
                              "(APIs & Services → Library → Google Drive API → Enable).")
        if r.status_code == 404:
            raise BackupError("Folder/file Drive tidak ditemukan atau akun ini tidak punya akses.")
        raise BackupError(f"Google Drive menolak permintaan ({r.status_code}): {teks}")
    return r.json() if r.content else {}


def id_folder(link: str) -> str:
    t = (link or "").strip()
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", t) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", t)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", t):
        return t
    raise BackupError("Link folder tidak dikenali. Tempel link seperti https://drive.google.com/drive/folders/….")


def link_folder(fid: str) -> str:
    return f"https://drive.google.com/drive/folders/{fid}"


def _q(teks: str) -> str:
    return teks.replace("\\", "\\\\").replace("'", "\\'")


def _cari(sesi: AuthorizedSession, q: str, fields: str = "id,name,mimeType,appProperties") -> list[dict]:
    out, token = [], None
    while True:
        params = {"q": q, "fields": f"nextPageToken,files({fields})", "pageSize": 1000,
                  "includeItemsFromAllDrives": "true", "corpora": "allDrives", **UMUM}
        if token:
            params["pageToken"] = token
        r = _panggil(sesi, "GET", DRIVE, params=params)
        out += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def _folder_anak(sesi: AuthorizedSession, induk: str, nama: str, ciri: dict[str, str]) -> str:
    """Id subfolder `nama` di `induk`; dibuat bila belum ada. Folder yang sudah ada diberi ciri appProperties."""
    ada = _cari(sesi, f"'{induk}' in parents and name = '{_q(nama)}' and mimeType = '{FOLDER}' and trashed = false")
    if ada:
        f = ada[0]
        if any((f.get("appProperties") or {}).get(k) != v for k, v in ciri.items()):
            _panggil(sesi, "PATCH", f"{DRIVE}/{f['id']}", params=UMUM, json={"appProperties": ciri})
        return f["id"]
    return _panggil(sesi, "POST", DRIVE, params={"fields": "id", **UMUM},
                    json={"name": nama, "mimeType": FOLDER, "parents": [induk], "appProperties": ciri})["id"]


def _unggah(sesi: AuthorizedSession, induk: str, nama: str, isi: bytes, ciri: dict[str, str], ket: str,
            ganti: str = "") -> dict:
    """Unggah resumable (file WEEK bisa belasan MB, multipart dibatasi 5 MB). `ganti` = id file lama yang isinya
    ditimpa (riwayat versi tetap tersimpan di Drive)."""
    meta: dict[str, Any] = {"name": nama, "mimeType": "text/csv", "appProperties": ciri, "description": ket}
    if ganti:
        method, url = "PATCH", f"{UNGGAH}/{ganti}"
    else:
        method, url = "POST", UNGGAH
        meta["parents"] = [induk]
    r = sesi.request(method, url, timeout=60, json=meta, params={"uploadType": "resumable", **UMUM},
                     headers={"X-Upload-Content-Type": "text/csv", "X-Upload-Content-Length": str(len(isi))})
    if r.status_code >= 400 or not r.headers.get("Location"):
        _panggil(sesi, method, url, json=meta, params={"uploadType": "resumable", **UMUM})  # pesan error yang rapi
        raise BackupError(f"Google Drive tidak memberi alamat unggah ({r.status_code}).")
    return _panggil(sesi, "PUT", r.headers["Location"], timeout=600, data=isi,
                    headers={"Content-Type": "text/csv"}, params={"fields": "id,name,webViewLink,size"})


def info_folder(fid: str) -> dict[str, str]:
    r = _panggil(_sesi(), "GET", f"{DRIVE}/{fid}", params={"fields": "id,name,mimeType,trashed,capabilities", **UMUM})
    if r.get("mimeType") != FOLDER or r.get("trashed"):
        raise BackupError("Link itu bukan folder Drive (atau sudah di tempat sampah).")
    if not (r.get("capabilities") or {}).get("canAddChildren", True):
        raise BackupError("Akun ini hanya bisa melihat folder itu. Minta akses Editor dulu.")
    return {"id": r["id"], "nama": r.get("name", "")}


def _lupakan() -> None:
    f = folder()
    if f:
        cache.drop(f"backup_drive:{f['id']}")


def folder() -> dict[str, str] | None:
    f = db.get_setting(SET_FOLDER)
    return f if isinstance(f, dict) and f.get("id") else None


def atur_folder(link: str) -> dict[str, str]:
    f = info_folder(id_folder(link))
    db.set_setting(SET_FOLDER, f)
    _lupakan()
    picu()
    return f


def otomatis() -> bool:
    return bool(db.get_setting(SET_OTOMATIS, True))


def atur_otomatis(aktif: bool) -> None:
    db.set_setting(SET_OTOMATIS, bool(aktif))
    if aktif:
        picu()


def siap() -> bool:
    return folder() is not None and punya_izin()


# ---------- isi CSV ----------

def csv_week(sesi: AuthorizedSession, week: int) -> bytes:
    """Tab WEEK sebagai CSV (persis seperti tampilan sheet)."""
    ws = lk_baru._ss().worksheet(lk_baru.tab_week(week))
    r = sesi.request("GET", f"https://docs.google.com/spreadsheets/d/{lk_baru.sheet_id()}/export",
                     params={"format": "csv", "gid": ws.id}, timeout=300)
    if r.status_code >= 400 or "text/csv" not in r.headers.get("Content-Type", ""):
        raise BackupError(f"Tab {lk_baru.tab_week(week)} tidak bisa diambil sebagai CSV ({r.status_code}). "
                          "Pastikan akun izin Drive bisa membuka LK.")
    return b"\xef\xbb\xbf" + r.content  # BOM: Excel membaca huruf non-ASCII dengan benar


# ---------- aturan tujuan ----------

def akhir_sesi(hari: date) -> int | None:
    """Nomor sesi bila `hari` adalah hari terakhir sesinya (Rabu / Sabtu; Minggu ikut sesi terakhir), selain itu None."""
    sesi = lk_baru.sesi_hari()
    b = lk_baru.blok_untuk(hari, sesi)
    z = sesi[b][1]
    wd = hari.weekday()
    return b if wd == z or (b == max(sesi) and wd > z) else None


def week_ada(week: int) -> int:
    """Tab WEEK yang benar-benar ada. Tab WEEK lama bisa sudah diganti nama jadi WEEK berikutnya (cutoff Senin dini hari
    tercatat WEEK 4, lalu tab itu menjadi WEEK 5): pakai WEEK terdekat sesudahnya."""
    ada = lk_baru.daftar_week(refresh=True)
    if week in ada:
        return week
    lebih = [w for w in ada if w > week]
    if lebih:
        return lebih[0]
    raise BackupError(f"Tab WEEK {week} tidak ada di LK.")


def _cap(w: datetime) -> str:
    return w.strftime("%Y-%m-%d %H%M")


def cutoff_lk() -> dict[str, Any] | None:
    """Baris terakhir tab Log Tarik Data: {waktu, week, oleh, kunci}."""
    from . import cutoff_baru

    r = lk_baru._ss().values_get(f"'{cutoff_baru.TAB_LOG}'!A2:F").get("values", [])
    r = [x for x in r if x and str(x[0]).strip()]
    if not r:
        return None
    a = list(r[-1]) + [""] * 6
    m = re.search(r"\d+", str(a[1]))
    try:
        w = datetime.strptime(str(a[0])[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    if not m:
        return None
    return {"waktu": w, "week": int(m.group()), "oleh": str(a[5]), "kunci": f"{a[0][:16]}|WEEK {m.group()}"}


_status: dict[str, Any] = {"jalan": False, "langkah": "", "error": "", "hasil": None}
_lock = threading.Lock()


def status() -> dict[str, Any]:
    return dict(_status)


def jalankan(tujuan: str, week: int, waktu: datetime, sumber: str, oleh: str = "") -> dict[str, Any]:
    """Ambil tab WEEK lalu simpan ke tujuan. Satu file per slot (Mingguan, Sesi 1, Sesi 2): backup berikutnya ke slot
    yang sama menimpa isinya. `otomatis` = Mingguan bila WEEK itu belum punya, dan Sesi n bila `waktu` jatuh di hari
    terakhir sesi itu."""
    if tujuan not in TUJUAN:
        raise BackupError("Tujuan backup tidak dikenal.")
    f = folder()
    if not f:
        raise BackupError("Folder backup belum diatur.")
    week = week_ada(week)
    sesi = _sesi()
    root = f["id"]
    _status["langkah"] = f"Menyiapkan folder WEEK {week}"
    f_week = _folder_anak(sesi, root, f"WEEK {week}", {"lkm": "folder", "root": root, "week": str(week), "jenis": "week"})

    def lama(induk: str, jenis: str) -> str:
        r = _cari(sesi, f"'{induk}' in parents and trashed = false and "
                        f"appProperties has {{ key='jenis' and value='{jenis}' }}", "id")
        return r[0]["id"] if r else ""

    sasaran: list[tuple[str, str]] = []  # (jenis, sesi)
    if tujuan == "mingguan":
        sasaran.append(("mingguan", ""))
    elif tujuan in ("sesi1", "sesi2"):
        sasaran.append(("sesi", tujuan[-1]))
    else:
        if not lama(f_week, "mingguan"):
            sasaran.append(("mingguan", ""))
        b = akhir_sesi(waktu.date())
        if b:
            sasaran.append(("sesi", str(b)))
    if not sasaran:
        return {"week": week, "file": [], "ukuran": 0,
                "lewati": f"Cutoff {waktu:%d/%m %H:%M} bukan hari terakhir sesi dan Mingguan WEEK {week} sudah ada."}

    _status["langkah"] = f"Mengambil tab WEEK {week} dari LK"
    isi = csv_week(sesi, week)
    diambil = schedule.now().strftime("%Y-%m-%d %H:%M")
    ket = (f"Backup tab WEEK {week} dari LK, cutoff {waktu:%Y-%m-%d %H:%M}"
           + (f" (ditarik {oleh})" if oleh else "") + f". Diambil {diambil}, {sumber}.")
    hasil = []
    for jenis, s in sasaran:
        if jenis == "mingguan":
            induk, nama = f_week, f"WEEK {week} - Mingguan - {_cap(waktu)}"
        else:
            _status["langkah"] = f"Menyiapkan folder Sesi {s}"
            induk = _folder_anak(sesi, f_week, f"Sesi {s}", {"lkm": "folder", "root": root, "week": str(week),
                                                              "jenis": "sesi", "sesi": s})
            nama = f"WEEK {week} - Sesi {s} - {_cap(waktu)}"
        if sumber == "manual":
            nama += " (manual)"
        nama += ".csv"
        _status["langkah"] = f"Mengunggah {nama}"
        ciri = {k: v for k, v in {"lkm": "backup", "root": root, "week": str(week), "jenis": jenis, "sesi": s,
                                  "cutoff": waktu.strftime("%Y-%m-%d %H:%M"), "sumber": sumber}.items() if v}
        r = _unggah(sesi, induk, nama, isi, ciri, ket, ganti=lama(induk, jenis))
        hasil.append({"nama": r.get("name", nama), "link": r.get("webViewLink", ""), "jenis": jenis, "sesi": s})
    _lupakan()
    return {"week": week, "file": hasil, "ukuran": len(isi)}


def _jalan_aman(tujuan: str, week: int, waktu: datetime, sumber: str, oleh: str, kunci: str = "") -> None:
    try:
        hasil = jalankan(tujuan, week, waktu, sumber, oleh)
        if kunci:
            db.set_setting(SET_TERAKHIR, kunci)
        cache.drop("backup_cutoff_lk")
        _status.update(hasil={**hasil, "waktu": schedule.now().strftime("%Y-%m-%d %H:%M"), "sumber": sumber}, error="")
    except Exception as e:  # noqa: BLE001
        log.warning("Backup WEEK ke Drive gagal", exc_info=True)
        _status.update(error=str(e))
    finally:
        _status.update(jalan=False, langkah="")


def mulai(tujuan: str, week: int, waktu: datetime, sumber: str, oleh: str = "", kunci: str = "",
          tunggu: bool = False) -> dict[str, Any]:
    with _lock:
        if _status["jalan"]:
            raise BackupError("Backup lain masih berjalan.")
        _status.update(jalan=True, langkah="Mulai", error="")
    if tunggu:
        _jalan_aman(tujuan, week, waktu, sumber, oleh, kunci)
    else:
        threading.Thread(target=_jalan_aman, args=(tujuan, week, waktu, sumber, oleh, kunci),
                         name="backup-lk", daemon=True).start()
    return status()


def manual(tujuan: str, oleh: str) -> dict[str, Any]:
    if tujuan not in TUJUAN:
        raise BackupError("Tujuan backup tidak dikenal.")
    if not siap():
        raise BackupError("Atur folder dan izin Google Drive dulu.")
    return mulai(tujuan, lk_baru.week_aktif(), schedule.now().replace(tzinfo=None), "manual", oleh)


# ---------- otomatis ----------

def periksa_otomatis() -> bool:
    """Backup bila Log Tarik punya cutoff yang belum di-backup. True bila backup dijalankan."""
    from . import cutoff_baru

    if not (otomatis() and siap()) or _status["jalan"] or cutoff_baru.status().get("jalan"):
        return False
    c = cutoff_lk()
    if not c or c["kunci"] == db.get_setting(SET_TERAKHIR):
        return False
    try:
        mulai("otomatis", c["week"], c["waktu"], "otomatis", c["oleh"], c["kunci"], tunggu=True)
    except BackupError:
        return False
    return True


_bangun = threading.Event()
_mulai_lock = threading.Lock()
_thread: threading.Thread | None = None


def _loop() -> None:
    while True:
        try:
            periksa_otomatis()
        except Exception:  # noqa: BLE001
            log.warning("Cek backup otomatis gagal", exc_info=True)
        _bangun.wait(timeout=JEDA_CEK)
        _bangun.clear()


def picu() -> None:
    """Cek cutoff baru sekarang (dan tiap 15 menit). Tidak melakukan apa pun bila backup belum diatur."""
    global _thread
    if not siap():
        return
    _bangun.set()
    with _mulai_lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_loop, name="backup-otomatis", daemon=True)
            _thread.start()


# ---------- ringkasan untuk tampilan ----------

def _item(f: dict) -> dict[str, Any]:
    p = f.get("appProperties") or {}
    return {"nama": f.get("name", ""), "link": f.get("webViewLink", ""), "cutoff": p.get("cutoff", ""),
            "sumber": p.get("sumber", ""), "jenis": p.get("jenis", ""), "sesi": p.get("sesi", ""),
            "ukuran": int(f.get("size") or 0)}


def susun(files: list[dict], folders: list[dict], week_aktif: int | None, hari_ini: date,
          maks: int = 4) -> list[dict[str, Any]]:
    """Per WEEK tiga slot: Mingguan (Senin), Sesi 1 (hari terakhirnya, Rabu), Sesi 2 (Sabtu); masing-masing satu file."""
    per_week: dict[int, list[dict]] = {}
    for f in files:
        try:
            per_week.setdefault(int((f.get("appProperties") or {}).get("week", "")), []).append(_item(f))
        except ValueError:
            continue
    link_week, link_sesi = {}, {}
    for f in folders:
        p = f.get("appProperties") or {}
        try:
            w = int(p.get("week", ""))
        except ValueError:
            continue
        if p.get("jenis") == "week":
            link_week[w] = link_folder(f["id"])
        elif p.get("jenis") == "sesi":
            link_sesi[(w, p.get("sesi", ""))] = link_folder(f["id"])
    weeks = set(per_week) | set(link_week) | ({week_aktif} if week_aktif else set())
    sesi = lk_baru.sesi_hari()
    senin_ini = hari_ini - timedelta(days=hari_ini.weekday())
    out = []
    for w in sorted(weeks, reverse=True)[:maks]:
        items = sorted(per_week.get(w, []), key=lambda x: x["cutoff"])
        if week_aktif:
            senin = senin_ini - timedelta(weeks=week_aktif - w)
        else:
            tgl = [datetime.strptime(x["cutoff"][:10], "%Y-%m-%d").date() for x in items if x["cutoff"]]
            acuan = min(tgl) if tgl else hari_ini
            senin = acuan - timedelta(days=acuan.weekday())

        def terbaru(jenis: str, s: str = "") -> dict[str, Any] | None:
            x = [i for i in items if i["jenis"] == jenis and (not s or i["sesi"] == s)]
            return x[-1] if x else None

        slot = [{"kunci": "mingguan", "judul": "Mingguan", "ket": "cutoff pertama minggu ini",
                 "target": senin.isoformat(), "file": terbaru("mingguan"), "link": link_week.get(w, "")}]
        for b in sorted(sesi):
            akhir = senin + timedelta(days=sesi[b][1])
            slot.append({"kunci": f"sesi{b}", "judul": f"Sesi {b}", "ket": lk_baru.label_blok(b, sesi),
                         "target": akhir.isoformat(), "file": terbaru("sesi", str(b)),
                         "link": link_sesi.get((w, str(b)), "")})
        out.append({"week": w, "link": link_week.get(w, ""), "senin": senin.isoformat(), "slot": slot})
    return out


def sesi_hari_ini() -> int:
    return lk_baru.blok_untuk(schedule.now().date())


def ringkasan() -> dict[str, Any]:
    f = folder()
    izin = punya_izin()
    out: dict[str, Any] = {
        "folder": {**f, "link": link_folder(f["id"])} if f else None, "izin": izin,
        "izin_status": izin_state.status, "izin_error": izin_state.error,
        "otomatis": otomatis(), "status": status(), "minggu": [], "tertunda": None, "error": "",
        "sesi_hari_ini": sesi_hari_ini(),
    }
    try:
        c = cache.get("backup_cutoff_lk", 20, cutoff_lk)
        if c and c["kunci"] != db.get_setting(SET_TERAKHIR):
            out["tertunda"] = {"waktu": c["waktu"].strftime("%Y-%m-%d %H:%M"), "week": c["week"], "oleh": c["oleh"]}
    except Exception:  # noqa: BLE001
        pass
    if not (f and izin):
        return out
    try:
        def load() -> dict[str, Any]:
            sesi = _sesi()
            root = f["id"]
            q = f"appProperties has {{ key='root' and value='{_q(root)}' }} and trashed = false"
            semua = _cari(sesi, q, "id,name,mimeType,appProperties,webViewLink,size")
            return {"files": [x for x in semua if x.get("mimeType") != FOLDER],
                    "folders": [x for x in semua if x.get("mimeType") == FOLDER]}

        d = cache.get(f"backup_drive:{f['id']}", 120, load)
        try:
            aktif = lk_baru.week_aktif()
        except Exception:  # noqa: BLE001
            aktif = None
        out["minggu"] = susun(d["files"], d["folders"], aktif, schedule.now().date())
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out
