"""Isi Tindak Lanjut di LK otomatis dari balasan fasil di WhatsApp. Kendala tetap diisi petugas.

Dipanggil setiap kali chat fasil dibaca (pembaruan chat berkala). Polanya:
1. Cari pesan keluar terakhir yang meminta "Kendala / Tindak lanjut" (template "Tanya kendala per sekolah").
2. Ambil pesan masuk sesudahnya, lalu baca format "1. Sekolah / Kendala: … / Tindak lanjut: …".
3. Nomor di balasan dicocokkan dengan daftar sekolah di pesan kita sendiri (jadi tetap benar walau blast
   dipersempit ke satu komponen); bila nama sekolah ditulis, nama yang dipakai.
4. Hanya sel Tindak Lanjut yang kosong atau berisi keterangan otomatis yang ditulis. Isian petugas tidak ditimpa.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field

from . import aktivitas, db, events, komunikasi, lk_baru, schedule, todo
from .wa.actions import Row

log = logging.getLogger(__name__)

_KEPALA = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(.*)$")
_KENDALA = re.compile(r"^\s*[•*\-]?\s*\*?kendala\*?\s*[:：=-]\s*(.*)$", re.I)
_TL = re.compile(r"^\s*[•*\-]?\s*\*?(?:tindak\s*lanjut|tl|rencana(?:\s*tindak\s*lanjut)?)\*?\s*[:：=-]\s*(.*)$", re.I)
_POIN = re.compile(r"^\s*[•\-]\s*(.+)$")
_FORMAT = re.compile(r"tindak\s*lanjut\s*:", re.I)  # pesan kita yang meminta format Kendala/Tindak lanjut

SCHEMA = """
CREATE TABLE IF NOT EXISTS tl_auto (
    kunci  TEXT PRIMARY KEY,
    waktu  TEXT NOT NULL
);
"""
_siap = False


@dataclass
class Jawaban:
    no: int
    judul: str
    kendala: str = ""
    tl: str = ""


@dataclass
class Butir:
    no: int
    nama: str
    poin: list[str] = field(default_factory=list)


def _bersih(s: str) -> str:
    s = s.replace("*", "").strip()
    s = re.sub(r"^\.{2,}$", "", s)
    s = re.sub(r"\s*\.{3,}\s*$", "", s)
    return s.strip()


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def baca_balasan(teks: str) -> list[Jawaban]:
    """'1. SD A … Kendala: x … Tindak lanjut: y' -> per nomor. Baris lanjutan ikut isian di atasnya."""
    out: list[Jawaban] = []
    cur: Jawaban | None = None
    isian = ""
    for baris in teks.replace("\r", "").split("\n"):
        k = _KEPALA.match(baris)
        if k and not _KENDALA.match(k.group(2)) and not _TL.match(k.group(2)):
            cur = Jawaban(int(k.group(1)), _bersih(k.group(2)))
            out.append(cur)
            isian = ""
            continue
        if not cur:
            continue
        a, b = _KENDALA.match(baris), _TL.match(baris)
        if a:
            cur.kendala, isian = _bersih(a.group(1)), "kendala"
            continue
        if b:
            cur.tl, isian = _bersih(b.group(1)), "tl"
            continue
        lanjut = _bersih(baris)
        if not baris.strip():
            isian = ""  # baris kosong mengakhiri isian (mis. paragraf penutup)
        elif isian and lanjut and not baris.strip().startswith("•"):
            setattr(cur, isian, f"{getattr(cur, isian)} {lanjut}".strip())
    return [x for x in out if x.kendala or x.tl]


def baca_daftar(teks: str) -> list[Butir]:
    """Daftar sekolah + to-do di pesan kita sendiri: '1. SD A' lalu '• Kirim Laporan …'."""
    out: list[Butir] = []
    for baris in teks.replace("\r", "").split("\n"):
        k = _KEPALA.match(baris)
        if k and not _KENDALA.match(k.group(2)) and not _TL.match(k.group(2)):
            out.append(Butir(int(k.group(1)), _bersih(k.group(2))))
        elif out and (p := _POIN.match(baris)):
            out[-1].poin.append(_bersih(p.group(1)))
    return out


def cocokkan(jawab: list[Jawaban], nama: list[str]) -> dict[int, Jawaban]:
    """{indeks di `nama`: jawaban}: lewat nama di baris judul, bila tidak ketemu lewat nomor urut."""
    out: dict[int, Jawaban] = {}
    nn = [norm(x) for x in nama]
    for j in jawab:
        n = norm(j.judul)
        idx = next((i for i, m in enumerate(nn) if n and m and (m in n or n in m)), None)
        if idx is None and 1 <= j.no <= len(nama):
            idx = j.no - 1
        if idx is not None and idx not in out:
            out[idx] = j
    return out


def potong_balasan(rows: list[Row]) -> tuple[str, str] | None:
    """(pesan permintaan kita, gabungan balasan sesudahnya), atau None bila belum ada balasan."""
    idx = next((i for i in range(len(rows) - 1, -1, -1)
                if rows[i].out and _FORMAT.search(rows[i].text)), None)
    if idx is None:
        return None
    masuk = [r.text for r in rows[idx + 1:] if not r.out and r.text]
    return (rows[idx].text, "\n".join(masuk)) if masuk else None


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
        _siap = True


def aktif() -> bool:
    return bool(db.get_setting("tl_otomatis", True)) and bool(db.get_setting("wa_otomatis", True))


def rencana_isi(pesan: str, balasan: str, sekolah: list[lk_baru.Sekolah], blok: int,
                kolom: set[str]) -> list[tuple[lk_baru.Sekolah, int, str, str, str]]:
    """Tindak Lanjut yang akan ditulis: [(sekolah, blok, kode komponen, kendala lama, tindak lanjut baru)]."""
    jawab = [j for j in baca_balasan(balasan) if j.tl]
    if not jawab:
        return []
    per_nama = {norm(s.nama): s for s in sekolah}

    def cari(nama: str) -> lk_baru.Sekolah | None:
        n = norm(nama)
        return per_nama.get(n) or next((s for m, s in per_nama.items() if n and (m in n or n in m)), None)

    daftar = baca_daftar(pesan)
    if daftar:
        butir = [(b.nama, b.poin) for b in daftar]
    else:
        butir = [(s.nama, []) for s in sorted(sekolah, key=lambda s: s.nama) if todo.rencana(s).todo]
    out = []
    for i, j in cocokkan(jawab, [n for n, _ in butir]).items():
        nama, poin = butir[i]
        s = cari(nama)
        if not s:
            continue
        r = todo.rencana(s)
        ts = [t for t in r.todo if any(p.startswith(t.judul) for p in poin)] or r.todo
        isi = s.isian.get(blok, {})
        sudah: set[str] = set()
        for t in ts:
            for k in t.komponen:
                if k in sudah or k not in kolom:
                    continue
                sudah.add(k)
                kendala, lama = isi.get(k, ("", ""))
                if lama and not todo.otomatis(lama):
                    continue  # sudah diisi petugas
                baru = " ".join(j.tl.split())
                if baru != lama:
                    out.append((s, blok, k, kendala, baru))
    return out


def proses(nomor: str, rows: list[Row]) -> int:
    """Tulis Tindak Lanjut dari balasan terbaru fasil `nomor`. Mengembalikan jumlah sekolah yang terisi."""
    if not nomor or not rows or not aktif():
        return 0
    potong = potong_balasan(rows)
    if not potong or not any(j.tl for j in baca_balasan(potong[1])):
        return 0
    _db()
    kunci = hashlib.sha1(f"{nomor}\n{potong[0]}\n{potong[1]}".encode()).hexdigest()
    if db.query_one("SELECT 1 FROM tl_auto WHERE kunci = ?", (kunci,)):
        return 0
    from .routers.lkb import blok_hari_ini

    f = next((f for f in komunikasi.fasil_saya().values() if nomor in [f.nomor, *f.nomor_lain]), None)
    n = 0
    if f:
        week = lk_baru.week_aktif()
        blok = blok_hari_ini()
        kolom = set(lk_baru.tata(week).isian.get(blok, {}))
        tulis = rencana_isi(potong[0], potong[1], f.sekolah, blok, kolom)
        if tulis:
            lk_baru.tulis_isian(week, tulis, hanya_tl=True)
            nama = sorted({s.nama for s, *_ in tulis})
            n = len(nama)
            aktivitas.catat(nomor, "lk", f"Tindak lanjut otomatis dari balasan WhatsApp ({lk_baru.BLOK_LABEL[blok]}): "
                            + ", ".join(nama[:3]) + (f", +{n - 3} lagi" if n > 3 else ""), f.nama)
            events.publish("lk_diperbarui", jumlah=n)
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO tl_auto(kunci, waktu) VALUES(?, ?)",
                  (kunci, schedule.now().isoformat(timespec="seconds")))
    return n
