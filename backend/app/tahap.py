"""Tahap komunikasi dengan fasil dan kelengkapan isian LK.

Dipakai panel fasil dan halaman Rekap supaya hitungannya sama.
"""

from datetime import timedelta
from typing import Any

from . import schedule
from .sheets import Sekolah

TAHAP = (
    ("terkirim", "Sudah dihubungi"),
    ("dibaca", "Dibaca"),
    ("dibalas", "Fasil membalas"),
    ("ditanya", "Isian LK ditanyakan"),
    ("lk_lengkap", "Isian LK lengkap"),
)
BLOK_LABEL = {1: "Senin–Rabu", 2: "Rabu–Jumat"}
BLOK_KOLOM_LABEL = {1: "P–U", 2: "V–AA"}


def blok_hari_ini() -> int:
    """Senin–Selasa isi blok 1 (P–U), Rabu dan seterusnya blok 2 (V–AA)."""
    return 1 if schedule.now().weekday() <= 1 else 2


def grup_relevan(s: Sekolah) -> list[str]:
    """Alasan yang wajib diisi di LK, mengikuti tahapan sekolah:
    progres < 50% -> progres, submit, reviu; sudah 50% tapi belum submit -> submit, reviu;
    sudah submit tapi belum direviu -> reviu saja.

    Sekolah yang belum submit dapat isian otomatis di aplikasi (b bila progres < 50%, c selalu)."""
    if s.progres is None or s.progres < 50:
        return ["a", "b", "c"]
    if s.submit != "Ya":
        return ["b", "c"]
    if s.reviu != "Ya":
        return ["c"]
    return []


def sekolah_lengkap(s: Sekolah, blok: int) -> bool:
    """Lengkap bila status komunikasi terisi dan semua alasan yang relevan terisi di blok itu."""
    if s.prioritas.strip().lower() == "selesai":
        return True
    isi = s.isian.get(blok, {})
    return bool(s.komunikasi) and all(isi.get(f"{g}1") for g in grup_relevan(s))


def perlu_isian(s: Sekolah) -> bool:
    return s.prioritas.strip().lower() != "selesai"


def senin_iso() -> str:
    """Awal minggu ini (Senin 00.00) dalam format ISO, untuk membandingkan string waktu."""
    d = schedule.now().date()
    return (d - timedelta(days=d.weekday())).isoformat()


def kontak_minggu() -> dict[str, dict[str, bool]]:
    """Status kontak per nomor MINGGU INI (Senin–Minggu).

    terkirim = Broadcast terkirim atau chat dikirim dari aplikasi; dibaca / dibalas dari pengecekan chat.
    Minggu berikutnya semuanya mulai dari belum lagi.
    """
    from . import db

    senin = senin_iso()
    out: dict[str, dict[str, bool]] = {}

    def e(n: str) -> dict[str, bool]:
        return out.setdefault(n, {"terkirim": False, "dibaca": False, "dibalas": False, "gagal": False})

    kirim_akhir: dict[str, str] = {}
    for r in db.query("SELECT nomor, status, waktu FROM sends WHERE coba = 0 AND waktu >= ? ORDER BY waktu, id",
                      (senin,)):
        if r["status"] == "terkirim":
            e(r["nomor"])["terkirim"] = True
            kirim_akhir[r["nomor"]] = max(kirim_akhir.get(r["nomor"], ""), r["waktu"])
        elif r["status"] == "gagal" and not e(r["nomor"])["terkirim"]:
            e(r["nomor"])["gagal"] = True
    for r in db.query("SELECT nomor, jenis, waktu FROM aktivitas WHERE waktu >= ?", (senin,)):
        x = e(r["nomor"])
        if r["jenis"] == "balas":
            x["terkirim"] = True
            kirim_akhir[r["nomor"]] = max(kirim_akhir.get(r["nomor"], ""), r["waktu"])
        elif r["jenis"] == "dibaca":
            x["dibaca"] = True
        elif r["jenis"] == "dibalas":
            x["dibaca"] = x["dibalas"] = True
    for r in db.query("SELECT nomor, status, waktu_balasan, dicek FROM chat_status"):
        x = out.get(r["nomor"])
        if not x or not x["terkirim"]:
            continue  # status chat lama (minggu lalu) tidak dihitung
        # Status chat dicek setelah pesan minggu ini dikirim -> berlaku untuk pesan itu
        if r["status"] in ("dibaca", "dibalas") and (r["dicek"] or "") >= kirim_akhir.get(r["nomor"], ""):
            x["dibaca"] = True
        if r["status"] == "dibalas" and (r["waktu_balasan"] or "") >= senin:
            x["dibalas"] = True
    for x in out.values():
        if x["terkirim"]:
            x["gagal"] = False
    return out


def manual_minggu(manual: dict[str, dict]) -> dict[str, dict]:
    """Centang manual hanya berlaku di minggu saat dicentang."""
    senin = senin_iso()
    return {k: v for k, v in manual.items() if (v.get("waktu") or "") >= senin}


def hitung(nomor: str, sekolah: list[Sekolah], kontak: dict[str, bool] | None,
           manual: dict[str, dict], blok: int) -> list[dict[str, Any]]:
    """Status tiap tahap untuk satu fasil minggu ini. Centang manual (minggu ini) menimpa deteksi otomatis."""
    k = kontak or {}
    perlu = [x for x in sekolah if perlu_isian(x)]
    auto = {
        "terkirim": bool(k.get("terkirim")),
        "dibaca": bool(k.get("dibaca")),
        "dibalas": bool(k.get("dibalas")),
        "ditanya": False,
        "lk_lengkap": bool(perlu) and all(sekolah_lengkap(x, blok) for x in perlu),
    }
    manual = manual_minggu(manual)
    out = []
    for kode, label in TAHAP:
        m = manual.get(kode)
        if m is not None and kode != "lk_lengkap":
            out.append({"kode": kode, "label": label, "selesai": m["nilai"], "sumber": m["sumber"], "waktu": m["waktu"]})
        else:
            out.append({"kode": kode, "label": label, "selesai": auto[kode], "sumber": "otomatis", "waktu": ""})
    return out
