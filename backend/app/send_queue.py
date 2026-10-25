"""Antrean kirim: gabungan baris Broadcast milik petugas + catatan kirim lokal.

Aturan (PRD §7.4):
- Kunci anti-dobel = nomor + hash isi pesan. Sudah 'terkirim' dengan kunci sama -> tidak dikirim lagi.
- Isi pesan di Broadcast berubah -> hash berubah -> masuk antrean lagi.
- Nomor tidak valid / pesan kosong / baris dobel -> Dilewati.
- Gagal karena nomor tidak terdaftar di WhatsApp -> tidak dicoba lagi untuk pesan yang sama.
- Gagal karena sebab lain -> dicoba lagi di kesempatan berikutnya.
"""

from dataclasses import dataclass
from typing import Iterable

from .sheets import BroadcastRow

GAGAL_PERMANEN = "nomor_tidak_terdaftar"


@dataclass
class Item:
    baris: int
    nama_fasil: str
    nomor: str
    pesan: str
    hash_pesan: str
    status: str  # menunggu | terkirim | gagal | dilewati
    keterangan: str = ""
    waktu: str = ""  # waktu terkirim / gagal terakhir

    @property
    def bisa_dikirim(self) -> bool:
        return self.status == "menunggu" or (self.status == "gagal" and GAGAL_PERMANEN not in self.keterangan)


def build(rows: Iterable[BroadcastRow], sends: Iterable[dict]) -> list[Item]:
    """`sends`: baris tabel sends (dict) non-coba, urut waktu naik."""
    terkirim: dict[tuple[str, str], str] = {}
    gagal: dict[tuple[str, str], tuple[str, str]] = {}
    for s in sends:
        key = (s["nomor"], s["hash_pesan"])
        if s["status"] == "terkirim":
            terkirim[key] = s["waktu"]
        elif s["status"] == "gagal":
            gagal[key] = (s["waktu"], s["keterangan"])

    items: list[Item] = []
    seen: dict[tuple[str, str], int] = {}
    for r in rows:
        base = dict(baris=r.baris, nama_fasil=r.nama_fasil, nomor=r.nomor, pesan=r.pesan, hash_pesan=r.hash_pesan)
        if not r.nomor:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor tidak valid: {r.nomor_asli or '(kosong)'}"))
            continue
        if not r.pesan:
            items.append(Item(**base, status="dilewati", keterangan="Pesan kosong"))
            continue
        key = (r.nomor, r.hash_pesan)
        if key in seen:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor & pesan sama dengan baris {seen[key]}"))
            continue
        seen[key] = r.baris
        if key in terkirim:
            items.append(Item(**base, status="terkirim", waktu=terkirim[key]))
        elif key in gagal:
            waktu, ket = gagal[key]
            items.append(Item(**base, status="gagal", keterangan=ket, waktu=waktu))
        else:
            items.append(Item(**base, status="menunggu"))
    return items


def eligible(items: list[Item]) -> list[Item]:
    """Yang boleh dikirim, urut: belum pernah dicoba dulu (urutan sheet), lalu yang pernah gagal."""
    fresh = [i for i in items if i.status == "menunggu"]
    retry = [i for i in items if i.status == "gagal" and i.bisa_dikirim]
    return fresh + retry
