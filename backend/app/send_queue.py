"""Antrean kirim: gabungan baris Broadcast milik petugas + catatan kirim lokal.

Aturan:
- Anti-dobel per nomor per minggu (Senin–Minggu): nomor yang sudah 'terkirim' minggu ini tidak dikirim
  lagi walaupun isi pesan di Broadcast berubah. Minggu berikutnya boleh dikirim lagi.
- Petugas bisa meminta "Kirim ulang" untuk nomor tertentu; berlaku sekali (sampai terkirim lagi).
- Nomor tidak valid / pesan kosong / baris dobel -> Dilewati.
- Gagal karena nomor tidak terdaftar di WhatsApp -> tidak dicoba lagi untuk pesan yang sama.
- Gagal karena sebab lain -> dicoba lagi di kesempatan berikutnya.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    diulang: bool = False  # petugas meminta kirim ulang

    @property
    def bisa_dikirim(self) -> bool:
        return self.status == "menunggu" or (self.status == "gagal" and GAGAL_PERMANEN not in self.keterangan)


def senin(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build(rows: Iterable[BroadcastRow], sends: Iterable[dict], hari_ini: date | None = None,
          ulang: dict[str, str] | None = None) -> list[Item]:
    """`sends`: baris tabel sends (dict) non-coba, urut waktu naik. `ulang`: {nomor: waktu permintaan}."""
    if hari_ini is None:
        from .schedule import now  # hindari import melingkar
        hari_ini = now().date()
    minggu = senin(hari_ini)
    ulang = ulang or {}
    terkirim: dict[str, str] = {}             # nomor -> waktu terkirim terakhir minggu ini
    gagal: dict[str, tuple[str, str]] = {}    # nomor -> (waktu, keterangan) gagal terakhir minggu ini
    for s in sends:
        if senin(datetime.fromisoformat(s["waktu"]).date()) != minggu:
            continue
        if s["status"] == "terkirim":
            terkirim[s["nomor"]] = s["waktu"]
            gagal.pop(s["nomor"], None)
        elif s["status"] == "gagal":
            gagal[s["nomor"]] = (s["waktu"], s["keterangan"])

    items: list[Item] = []
    seen: dict[str, int] = {}
    for r in rows:
        base = dict(baris=r.baris, nama_fasil=r.nama_fasil, nomor=r.nomor, pesan=r.pesan, hash_pesan=r.hash_pesan)
        if not r.nomor:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor tidak valid: {r.nomor_asli or '(kosong)'}"))
            continue
        if not r.pesan:
            items.append(Item(**base, status="dilewati", keterangan="Pesan kosong"))
            continue
        if r.nomor in seen:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor sama dengan baris {seen[r.nomor]}"))
            continue
        seen[r.nomor] = r.baris
        diminta = ulang.get(r.nomor, "")
        t = terkirim.get(r.nomor)
        g = gagal.get(r.nomor)
        if t and not (diminta and diminta > t):
            items.append(Item(**base, status="terkirim", waktu=t))
        elif g and (not t or g[0] > t):
            items.append(Item(**base, status="gagal", keterangan=g[1], waktu=g[0], diulang=bool(diminta)))
        else:
            items.append(Item(**base, status="menunggu", diulang=bool(diminta and t),
                              keterangan="Kirim ulang diminta" if diminta and t else ""))
    return items


def eligible(items: list[Item]) -> list[Item]:
    """Yang boleh dikirim, urut: belum pernah dicoba dulu (urutan sheet), lalu yang pernah gagal."""
    fresh = [i for i in items if i.status == "menunggu"]
    retry = [i for i in items if i.status == "gagal" and i.bisa_dikirim]
    return fresh + retry
