"""Blast progres mingguan: antrean kirim dari LK WEEK aktif (bukan lagi sheet Broadcast).

Satu pesan per fasil binaan petugas, berisi daftar sekolahnya yang belum tuntas, satu poin per sekolah
(progres, tahap) dengan kendala dan rencana di baris sendiri, sama seperti template "Tanya semua sekaligus".
Pembuka menyesuaikan riwayat: fasil yang membalas minggu lalu diberi terima kasih, yang belum diajak melanjutkan.

Kiriman dicatat dengan hash_pesan berawalan "pm:"; setelah terkirim, tahap "Isian ditanyakan" ikut tercentang.
Salam ({salam}) diisi saat pesan dikirim.
"""

from datetime import date, timedelta

from . import db
from .sheets import BroadcastRow, Sekolah, message_hash, nomor_key, nomor_lk, normalize_petugas

AWALAN = "pm:"
T_PROGRES = ("Kendala progres fisik", "Rencana tindak lanjut")
T_SUBMIT = ("Kendala submit laporan 50%", "Rencana unggah")
T_REVIU = ("Kendala reviu", "Perkiraan selesai reviu")
SEMUA_SELESAI = "Semua sekolahnya sudah selesai, tidak ada yang perlu ditanyakan"


def _belum_50(s: Sekolah) -> bool:
    return s.progres is None or s.progres < 50


def pertanyaan(s: Sekolah) -> list[str]:
    q: list[str] = []
    if _belum_50(s):
        q += T_PROGRES
    elif s.submit != "Ya":
        q += T_SUBMIT
    if s.submit == "Ya" and s.reviu != "Ya":
        q += T_REVIU
    return q


def status(s: Sekolah) -> str:
    p = "progres belum ada" if s.progres is None else f"{s.progres:.1f}".replace(".", ",") + "%"
    t = "belum submit" if s.submit != "Ya" else "belum direviu" if s.reviu != "Ya" else "sudah direviu"
    return f" ({p}, {t})"


def susun(nama: str, sekolah: list[Sekolah], week: str, membalas: bool) -> str:
    """Pesan untuk satu fasil; '' bila tidak ada sekolah yang perlu ditanyakan."""
    tanya = [s for s in sekolah if s.prioritas.strip().lower() != "selesai" and pertanyaan(s)]
    if not tanya:
        return ""
    lanjut = ("Terima kasih atas tanggapan Bapak/Ibu minggu lalu. Berikut" if membalas
              else "Melanjutkan pesan kami minggu lalu, berikut")
    poin = "\n\n".join(
        f"{i}. {s.nama}{status(s)}\n" + "\n".join(f"   {q}: ..." for q in pertanyaan(s))
        for i, s in enumerate(tanya, 1))
    return (f"Selamat {{salam}} Bapak/Ibu {nama} 🙏\n\n"
            f"{lanjut} update progres Minggu ke-{week} sekolah dampingan Bapak/Ibu yang laporan kemajuan "
            f"50%-nya belum tuntas:\n\n{poin}\n\n"
            "Mohon dibantu dijawab *per sekolah* sesuai nomor di atas (cukup isi titik-titiknya), supaya "
            "kendalanya mudah kami rekap. Terima kasih 🙏")


def membalas_minggu_lalu(hari_ini: date) -> set[str]:
    senin = hari_ini - timedelta(days=hari_ini.weekday())
    lalu = senin - timedelta(days=7)
    rows = db.query("SELECT DISTINCT nomor FROM aktivitas WHERE jenis = 'dibalas' AND waktu >= ? AND waktu < ?",
                    (lalu.isoformat(), senin.isoformat()))
    return {r["nomor"] for r in rows}


def baris(lk: list[Sekolah], petugas: str, week: str, hari_ini: date) -> list[BroadcastRow]:
    """Satu baris antrean per fasil binaan (kunci: nomor WA pertama di No Fasil, atau nama bila kosong)."""
    target = normalize_petugas(petugas)
    fasil: dict[str, dict] = {}
    for s in lk:
        if normalize_petugas(s.petugas) != target or not (s.fasil or "").strip():
            continue
        nomors = nomor_lk(s)
        kunci = nomor_key(nomors[0]) if nomors else "nama:" + " ".join(s.fasil.casefold().split())
        f = fasil.setdefault(kunci, {"baris": s.baris, "nama": " ".join(s.fasil.split()),
                                     "nomor": nomors[0] if nomors else "", "asli": s.nomor_fasil, "sekolah": []})
        f["sekolah"].append(s)
    balas = membalas_minggu_lalu(hari_ini)
    out = []
    for f in fasil.values():
        pesan = susun(f["nama"], f["sekolah"], week, f["nomor"] in balas)
        out.append(BroadcastRow(f["baris"], petugas, f["nama"], f["nomor"], f["asli"], pesan,
                                AWALAN + message_hash(pesan) if pesan else ""))
    out.sort(key=lambda r: r.baris)
    return out
