"""Kode Log Komunikasi per siklus kirim: satu blast berlaku sampai putaran blast berikutnya.

Putaran blast = hari ada blast/Broadcast ke banyak fasil (dari aplikasi, atau terbaca dari chat bila lewat HP).
Siklus fasil berakhir sehari sebelum putaran berikutnya; fasil yang tidak ikut putaran itu kosong sejak hari itu.
Survei dan undangan WAG bukan blast monitoring, jadi tidak memulai siklus.

Siklus dimulai pada hari pesan terakhir terkirim (blast atau chat dari aplikasi). Setiap hari kerja (Senin–Sabtu)
dari hari itu sampai hari ini diisi, termasuk hari yang terlewat karena laptop mati. Kode tiap hari mengikuti
kejadian hari itu; bila tidak ada kejadian baru, kode hari sebelumnya diteruskan (termasuk kode yang diisi
petugas sendiri).

  C   terlihat masih centang satu     C2  centang dua abu-abu (diterima, belum dibaca)
  (kosong) terkirim tapi belum ada info apa pun: sel tidak diisi
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
# Balasan berisi (bukan sekadar "oke/siap"): menyebut progres, laporan, dokumen, atau langkah yang sudah dikerjakan.
_ISI = re.compile(r"\b(progres|progress|laporan|lpj|adendum|addendum|reviu|review|revisi|kendala|tindak\s*lanjut|"
                  r"update|perkembangan|bku|bpp|fisik|mingguan|bulanan|pendahuluan|e-?meterai|"
                  r"sudah\s+(saya\s+)?(kirim|dikirim|upload|diupload|unggah|diunggah|isi|diisi|submit|lapor|reviu|"
                  r"direviu|cek|dicek|koordinasi|hubungi|dihubungi|ingatkan|diingatkan|tolak|ditolak|setujui|disetujui))\b",
                  re.I)
MEDIA = ("[foto]", "[dokumen]", "[video]", "[pesan suara]")
TIPE_SURVEI_WAG = ("svy:", "wag:")
MIN_PUTARAN = 5        # blast ke sekian fasil di hari yang sama = satu putaran
LAMBAT_HARI_KERJA = 3  # balasan pertama sesudah sekian hari kerja = respon lambat (T2)


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
        _siap = True


def konfirmasi(teks: str) -> bool:
    """Balasan yang menjawab (T): format Kendala / Tindak lanjut, menyebut progres / laporan / langkah yang sudah
    dikerjakan, cukup panjang, atau berupa foto / dokumen. Jawaban pendek seperti "oke kak, nanti dicek" = belum."""
    t = (teks or "").strip()
    if not t:
        return False
    if _KONFIRMASI.search(t) or _ISI.search(t) or t.startswith(MEDIA):
        return True
    return len(" ".join(t.split())) >= 80


# ---------- siklus ----------

@dataclass
class Siklus:
    awal: date
    gagal: bool = False  # kiriman gagal permanen (nomor tidak ada WA), tidak ada yang terkirim di hari itu
    akhir: date | None = None  # hari terakhir siklus (sehari sebelum siklus berikutnya); None = sampai hari ini


_BUKAN_BLAST = " AND ".join(f"hash_pesan NOT LIKE '{x}%'" for x in TIPE_SURVEI_WAG)


def _rentang(hari: date) -> tuple[str, str]:
    return (hari - timedelta(days=MAKS_HARI)).isoformat(), (hari + timedelta(days=1)).isoformat()


def putaran(hari: date) -> list[date]:
    """Tanggal putaran blast: blast/Broadcast dari aplikasi, atau pesan keluar yang terbaca di chat (blast lewat HP),
    ke minimal MIN_PUTARAN fasil di hari yang sama."""
    _db()
    batas, akhir = _rentang(hari)
    rows = db.query(
        "SELECT w, COUNT(DISTINCT nomor) AS n FROM ("
        f"SELECT substr(waktu, 1, 10) AS w, nomor FROM sends WHERE coba = 0 AND status = 'terkirim' AND {_BUKAN_BLAST} "
        "AND waktu >= ? AND waktu < ? UNION SELECT m.tanggal, m.nomor FROM kom_mulai m WHERE m.tanggal >= ? "
        "AND m.tanggal < ? AND NOT EXISTS (SELECT 1 FROM sends x WHERE x.nomor = m.nomor AND x.coba = 0 "
        f"AND substr(x.waktu, 1, 10) = m.tanggal AND NOT ({_BUKAN_BLAST.replace('hash_pesan', 'x.hash_pesan')}))"
        ") GROUP BY w", (batas, akhir, batas, akhir))
    return sorted(date.fromisoformat(r["w"]) for r in rows if r["n"] >= MIN_PUTARAN)


def daftar_siklus(nomor: str, hari: date, putaran_: list[date] | None = None) -> list[Siklus]:
    """Semua siklus kirim fasil ini dalam MAKS_HARI terakhir, urut dari yang lama. Tiap siklus berlaku sampai sehari
    sebelum siklus fasil ini berikutnya ATAU putaran blast berikutnya (yang lebih dulu)."""
    if not nomor:
        return []
    _db()
    batas, akhir = _rentang(hari)
    kirim = {r["w"] for r in db.query(
        f"SELECT substr(waktu, 1, 10) AS w FROM sends WHERE coba = 0 AND nomor = ? AND status = 'terkirim' AND {_BUKAN_BLAST} "
        "AND waktu >= ? AND waktu < ?", (nomor, batas, akhir))}
    # pesan keluar yang terbaca di chat, kecuali hari survei / undangan WAG untuk nomor ini
    lain = {r["w"] for r in db.query(
        "SELECT substr(waktu, 1, 10) AS w FROM sends WHERE coba = 0 AND nomor = ? AND status = 'terkirim' "
        f"AND NOT ({_BUKAN_BLAST}) AND waktu >= ? AND waktu < ?", (nomor, batas, akhir))}
    kirim |= {r["tanggal"] for r in db.query(
        "SELECT tanggal FROM kom_mulai WHERE nomor = ? AND tanggal >= ? AND tanggal < ?", (nomor, batas, akhir))
        if r["tanggal"] not in lain}
    gagal = {r["w"] for r in db.query(
        "SELECT substr(waktu, 1, 10) AS w FROM sends WHERE coba = 0 AND nomor = ? AND status = 'gagal' "
        "AND lower(keterangan) LIKE '%tidak terdaftar%' AND waktu >= ? AND waktu < ?", (nomor, batas, akhir))}
    out = [Siklus(date.fromisoformat(w), gagal=w not in kirim) for w in sorted(kirim | gagal)]
    put = putaran(hari) if putaran_ is None else putaran_
    for i, s in enumerate(out):
        batas_akhir = [b.awal for b in out[i + 1:i + 2]] + [p for p in put if p > s.awal][:1]
        if batas_akhir:
            s.akhir = min(batas_akhir) - timedelta(days=1)
    return out


def siklus(nomor: str, hari: date) -> Siklus | None:
    """Siklus kirim yang berlaku pada `hari` untuk nomor ini."""
    semua = daftar_siklus(nomor, hari)
    return semua[-1] if semua else None


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
    centang1: bool = False          # sempat terlihat masih centang satu


def kejadian(nomor: str, s: Siklus) -> Kejadian:
    _db()
    a = s.awal.isoformat()
    amat = {r["jenis"]: date.fromisoformat(r["tanggal"])
            for r in db.query("SELECT jenis, tanggal FROM kom_amat WHERE nomor = ? AND awal = ?", (nomor, a))}
    # Minggu tidak ada di Log Komunikasi: balasan hari Minggu digabung ke Senin, juga bila Senin ada blast baru.
    dari = (s.awal - timedelta(days=1)).isoformat() if s.awal.weekday() == 0 else a
    bls = db.query("SELECT tanggal, konfirmasi FROM kom_balas WHERE nomor = ? AND tanggal >= ? ORDER BY tanggal",
                   (nomor, dari))
    k = Kejadian(centang1="masih_c" in amat)
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
        lambat = len(hari_kerja(s.awal, k.balas)) - 1 >= LAMBAT_HARI_KERJA
        return "T2" if lambat else "T1"
    if k.dibaca and k.dibaca <= d:
        return "R"
    if k.diterima and k.diterima <= d:
        return "C2"
    return "C" if k.centang1 else ""  # belum ada info apa pun: kosong, jangan menebak


def status_sekarang(nomor: str, hari: date, putaran_: list[date] | None = None) -> str:
    """Status chat di siklus yang masih berlaku hari ini: dibalas | dibaca | terkirim | '' (tidak ikut putaran
    terakhir / belum dikirimi)."""
    semua = daftar_siklus(nomor, hari, putaran_)
    if not semua:
        return ""
    s = semua[-1]
    if (s.akhir and s.akhir < hari) or s.gagal:
        return ""
    k = kejadian(nomor, s)
    return "dibalas" if k.balas else "dibaca" if k.dibaca else "terkirim"


def lebih_baik(a: str, b: str) -> bool:
    return PERINGKAT.get(a, -1) > PERINGKAT.get(b, -1)


def susun(s: Siklus, k: Kejadian, hari: date, isi_lk: dict[str, str], auto: dict[str, str]) -> dict[str, str]:
    """{tanggal: kode yang harus ditulis} untuk satu fasil.

    isi_lk: {tanggal: kode di sheet}; auto: {tanggal: kode yang dulu ditulis aplikasi}. Sel yang diisi petugas
    (berbeda dengan catatan aplikasi) tidak ditimpa dan kodenya diteruskan ke hari berikutnya.
    """
    tulis: dict[str, str] = {}
    lalu = ""
    sampai = min(hari, s.akhir) if s.akhir else hari
    for d in hari_kerja(s.awal, sampai):
        t = d.isoformat()
        ada = isi_lk.get(t, "")
        if ada and auto.get(t) != ada:  # isian petugas
            lalu = ada
            continue
        baru = kode_kejadian(k, s, d)
        kode = baru if not lalu or lebih_baik(baru, lalu) else lalu
        if kode != ada:
            tulis[t] = kode  # "" = hapus tebakan aplikasi yang dulu
        lalu = kode
    return tulis


def susun_semua(nomor: str, hari: date, isi_lk: dict[str, str], auto: dict[str, str],
                putaran_: list[date] | None = None) -> dict[str, str]:
    """{tanggal: kode} untuk semua siklus fasil ini. Sel buatan aplikasi di luar siklus mana pun dikosongkan."""
    tulis: dict[str, str] = {}
    tercakup: set[str] = set()
    for s in daftar_siklus(nomor, hari, putaran_):
        tulis.update(susun(s, kejadian(nomor, s), hari, isi_lk, auto))
        sampai = min(hari, s.akhir) if s.akhir else hari
        tercakup |= {d.isoformat() for d in hari_kerja(s.awal, sampai)}
    for t, v in auto.items():
        if v and t not in tercakup and isi_lk.get(t, "") == v:
            tulis[t] = ""
    return tulis
