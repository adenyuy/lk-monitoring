"""Forum tanya jawab tim: pertanyaan + jawaban dari semua petugas, disimpan di tab "Forum" sheet LK Monitoring.

Satu baris = satu pertanyaan atau satu jawaban. Baris tidak pernah dihapus (hapus = status "dihapus"), jadi nomor
baris tetap dan dua petugas yang menulis bersamaan tidak saling menimpa (baris baru selalu lewat append).

Kolom: id | jenis | induk | judul | isi | topik | foto | email | nama | dibuat | diubah | status | solusi
  jenis   tanya | jawab | pengumuman (pengumuman hanya ditulis admin, tampil di kolom kanan Forum)
  induk   id pertanyaan (untuk jawaban)
  foto    id file Google Drive, dipisah koma
  solusi  id jawaban yang dipilih penanya sebagai jawaban yang benar (untuk pertanyaan)

Foto diunggah ke Google Drive pengunggah (izin drive.file yang sama dengan Paparan), lalu dibuka untuk
"siapa saja yang punya link" supaya bisa dilihat petugas lain.
"""

import json
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from google.auth.transport.requests import AuthorizedSession

from . import lk_baru, paparan, paths
from .sheets import cache, col_letter

log = logging.getLogger(__name__)

TAB = "Forum"
KOLOM = ["id", "jenis", "induk", "judul", "isi", "topik", "foto", "email", "nama", "dibuat", "diubah", "status",
         "solusi"]
AKHIR = col_letter(len(KOLOM) - 1)
CACHE_DETIK = 30
MAKS_JUDUL, MAKS_ISI, MAKS_TOPIK, MAKS_FOTO = 200, 8000, 40, 4
TOPIK_AWAL = ["Isian LK", "Komunikasi fasil", "Sekolah", "WA Blast", "Aplikasi", "Lainnya"]

_tulis_lock = threading.Lock()


class ForumError(Exception):
    """Pesan error-nya ditampilkan langsung ke pengguna."""


@dataclass
class Pos:
    id: str
    jenis: str
    induk: str
    judul: str
    isi: str
    topik: str
    foto: list[str]
    email: str
    nama: str
    dibuat: str
    diubah: str
    status: str
    solusi: str
    baris: int = 0
    jawaban: list["Pos"] = field(default_factory=list)


def _sel(r: list[Any], i: int) -> str:
    return str(r[i]).strip() if i < len(r) and r[i] is not None else ""


def _semua(values: list[list[Any]]) -> list[Pos]:
    if not values:
        return []
    kepala = [str(h).strip().casefold() for h in values[0]]
    idx = {k: (kepala.index(k) if k in kepala else -1) for k in KOLOM}
    semua: list[Pos] = []
    for n, r in enumerate(values[1:], start=2):
        ambil = lambda k: _sel(r, idx[k]) if idx[k] >= 0 else ""  # noqa: E731
        pid = ambil("id")
        if not pid or ambil("status").casefold() == "dihapus":
            continue
        semua.append(Pos(
            id=pid, jenis=ambil("jenis").casefold(), induk=ambil("induk"), judul=ambil("judul"), isi=ambil("isi"),
            topik=ambil("topik"), foto=[f for f in (x.strip() for x in ambil("foto").split(",")) if f],
            email=ambil("email").casefold(), nama=ambil("nama"), dibuat=ambil("dibuat"), diubah=ambil("diubah"),
            status=ambil("status"), solusi=ambil("solusi"), baris=n))
    return semua


def parse(values: list[list[Any]]) -> list[Pos]:
    """Baris sheet -> daftar pertanyaan (jawaban sudah dikelompokkan, yang dihapus dibuang)."""
    semua = _semua(values)
    tanya = {p.id: p for p in semua if p.jenis == "tanya"}
    for p in semua:
        if p.jenis == "jawab" and p.induk in tanya:
            tanya[p.induk].jawaban.append(p)
    for t in tanya.values():
        t.jawaban.sort(key=lambda j: j.dibuat)
    return list(tanya.values())


def parse_pengumuman(values: list[list[Any]]) -> list[Pos]:
    """Pengumuman terbaru dulu."""
    return sorted((p for p in _semua(values) if p.jenis == "pengumuman"), key=lambda p: (p.dibuat, p.baris), reverse=True)


# ---------- sheet ----------

