"""PIC per Fasil: samakan PIC semua sekolah di LK dengan pemetaan fasilitator -> anggota (PIC).

Satu fasil dipegang satu PIC. Admin menempelkan link sheet pembagian (mis. "Pembagian PTN per Tim"); aplikasi mencari
tab yang punya kolom Fasilitator dan Nama Anggota (tab tanpa kolom NPSN, mis. "Fasilitator per Anggota", didahulukan),
lalu menulis kolom PIC di tab WEEK aktif sesuai fasil tiap sekolah. Cukup dijalankan sekali atau saat pembagian ulang;
sesudahnya cutoff menjaga PIC tetap mengikuti fasil (lihat cutoff_baru.pic_per_fasil).
"""

import re
from collections import Counter, defaultdict
from typing import Any

from . import db, lk_baru
from .google_auth import gspread_client, id_sheet
from .sheets import cache, col_letter, normalize_petugas

KUNCI_LINK = "link_pembagian_pic"
_JUDUL_FASIL = ("fasilitator", "nama fasilitator")
_JUDUL_ANGGOTA = ("nama anggota", "anggota", "nama pic", "pic")
_RE_KODE = re.compile(r"^\s*\d+(\.\d+)?\s+")


class PicError(ValueError):
    """Pesannya untuk pengguna."""


