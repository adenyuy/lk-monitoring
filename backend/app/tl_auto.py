"""Isi Tindak Lanjut di LK otomatis dari balasan fasil di WhatsApp (Kendala hanya bila selnya masih kosong).

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
class Poin:
    judul: str
    kendala: str = ""
    tl: str = ""


@dataclass
class Jawaban:
    no: int
    judul: str
    kendala: str = ""  # isian tingkat sekolah (format lama: satu Kendala/TL untuk semua to-do)
    tl: str = ""
    poin: list[Poin] = field(default_factory=list)  # isian per to-do ("• To-do / Kendala / Tindak lanjut")


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
    """'1. SD A / • To-do / Kendala: x / Tindak lanjut: y' -> per nomor sekolah, per to-do. Kendala/TL sebelum
    poin pertama berlaku untuk sekolah itu. Baris lanjutan ikut isian di atasnya."""
    out: list[Jawaban] = []
    cur: Jawaban | None = None
    poin: Poin | None = None
    isian = ""
    for baris in teks.replace("\r", "").split("\n"):
        k = _KEPALA.match(baris)
        if k and not _KENDALA.match(k.group(2)) and not _TL.match(k.group(2)):
            cur = Jawaban(int(k.group(1)), _bersih(k.group(2)))
            out.append(cur)
            poin, isian = None, ""
            continue
        if not cur:
            continue
        tuju = poin or cur
        a, b = _KENDALA.match(baris), _TL.match(baris)
        if a:
            tuju.kendala, isian = _bersih(a.group(1)), "kendala"
            continue
        if b:
            tuju.tl, isian = _bersih(b.group(1)), "tl"
            continue
        if p := _POIN.match(baris):
            poin, isian = Poin(_bersih(p.group(1))), ""
            cur.poin.append(poin)
            continue
        lanjut = _bersih(baris)
        if not baris.strip():
            isian = ""  # baris kosong mengakhiri isian (mis. paragraf penutup)
        elif isian and lanjut:
            setattr(tuju, isian, f"{getattr(tuju, isian)} {lanjut}".strip())
    for x in out:
        x.poin = [p for p in x.poin if p.kendala or p.tl]
    return [x for x in out if x.kendala or x.tl or x.poin]


def isian_todo(j: Jawaban, judul: str, jumlah_todo: int) -> tuple[str, str] | None:
    """(kendala, tl) untuk satu to-do: poin yang judulnya cocok, bila tidak ada isian tingkat sekolah, bila tidak
    ada dan hanya ada satu poin untuk satu to-do, poin itu."""
    n = norm(judul)
    for p in j.poin:
        m = norm(p.judul)
        if n and (m.startswith(n) or (len(m) > 8 and n.startswith(m))):
            return p.kendala, p.tl
    if j.kendala or j.tl:
        return j.kendala, j.tl
    if len(j.poin) == 1 and jumlah_todo == 1:
        return j.poin[0].kendala, j.poin[0].tl
    return None


_TIDAK_ADA = re.compile(r"^(tidak ada|tdk ada|ga ada|gak ada|tidak ada kendala|aman|lancar|ok|nihil|belum ada|-)$")


def pilih_kendala(teks: str, opsi: list[str]) -> str:
    """Pilihan dropdown Kendala yang cocok dengan teks jawaban, atau '' (sama dengan pilihKendala di web/lib/pesan.ts)."""
    t = norm(teks)
    if not t:
        return ""
    for o in opsi:
        if norm(o) == t or norm(re.sub(r"^\d+\.\s*", "", o)) == t:
            return o
    no = re.match(r"^(\d{1,2})\s*[.)]?$", teks.strip()) or re.match(r"^(\d{1,2})\s*[.)]\s", teks.strip())
    if no:
        o = next((x for x in opsi if x.startswith(f"{no.group(1)}.")), "")
        if o:
            return o
    if _TIDAK_ADA.match(t):
        return next((o for o in opsi if "tidak ada kendala" in norm(o)), "")
    if re.match(r"^lainnya\b", t):
        return next((o for o in opsi if "lainnya" in o.lower()), "")
    kata = {k for k in t.split() if len(k) > 3}
    terbaik, skor = "", 0.0
    for o in opsi:
        ko = [k for k in norm(re.sub(r"^\d+\.\s*", "", o)).split() if len(k) > 3]
        if not ko:
            continue
        sk = sum(1 for k in ko if k in kata) / len(ko)
        if sk > skor:
            terbaik, skor = o, sk
    return terbaik if skor >= 0.6 else ""


def isi_kendala(kendala: str, tl: str, opsi: list[str]) -> tuple[str, str]:
    """(kendala, tl) siap isi: kendala yang ada di dropdown dipakai apa adanya; yang tidak ada jadi pilihan
    "Lainnya" dan teksnya digabung ke depan Tindak lanjut ("Dana sudah cair, Sedang proses …")."""
    k, t = " ".join(kendala.split()), " ".join(tl.split())
    if not k:
        return "", t
    cocok = pilih_kendala(k, opsi)
    if cocok:
        return cocok, t
    lain = next((o for o in opsi if "lainnya" in o.lower()), "")
    if not lain:
        return k, t
    if not t:
        return lain, k
    if norm(t).startswith(norm(k)):
        return lain, t
    return lain, f"{k.rstrip(' ,.;')}, {t}"


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
                kolom: set[str], opsi: dict[str, list[str]] | None = None
                ) -> list[tuple[lk_baru.Sekolah, int, str, str, str]]:
    """Isian yang akan ditulis: [(sekolah, blok, kode komponen, kendala, tindak lanjut baru)], per to-do.
    Kendala di sheet hanya diisi bila masih kosong (selain itu kendala lama yang dikembalikan); kendala yang
    tidak ada di dropdown (`opsi`) jadi "Lainnya" dan teksnya digabung ke depan Tindak lanjut."""
    opsi = opsi or {}
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
            ji = isian_todo(j, t.judul, len(ts))
            if not ji:
                continue
            for k in t.komponen:
                if k in sudah or k not in kolom:
                    continue
                sudah.add(k)
                kendala_lama, lama = isi.get(k, ("", ""))
                if lama and not todo.otomatis(lama):
                    continue  # sudah diisi petugas
                kendala, baru = isi_kendala(ji[0], ji[1], opsi.get(k, []))
                if not baru:
                    continue
                if kendala_lama and not todo.otomatis(kendala_lama) or k not in opsi:
                    kendala = kendala_lama  # Kendala petugas tidak ditimpa; tanpa dropdown tidak diisi
                if baru != lama or kendala != kendala_lama:
                    out.append((s, blok, k, kendala, baru))
    return out


def proses(nomor: str, rows: list[Row]) -> int:
    """Tulis Tindak Lanjut dari balasan terbaru fasil `nomor`. Mengembalikan jumlah sekolah yang terisi."""
    if not nomor or not rows or not aktif():
        return 0
    potong = potong_balasan(rows)
    if not potong or not baca_balasan(potong[1]):
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
        try:
            opsi = lk_baru.opsi_kendala(week)
        except Exception:  # noqa: BLE001 - tanpa dropdown: Kendala tidak diisi, Tindak lanjut tetap
            log.warning("Dropdown Kendala tidak terbaca", exc_info=True)
            opsi = {}
        tulis = rencana_isi(potong[0], potong[1], f.sekolah, blok, kolom, opsi)
        if tulis:
            # Kendala ikut ditulis hanya untuk sel yang berubah (sebelumnya kosong / keterangan otomatis).
            dua = [x for x in tulis if x[3] != x[0].isian.get(blok, {}).get(x[2], ("", ""))[0]]
            satu = [x for x in tulis if x not in dua]
            if dua:
                lk_baru.tulis_isian(week, dua)
            if satu:
                lk_baru.tulis_isian(week, satu, hanya_tl=True)
            nama = sorted({s.nama for s, *_ in tulis})
            n = len(nama)
            aktivitas.catat(nomor, "lk", f"Tindak lanjut otomatis dari balasan WhatsApp ({lk_baru.label_blok(blok)}): "
                            + ", ".join(nama[:3]) + (f", +{n - 3} lagi" if n > 3 else ""), f.nama)
            events.publish("lk_diperbarui", jumlah=n)
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO tl_auto(kunci, waktu) VALUES(?, ?)",
                  (kunci, schedule.now().isoformat(timespec="seconds")))
    return n
