"""Akses tabel `sends` dan `chat_status`."""

from collections import defaultdict
from typing import Any

from . import db


def record_send(
    *, tanggal: str, waktu: str, sesi: int, nama_fasil: str, nomor: str, hash_pesan: str,
    status: str, keterangan: str = "", coba: bool = False,
) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status, keterangan, coba) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status, keterangan, int(coba)),
        )


def sends_real() -> list[dict[str, Any]]:
    """Semua percobaan kirim sungguhan (bukan mode coba), urut waktu naik."""
    rows = db.connect().execute(
        "SELECT * FROM sends WHERE coba = 0 ORDER BY waktu, id"
    ).fetchall()
    return [dict(r) for r in rows]


def counts(tanggal: str) -> tuple[int, dict[int, int]]:
    """(terkirim hari itu, {sesi: terkirim}). Hanya status terkirim yang mengurangi kuota."""
    rows = db.connect().execute(
        "SELECT sesi, COUNT(*) AS n FROM sends WHERE tanggal = ? AND status = 'terkirim' AND coba = 0 GROUP BY sesi",
        (tanggal,),
    ).fetchall()
    per = defaultdict(int, {r["sesi"]: r["n"] for r in rows})
    return sum(per.values()), dict(per)


def sends_on(tanggal: str) -> list[dict[str, Any]]:
    rows = db.connect().execute(
        "SELECT * FROM sends WHERE tanggal = ? ORDER BY waktu, id", (tanggal,)
    ).fetchall()
    return [dict(r) for r in rows]


def to_refresh(since_tanggal: str) -> list[str]:
    """Nomor yang terkirim sejak tanggal itu dan belum tercatat 'dibalas'."""
    rows = db.connect().execute(
        "SELECT DISTINCT s.nomor FROM sends s LEFT JOIN chat_status c ON c.nomor = s.nomor "
        "WHERE s.status = 'terkirim' AND s.coba = 0 AND s.tanggal >= ? "
        "AND (c.status IS NULL OR c.status != 'dibalas')",
        (since_tanggal,),
    ).fetchall()
    return [r["nomor"] for r in rows]


def save_chat_status(nomor: str, status: str, balasan: str, dicek: str) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO chat_status(nomor, status, balasan_terakhir, waktu_balasan, dicek) VALUES(?,?,?,?,?) "
            "ON CONFLICT(nomor) DO UPDATE SET status=excluded.status, "
            "balasan_terakhir=CASE WHEN excluded.balasan_terakhir != '' THEN excluded.balasan_terakhir ELSE chat_status.balasan_terakhir END, "
            "waktu_balasan=CASE WHEN excluded.balasan_terakhir != '' AND excluded.balasan_terakhir != chat_status.balasan_terakhir "
            "THEN excluded.dicek ELSE chat_status.waktu_balasan END, dicek=excluded.dicek",
            (nomor, status, balasan, dicek if balasan else "", dicek),
        )


def chat_status_all() -> dict[str, dict[str, Any]]:
    rows = db.connect().execute("SELECT * FROM chat_status").fetchall()
    return {r["nomor"]: dict(r) for r in rows}
