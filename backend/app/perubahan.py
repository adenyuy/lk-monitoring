"""Catat perubahan data Broadcast & LK (milik petugas ini) setiap kali sheet dibaca ulang.

Cara kerja: simpan potret terakhir di tabel settings, bandingkan dengan hasil baca baru,
tulis ringkasan + rincian ke tabel `perubahan`. Potret pertama tidak dicatat sebagai perubahan.
"""

import json
import logging
import re
from collections import Counter
from typing import Any, Iterable

from . import db, schedule

log = logging.getLogger(__name__)
MAKS_RINCIAN = 200
MAKS_BARIS_LOG = 300


def _petugas() -> str:
    from .sheets import normalize_petugas

    return normalize_petugas(db.get_setting("nama_petugas") or "")


def _simpan_log(sumber: str, judul: str, ringkasan: str, rincian: list[str]) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO perubahan(waktu, sumber, judul, ringkasan, rincian) VALUES(?,?,?,?,?)",
            (schedule.now().isoformat(timespec="seconds"), sumber, judul, ringkasan,
             json.dumps(rincian[:MAKS_RINCIAN], ensure_ascii=False)),
        )
        c.execute("DELETE FROM perubahan WHERE id NOT IN (SELECT id FROM perubahan ORDER BY id DESC LIMIT ?)",
                  (MAKS_BARIS_LOG,))


def _ganti_potret(kunci: str, data: dict) -> dict | None:
    """Simpan potret baru; kembalikan potret lama bila milik petugas yang sama."""
    lama = db.get_setting(kunci)
    petugas = _petugas()
    db.set_setting(kunci, {"petugas": petugas, "data": data})
    if not lama or lama.get("petugas") != petugas:
        return None
    return lama.get("data") or {}


# ---------- Broadcast ----------

def sekolah_di_pesan(pesan: str) -> list[str]:
    """Nama sekolah dari daftar bernomor di pesan ('1. SD NEGERI ...')."""
    return [re.sub(r"\s+", " ", m).strip().upper() for m in re.findall(r"^\s*\d+\.\s*(.+?)\s*$", pesan, re.M)]


def catat_broadcast(rows: Iterable[Any]) -> None:
    try:
        from .sheets import filter_petugas

        milik = filter_petugas(list(rows), db.get_setting("nama_petugas") or "")
        baru = {r.nomor: {"nama": r.nama_fasil, "hash": r.hash_pesan, "sekolah": sekolah_di_pesan(r.pesan)}
                for r in milik if r.nomor}
        lama = _ganti_potret("potret_broadcast", baru)
        if lama is None:
            return
        tambah = [baru[n]["nama"] for n in baru if n not in lama]
        hilang = [lama[n]["nama"] for n in lama if n not in baru]
        rincian = [f"Fasil baru: {x}" for x in tambah] + [f"Tidak ada lagi di Broadcast: {x}" for x in hilang]
        pesan_berubah = 0
        for n in baru.keys() & lama.keys():
            if baru[n]["hash"] == lama[n]["hash"]:
                continue
            pesan_berubah += 1
            plus = [s for s in baru[n]["sekolah"] if s not in lama[n]["sekolah"]]
            minus = [s for s in lama[n]["sekolah"] if s not in baru[n]["sekolah"]]
            if plus or minus:
                bagian = ([f"+ {', '.join(plus)}"] if plus else []) + ([f"− {', '.join(minus)}"] if minus else [])
                rincian.append(f"Pesan {baru[n]['nama']} berubah: {'; '.join(bagian)}")
            else:
                rincian.append(f"Pesan {baru[n]['nama']} berubah (daftar sekolah sama)")
        if not rincian:
            return
        ringkas = []
        if tambah:
            ringkas.append(f"{len(tambah)} fasil baru")
        if hilang:
            ringkas.append(f"{len(hilang)} fasil hilang")
        if pesan_berubah:
            ringkas.append(f"{pesan_berubah} pesan berubah")
        _simpan_log("broadcast", "Broadcast", ", ".join(ringkas), rincian)
    except Exception:
        log.exception("Gagal mencatat perubahan Broadcast")


# ---------- LK ----------

def _p(x: float | None) -> str:
    return "–" if x is None else f"{x:.1f}".replace(".", ",") + "%"


def _singkat(prio: str) -> str:
    return {"prioritas 1": "P1", "prioritas 2": "P2", "prioritas 3": "P3", "selesai": "Selesai"}.get(
        prio.strip().lower(), prio or "–")


def catat_lk(tab: str, sekolah: Iterable[Any]) -> None:
    try:
        from .sheets import normalize_petugas

        petugas = _petugas()
        baru = {s.npsn: [s.nama, s.fasil, s.prioritas, None if s.progres is None else round(s.progres, 1),
                         s.submit, s.reviu]
                for s in sekolah if normalize_petugas(s.petugas) == petugas}
        lama = _ganti_potret(f"potret_lk:{tab}", baru)
        if lama is None:
            return
        rincian: list[str] = []
        transisi: Counter = Counter()
        lewat50 = 0
        for npsn in baru.keys() & lama.keys():
            nama, fasil, prio, prog, sub, rev = baru[npsn]
            _, _, prio0, prog0, sub0, rev0 = lama[npsn]
            if prio != prio0:
                transisi[f"{_singkat(prio0)} → {_singkat(prio)}"] += 1
                rincian.append(f"{nama} ({fasil}): {_singkat(prio0)} → {_singkat(prio)}")
            if prog is not None and prog >= 50 and (prog0 is None or prog0 < 50):
                lewat50 += 1
                rincian.append(f"{nama}: progres {_p(prog0)} → {_p(prog)}")
            if sub == "Ya" and sub0 != "Ya":
                rincian.append(f"{nama}: laporan 50% sudah submit")
            if rev == "Ya" and rev0 != "Ya":
                rincian.append(f"{nama}: laporan 50% sudah direviu")
        tambah = [baru[n][0] for n in baru if n not in lama]
        hilang = [lama[n][0] for n in lama if n not in baru]
        rincian += [f"Sekolah baru: {x}" for x in tambah] + [f"Tidak ada lagi di LK: {x}" for x in hilang]
        if not rincian:
            return
        ringkas = [f"{v} sekolah {k}" for k, v in transisi.most_common(4)]
        if lewat50:
            ringkas.append(f"{lewat50} progres melewati 50%")
        if tambah:
            ringkas.append(f"{len(tambah)} sekolah baru")
        if hilang:
            ringkas.append(f"{len(hilang)} sekolah hilang")
        if not ringkas:
            ringkas.append(f"{len(rincian)} perubahan status")
        _simpan_log("lk", f"LK {tab}", ", ".join(ringkas), rincian)
    except Exception:
        log.exception("Gagal mencatat perubahan LK")


def daftar(batas: int = 50) -> list[dict[str, Any]]:
    rows = db.query("SELECT id, waktu, sumber, judul, ringkasan, rincian FROM perubahan ORDER BY id DESC LIMIT ?",
                    (batas,))
    return [{**dict(r), "rincian": json.loads(r["rincian"])} for r in rows]
