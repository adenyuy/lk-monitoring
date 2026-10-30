"""Login Google (OAuth installed app) dan klien gspread.

Login berjalan di thread latar: browser terbuka, pengguna memilih akun, lalu
token disimpan di folder data. UI memantau status lewat /api/me.
"""

import json
import re
import os
import threading
from dataclasses import dataclass

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config, db, paths

# Google kadang mengembalikan scope dengan urutan/isi berbeda (mis. menambah "openid").
# Tanpa ini oauthlib melempar error "Scope has changed".
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class NotLoggedIn(Exception):
    pass


# ---------- credentials.json (OAuth client dari admin) ----------

def has_credentials() -> bool:
    """credentials.json terpasang DAN alamat ketiga sheet tim sudah diketahui."""
    return paths.CREDENTIALS_FILE.exists() and all(config.sheet_ids().values())


def id_sheet(nilai: str) -> str:
    """Terima ID atau link Google Sheets, kembalikan ID-nya ('' bila tidak valid)."""
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", nilai or "")
    x = m.group(1) if m else (nilai or "").strip()
    return x if re.fullmatch(r"[A-Za-z0-9_-]{20,}", x) else ""


def save_credentials(raw: bytes) -> None:
    """Pasang file paket lk-monitoring.json (credentials + alamat sheet) atau credentials.json biasa."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("File bukan JSON yang valid.") from e
    if "installed" not in data:
        raise ValueError(
            'File ini bukan file aplikasi dari admin (tidak ada bagian "installed"). '
            "Minta file lk-monitoring.json ke admin."
        )
    sheets = data.pop("lkm_sheets", None)
    ids = {k: id_sheet(str((sheets or {}).get(k, ""))) for k in config.SHEET_KEYS} if sheets else None
    if ids is not None and not all(ids.values()):
        raise ValueError("Alamat sheet di file ini tidak lengkap. Minta file lk-monitoring.json yang baru ke admin.")
    if ids is None and not all(config.sheet_ids().values()):
        raise ValueError(
            "File ini belum berisi alamat sheet tim. Pakai file lk-monitoring.json dari admin, bukan credentials.json."
        )
    paths.ensure_dirs()
    paths.CREDENTIALS_FILE.write_text(json.dumps(data), encoding="utf-8")
    if ids is not None:
        if (sheets or {}).get("eskalasi"):  # opsional: sheet LK Eskalasi
            ids["eskalasi"] = id_sheet(str(sheets["eskalasi"]))
        (paths.DATA_DIR / "sheets.json").write_text(json.dumps(ids), encoding="utf-8")


# ---------- token ----------

_creds_lock = threading.Lock()
_creds: Credentials | None = None


def _load_creds() -> Credentials | None:
    """Token tersimpan, di-refresh bila kedaluwarsa. None bila belum/tidak bisa login."""
    global _creds
    with _creds_lock:
        if _creds is None and paths.TOKEN_FILE.exists():
            try:
                _creds = Credentials.from_authorized_user_file(str(paths.TOKEN_FILE), config.SCOPES)
            except (ValueError, json.JSONDecodeError):
                _creds = None
        if _creds is None:
            return None
        if not _creds.valid:
            if _creds.expired and _creds.refresh_token:
                try:
                    _creds.refresh(Request())
                    paths.TOKEN_FILE.write_text(_creds.to_json(), encoding="utf-8")
                except RefreshError:
                    # Mis. app OAuth mode Testing: refresh token habis tiap 7 hari.
                    _creds = None
                    return None
            else:
                _creds = None
                return None
        return _creds


def credentials() -> Credentials:
    creds = _load_creds()
    if creds is None:
        raise NotLoggedIn("Belum masuk ke akun Google.")
    return creds


def is_logged_in() -> bool:
    return _load_creds() is not None


def fetch_email(creds: Credentials) -> str:
    resp = AuthorizedSession(creds).get(USERINFO_URL, timeout=20)
    resp.raise_for_status()
    email = resp.json().get("email", "")
    if not email:
        raise RuntimeError("Google tidak mengirim alamat email.")
    return email.lower()


def current_email() -> str | None:
    return db.get_setting("email")


# ---------- proses login (thread latar) ----------

@dataclass
class LoginState:
    status: str = "idle"  # idle | running | done | error
    error: str = ""


login_state = LoginState()
_login_thread: threading.Thread | None = None


def _run_login() -> None:
    global _creds
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(paths.CREDENTIALS_FILE), config.SCOPES)
        creds = flow.run_local_server(
            port=0,
            open_browser=True,
            authorization_prompt_message="",
            success_message="Login berhasil. Tutup tab ini dan kembali ke LK Monitoring.",
            prompt="select_account",
        )
        paths.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        with _creds_lock:
            _creds = creds
        db.set_setting("email", fetch_email(creds))
        login_state.status, login_state.error = "done", ""
    except Exception as e:  # ditampilkan ke pengguna apa adanya
        login_state.status, login_state.error = "error", f"Login gagal: {e}"


def start_login() -> LoginState:
    global _login_thread
    if not has_credentials():
        raise FileNotFoundError("credentials.json belum dipasang.")
    if login_state.status == "running" and _login_thread and _login_thread.is_alive():
        return login_state
    login_state.status, login_state.error = "running", ""
    _login_thread = threading.Thread(target=_run_login, name="google-login", daemon=True)
    _login_thread.start()
    return login_state


def logout() -> None:
    global _creds
    with _creds_lock:
        _creds = None
        if paths.TOKEN_FILE.exists():
            paths.TOKEN_FILE.unlink()
    db.delete_setting("email")
    login_state.status, login_state.error = "idle", ""
    _gc_cache.clear()


# ---------- gspread ----------

_gc_cache: dict[int, gspread.Client] = {}


def gspread_client() -> gspread.Client:
    creds = credentials()
    key = id(creds)
    if key not in _gc_cache:
        _gc_cache.clear()
        _gc_cache[key] = gspread.authorize(creds)
    return _gc_cache[key]
