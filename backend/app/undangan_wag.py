"""Undangan WAG: blast ajakan bergabung ke grup WhatsApp tim monitoring milik petugas.

Saat mode ini dinyalakan, Blast mengirim pesan undangan (bukan pesan Broadcast minggu ini) ke fasil binaan petugas,
dengan jam sesi, kuota, batas harian, dan jeda yang sama. Link grup ditempel sendiri oleh tiap petugas.

- Tiap fasil diundang SEKALI per link (bukan per minggu). Ganti link grup = semua fasil diundang lagi.
- Kiriman undangan dicatat di tabel sends dengan hash_pesan berawalan "wag:", sehingga tidak dihitung sebagai
  pesan Broadcast minggu ini (Broadcast tetap bisa dikirim setelah mode dimatikan).
- Salam (pagi/siang/sore/malam) diisi saat pesan dikirim.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from . import db
from .send_queue import GAGAL_PERMANEN, Item
from .sheets import BroadcastRow

KUNCI = "undangan_wag"
AWALAN = "wag:"
POLA_LINK = re.compile(r"^https://chat\.whatsapp\.com/[A-Za-z0-9_-]{10,}$")
TANDA_SALAM = "{salam}"

TEKS_AWAL = (
    "Selamat {salam} rekan fasilitator {nama} 🙏\n\n"
    "Mohon dapat segera bergabung ke WAG Tim Monitoring {tim} melalui link berikut:\n\n"
    "🔗 {link}\n\n"
    "Tujuan:\n"
    "✅ Seluruh tim monitoring, fasilitator, dan operator berada dalam satu ekosistem komunikasi yang sama\n"
    "✅ Informasi tersampaikan secara serentak\n\n"
    "Jika link tidak bisa dibuka, mohon balas pesan ini dan saya akan bantu tambahkan secara manual.\n\n"
    "Terima kasih 🙏"
)
# Teks awal versi sebelumnya: bila tersimpan tanpa diedit, otomatis diganti teks awal terbaru
_TEKS_AWAL_LAMA = (
    "Selamat {salam} Bapak/Ibu {nama} 🙏\n\n"
    "Mengingatkan kembali, mohon Bapak/Ibu dapat segera bergabung ke WAG Tim Monitoring {tim} melalui link berikut:\n\n"
    "🔗 {link}\n\n"
    "Tujuan:\n"
    "✅ Seluruh tim monitoring, fasilitator, dan operator berada dalam satu ekosistem komunikasi yang sama\n"
    "✅ Informasi tersampaikan secara serentak\n"
    "✅ Meminimalisir risiko nomor terblokir WhatsApp akibat pengiriman pesan massal/japri dalam jumlah besar\n\n"
    "Jika link tidak bisa dibuka, mohon balas pesan ini dan saya akan bantu tambahkan secara manual.\n\n"
    "Terima kasih 🙏",
)


def _terkini(teks: str) -> str:
    return TEKS_AWAL if teks in _TEKS_AWAL_LAMA else teks


class UndanganError(ValueError):
    """Pengaturan undangan tidak valid. Pesannya untuk pengguna."""


@dataclass
class Pengaturan:
    aktif: bool = False
    link: str = ""
    tim: str = ""
    teks: str = TEKS_AWAL

    def as_dict(self) -> dict[str, Any]:
        return {"aktif": self.aktif, "link": self.link, "tim": self.tim, "teks": self.teks, "teks_awal": TEKS_AWAL}


def pengaturan() -> Pengaturan:
    d = db.get_setting(KUNCI) or {}
    return Pengaturan(aktif=bool(d.get("aktif")) and bool(d.get("link")), link=d.get("link", ""),
                      tim=d.get("tim", ""), teks=_terkini(d.get("teks") or TEKS_AWAL))


def rapikan_link(link: str) -> str:
    link = (link or "").strip().split("?")[0].rstrip("/")
    if link.startswith("chat.whatsapp.com/"):
        link = "https://" + link
    return link.replace("http://", "https://", 1)


def simpan(*, aktif: bool, link: str, tim: str, teks: str) -> Pengaturan:
    link = rapikan_link(link)
    if link and not POLA_LINK.match(link):
        raise UndanganError("Link grup harus berupa link undangan WhatsApp, contoh https://chat.whatsapp.com/AbCdEf123456.")
    if aktif and not link:
        raise UndanganError("Tempel link grup WhatsApp dulu sebelum menyalakan Undangan WAG.")
    teks = _terkini((teks or "").strip() or TEKS_AWAL)
    if "{link}" not in teks:
        raise UndanganError("Teks undangan harus memuat {link} supaya link grup ikut terkirim.")
    p = Pengaturan(aktif=aktif, link=link, tim=" ".join((tim or "").split()), teks=teks)
    db.set_setting(KUNCI, {"aktif": p.aktif, "link": p.link, "tim": p.tim, "teks": p.teks})
    return p


def hash_link(link: str) -> str:
    return AWALAN + hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]


def salam(t: datetime) -> str:
    j = t.hour
    return "pagi" if j < 11 else "siang" if j < 15 else "sore" if j < 18 else "malam"


def susun(p: Pengaturan, nama: str) -> str:
    """Isi teks undangan untuk satu fasil. {salam} dibiarkan, diisi saat dikirim (lihat isi_salam)."""
    tim = p.tim or ""
    teks = p.teks.replace("{nama}", nama.strip()).replace("{link}", p.link).replace("{tim}", tim)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r" {2,}", " ", teks))  # rapikan bila {tim} kosong


def isi_salam(teks: str, t: datetime) -> str:
    return teks.replace(TANDA_SALAM, salam(t))


def build(rows: Iterable[BroadcastRow], sends: Iterable[dict], p: Pengaturan) -> list[Item]:
    """Antrean undangan. `sends`: baris tabel sends non-coba, urut waktu naik (semua waktu, bukan per minggu)."""
    kunci = hash_link(p.link)
    terkirim: dict[str, str] = {}
    gagal: dict[str, tuple[str, str]] = {}
    for s in sends:
        if s["hash_pesan"] != kunci:
            continue
        if s["status"] == "terkirim":
            terkirim[s["nomor"]] = s["waktu"]
            gagal.pop(s["nomor"], None)
        elif s["status"] == "gagal" and s["nomor"] not in terkirim:
            gagal[s["nomor"]] = (s["waktu"], s["keterangan"])

    items: list[Item] = []
    seen: dict[str, int] = {}
    for r in rows:
        base = dict(baris=r.baris, nama_fasil=r.nama_fasil, nomor=r.nomor, pesan=susun(p, r.nama_fasil),
                    hash_pesan=kunci)
        if not r.nomor:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor tidak valid: {r.nomor_asli or '(kosong)'}"))
        elif r.nomor in seen:
            items.append(Item(**base, status="dilewati", keterangan=f"Nomor sama dengan baris {seen[r.nomor]}"))
        else:
            seen[r.nomor] = r.baris
            if r.nomor in terkirim:
                items.append(Item(**base, status="terkirim", waktu=terkirim[r.nomor]))
            elif r.nomor in gagal:
                w, ket = gagal[r.nomor]
                items.append(Item(**base, status="gagal", keterangan=ket, waktu=w))
            else:
                items.append(Item(**base, status="menunggu"))
    return items


def ringkasan(items: list[Item]) -> dict[str, int]:
    valid = [i for i in items if i.status != "dilewati"]
    return {
        "total": len(valid),
        "terkirim": sum(1 for i in valid if i.status == "terkirim"),
        "gagal_permanen": sum(1 for i in valid if i.status == "gagal" and GAGAL_PERMANEN in i.keterangan),
        "belum": sum(1 for i in valid if i.bisa_dikirim),
    }