def _ws(buat: bool = False):
    ss = lk_baru._ss()
    for w in ss.worksheets():
        if w.title == TAB:
            return w
    if not buat:
        return None
    w = ss.add_worksheet(TAB, rows=200, cols=len(KOLOM))
    w.update([KOLOM], f"A1:{AKHIR}1", value_input_option="RAW")
    try:
        w.freeze(rows=1)
    except Exception:
        pass
    return w


def _values(refresh: bool = False) -> list[list[Any]]:
    def load() -> list[list[Any]]:
        w = _ws()
        return w.get_values(f"A1:{AKHIR}") if w else []

    return cache.get("forum", CACHE_DETIK, load, refresh)


def baca(refresh: bool = False) -> list[Pos]:
    return parse(_values(refresh))


def pengumuman(refresh: bool = False) -> list[Pos]:
    return parse_pengumuman(_values(refresh))


def _sekarang() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _baris_baru(**isi: str) -> list[str]:
    return [isi.get(k, "") for k in KOLOM]


def _append(baris: list[list[str]]) -> None:
    with _tulis_lock:
        w = _ws(buat=True)
        w.append_rows(baris, value_input_option="RAW", insert_data_option="INSERT_ROWS",
                      table_range=f"A1:{AKHIR}1")
    cache.drop("forum")


def _cari(pid: str) -> tuple[Pos, Pos | None]:
    """(pos, pertanyaan induknya bila pos jawaban). Dibaca ulang supaya nomor baris pasti terbaru."""
    for t in baca(refresh=True):
        if t.id == pid:
            return t, None
        for j in t.jawaban:
            if j.id == pid:
                return j, t
    for p in pengumuman():
        if p.id == pid:
            return p, None
    raise ForumError("Tulisan ini tidak ditemukan. Mungkin sudah dihapus.")


def _ubah_sel(pos: Pos, nilai: dict[str, str]) -> None:
    with _tulis_lock:
        w = _ws()
        if w is None:
            raise ForumError("Tab Forum tidak ada di sheet LK.")
        sel = w.get_values(f"A{pos.baris}") if pos.baris else []
        if not sel or _sel(sel[0], 0) != pos.id:
            raise ForumError("Data forum baru saja berubah. Muat ulang halaman lalu coba lagi.")
        data = [{"range": f"{col_letter(KOLOM.index(k))}{pos.baris}", "values": [[v]]} for k, v in nilai.items()]
        w.batch_update(data, value_input_option="RAW")
    cache.drop("forum")


# ---------- aturan ----------

def _rapi(teks: str, maks: int) -> str:
    return (teks or "").strip()[:maks]


def _cek_foto(foto: list[str]) -> list[str]:
    out = [f.strip() for f in foto if f and f.strip()]
    if len(out) > MAKS_FOTO:
        raise ForumError(f"Maksimal {MAKS_FOTO} foto per tulisan.")
    if any(not all(c.isalnum() or c in "-_" for c in f) for f in out):
        raise ForumError("ID foto tidak valid.")
    return out


def _boleh(pos: Pos, email: str, admin: bool) -> None:
    if not admin and pos.email != email.casefold():
        raise ForumError("Hanya penulisnya (atau admin) yang boleh mengubah tulisan ini.")


def _id() -> str:
    return datetime.now().strftime("%y%m%d") + secrets.token_hex(3)


def buat_tanya(email: str, nama: str, judul: str, isi: str, topik: str, foto: list[str],
               jawaban: str = "", foto_jawaban: list[str] | None = None) -> str:
    judul, isi, topik = _rapi(judul, MAKS_JUDUL), _rapi(isi, MAKS_ISI), _rapi(topik, MAKS_TOPIK) or "Lainnya"
    if len(judul) < 5:
        raise ForumError("Judul pertanyaan minimal 5 huruf.")
    foto = _cek_foto(foto)
    jawaban = _rapi(jawaban, MAKS_ISI)
    kini, tid = _sekarang(), _id()
    jid = _id() if jawaban else ""
    baris = [_baris_baru(id=tid, jenis="tanya", judul=judul, isi=isi, topik=topik, foto=",".join(foto),
                         email=email.casefold(), nama=nama, dibuat=kini, solusi=jid)]
    if jawaban:
        baris.append(_baris_baru(id=jid, jenis="jawab", induk=tid, isi=jawaban,
                                 foto=",".join(_cek_foto(foto_jawaban or [])), email=email.casefold(), nama=nama,
                                 dibuat=kini))
    _append(baris)
    return tid


