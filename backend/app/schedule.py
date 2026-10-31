"""Aturan waktu WA Blast: sesi aktif, kuota efektif, judul kondisi hari ini.

Fungsi di sini murni (waktu & angka diberikan dari luar) supaya mudah dites.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config
from .config import Sesi

TZ = ZoneInfo(config.TIMEZONE)
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def now() -> datetime:
    """Waktu sekarang (WIB). LKM_FAKE_NOW='YYYY-MM-DD HH:MM' hanya untuk develop/uji."""
    fake = os.environ.get("LKM_FAKE_NOW")
    if fake:
        return datetime.strptime(fake, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    return datetime.now(TZ)


def tanggal_str(d: date) -> str:
    return d.isoformat()


def tanggal_panjang(d: date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month]} {d.year}"


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def jam(s: str) -> str:
    """'14:00' -> '14.00' (format jam Indonesia)."""
    return s.replace(":", ".")


def sesi_at(t: datetime) -> Sesi | None:
    """Sesi yang sedang aktif pada waktu t (batas 'sampai' inklusif sampai menit itu habis)."""
    hm = t.time().replace(second=0, microsecond=0)
    for s in config.SESI:
        if _hm(s.mulai) <= hm <= _hm(s.sampai):
            return s
    return None


def sesi_by_no(no: int) -> Sesi:
    return next(s for s in config.SESI if s.no == no)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def next_sesi(t: datetime, kirim_akhir_pekan: bool) -> tuple[Sesi, datetime]:
    """Sesi berikutnya yang dimulai setelah t (bisa besok / lewat akhir pekan)."""
    d = t.date()
    for offset in range(0, 8):
        day = d + timedelta(days=offset)
        if is_weekend(day) and not kirim_akhir_pekan:
            continue
        for s in config.SESI:
            start = datetime.combine(day, _hm(s.mulai), tzinfo=TZ)
            if start > t:
                return s, start
    s = config.SESI[0]
    return s, datetime.combine(d + timedelta(days=1), _hm(s.mulai), tzinfo=TZ)


BYPASS_MULAI = time(7, 0)
BYPASS_SAMPAI = time(22, 0)
KALIMAT_RISIKO = config.KALIMAT_RISIKO


def kuota_efektif(sesi: Sesi, terkirim_sesi: int, batas_harian: int, terkirim_hari: int, sisa_antrean: int) -> int:
    return max(0, min(sesi.kuota - terkirim_sesi, batas_harian - terkirim_hari, sisa_antrean))


@dataclass
class Kondisi:
    kode: str  # berjalan | bypass | undangan | undangan_jam | bypass_jam | kuota_sesi_habis | batas_harian | sebelum_sesi | selesai_hari | akhir_pekan | antrean_habis
    judul: str
    bisa_kirim: bool
    sesi: Sesi | None  # sesi aktif (bila ada)
    kuota: int  # pesan yang boleh dikirim sekarang
    sesi_berikutnya: Sesi | None
    mulai_berikutnya: datetime | None

    def as_dict(self) -> dict:
        return {
            "kode": self.kode,
            "judul": self.judul,
            "bisa_kirim": self.bisa_kirim,
            "sesi": self.sesi.no if self.sesi else None,
            "kuota": self.kuota,
            "sesi_berikutnya": self.sesi_berikutnya.no if self.sesi_berikutnya else None,
            "mulai_berikutnya": self.mulai_berikutnya.isoformat() if self.mulai_berikutnya else None,
        }


def kondisi(
    t: datetime,
    batas_harian: int,
    kirim_akhir_pekan: bool,
    terkirim_hari: int,
    terkirim_per_sesi: dict[int, int],
    sisa_antrean: int,
    bypass: bool = False,
) -> Kondisi:
    nxt, nxt_at = next_sesi(t, kirim_akhir_pekan)
    besok = nxt_at.date() != t.date()
    lanjut = f"Sesi {nxt.no} mulai {jam(nxt.mulai)}" + (f", {HARI[nxt_at.weekday()]}" if besok else "")

    def k(kode, judul, sesi=None, kuota=0):
        return Kondisi(kode, judul, kuota > 0, sesi, kuota, nxt, nxt_at)

    if is_weekend(t.date()) and not kirim_akhir_pekan:
        return k("akhir_pekan", f"Akhir pekan, kirim dimatikan. {lanjut}")
    if terkirim_hari >= batas_harian:
        return k("batas_harian", f"Batas harian {batas_harian} pesan tercapai. {lanjut}")

    s = sesi_at(t)
    if bypass:
        # Bypass sesi: abaikan jam & kuota per sesi; batas harian, akhir pekan, dan jam wajar tetap berlaku
        if not (BYPASS_MULAI <= t.time() <= BYPASS_SAMPAI):
            return k("bypass_jam", f"Bypass sesi aktif, tapi pesan hanya dikirim pukul {BYPASS_MULAI:%H.%M}–"
                                   f"{BYPASS_SAMPAI:%H.%M}. {lanjut}")
        if sisa_antrean <= 0:
            return k("antrean_habis", "Semua fasilitator sudah dikirimi pesan", sesi=s)
        kuota = max(0, min(batas_harian - terkirim_hari, sisa_antrean))
        return k("bypass", f"Bypass sesi: sisa {kuota} pesan hari ini", sesi=s, kuota=kuota)

    if s is None:
        if t.time() < _hm(config.SESI[0].mulai):
            return k("sebelum_sesi", lanjut)
        if t.time() > _hm(config.SESI[-1].sampai):
            return k("selesai_hari", f"Pengiriman hari ini selesai. {lanjut}")
        return k("sebelum_sesi", lanjut)  # celah antar-sesi (tidak ada di jadwal sekarang)

    if sisa_antrean <= 0:
        return k("antrean_habis", "Semua fasilitator sudah dikirimi pesan", sesi=s)
    sisa_sesi = s.kuota - terkirim_per_sesi.get(s.no, 0)
    if sisa_sesi <= 0:
        return k("kuota_sesi_habis", f"Kuota sesi {s.no} habis. {lanjut}", sesi=s)

    kuota = kuota_efektif(s, terkirim_per_sesi.get(s.no, 0), batas_harian, terkirim_hari, sisa_antrean)
    return k("berjalan", f"Sesi {s.no} sedang berjalan, sampai {jam(s.sampai)}", sesi=s, kuota=kuota)


def kondisi_undangan(t: datetime, kirim_akhir_pekan: bool, sisa_antrean: int) -> Kondisi:
    """Mode Undangan WAG: langsung ke semua fasil hari ini. Jam sesi, kuota sesi, batas harian, dan libur akhir pekan
    diabaikan; hanya pukul 07.00–22.00 (jeda acak antarpesan tetap)."""
    nxt, nxt_at = next_sesi(t, kirim_akhir_pekan)
    if not (BYPASS_MULAI <= t.time() <= BYPASS_SAMPAI):
        return Kondisi("undangan_jam", f"Undangan WAG dikirim pukul {BYPASS_MULAI:%H.%M}–{BYPASS_SAMPAI:%H.%M}.",
                       False, None, 0, nxt, nxt_at)
    if sisa_antrean <= 0:
        return Kondisi("antrean_habis", "Semua fasil sudah diundang ke WAG", False, sesi_at(t), 0, nxt, nxt_at)
    return Kondisi("undangan", f"Undangan WAG: {sisa_antrean} fasil belum diundang, dikirim langsung tanpa menunggu sesi",
                   True, sesi_at(t), sisa_antrean, nxt, nxt_at)
