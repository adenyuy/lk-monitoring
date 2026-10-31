"""Ubah nama / nomor WhatsApp fasil dari aplikasi.

Ditulis ke:
- sheet Broadcast: kolom Nama Fasil dan Nomor HP di baris fasil itu (milik petugas ini);
- LK WEEK aktif: kolom Fasilitator dan No Fasil di sekolah binaan petugas ini yang memakai nomor itu
  (bila sel No Fasil berisi beberapa nomor, hanya nomor lama yang diganti);
- data lokal aplikasi: riwayat kirim, status chat, tahap, aktivitas, dll. pindah ke nomor baru.

Gaya penulisan nomor mengikuti isi sel lama (0812…, 62812…, +62812…, atau https://wa.me/62812…).
"""

import re
from dataclasses import dataclass

from . import config, db
from .sheets import (cache, gspread_client, kolom_lk, nomor_key, nomor_lk, normalize_nomor, normalize_petugas,
                     read_broadcast, read_lk, filter_petugas, week_aktif, write_isian, col_letter, _col)

_RE_NOMOR = re.compile(r"(?:https?://wa\.me/)?\+?\d[\d\s\-.]{7,}\d")
TABEL_NOMOR = ("sends", "chat_status", "chat_tahap", "aktivitas", "kirim_ulang", "tag_warna")


class UbahFasilError(ValueError):
    """Pesannya untuk pengguna."""


@dataclass
class Hasil:
    nomor: str
    broadcast: int
    lk: int


def gaya(lama: str, baru: str) -> str:
    """Tulis nomor `baru` (62…) dengan gaya penulisan `lama`."""
    lama = (lama or "").strip()
    if "wa.me" in lama:
        return "https://wa.me/" + baru
    if lama.startswith("+"):
        return "+" + baru
    if lama.startswith("0"):
        return "0" + baru[2:]
    return baru


def ganti_di_sel(sel: str, lama: str, baru: str) -> str:
    """Ganti nomor `lama` di sel No Fasil (bisa berisi beberapa nomor) dengan `baru`; nomor lain dibiarkan."""
    kunci = nomor_key(lama)

    def ganti(m: re.Match) -> str:
        t = m.group(0)
        return gaya(t, baru) if nomor_key(normalize_nomor(t)) == kunci else t

    return _RE_NOMOR.sub(ganti, sel or "")


def pindah_lokal(lama: str, baru: str) -> None:
    """Riwayat di database lokal ikut pindah ke nomor baru (baris di nomor baru yang sudah ada dipertahankan)."""
    with db.tx() as c:
        for t in TABEL_NOMOR:
            c.execute(f"UPDATE OR IGNORE {t} SET nomor = ? WHERE nomor = ?", (baru, lama))
            c.execute(f"DELETE FROM {t} WHERE nomor = ?", (lama,))


def ubah(nomor: str, nama: str, nomor_baru: str) -> Hasil:
    petugas = db.get_setting("nama_petugas") or ""
    if not petugas:
        raise UbahFasilError("Nama petugas belum dipilih.")
    nama = " ".join((nama or "").split())
    if not nama:
        raise UbahFasilError("Nama fasil tidak boleh kosong.")
    baru = nomor
    if (nomor_baru or "").strip():
        baru = normalize_nomor(nomor_baru)
        if not baru:
            raise UbahFasilError("Nomor WhatsApp tidak valid. Contoh: 081234567890.")
    ganti_nomor = nomor_key(baru) != nomor_key(nomor)

    # --- sheet Broadcast ---
    rows_bc = filter_petugas(read_broadcast(refresh=True), petugas)
    if ganti_nomor and any(nomor_key(r.nomor) == nomor_key(baru) for r in rows_bc):
        raise UbahFasilError("Nomor itu sudah dipakai fasil lain di Broadcast Anda.")
    target_bc = [r for r in rows_bc if r.nomor and nomor_key(r.nomor) == nomor_key(nomor)]
    n_bc = 0
    if target_bc:
        ss = gspread_client().open_by_key(config.BROADCAST_SHEET_ID)
        tab = config.BROADCAST_TAB
        header = (ss.values_get(f"'{tab}'!A1:Z1").get("values") or [[]])[0]
        c_nama, c_nomor = col_letter(_col(header, "Nama Fasil")), col_letter(_col(header, "Nomor HP"))
        c_petugas = col_letter(_col(header, "Nama Petugas"))
        # cek baris masih milik fasil yang sama (urutan sheet bisa berubah)
        cek = ss.values_batch_get([f"'{tab}'!{c_nomor}{r.baris}:{c_nomor}{r.baris}" for r in target_bc]
                                  + [f"'{tab}'!{c_petugas}{r.baris}:{c_petugas}{r.baris}" for r in target_bc])
        vr = cek.get("valueRanges", [])
        data = []
        for i, r in enumerate(target_bc):
            isi_nomor = ((vr[i].get("values") or [[""]])[0] or [""])[0]
            isi_petugas = ((vr[len(target_bc) + i].get("values") or [[""]])[0] or [""])[0]
            if nomor_key(normalize_nomor(isi_nomor)) != nomor_key(nomor) or \
                    normalize_petugas(isi_petugas) != normalize_petugas(petugas):
                cache.clear()
                raise UbahFasilError("Urutan sheet Broadcast berubah. Tutup panel, muat ulang, lalu coba lagi.")
            data.append({"range": f"'{tab}'!{c_nama}{r.baris}", "values": [[nama]]})
            if ganti_nomor:
                data.append({"range": f"'{tab}'!{c_nomor}{r.baris}", "values": [[gaya(isi_nomor, baru)]]})
        ss.values_batch_update({"valueInputOption": "RAW", "data": data})
        n_bc = len(target_bc)

    # --- LK WEEK aktif ---
    week = week_aktif()
    kol = kolom_lk(week, refresh=True)
    perubahan = []
    for s in read_lk(week, refresh=True):
        if normalize_petugas(s.petugas) != normalize_petugas(petugas):
            continue
        if nomor_key(nomor) not in {nomor_key(n) for n in nomor_lk(s)}:
            continue
        sel = {}
        if s.fasil.strip() != nama:
            sel[kol.fasil] = nama
        if ganti_nomor:
            sel[kol.nomor] = ganti_di_sel(s.nomor_fasil, nomor, baru)
        if sel:
            perubahan.append((s, sel))
    write_isian(week, perubahan, kol)

    if not target_bc and not perubahan and not any(
            normalize_petugas(s.petugas) == normalize_petugas(petugas) and nomor_key(nomor) in s.nomor_keys
            for s in read_lk(week)):
        raise UbahFasilError("Fasil ini tidak ditemukan di Broadcast maupun LK Anda.")

    if ganti_nomor:
        pindah_lokal(nomor, baru)
    cache.clear()
    from . import aktivitas

    ket = []
    if ganti_nomor:
        ket.append("nomor WhatsApp diganti")
    ket.append(f"nama: {nama}")
    aktivitas.catat(baru, "tahap", "Data fasil diubah (" + ", ".join(ket) + ")")
    return Hasil(nomor=baru, broadcast=n_bc, lk=len(perubahan))