def buat_pengumuman(email: str, nama: str, admin: bool, judul: str, isi: str) -> str:
    if not admin:
        raise ForumError("Pengumuman hanya bisa ditulis admin.")
    judul, isi = _rapi(judul, MAKS_JUDUL), _rapi(isi, MAKS_ISI)
    if len(isi) < 5:
        raise ForumError("Isi pengumuman minimal 5 huruf.")
    pid = _id()
    _append([_baris_baru(id=pid, jenis="pengumuman", judul=judul, isi=isi, email=email.casefold(), nama=nama,
                         dibuat=_sekarang())])
    return pid


def buat_jawab(email: str, nama: str, induk: str, isi: str, foto: list[str]) -> str:
    isi = _rapi(isi, MAKS_ISI)
    if len(isi) < 2:
        raise ForumError("Jawaban masih kosong.")
    t, _ = _cari(induk)
    if t.jenis != "tanya":
        raise ForumError("Pertanyaan tidak ditemukan.")
    jid = _id()
    _append([_baris_baru(id=jid, jenis="jawab", induk=t.id, isi=isi, foto=",".join(_cek_foto(foto)),
                         email=email.casefold(), nama=nama, dibuat=_sekarang())])
    return jid


def ubah(email: str, admin: bool, pid: str, judul: str | None, isi: str | None, topik: str | None,
         foto: list[str] | None) -> None:
    pos, _ = _cari(pid)
    _boleh(pos, email, admin)
    nilai: dict[str, str] = {"diubah": _sekarang()}
    if pos.jenis == "tanya":
        if judul is not None:
            if len(judul.strip()) < 5:
                raise ForumError("Judul pertanyaan minimal 5 huruf.")
            nilai["judul"] = _rapi(judul, MAKS_JUDUL)
        if topik is not None:
            nilai["topik"] = _rapi(topik, MAKS_TOPIK) or "Lainnya"
    if pos.jenis == "pengumuman":
        if not admin:
            raise ForumError("Pengumuman hanya bisa diubah admin.")
        if judul is not None:
            nilai["judul"] = _rapi(judul, MAKS_JUDUL)
        if isi is not None and len(isi.strip()) < 5:
            raise ForumError("Isi pengumuman minimal 5 huruf.")
    if isi is not None:
        if pos.jenis == "jawab" and len(isi.strip()) < 2:
            raise ForumError("Jawaban masih kosong.")
        nilai["isi"] = _rapi(isi, MAKS_ISI)
    if foto is not None:
        nilai["foto"] = ",".join(_cek_foto(foto))
    _ubah_sel(pos, nilai)


def hapus(email: str, admin: bool, pid: str) -> None:
    pos, induk = _cari(pid)
    _boleh(pos, email, admin)
    _ubah_sel(pos, {"status": "dihapus", "diubah": _sekarang()})
    if induk and induk.solusi == pos.id:
        _ubah_sel(induk, {"solusi": ""})


def pilih_solusi(email: str, admin: bool, tid: str, jid: str) -> None:
    t, _ = _cari(tid)
    if t.jenis != "tanya":
        raise ForumError("Pertanyaan tidak ditemukan.")
    _boleh(t, email, admin)
    if jid and jid not in {j.id for j in t.jawaban}:
        raise ForumError("Jawaban tidak ditemukan.")
    _ubah_sel(t, {"solusi": jid})


# ---------- tampilan ----------

def _pos_json(p: Pos, email: str, admin: bool) -> dict[str, Any]:
    return {"id": p.id, "isi": p.isi, "foto": p.foto, "nama": p.nama or p.email.split("@")[0], "dibuat": p.dibuat,
            "diubah": p.diubah, "milik_saya": p.email == email.casefold(), "boleh_ubah": admin or p.email == email.casefold()}


def ringkas(daftar: list[Pos], email: str) -> list[dict[str, Any]]:
    out = []
    for t in daftar:
        terakhir = max([t.dibuat, *(j.dibuat for j in t.jawaban)])
        out.append({"id": t.id, "judul": t.judul, "cuplikan": " ".join(t.isi.split())[:180], "topik": t.topik,
                    "nama": t.nama or t.email.split("@")[0], "dibuat": t.dibuat, "aktif": terakhir,
                    "jawaban": len(t.jawaban), "selesai": bool(t.solusi), "ada_foto": bool(t.foto),
                    "milik_saya": t.email == email.casefold(),
                    "cari": " ".join([t.judul, t.isi, t.topik, *(j.isi for j in t.jawaban)]).casefold()})
    out.sort(key=lambda x: x["aktif"], reverse=True)
    return out


