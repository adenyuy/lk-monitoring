"""Isian LK otomatis: status komunikasi sekolah mengikuti keadaan chat fasil minggu ini.

- Fasil membalas                          -> "0. Terhubung"
- Pesan dibaca tapi tidak dibalas         -> "3. Chat hanya di Read"
- Nomor tidak terdaftar di WhatsApp       -> "1. Nomor Tidak Terhubung Whatsapp"

Terhubung menimpa status kosong atau status otomatis lain (Read / Tidak terhubung / Checklist 1); status lain
hanya mengisi yang kosong, jadi pilihan manual (mis. "Respon Lambat") tidak tertimpa. Sekolah Selesai tidak disentuh.

Alasan yang sudah pasti dari data LK juga diisi di kolom sesi hari ini (bila masih kosong):
- belum submit dan progres < 50%  -> alasan submit "Progres fisik belum mencapai 50%"
- belum submit                    -> alasan reviu "Sekolah Belum Submit"
Bila datanya sudah berubah (mis. sekolah sudah submit), alasan otomatis yang tidak berlaku lagi dikosongkan.
Dijalankan di latar (tidak menahan pengecekan chat) dan tidak pernah menggagalkan aksi utama.
"""

import logging
import os
import threading
import time

from . import aktivitas, db, tahap
from .send_queue import GAGAL_PERMANEN
from .sheets import (
    ISIAN_KEYS, kolom_lk, nomor_key, nomor_lk, normalize_petugas, read_lk, read_validasi, sekolah_per_fasil, week_aktif,
    write_isian,
)

log = logging.getLogger(__name__)
_lock = threading.Lock()
_bangun = threading.Event()
_mulai = threading.Lock()
_thread: threading.Thread | None = None

TERHUBUNG, TIDAK_WA, HANYA_READ = "terhubung", "tidak_wa", "read"


def pilihan(opsi: list[str], jenis: str) -> str:
    """Teks pilihan status komunikasi (tab validasi) untuk `jenis`."""
    def cocok(o: str) -> bool:
        t = o.lower()
        if jenis == TERHUBUNG:
            return "terhubung" in t and "tidak" not in t and "belum" not in t
        if jenis == TIDAK_WA:
            return "tidak terhubung" in t or ("tidak" in t and "whatsapp" in t)
        return "read" in t or "dibaca" in t

    return next((o for o in opsi if cocok(o)), "")


def pilihan_terhubung(opsi: list[str]) -> str:
    return pilihan(opsi, TERHUBUNG)


def _boleh_ditimpa(nilai: str, jenis: str) -> bool:
    t = nilai.strip().lower()
    if not t:
        return True
    return jenis == TERHUBUNG and ("read" in t or "tidak terhubung" in t or "checklist" in t)


def status_minggu() -> dict[str, str]:
    """{nomor: jenis} dari kiriman dan pengecekan chat minggu ini."""
    senin = tahap.senin_iso()
    out: dict[str, str] = {}
    for r in db.query("SELECT nomor FROM sends WHERE coba = 0 AND status = 'gagal' AND waktu >= ? AND keterangan LIKE ?",
                      (senin, f"%{GAGAL_PERMANEN}%")):
        out[r["nomor"]] = TIDAK_WA
    for n, k in tahap.kontak_minggu().items():
        if k["dibalas"]:
            out[n] = TERHUBUNG
        elif k["dibaca"]:
            out[n] = HANYA_READ
        elif k["terkirim"] and out.get(n) == TIDAK_WA:
            del out[n]  # sempat gagal tapi akhirnya terkirim
    # Membalas minggu ini walau pesan kita terkirim minggu lalu
    for r in db.query("SELECT nomor FROM chat_status WHERE status = 'dibalas' AND waktu_balasan >= ?", (senin,)):
        out[r["nomor"]] = TERHUBUNG
    return out


def _cari(opsi: list[str], kata: str) -> str:
    return next((o for o in opsi if kata in o.lower()), "")


def alasan_pasti(s, opsi: dict[str, list[str]]) -> dict[str, str]:
    """{b1/c1: pilihan} yang sudah pasti dari progres & status submit (sama dengan isianOtomatis di web)."""
    if str(s.submit).strip().lower() == "ya":
        return {}
    out = {}
    if s.progres is None or s.progres < 50:
        out["b1"] = _cari(opsi["alasan_submit"], "belum mencapai 50")
    out["c1"] = _cari(opsi["alasan_reviu"], "belum submit")
    return {k: v for k, v in out.items() if v}


