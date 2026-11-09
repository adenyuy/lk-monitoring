"""Kode Log Komunikasi per siklus kirim: satu blast berlaku sampai fasil itu dikirimi lagi.

Siklus dimulai pada hari pesan terakhir terkirim (blast atau chat dari aplikasi). Setiap hari kerja (Senin–Sabtu)
dari hari itu sampai hari ini diisi, termasuk hari yang terlewat karena laptop mati. Kode tiap hari mengikuti
kejadian hari itu; bila tidak ada kejadian baru, kode hari sebelumnya diteruskan (termasuk kode yang diisi
petugas sendiri).

  C   terkirim, centang satu          C2  centang dua abu-abu (diterima, belum dibaca)
  R   dibaca, tidak membalas          T1  membalas, belum konfirmasi Kendala / Tindak lanjut
  T   membalas dengan Kendala / Tindak lanjut (konfirmasi)
  N   nomor tidak ada WhatsApp (kiriman gagal permanen)

Kode tidak pernah turun dalam satu siklus (mis. T1 tidak kembali ke R). Kode petugas dipertahankan; kode
otomatis hanya naik bila ada kejadian baru yang lebih baik.

Siklus juga dimulai oleh pesan keluar yang terbaca di chat (blast lewat HP), memakai tanggal pesan aslinya.

Kejadian dicatat setiap kali chat dicek:
- centang pesan keluar pertama di siklus (masih centang satu / diterima / dibaca) dengan tanggal pengamatan;
- pesan masuk dengan tanggal pesan aslinya (dari WhatsApp), dan apakah berisi "Kendala:" / "Tindak lanjut:".
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from . import db

MAKS_HARI = 21  # siklus lebih lama dari ini dianggap selesai

SCHEMA = """
CREATE TABLE IF NOT EXISTS kom_amat (
    nomor   TEXT NOT NULL,
    awal    TEXT NOT NULL,      -- tanggal awal siklus
    jenis   TEXT NOT NULL,      -- masih_c (terakhir terlihat centang satu) | diterima | dibaca
    tanggal TEXT NOT NULL,
    PRIMARY KEY (nomor, awal, jenis)
);
CREATE TABLE IF NOT EXISTS kom_mulai (
    nomor   TEXT NOT NULL,      -- pesan keluar yang terbaca di chat (blast dari HP / chat dari aplikasi)
    tanggal TEXT NOT NULL,
    PRIMARY KEY (nomor, tanggal)
);
CREATE TABLE IF NOT EXISTS kom_balas (
    nomor      TEXT NOT NULL,
    tanggal    TEXT NOT NULL,
    konfirmasi INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (nomor, tanggal)
);
"""
_siap = False

PERINGKAT = {"N": 0, "C": 1, "C2": 2, "R": 3, "T1": 4, "T2": 4, "T": 5, "TP": 5}

_KONFIRMASI = re.compile(r"(^|\n)\s*[•*\-]?\s*\*?(kendala|tindak\s*lanjut|tl)\*?\s*[:：=]", re.I)


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
        _siap = True


def konfirmasi(teks: str) -> bool:
    """Balasan berisi jawaban Kendala / Tindak lanjut."""
    return bool(_KONFIRMASI.search(teks or ""))


# ---------- siklus ----------

@dataclass
class Siklus:
    awal: date
    gagal: bool = False  # kiriman gagal permanen (nomor tidak ada WA), tidak ada yang terkirim sesudahnya


def siklus(nomor: str, hari: date) -> Siklus | None:
    """Siklus kirim yang berlaku pada `hari` untuk nomor ini."""
    if not nomor:
        return None
    _db()
    batas = (hari - timedelta(days=MAKS_HARI)).isoformat()
    akhir = (hari + timedelta(days=1)).isoformat()
    kirim = db.query_one(
        "SELECT MAX(w) AS w FROM (SELECT substr(waktu, 1, 10) AS w FROM sends WHERE coba = 0 AND nomor = ? "
        "AND status = 'terkirim' AND waktu >= ? AND waktu < ? UNION ALL SELECT tanggal FROM kom_mulai "
        "WHERE nomor = ? AND tanggal >= ? AND tanggal < ?)",
        (nomor, batas, akhir, nomor, batas, akhir))
    gagal = db.query_one(
        "SELECT MAX(substr(waktu, 1, 10)) AS w FROM sends WHERE coba = 0 AND nomor = ? AND status = 'gagal' "
        "AND lower(keterangan) LIKE '%tidak terdaftar%' AND waktu >= ? AND waktu < ?", (nomor, batas, akhir))
    k = kirim["w"] if kirim else None
    g = gagal["w"] if gagal else None
    if g and (not k or g > k):
        return Siklus(date.fromisoformat(g), gagal=True)
    return Siklus(date.fromisoformat(k)) if k else None


def hari_kerja(awal: date, hari: date) -> list[date]:
    out, d = [], awal
    while d <= hari:
        if d.weekday() < 6:
            out.append(d)
        d += timedelta(days=1)
    return out


# ---------- pencatatan kejadian ----------

def catat_amat(nomor: str, awal: date, centang: str, hari: date) -> None:
    """centang pesan keluar pertama di siklus: sent | pending | delivered | read."""
    _db()
    a, h = awal.isoformat(), hari.isoformat()
    with db.tx() as c:
        if centang in ("sent", "pending"):
            c.execute("INSERT INTO kom_amat VALUES(?,?,?,?) ON CONFLICT(nomor, awal, jenis) DO UPDATE SET "
                      "tanggal = MAX(tanggal, excluded.tanggal)", (nomor, a, "masih_c", h))
        for jenis in (("diterima",) if centang == "delivered" else ("diterima", "dibaca") if centang == "read" else ()):
            c.execute("INSERT INTO kom_amat VALUES(?,?,?,?) ON CONFLICT(nomor, awal, jenis) DO UPDATE SET "
                      "tanggal = MIN(tanggal, excluded.tanggal)", (nomor, a, jenis, h))


def catat_balas(nomor: str, balasan: list[tuple[date, str]]) -> None:
    _db()
    with db.tx() as c:
        c.executemany("INSERT INTO kom_balas VALUES(?,?,?) ON CONFLICT(nomor, tanggal) DO UPDATE SET "
                      "konfirmasi = MAX(konfirmasi, excluded.konfirmasi)",
                      [(nomor, d.isoformat(), int(konfirmasi(t))) for d, t in balasan])


def awal_siklus(rows, tgl: list[date | None]) -> list[date]:
    """Tanggal pesan keluar yang memulai siklus baru: pesan keluar pertama di hari itu yang tidak didahului pesan
    fasil di hari yang sama (membalas fasil di hari yang sama = bagian dari obrolan, bukan blast baru)."""
    out: list[date] = []
    masuk: set[date] = set()
    for r, d in zip(rows, tgl):
        if not d:
            continue
        if not r.out:
            masuk.add(d)
        elif d not in masuk and d not in out:
            out.append(d)
    return out


def catat_chat(nomor: str, rows, tanggal_pesan, hari: date) -> None:
    """Catat kejadian dari isi chat yang baru dibaca (rows: wa.actions.Row; tanggal_pesan: waktu -> date).
    Pesan keluar yang terbaca di chat (mis. blast lewat HP) ikut memulai siklus, dengan tanggal pesan aslinya."""
    _db()
    tgl = [tanggal_pesan(r.waktu) for r in rows]
    batas = hari - timedelta(days=MAKS_HARI)
    mulai = [d for d in awal_siklus(rows, tgl) if batas <= d <= hari]
    if mulai:
        with db.tx() as c:
            c.executemany("INSERT OR IGNORE INTO kom_mulai VALUES(?,?)", [(nomor, d.isoformat()) for d in mulai])
    s = siklus(nomor, hari)
    if s is None or s.gagal:
        return
    di_siklus = [(r, d) for r, d in zip(rows, tgl) if d and d >= s.awal]
    keluar = [r for r, _ in di_siklus if r.out]
    if not keluar:  # tanggal tidak terbaca: pakai pesan keluar terakhir
        keluar = [r for r in rows if r.out][-1:]
    if keluar:
        catat_amat(nomor, s.awal, keluar[0].status, hari)
    dari = s.awal - timedelta(days=1) if s.awal.weekday() == 0 else s.awal  # balasan Minggu ikut Senin
    masuk = [(d, r.text) for r, d in zip(rows, tgl) if d and d >= dari and not r.out and r.text]
    if masuk:
        catat_balas(nomor, masuk)


# ---------- kode per hari ----------

@dataclass
class Kejadian:
    diterima: date | None = None   # paling awal diketahui diterima
    dibaca: date | None = None
    balas: date | None = None      # balasan pertama di siklus
    konfirmasi: date | None = None  # balasan pertama berisi Kendala / Tindak lanjut


def kejadian(nomor: str, s: Siklus) -> Kejadian:
    _db()
    a = s.awal.isoformat()
    amat = {r["jenis"]: date.fromisoformat(r["tanggal"])
            for r in db.query("SELECT jenis, tanggal FROM kom_amat WHERE nomor = ? AND awal = ?", (nomor, a))}
    # Minggu tidak ada di Log Komunikasi: balasan hari Minggu digabung ke Senin, juga bila Senin ada blast baru.
    dari = (s.awal - timedelta(days=1)).isoformat() if s.awal.weekday() == 0 else a
    bls = db.query("SELECT tanggal, konfirmasi FROM kom_balas WHERE nomor = ? AND tanggal >= ? ORDER BY tanggal",
                   (nomor, dari))
    k = Kejadian()
    if bls:
        k.balas = date.fromisoformat(bls[0]["tanggal"])
        konf = [r for r in bls if r["konfirmasi"]]
        k.konfirmasi = date.fromisoformat(konf[0]["tanggal"]) if konf else None
    bukti = [d for d in (amat.get("diterima"), amat.get("dibaca"), k.balas) if d]
    k.dibaca = min([d for d in (amat.get("dibaca"), k.balas) if d], default=None)
    if bukti:
        # Kapan persisnya diterima tidak diketahui bila laptop mati: anggap sejak hari kirim, kecuali sempat
        # terlihat masih centang satu (lalu sejak hari sesudahnya).
        mulai = amat["masih_c"] + timedelta(days=1) if "masih_c" in amat else s.awal
        k.diterima = min(min(bukti), max(mulai, s.awal))
    return k


def kode_kejadian(k: Kejadian, s: Siklus, d: date) -> str:
    if s.gagal:
        return "N"
    if k.konfirmasi and k.konfirmasi <= d:
        return "T"
    if k.balas and k.balas <= d:
        return "T1"
    if k.dibaca and k.dibaca <= d:
        return "R"
    if k.diterima and k.diterima <= d:
        return "C2"
    return "C"


def lebih_baik(a: str, b: str) -> bool:
    return PERINGKAT.get(a, -1) > PERINGKAT.get(b, -1)


def susun(s: Siklus, k: Kejadian, hari: date, isi_lk: dict[str, str], auto: dict[str, str]) -> dict[str, str]:
    """{tanggal: kode yang harus ditulis} untuk satu fasil.

    isi_lk: {tanggal: kode di sheet}; auto: {tanggal: kode yang dulu ditulis aplikasi}. Sel yang diisi petugas
    (berbeda dengan catatan aplikasi) tidak ditimpa dan kodenya diteruskan ke hari berikutnya.
    """
    tulis: dict[str, str] = {}
    lalu = ""
    for d in hari_kerja(s.awal, hari):
        t = d.isoformat()
        ada = isi_lk.get(t, "")
        if ada and auto.get(t) != ada:  # isian petugas
            lalu = ada
            continue
        baru = kode_kejadian(k, s, d)
        kode = baru if not lalu or lebih_baik(baru, lalu) else lalu
        if kode != ada:
            tulis[t] = kode
        lalu = kode
    return tulis
