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
    rows = db.query("SELECT * FROM sends WHERE coba = 0 ORDER BY waktu, id")
    return [dict(r) for r in rows]


def counts(tanggal: str) -> tuple[int, dict[int, int]]:
    """(terkirim hari itu, {sesi: terkirim}). Hanya status terkirim yang mengurangi kuota."""
    rows = db.query(
        "SELECT sesi, COUNT(*) AS n FROM sends WHERE tanggal = ? AND status = 'terkirim' AND coba = 0 GROUP BY sesi",
        (tanggal,),
    )
    per = defaultdict(int, {r["sesi"]: r["n"] for r in rows})
    return sum(per.values()), dict(per)


def sends_on(tanggal: str) -> list[dict[str, Any]]:
    rows = db.query("SELECT * FROM sends WHERE tanggal = ? ORDER BY waktu, id", (tanggal,))
    return [dict(r) for r in rows]


def to_refresh(since_tanggal: str) -> list[str]:
    """Nomor yang terkirim sejak tanggal itu dan belum tercatat 'dibalas'."""
    rows = db.query(
        "SELECT DISTINCT s.nomor FROM sends s LEFT JOIN chat_status c ON c.nomor = s.nomor "
        "WHERE s.status = 'terkirim' AND s.coba = 0 AND s.tanggal >= ? "
        "AND (c.status IS NULL OR c.status != 'dibalas')",
        (since_tanggal,),
    )
    return [r["nomor"] for r in rows]


def save_chat_status(nomor: str, status: str, balasan: str, dicek: str) -> None:
    lama = db.query("SELECT status, balasan_terakhir FROM chat_status WHERE nomor = ?", (nomor,))
    lama_st = lama[0]["status"] if lama else ""
    lama_bls = lama[0]["balasan_terakhir"] if lama else ""
    with db.tx() as c:
        c.execute(
            "INSERT INTO chat_status(nomor, status, balasan_terakhir, waktu_balasan, dicek) VALUES(?,?,?,?,?) "
            "ON CONFLICT(nomor) DO UPDATE SET status=excluded.status, "
            "balasan_terakhir=CASE WHEN excluded.balasan_terakhir != '' THEN excluded.balasan_terakhir ELSE chat_status.balasan_terakhir END, "
            "waktu_balasan=CASE WHEN excluded.balasan_terakhir != '' AND excluded.balasan_terakhir != chat_status.balasan_terakhir "
            "THEN excluded.dicek ELSE chat_status.waktu_balasan END, dicek=excluded.dicek",
            (nomor, status, balasan, dicek if balasan else "", dicek),
        )
    # Riwayat per fasil: catat saat pesan baru terbaca / ada balasan baru
    from . import aktivitas

    if status == "dibalas" and balasan and balasan != lama_bls:
        ringkas = " ".join(balasan.split())
        aktivitas.catat(nomor, "dibalas", "Balasan: " + (ringkas if len(ringkas) <= 90 else ringkas[:89] + "…"))
    elif status == "dibaca" and lama_st in ("", "terkirim"):
        aktivitas.catat(nomor, "dibaca", "Pesan sudah dibaca fasil")


def chat_status_all() -> dict[str, dict[str, Any]]:
    rows = db.query("SELECT * FROM chat_status")
    return {r["nomor"]: dict(r) for r in rows}


# ---------- tahap chat ----------

def set_tahap(nomor: str, tahap: str, nilai: bool, sumber: str, waktu: str) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO chat_tahap(nomor, tahap, nilai, sumber, waktu) VALUES(?,?,?,?,?) "
            "ON CONFLICT(nomor, tahap) DO UPDATE SET nilai=excluded.nilai, sumber=excluded.sumber, waktu=excluded.waktu",
            (nomor, tahap, int(nilai), sumber, waktu),
        )


def tahap_all() -> dict[str, dict[str, dict]]:
    """{nomor: {tahap: {nilai, sumber, waktu}}}"""
    out: dict[str, dict[str, dict]] = {}
    for r in db.query("SELECT nomor, tahap, nilai, sumber, waktu FROM chat_tahap"):
        out.setdefault(r["nomor"], {})[r["tahap"]] = {"nilai": bool(r["nilai"]), "sumber": r["sumber"], "waktu": r["waktu"]}
    return out


def delete_tahap(nomor: str, tahap: str) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM chat_tahap WHERE nomor = ? AND tahap = ?", (nomor, tahap))


# ---------- tag warna Broadcast P1 ----------

def tag_all() -> dict[str, str]:
    return {r["nomor"]: r["warna"] for r in db.query("SELECT nomor, warna FROM tag_warna")}


def set_tag(nomor: str, warna: str, waktu: str) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO tag_warna(nomor, warna, waktu) VALUES(?,?,?) "
            "ON CONFLICT(nomor) DO UPDATE SET warna=excluded.warna, waktu=excluded.waktu",
            (nomor, warna, waktu),
        )


# ---------- kirim ulang ----------

def ulang_all() -> dict[str, str]:
    return {r["nomor"]: r["waktu"] for r in db.query("SELECT nomor, waktu FROM kirim_ulang")}


def set_ulang(nomor: str, waktu: str | None) -> None:
    with db.tx() as c:
        if waktu is None:
            c.execute("DELETE FROM kirim_ulang WHERE nomor = ?", (nomor,))
        else:
            c.execute("INSERT INTO kirim_ulang(nomor, waktu) VALUES(?, ?) "
                      "ON CONFLICT(nomor) DO UPDATE SET waktu = excluded.waktu", (nomor, waktu))