def isi_alasan(week: str | None = None, data=None, kol=None) -> int:
    """Isi alasan yang sudah pasti di kolom sesi hari ini untuk sekolah binaan petugas ini."""
    petugas = normalize_petugas(db.get_setting("nama_petugas") or "")
    if not petugas:
        return 0
    week = week or week_aktif()
    opsi = read_validasi()
    otomatis = {"b1": _cari(opsi["alasan_submit"], "belum mencapai 50"), "c1": _cari(opsi["alasan_reviu"], "belum submit")}
    blok = tahap.blok_hari_ini()
    kol = kol or kolom_lk(week, refresh=True)
    ubah, per_fasil = [], {}
    for s in data if data is not None else read_lk(week, refresh=True):
        if normalize_petugas(s.petugas) != petugas or not tahap.perlu_isian(s):
            continue
        isi = s.isian.get(blok, {})
        pasti = alasan_pasti(s, opsi)
        sel = {}
        for k, oto in otomatis.items():
            lama = (isi.get(k) or "").strip()
            if k in pasti and not lama:
                sel[k] = pasti[k]
            elif k not in pasti and oto and lama == oto:
                sel[k] = ""  # tidak berlaku lagi
        if sel:
            ubah.append((s, sel))
            per_fasil.setdefault((nomor_lk(s) or [f"nama:{s.fasil}"])[0], []).append(s)
    if not ubah:
        return 0
    write_isian(week, [(s, {kol.blok[blok][ISIAN_KEYS.index(k)]: v for k, v in sel.items()}) for s, sel in ubah], kol)
    for s, sel in ubah:
        s.isian.setdefault(blok, {}).update(sel)
    for nomor, sekolah in per_fasil.items():
        aktivitas.catat(nomor, "lk", f"Alasan otomatis (belum 50% / belum submit) untuk {len(sekolah)} sekolah",
                        sekolah[0].fasil)
    return len(ubah)


def sinkron() -> int:
    """Tulis isian otomatis (status komunikasi + alasan pasti) ke LK. Mengembalikan jumlah sekolah yang diubah.
    LK dibaca SEKALI per putaran untuk keduanya (hemat kuota baca Google Sheets)."""
    with _lock:
        try:
            week = week_aktif()
            data = read_lk(week, refresh=True)
            kol = kolom_lk(week, refresh=True)
        except Exception:
            log.exception("LK tidak terbaca untuk isian otomatis")
            return 0
        n = 0
        try:
            n = isi_alasan(week, data, kol)
        except Exception:
            log.exception("Gagal mengisi alasan otomatis")
        return n + _sinkron_komunikasi(week, data, kol)


def _sinkron_komunikasi(week: str, data, kol) -> int:
    try:
        status = status_minggu()
        petugas = db.get_setting("nama_petugas") or ""
        if not status or not petugas:
            return 0
        per_fasil = sekolah_per_fasil(data, petugas)
        opsi = read_validasi()["komunikasi"]
        ubah, catatan = [], []
        for nomor, jenis in status.items():
            target = pilihan(opsi, jenis)
            sekolah = [s for s in per_fasil.get(nomor_key(nomor), [])
                       if tahap.perlu_isian(s) and s.komunikasi != target and _boleh_ditimpa(s.komunikasi, jenis)]
            if target and sekolah:
                ubah += [(s, target) for s in sekolah]
                catatan.append((nomor, target, sekolah))
        if not ubah:
            return 0
        write_isian(week, [(s, {kol.komunikasi: t}) for s, t in ubah], kol)
        for s, t in ubah:
            s.komunikasi = t
        for nomor, t, sekolah in catatan:
            aktivitas.catat(nomor, "lk", f"Status komunikasi otomatis “{t}” untuk {len(sekolah)} sekolah",
                            sekolah[0].fasil)
        return len(ubah)
    except Exception:
        log.exception("Gagal mengisi status komunikasi otomatis")
        return 0


JEDA_MIN = 3 * 60  # paling sering sekali per 3 menit: tiap putaran membaca seluruh LK


def _loop() -> None:
    terakhir = 0.0
    while True:
        _bangun.wait(timeout=30 * 60)  # juga tiap 30 menit: progres/submit bisa berubah karena tarik cutoff
        # kumpulkan pemicu (mis. pindai chat banyak fasil) jadi sekali tulis
        time.sleep(max(5.0, JEDA_MIN - (time.monotonic() - terakhir)))
        _bangun.clear()
        sinkron()
        terakhir = time.monotonic()


def picu() -> None:
    """Jadwalkan sinkron di latar. Aman dipanggil berkali-kali."""
    if os.environ.get("LKM_LK_OTOMATIS_OFF") == "1":
        return
    global _thread
    _bangun.set()
    with _mulai:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_loop, name="lk-otomatis", daemon=True)
            _thread.start()