def _rapi(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def kunci_fasil(v: Any) -> str:
    """Nama fasil untuk dicocokkan: abaikan huruf besar/kecil dan spasi."""
    return _rapi(v).casefold()


def bersih_nama(v: str) -> str:
    """'1.1 Marvin Nugraha' -> 'Marvin Nugraha'."""
    return _RE_KODE.sub("", _rapi(v))


def cari_kolom(baris: list[list[Any]]) -> tuple[int, int, int, bool] | None:
    """(indeks baris judul, kolom Fasilitator, kolom anggota, ada kolom NPSN) dari beberapa baris teratas sebuah tab."""
    for i, r in enumerate(baris):
        judul = [_rapi(x).casefold() for x in r]
        f = next((j for j, h in enumerate(judul) if h in _JUDUL_FASIL), None)
        if f is None:
            continue
        for kunci in _JUDUL_ANGGOTA:
            a = next((j for j, h in enumerate(judul) if h == kunci), None)
            if a is not None:
                return i, f, a, "npsn" in judul
    return None


def peta_fasil(nilai: list[list[Any]], kf: int, ka: int) -> tuple[dict[str, str], set[str]]:
    """({kunci fasil: nama PIC}, nama fasil yang tercatat di lebih dari satu PIC). Fasil ganda tidak dipetakan."""
    per: dict[str, dict[str, str]] = defaultdict(dict)
    nama_f: dict[str, str] = {}
    for r in nilai:
        r = list(r) + [""] * (max(kf, ka) + 1 - len(r))
        f, nama = kunci_fasil(r[kf]), bersih_nama(r[ka])
        if f and nama:
            per[f].setdefault(normalize_petugas(nama), nama)
            nama_f.setdefault(f, _rapi(r[kf]))
    peta = {f: next(iter(p.values())) for f, p in per.items() if len(p) == 1}
    return peta, {nama_f[f] for f, p in per.items() if len(p) > 1}


def baca_pembagian(link: str) -> tuple[str, str, dict[str, str], set[str]]:
    """(judul file, nama tab, {kunci fasil: nama PIC}, fasil ganda) dari tab pemetaan fasil terbaik."""
    sid = id_sheet(link)
    if not sid:
        raise PicError("Link sheet tidak valid. Salin link Google Sheets-nya dari address bar.")
    try:
        ss = gspread_client().open_by_key(sid)
    except Exception as e:
        raise PicError("Sheet tidak bisa dibuka. Pastikan akun Google kamu punya akses ke sheet itu.") from e
    terbaik: tuple[tuple[bool, int], str, dict[str, str], set[str]] | None = None
    for w in ss.worksheets():
        try:
            atas = w.get_values("A1:Z6")
        except Exception:
            continue
        pos = cari_kolom(atas)
        if not pos:
            continue
        i, kf, ka, ada_npsn = pos
        a0 = min(kf, ka)
        nilai = w.get_values(f"{col_letter(a0)}{i + 2}:{col_letter(max(kf, ka))}")
        peta, ganda = peta_fasil(nilai, kf - a0, ka - a0)
        skor = (not ada_npsn, len(peta))  # tab per fasil lebih dulu daripada tab per sekolah
        if peta and (terbaik is None or skor > terbaik[0]):
            terbaik = (skor, w.title, peta, ganda)
    if not terbaik:
        raise PicError("Tidak ada tab dengan kolom Fasilitator dan Nama Anggota di sheet ini.")
    return ss.title, terbaik[1], terbaik[2], terbaik[3]


def rencana(link: str) -> dict[str, Any]:
    """Bandingkan PIC di LK WEEK aktif dengan pemetaan fasil, tanpa menulis apa pun."""
    judul, tab, peta, ganda = baca_pembagian(link)
    week = lk_baru.week_aktif()
    sekolah = lk_baru.baca_semua(week, refresh=True)
    dikenal = {normalize_petugas(p["nama"]): p["nama"] for p in lk_baru.daftar_petugas()}
    for s in sekolah:
        if s.petugas.strip():
            dikenal.setdefault(normalize_petugas(s.petugas), s.petugas.strip())
    ubah, asing = [], set()
    tanpa: Counter = Counter()
    for s in sekolah:
        baru = peta.get(kunci_fasil(s.fasil), "")
        if not baru:
            tanpa[_rapi(s.fasil) or "(fasil kosong)"] += 1
            continue
        baku = dikenal.get(normalize_petugas(baru))
        if not baku:
            asing.add(baru)
        elif normalize_petugas(baku) != normalize_petugas(s.petugas):
            ubah.append({"npsn": s.npsn, "nama": s.nama, "baris": s.baris, "fasil": _rapi(s.fasil), "pic": baku,
                         "pic_lama": s.petugas.strip()})
    return {
        "file": judul, "tab": tab, "week": week, "lk_tab": lk_baru.tab_week(week), "sheet_fasil": len(peta),
        "ubah": ubah, "asing": sorted(asing), "ganda": sorted(ganda),
        "tanpa": [{"fasil": f, "sekolah": n} for f, n in tanpa.most_common()],
        "per_pic": [{"pic": k, "jumlah": v} for k, v in Counter(x["pic"] for x in ubah).most_common()],
        "akan_ditulis": len(ubah),
    }


def tulis(link: str) -> dict[str, Any]:
    rc = rencana(link)
    if rc["ubah"]:
        t = lk_baru.tata(rc["week"])
        kol = col_letter(t.identitas["petugas"])
        ss = lk_baru._ss()
        isi = [{"range": f"'{rc['lk_tab']}'!{kol}{x['baris']}", "values": [[x["pic"]]]} for x in rc["ubah"]]
        for i in range(0, len(isi), 200):
            ss.values_batch_update({"valueInputOption": "RAW", "data": isi[i:i + 200]})
        cache.clear()
    db.set_setting(KUNCI_LINK, link)
    from .cutoff_baru import sinkron_log_kom

    log_kom = sinkron_log_kom(lk_baru.baca_semua(rc["week"], refresh=True))
    return {"ditulis": len(rc["ubah"]), "tanpa": rc["tanpa"], "lk_tab": rc["lk_tab"], "log_kom": log_kom}


def ringkas() -> dict[str, Any]:
    """Untuk kartu di halaman Tarik Cutoff: sekolah tanpa PIC, fasil yang dipegang lebih dari satu PIC, link terakhir."""
    sekolah = lk_baru.baca_semua()
    per: dict[str, set[str]] = defaultdict(set)
    for s in sekolah:
        if kunci_fasil(s.fasil) and s.petugas.strip():
            per[kunci_fasil(s.fasil)].add(normalize_petugas(s.petugas))
    return {"kosong": sum(1 for s in sekolah if not s.petugas.strip()),
            "fasil_ganda": sum(1 for p in per.values() if len(p) > 1),
            "link": db.get_setting(KUNCI_LINK, "") or ""}
