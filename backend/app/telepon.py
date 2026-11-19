"""Telepon ke fasil: kapan perlu ditelepon, dan catatan telepon (manual dari aplikasi atau terbaca dari WhatsApp).

Perlu telepon / hubungi koordinator (tanda informasi, bukan kode), dihitung dari kode Log Komunikasi fasil:
  - nomor tidak ada WhatsApp (N)
  - 2 hari kerja berturut-turut sulit dihubungi: R, C, C2, atau TX (boleh campur, mis. R lalu C2)

Catatan telepon:
  - diangkat  -> hari itu ditulis TP di Log Komunikasi; tanda hilang karena kodenya bukan R / C lagi
  - tidak     -> hari itu ditulis TX; tanda jadi "sudah dicoba hari ini" dan muncul lagi besok bila masih belum ada kabar
Menghubungi koordinator lewat aplikasi menulis K hari itu, jadi tanda juga hilang (K bukan kode sulit).
Telepon WhatsApp dari HP terbaca lewat pendengar (neonize) bila perangkat tertaut menerima kabar panggilannya.
"""

from datetime import date, datetime
from typing import Any

from . import db, schedule

SCHEMA = """
CREATE TABLE IF NOT EXISTS telepon (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nomor   TEXT NOT NULL,
    waktu   TEXT NOT NULL,
    hasil   TEXT NOT NULL,              -- diangkat | tidak
    sumber  TEXT NOT NULL DEFAULT 'manual',  -- manual | wa
    panggil TEXT NOT NULL DEFAULT ''    -- ID panggilan WhatsApp (sumber wa)
);
CREATE INDEX IF NOT EXISTS telepon_nomor ON telepon(nomor, waktu);
"""
_siap = False
HASIL = {"diangkat": "Diangkat", "tidak": "Tidak diangkat"}


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
        _siap = True


def catat(nomor: str, hasil: str, sumber: str = "manual", panggil: str = "", waktu: datetime | None = None) -> int:
    if hasil not in HASIL:
        raise ValueError("Hasil telepon tidak dikenal.")
    _db()
    w = (waktu or schedule.now()).isoformat(timespec="seconds")
    with db.tx() as c:
        if panggil:  # satu panggilan WhatsApp = satu catatan (diperbarui bila akhirnya diangkat)
            ada = c.execute("SELECT id FROM telepon WHERE panggil = ?", (panggil,)).fetchone()
            if ada:
                c.execute("UPDATE telepon SET hasil = CASE WHEN hasil = 'diangkat' THEN hasil ELSE ? END WHERE id = ?",
                          (hasil, ada[0]))
                return ada[0]
        cur = c.execute("INSERT INTO telepon(nomor, waktu, hasil, sumber, panggil) VALUES(?,?,?,?,?)",
                        (nomor, w, hasil, sumber, panggil))
        return int(cur.lastrowid)


def riwayat(nomor: str, batas: int = 10) -> list[dict[str, Any]]:
    _db()
    return [{"waktu": r["waktu"], "hasil": r["hasil"], "label": HASIL[r["hasil"]], "sumber": r["sumber"]}
            for r in db.query("SELECT waktu, hasil, sumber FROM telepon WHERE nomor = ? ORDER BY waktu DESC LIMIT ?",
                              (nomor, batas))]


def hari_kerja_terakhir(hari: date, jumlah: int, mulai: str = "") -> list[str]:
    from .komunikasi import hari_terakhir

    return hari_terakhir(hari, jumlah, mulai)


def perlu(kode: dict[str, str], hari: str, mulai_lk: str = "") -> tuple[bool, str]:
    """(perlu ditelepon, alasan) dari kode Log Komunikasi fasil {tanggal: kode}."""
    dua = hari_kerja_terakhir(date.fromisoformat(hari), 2, mulai_lk)
    if not dua:
        return False, ""
    k = [kode.get(d, "").upper() for d in dua]
    if k[-1] == "N":
        return True, "Nomor tidak ada WhatsApp"
    if len(k) == 2 and k[0] == k[1] == "R":
        return True, "2 hari hanya dibaca, belum membalas"
    if len(k) == 2 and k[0] == k[1] == "C":
        return True, "2 hari pesan tidak sampai (centang satu)"
    if len(k) == 2 and all(x in SULIT for x in k):
        return True, "2 hari sulit dihubungi (" + " lalu ".join(ARTI_SULIT[x] for x in k) + ")"
    return False, ""


SULIT = {"R", "C", "C2", "TX", "N"}
ARTI_SULIT = {"R": "dibaca", "C": "centang satu", "C2": "centang dua", "TX": "tidak diangkat", "N": "tanpa WA"}


def keadaan(nomor: str, kode: dict[str, str], hari: str, mulai_lk: str = "") -> dict[str, Any]:
    """Tanda telepon untuk satu fasil: perlu, alasan, sudah dicoba hari ini, dan telepon terakhir."""
    p, alasan = perlu(kode, hari, mulai_lk)
    ada = riwayat(nomor, 1) if nomor else []
    terakhir = ada[0] if ada else None
    dicoba = bool(p and terakhir and terakhir["waktu"][:10] == hari and terakhir["hasil"] == "tidak")
    return {"perlu": p and not dicoba, "alasan": alasan, "dicoba": dicoba, "terakhir": terakhir}
