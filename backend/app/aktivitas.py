"""Riwayat per fasil: Broadcast terkirim (dari tabel sends) + kejadian lain (tabel aktivitas).

Kejadian lain: pesan dibaca / dibalas fasil (terdeteksi saat chat dicek), balasan dari aplikasi,
isian LK disimpan, centang tahap manual, permintaan kirim ulang.
"""

import logging
import re
from datetime import date, timedelta
from typing import Any

from . import db, schedule

log = logging.getLogger(__name__)
SIMPAN_HARI = 90

LABEL = {
    "kirim": "Broadcast terkirim",
    "gagal": "Broadcast gagal",
    "dibaca": "Dibaca",
    "dibalas": "Fasil membalas",
    "balas": "Chat dari aplikasi",
    "lk": "Isian LK",
    "tahap": "Tahap manual",
    "ulang": "Kirim ulang",
}


def catat(nomor: str, jenis: str, ringkasan: str, nama: str = "") -> None:
    """Simpan satu kejadian. Tidak pernah menggagalkan aksi utama."""
    try:
        with db.tx() as c:
            c.execute("INSERT INTO aktivitas(waktu, nomor, nama, jenis, ringkasan) VALUES(?,?,?,?,?)",
                      (schedule.now().isoformat(timespec="seconds"), nomor, nama, jenis, ringkasan[:300]))
            batas = (schedule.now().date() - timedelta(days=SIMPAN_HARI)).isoformat()
            c.execute("DELETE FROM aktivitas WHERE waktu < ?", (batas,))
    except Exception:
        log.exception("Gagal mencatat aktivitas")


def _nama_map() -> dict[str, str]:
    """{nomor: nama fasil} dari catatan kirim, Broadcast, dan LK (bila terbaca)."""
    out = {r["nomor"]: r["nama"] for r in db.query("SELECT nomor, nama FROM aktivitas WHERE nama != ''")}
    out.update({r["nomor"]: r["nama_fasil"] for r in db.query("SELECT nomor, nama_fasil FROM sends")})
    try:
        from .sheets import nomor_lk, read_broadcast, read_lk, week_aktif

        for r in read_broadcast():
            if r.nomor:
                out.setdefault(r.nomor, r.nama_fasil)
        for s in read_lk(week_aktif()):
            for n in nomor_lk(s):
                out.setdefault(n, s.fasil)
    except Exception:
        pass
    return out


def daftar(tanggal: str | None = None, nomor: str | None = None) -> list[dict[str, Any]]:
    """Kejadian satu hari (`tanggal`) atau seluruh riwayat satu fasil (`nomor`), terbaru di atas."""
    from .perubahan import _sesi

    syarat, arg = [], []
    if tanggal:
        syarat.append("substr(waktu, 1, 10) = ?")
        arg.append(tanggal)
    if nomor:
        syarat.append("nomor = ?")
        arg.append(nomor)
    where = (" AND " + " AND ".join(syarat)) if syarat else ""
    sends = db.query("SELECT id, waktu, nomor, nama_fasil, status, keterangan FROM sends "
                     f"WHERE coba = 0 AND status IN ('terkirim', 'gagal'){where}", tuple(arg))
    lain = db.query(f"SELECT id, waktu, nomor, nama, jenis, ringkasan FROM aktivitas WHERE 1=1{where}", tuple(arg))
    nama = _nama_map() if any(not r["nama"] for r in lain) else {}

    out = []
    for r in sends:
        jenis = "kirim" if r["status"] == "terkirim" else "gagal"
        out.append({"id": f"s{r['id']}", "waktu": r["waktu"], "nomor": r["nomor"], "nama": r["nama_fasil"],
                    "jenis": jenis, "label": LABEL[jenis],
                    "ringkasan": "Pesan Broadcast terkirim" if jenis == "kirim"
                    else re.sub(r"\s*\([a-z_]+\)\s*$", "", r["keterangan"] or "") or "Gagal terkirim"})
    for r in lain:
        out.append({"id": f"a{r['id']}", "waktu": r["waktu"], "nomor": r["nomor"],
                    "nama": r["nama"] or nama.get(r["nomor"], r["nomor"]),
                    "jenis": r["jenis"], "label": LABEL.get(r["jenis"], r["jenis"]), "ringkasan": r["ringkasan"]})
    out.sort(key=lambda x: x["waktu"], reverse=True)
    for x in out:
        x["sesi"], x["sesi_label"] = _sesi(x["waktu"])
    return out


def per_hari(awal: date, akhir: date) -> dict[str, int]:
    a, b = awal.isoformat(), akhir.isoformat()
    out: dict[str, int] = {}
    for r in db.query("SELECT substr(waktu, 1, 10) AS tgl, COUNT(*) AS n FROM sends WHERE coba = 0 "
                      "AND status IN ('terkirim', 'gagal') AND waktu >= ? AND waktu < ? GROUP BY tgl", (a, b)):
        out[r["tgl"]] = out.get(r["tgl"], 0) + r["n"]
    for r in db.query("SELECT substr(waktu, 1, 10) AS tgl, COUNT(*) AS n FROM aktivitas "
                      "WHERE waktu >= ? AND waktu < ? GROUP BY tgl", (a, b)):
        out[r["tgl"]] = out.get(r["tgl"], 0) + r["n"]
    return out


def paling_awal() -> str:
    r = db.query("SELECT MIN(w) AS w FROM (SELECT MIN(waktu) AS w FROM sends WHERE coba = 0 "
                 "UNION ALL SELECT MIN(waktu) FROM aktivitas)")
    return (r[0]["w"] or "")[:10] if r else ""


def fasil_tercatat() -> list[dict[str, str]]:
    """Fasil yang punya riwayat, untuk pilihan 'lihat riwayat fasil'."""
    rows = db.query("SELECT nomor, MAX(waktu) AS w FROM (SELECT nomor, waktu FROM sends WHERE coba = 0 "
                    "AND status IN ('terkirim', 'gagal') UNION ALL SELECT nomor, waktu FROM aktivitas) GROUP BY nomor")
    nama = _nama_map()
    out = [{"nomor": r["nomor"], "nama": nama.get(r["nomor"], r["nomor"]), "terakhir": r["w"]} for r in rows]
    return sorted(out, key=lambda x: x["nama"].casefold())
