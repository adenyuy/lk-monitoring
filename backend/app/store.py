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
    """Nomor yang perlu dicek chat-nya: ada pesan keluar (Broadcast atau chat dari aplikasi) sejak tanggal itu
    dan belum ada balasan yang lebih baru dari pesan keluar terakhir."""
    rows = db.query(
        "SELECT k.nomor FROM (SELECT nomor, MAX(waktu) AS w FROM ("
        "  SELECT nomor, waktu FROM sends WHERE status = 'terkirim' AND coba = 0 AND tanggal >= ? "
        "  UNION ALL SELECT nomor, waktu FROM aktivitas WHERE jenis = 'balas' AND waktu >= ?"
        ") GROUP BY nomor) k LEFT JOIN chat_status c ON c.nomor = k.nomor "
        "WHERE c.status IS NULL OR c.status != 'dibalas' OR c.waktu_balasan < k.w "
        "OR c.perlu_balas = 1",  # cek lagi: mungkin sudah dibalas lewat HP
        (since_tanggal, since_tanggal),
    )
    return [r["nomor"] for r in rows]


def perlu_dibalas(sejak_iso: str) -> list[dict[str, Any]]:
    """Fasil yang membalas (sejak waktu itu) dan pesan terakhirnya belum kita balas."""
    rows = db.query("SELECT nomor, balasan_terakhir, waktu_balasan FROM chat_status "
                    "WHERE perlu_balas = 1 AND waktu_balasan >= ? ORDER BY waktu_balasan", (sejak_iso,))
    return [dict(r) for r in rows]


def save_chat_status(nomor: str, status: str, balasan: str, dicek: str, perlu_balas: bool | None = None) -> None:
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
        if perlu_balas is not None:
            c.execute("UPDATE chat_status SET perlu_balas = ? WHERE nomor = ?", (int(perlu_balas), nomor))
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
