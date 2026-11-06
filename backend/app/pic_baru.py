"""Isi PIC sekolah baru di LK dari sheet pembagian tim (mis. "Pembagian PTN per Tim").

Sheet pembagian dibuat baru setiap ada sekolah baru, jadi admin menempelkan link terbarunya. Aplikasi mencari tab
yang punya kolom NPSN dan Nama Anggota (mis. "Penugasan Anggota"), mencocokkan per NPSN, lalu hanya menulis kolom PIC
di tab WEEK aktif. Bawaannya hanya sel PIC yang kosong; PIC yang berbeda diganti hanya bila diminta.
"""

import re
from collections import Counter
from typing import Any

from . import db, lk_baru
from .google_auth import gspread_client, id_sheet
from .sheets import cache, col_letter, normalize_petugas

KUNCI_LINK = "link_pembagian_pic"
_JUDUL_NPSN = ("npsn",)
_JUDUL_ANGGOTA = ("nama anggota", "anggota", "nama pic", "pic")
_RE_KODE = re.compile(r"^\s*\d+(\.\d+)?\s+")


class PicError(ValueError):
    """Pesannya untuk pengguna."""


def _rapi(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def bersih_nama(v: str) -> str:
    """'1.1 Marvin Nugraha' -> 'Marvin Nugraha'."""
    return _RE_KODE.sub("", _rapi(v))


def cari_kolom(baris: list[list[Any]]) -> tuple[int, int, int] | None:
    """(indeks baris judul, kolom NPSN, kolom anggota) dari beberapa baris teratas sebuah tab."""
    for i, r in enumerate(baris):
        judul = [_rapi(x).casefold() for x in r]
        n = next((j for j, h in enumerate(judul) if h in _JUDUL_NPSN), None)
        if n is None:
            continue
        for kunci in _JUDUL_ANGGOTA:
            a = next((j for j, h in enumerate(judul) if h == kunci), None)
            if a is not None:
                return i, n, a
    return None


def baca_pembagian(link: str) -> tuple[str, str, dict[str, str]]:
    """(judul file, nama tab, {npsn: nama PIC}) dari tab penugasan terlengkap di sheet pembagian."""
    sid = id_sheet(link)
    if not sid:
        raise PicError("Link sheet tidak valid. Salin link Google Sheets-nya dari address bar.")
    try:
        ss = gspread_client().open_by_key(sid)
    except Exception as e:
        raise PicError("Sheet tidak bisa dibuka. Pastikan akun Google kamu punya akses ke sheet itu.") from e
    terbaik: tuple[str, dict[str, str]] | None = None
    for w in ss.worksheets():
        try:
            atas = w.get_values("A1:Z6")
        except Exception:
            continue
        pos = cari_kolom(atas)
        if not pos:
            continue
        i, kn, ka = pos
        nilai = w.get_values(f"{col_letter(min(kn, ka))}{i + 2}:{col_letter(max(kn, ka))}")
        a0 = min(kn, ka)
        peta: dict[str, str] = {}
        for r in nilai:
            r = list(r) + [""] * (max(kn, ka) - a0 + 1 - len(r))
            n = re.sub(r"\.0+$", "", _rapi(r[kn - a0]))
            nama = bersih_nama(r[ka - a0])
            if n and nama:
                peta[n] = nama
        if peta and (terbaik is None or len(peta) > len(terbaik[1])):
            terbaik = (w.title, peta)
    if not terbaik:
        raise PicError("Tidak ada tab dengan kolom NPSN dan Nama Anggota di sheet ini.")
    return ss.title, terbaik[0], terbaik[1]


def rencana(link: str, ganti_beda: bool = False) -> dict[str, Any]:
    """Bandingkan PIC di LK WEEK aktif dengan sheet pembagian, tanpa menulis apa pun."""
    judul, tab, peta = baca_pembagian(link)
    week = lk_baru.week_aktif()
    sekolah = lk_baru.baca_semua(week, refresh=True)
    dikenal = {normalize_petugas(p["nama"]): p["nama"] for p in lk_baru.daftar_petugas()}
    for s in sekolah:
        if s.petugas.strip():
            dikenal.setdefault(normalize_petugas(s.petugas), s.petugas.strip())
    isi, beda, tanpa, asing = [], [], [], set()
    for s in sekolah:
        baru = peta.get(s.npsn, "")
        if baru:
            baku = dikenal.get(normalize_petugas(baru))
            if not baku:
                asing.add(baru)
                continue
            baru = baku
        if not s.petugas.strip():
            if baru:
                isi.append({"npsn": s.npsn, "nama": s.nama, "baris": s.baris, "pic": baru})
            else:
                tanpa.append({"npsn": s.npsn, "nama": s.nama, "fasil": s.fasil})
        elif baru and normalize_petugas(baru) != normalize_petugas(s.petugas):
            beda.append({"npsn": s.npsn, "nama": s.nama, "baris": s.baris, "pic": baru, "pic_lama": s.petugas.strip()})
    tulis = isi + (beda if ganti_beda else [])
    return {
        "file": judul, "tab": tab, "week": week, "lk_tab": lk_baru.tab_week(week), "sheet_sekolah": len(peta),
        "kosong": len(isi) + len(tanpa), "isi": isi, "beda": beda, "tanpa": tanpa, "asing": sorted(asing),
        "per_pic": [{"pic": k, "jumlah": v} for k, v in Counter(x["pic"] for x in tulis).most_common()],
        "akan_ditulis": len(tulis),
    }


def tulis(link: str, ganti_beda: bool = False) -> dict[str, Any]:
    rc = rencana(link, ganti_beda)
    data = rc["isi"] + (rc["beda"] if ganti_beda else [])
    if data:
        t = lk_baru.tata(rc["week"])
        kol = col_letter(t.identitas["petugas"])
        ss = lk_baru._ss()
        isi = [{"range": f"'{rc['lk_tab']}'!{kol}{x['baris']}", "values": [[x["pic"]]]} for x in data]
        for i in range(0, len(isi), 200):
            ss.values_batch_update({"valueInputOption": "RAW", "data": isi[i:i + 200]})
        cache.clear()
    db.set_setting(KUNCI_LINK, link)
    return {"ditulis": len(data), "diisi": len(rc["isi"]), "diganti": len(rc["beda"]) if ganti_beda else 0,
            "tanpa": rc["tanpa"], "lk_tab": rc["lk_tab"]}


def ringkas() -> dict[str, Any]:
    """Untuk kartu di halaman Tarik Cutoff: jumlah sekolah tanpa PIC dan link terakhir."""
    sekolah = lk_baru.baca_semua()
    return {"kosong": sum(1 for s in sekolah if not s.petugas.strip()), "link": db.get_setting(KUNCI_LINK, "") or ""}
