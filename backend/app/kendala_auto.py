"""Isi Kendala / Tindak Lanjut di LK otomatis dari balasan fasil di WhatsApp.

Dipanggil setiap kali chat fasil dibaca (pembaruan chat berkala). Polanya:
1. Cari pesan keluar terakhir yang meminta "Kendala" (template "Tanya kendala per sekolah").
2. Ambil pesan masuk sesudahnya, lalu baca format "1. Sekolah / Kendala: … / Tindak lanjut: …".
3. Nomor di balasan dicocokkan dengan daftar sekolah di pesan kita sendiri (jadi tetap benar walau blast
   dipersempit ke satu komponen); bila nama sekolah ditulis, nama yang dipakai.
4. Hanya sel yang kosong atau berisi keterangan otomatis yang ditulis. Isian petugas tidak pernah ditimpa.
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS kendala_auto (
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
    for j in jawab:
        n = norm(j.judul)
        nn = [norm(x) for x in nama]
        idx = next((i for i, m in enumerate(nn) if n and m and (m in n or n in m)), None)
        if idx is None and 1 <= j.no <= len(nama):
            idx = j.no - 1
        if idx is not None and idx not in out:
            out[idx] = j
    return out


def pilih_kendala(teks: str, opsi: list[str]) -> str:
    """Pilihan dropdown Kendala yang paling cocok dengan teks jawaban, atau teks aslinya."""
    t = norm(teks)
    if not t:
        return ""
    if re.fullmatch(r"tidak ada|tdk ada|aman|lancar|ok|nihil|-", t):
        return next((o for o in opsi if "tidak ada kendala" in norm(o)), teks)
    kata = {k for k in t.split() if len(k) > 3}
    terbaik, skor = "", 0.0
    for o in opsi:
        ko = [k for k in norm(re.sub(r"^\d+\.\s*", "", o)).split() if len(k) > 3]
        if not ko:
            continue
        s = sum(1 for k in ko if k in kata) / len(ko)
        if s > skor:
            terbaik, skor = o, s
    return terbaik if skor >= 0.6 else teks


def potong_balasan(rows: list[Row]) -> tuple[str, str] | None:
    """(pesan permintaan kita, gabungan balasan sesudahnya), atau None bila belum ada balasan berformat."""
    idx = next((i for i in range(len(rows) - 1, -1, -1) if rows[i].out and "kendala" in rows[i].text.lower()), None)
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
    return bool(db.get_setting("kendala_otomatis", True)) and bool(db.get_setting("wa_otomatis", True))


def rencana_isi(pesan: str, balasan: str, sekolah: list[lk_baru.Sekolah], blok: int,
                opsi: dict[str, list[str]], kolom: set[str]) -> list[tuple[lk_baru.Sekolah, int, str, str, str]]:
    """Isian yang akan ditulis: [(sekolah, blok, kode komponen, kendala, tindak lanjut)]."""
    jawab = baca_balasan(balasan)
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
                lama_k, lama_t = isi.get(k, ("", ""))
                baru_k = pilih_kendala(j.kendala, opsi.get(k, [])) if j.kendala and (
                    not lama_k or todo.otomatis(lama_k)) else lama_k
                baru_t = j.tl if j.tl and (not lama_t or todo.otomatis(lama_t)) else lama_t
                if (baru_k, baru_t) != (lama_k, lama_t):
                    out.append((s, blok, k, " ".join(baru_k.split()), baru_t.strip()))
    return out


def proses(nomor: str, rows: list[Row]) -> int:
    """Tulis Kendala/TL dari balasan terbaru fasil `nomor`. Mengembalikan jumlah sekolah yang terisi."""
    if not nomor or not rows or not aktif():
        return 0
    potong = potong_balasan(rows)
    if not potong or not baca_balasan(potong[1]):
        return 0
    _db()
    kunci = hashlib.sha1(f"{nomor}\n{potong[0]}\n{potong[1]}".encode()).hexdigest()
    if db.query_one("SELECT 1 FROM kendala_auto WHERE kunci = ?", (kunci,)):
        return 0
    from .routers.lkb import blok_hari_ini

    f = next((f for f in komunikasi.fasil_saya().values() if nomor in [f.nomor, *f.nomor_lain]), None)
    n = 0
    if f:
        week = lk_baru.week_aktif()
        blok = blok_hari_ini()
        kolom = set(lk_baru.tata(week).isian.get(blok, {}))
        tulis = rencana_isi(potong[0], potong[1], f.sekolah, blok, lk_baru.opsi_kendala(week), kolom)
        if tulis:
            lk_baru.tulis_isian(week, tulis)
            nama = sorted({s.nama for s, *_ in tulis})
            n = len(nama)
            aktivitas.catat(nomor, "lk", f"Kendala/TL otomatis dari balasan WhatsApp ({lk_baru.BLOK_LABEL[blok]}): "
                            + ", ".join(nama[:3]) + (f", +{n - 3} lagi" if n > 3 else ""), f.nama)
            events.publish("lk_diperbarui", jumlah=n)
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO kendala_auto(kunci, waktu) VALUES(?, ?)",
                  (kunci, schedule.now().isoformat(timespec="seconds")))
    return n

