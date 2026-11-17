"""Ubah nama / nomor WhatsApp fasil dari panel fasil di halaman LK (LK format baru, tab WEEK n).

Seperti fitur lama di LK 50% (ubah_fasil.py), tetapi untuk LK Monitoring Pelaporan:
- tab WEEK aktif: kolom Fasilitator dan No HP Fasilitator di sekolah binaan PETUGAS INI milik fasil itu
  (bila sel No HP berisi beberapa nomor, hanya nomor lama yang diganti; gaya penulisan nomor mengikuti sel lama);
- tab Log Komunikasi: kolom Fasil (nama) untuk sekolah-sekolah itu, bila nama berubah;
- data lokal aplikasi (riwayat kirim, chat, kode komunikasi, telepon, tag, aktivitas) pindah ke nomor baru.

Sekolah petugas lain tidak disentuh. WEEK baru menyalin WEEK aktif, jadi perubahan ikut terbawa.
"""

import re
from typing import Any

from . import aktivitas, db, komunikasi, lk_baru
from .sheets import cache, col_letter, normalize_nomor, normalize_petugas, nomor_key
from .ubah_fasil import ganti_di_sel, gaya

# tabel lokal yang memakai nomor fasil (kolom `nomor`) atau kunci fasil (kolom `kunci` = nomor)
TABEL_NOMOR = ("sends", "chat_status", "chat_tahap", "aktivitas", "kirim_ulang", "tag_warna", "kom_amat", "kom_mulai",
               "kom_balas", "telepon", "neo_pesan")
TABEL_KUNCI = ("fasil_tag",)
JUDUL_FASIL_LOG_KOM = ("fasilitator", "fasil", "nama fasil")  # dicari di baris 2 Log Komunikasi, tidak dipatok hurufnya


class UbahFasilError(ValueError):
    """Pesannya untuk pengguna."""


def _ada_tabel(c, t: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None


def pindah_lokal(lama: str, baru: str) -> None:
    """Riwayat lokal ikut pindah ke nomor baru (baris yang sudah ada di nomor baru dipertahankan)."""
    with db.tx() as c:
        for t, kol in [(t, "nomor") for t in TABEL_NOMOR] + [(t, "kunci") for t in TABEL_KUNCI]:
            if not _ada_tabel(c, t):
                continue
            c.execute(f"UPDATE OR IGNORE {t} SET {kol} = ? WHERE {kol} = ?", (baru, lama))
            c.execute(f"DELETE FROM {t} WHERE {kol} = ?", (lama,))


def kolom_fasil_log_kom(judul: list[Any]) -> int | None:
    """Indeks kolom nama fasil dari judul baris 2 Log Komunikasi (PIC | NPSN | Nama Sekolah | PTN | Koordinator |
    Fasilitator | tanggal…). None bila tidak ada: lebih baik dilewati daripada menimpa kolom lain."""
    j = [str(x or "").strip().casefold() for x in judul]
    for kunci in JUDUL_FASIL_LOG_KOM:
        if kunci in j:
            return j.index(kunci)
    return None


def ubah(kunci: str, nama: str, nomor_baru: str) -> dict[str, Any]:
    nama = " ".join((nama or "").split())
    if not nama:
        raise UbahFasilError("Nama fasil tidak boleh kosong.")
    sekolah = komunikasi.sekolah_saya(True)
    fasil = komunikasi.kelompokkan(sekolah).get(kunci)
    if not fasil:
        raise UbahFasilError("Fasil ini tidak ada di sekolah binaan Anda (mungkin data LK baru diperbarui). Muat ulang.")
    lama = fasil.nomor
    baru = lama
    if (nomor_baru or "").strip():
        baru = normalize_nomor(nomor_baru)
        if not baru:
            raise UbahFasilError("Nomor WhatsApp tidak valid. Contoh: 081234567890.")
    ganti_nomor = nomor_key(baru) != nomor_key(lama) if lama else bool(baru)
    if ganti_nomor and any(f.kunci != kunci and baru and nomor_key(f.nomor) == nomor_key(baru)
                           for f in komunikasi.kelompokkan(sekolah).values()):
        raise UbahFasilError("Nomor itu sudah dipakai fasil lain di sekolah binaan Anda.")
    ganti_nama = nama != fasil.nama.strip()
    if not ganti_nomor and not ganti_nama:
        raise UbahFasilError("Tidak ada yang berubah.")

    week = lk_baru.week_aktif()
    t = lk_baru.tata(week, refresh=True)
    tab = lk_baru.tab_week(week)
    c_npsn, c_fasil, c_hp = (col_letter(t.identitas[k]) for k in ("npsn", "fasil", "hp_fasil"))
    ss = lk_baru._ss()

    # pastikan baris masih berisi sekolah yang sama (urutan bisa berubah karena cutoff / urut PIC)
    cek = ss.values_batch_get([f"'{tab}'!{c_npsn}{s.baris}" for s in fasil.sekolah],
                              params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("valueRanges", [])
    for s, vr in zip(fasil.sekolah, cek):
        isi = ((vr.get("values") or [[""]])[0] or [""])[0]
        if re.sub(r"\.0+$", "", str(isi).strip()) != s.npsn:
            cache.clear()
            raise UbahFasilError("Urutan LK baru saja berubah. Tutup panel, muat ulang, lalu coba lagi.")

    data = []
    for s in fasil.sekolah:
        if ganti_nama and s.fasil.strip() != nama:
            data.append({"range": f"'{tab}'!{c_fasil}{s.baris}", "values": [[nama]]})
        if ganti_nomor:
            if lama and s.hp_fasil.strip():
                isi = ganti_di_sel(s.hp_fasil, lama, baru)
            else:
                isi = gaya(s.hp_fasil, baru) if s.hp_fasil.strip() else "0" + baru[2:]
            if isi != s.hp_fasil:
                data.append({"range": f"'{tab}'!{c_hp}{s.baris}", "values": [[isi]]})
    for i in range(0, len(data), 200):
        ss.values_batch_update({"valueInputOption": "RAW", "data": data[i:i + 200]})

    n_log = 0
    if ganti_nama:
        try:
            lk = lk_baru.baca_log_kom(refresh=True)
            npsn = [s.npsn for s in fasil.sekolah if s.npsn in lk.baris]
            judul = (ss.values_get(f"'{lk_baru.TAB_LOG_KOM}'!A2:Z2").get("values") or [[]])[0]
            kol = kolom_fasil_log_kom(judul)
            if kol is not None and npsn and lk_baru._baris_kom_cocok(lk, npsn):
                ss.values_batch_update({"valueInputOption": "RAW", "data": [
                    {"range": f"'{lk_baru.TAB_LOG_KOM}'!{col_letter(kol)}{lk.baris[n]}", "values": [[nama]]}
                    for n in npsn]})
                n_log = len(npsn)
        except Exception:  # noqa: BLE001 - LK sudah diubah; nama di Log Komunikasi bisa disamakan manual
            n_log = -1

    if ganti_nomor and lama:
        pindah_lokal(lama, baru)
    cache.clear()
    ket = (["nomor WhatsApp diganti"] if ganti_nomor else []) + ([f"nama: {nama}"] if ganti_nama else [])
    aktivitas.catat(baru or kunci, "tahap", "Data fasil diubah (" + ", ".join(ket) + ")")
    kunci_baru = baru if baru else "nama:" + normalize_petugas(nama)
    return {"kunci": kunci_baru, "nomor": baru, "sekolah": len(fasil.sekolah), "sel": len(data), "log_kom": n_log,
            "tab": tab}