def pengumuman_json(daftar: list[Pos], email: str, admin: bool) -> list[dict[str, Any]]:
    return [{**_pos_json(p, email, admin), "judul": p.judul, "boleh_ubah": admin} for p in daftar[:20]]


def detail(pid: str, email: str, admin: bool) -> dict[str, Any]:
    t = next((x for x in baca() if x.id == pid), None)
    if t is None:
        raise ForumError("Pertanyaan tidak ditemukan. Mungkin sudah dihapus.")
    jawab = sorted(t.jawaban, key=lambda j: (j.id != t.solusi, j.dibuat))
    return {**_pos_json(t, email, admin), "judul": t.judul, "topik": t.topik, "solusi": t.solusi,
            "jawaban": [{**_pos_json(j, email, admin), "penanya": j.email == t.email} for j in jawab]}


def topik(daftar: list[Pos]) -> list[str]:
    ada = {t.topik for t in daftar if t.topik}
    return TOPIK_AWAL + sorted(ada - set(TOPIK_AWAL))


# ---------- foto (Google Drive) ----------

DRIVE = "https://www.googleapis.com/drive/v3/files"
UNGGAH = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id"
FOLDER_NAMA = "LK Monitoring - Foto Forum"
FOLDER_FILE = paths.DATA_DIR / "forum_folder.txt"
JENIS_FOTO = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
MAKS_BYTE = 8 * 1024 * 1024


def _panggil(sesi: AuthorizedSession, method: str, url: str, **kw) -> dict:
    r = sesi.request(method, url, timeout=60, **kw)
    if r.status_code >= 400:
        teks = r.text[:400]
        if r.status_code == 401:
            paparan.cabut_izin()
            raise ForumError("Izin Google Drive kedaluwarsa. Unggah fotonya lagi untuk memberi izin ulang.")
        if "SERVICE_DISABLED" in teks or "has not been used" in teks or "is disabled" in teks:
            raise ForumError("Google Drive API belum diaktifkan di project Google Cloud aplikasi ini. Minta admin "
                             "mengaktifkannya (APIs & Services → Library → Google Drive API → Enable).")
        raise ForumError(f"Google Drive menolak permintaan ({r.status_code}): {teks}")
    return r.json() if r.content else {}


def _folder(sesi: AuthorizedSession) -> str:
    try:
        fid = FOLDER_FILE.read_text(encoding="utf-8").strip() if FOLDER_FILE.exists() else ""
    except OSError:
        fid = ""
    if fid:
        try:
            info = _panggil(sesi, "GET", f"{DRIVE}/{fid}", params={"fields": "id,trashed"})
            if not info.get("trashed"):
                return fid
        except ForumError:
            pass
    info = _panggil(sesi, "POST", DRIVE, params={"fields": "id"},
                    json={"name": FOLDER_NAMA, "mimeType": "application/vnd.google-apps.folder"})
    paths.ensure_dirs()
    FOLDER_FILE.write_text(info["id"], encoding="utf-8")
    return info["id"]


def unggah_foto(isi: bytes, jenis: str, nama: str) -> str:
    if jenis not in JENIS_FOTO:
        raise ForumError("Foto harus JPG, PNG, WEBP, atau GIF.")
    if len(isi) > MAKS_BYTE:
        raise ForumError("Foto terlalu besar (maks 8 MB).")
    c = paparan._creds_slides()
    if c is None:
        raise ForumError("Belum ada izin Google Drive.")
    sesi = AuthorizedSession(c)
    meta = {"name": f"forum-{datetime.now():%Y%m%d-%H%M%S}-{_rapi(nama, 60) or 'foto'}", "parents": [_folder(sesi)]}
    batas = "lkm" + secrets.token_hex(8)
    tubuh = (f"--{batas}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
             f"--{batas}\r\nContent-Type: {jenis}\r\n\r\n").encode() + isi + f"\r\n--{batas}--".encode()
    fid = _panggil(sesi, "POST", UNGGAH, data=tubuh,
                   headers={"Content-Type": f"multipart/related; boundary={batas}"})["id"]
    try:
        _panggil(sesi, "POST", f"{DRIVE}/{fid}/permissions", json={"role": "reader", "type": "anyone"})
    except ForumError as e:
        raise ForumError(f"Foto terunggah, tapi tidak bisa dibagikan ke tim: {e}") from e
    return fid
