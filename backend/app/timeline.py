"""Timeline mingguan Sep–Nov 2026: berapa sekolah yang sudah kirim/direviu tiap komponen LK sampai akhir tiap minggu.

Sumber: file export per sekolah di folder data bimtek (2-terbaru dan 3-harian; tiap cutoff otomatis menambah arsip).
Export hanya menyimpan tanggal kiriman/reviu TERAKHIR, jadi per sekolah dipakai tanggal paling awal dari semua export
(kirim ulang setelah revisi tidak menggeser sekolah ke minggu yang lebih baru). Mingguan, Bulanan, BKU, BPP, dan
progres tidak punya riwayat tanggal di export, jadi tidak ikut.

Minggu = Senin–Minggu, W1 tiap bulan = Senin pertama bulan itu: 7 Sep, 5 Okt, 2 Nov (tepat 12 minggu berurutan).
Pembagi dinamis: sekolah yang sudah PKS, atau sudah salur tahap 1, sampai akhir minggu itu.

Hasilnya (hanya angka, tanpa data sekolah) juga ditulis ke tab tersembunyi "Timeline" di LK supaya dashboard online
dan laptop tanpa folder data bimtek ikut membacanya.
"""

import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import cutoff_baru, rekap_bimtek

MULAI = datetime(2026, 9, 7)  # Senin pertama September 2026
BULAN = ("Sep", "Okt", "Nov")
BASIS = {"pks": "Tanggal PKS", "salur1": "Tanggal Salur Tahap 1"}
# (kode komponen LK, label, kolom tanggal di export)
KOMPONEN = (
    ("lp", "Lap. Pendahuluan", "Pendahuluan - Tgl Kirim"),
    ("lp_rev", "Reviu Lap. Pendahuluan", "Pendahuluan - Tgl Reviu"),
    ("l50", "Lap. 50%", "Tgl Kirim 50%"),
    ("l50_rev", "Reviu Lap. 50%", "Tgl Reviu Fasil 50%"),
    ("l100", "Lap. 100%", "Tgl Kirim 100%"),
    ("l100_rev", "Reviu Lap. 100%", "Tgl Reviu Fasil 100%"),
)

TAB = "Timeline"
TANDA = "timeline_v1"
log = logging.getLogger(__name__)
_cache: dict[str, Any] = {}


def _file() -> list[Path]:
    d = rekap_bimtek.folder()
    out = [f for sub in ("2-terbaru", rekap_bimtek.HARIAN) if (d / sub).is_dir() for f in (d / sub).iterdir()
           if "export" in f.name.lower() and f.suffix.lower() in (".csv", ".xlsx", ".xls")]
    return sorted(out, key=lambda f: rekap_bimtek.waktu_nama(f.name) or datetime.fromtimestamp(f.stat().st_mtime))


def baca() -> dict[str, Any] | None:
    """Hasil terakhir dari tab Timeline di LK (dipakai dashboard online)."""
    return rekap_bimtek.baca_json(TAB, TANDA, "lk2_timeline")


def hitung() -> dict[str, Any]:
    """Hitung dari file export di laptop ini; tanpa file export, pakai hasil terakhir di LK."""
    if not _file():
        data = baca()
        if data:
            return data
        raise ValueError(f"Belum ada file export di {rekap_bimtek.folder()} (2-terbaru / 3-harian), "
                         "dan belum ada hasil Timeline di LK.")
    data = _hitung_export()
    data = {**data, "intervensi": {"bimtek": _bimtek(data["minggu"])}}
    isi = repr({k: v for k, v in data.items() if k != "dibuat"})
    if _cache.get("tersimpan") != isi:
        _cache["tersimpan"] = isi
        threading.Thread(target=_simpan, args=(data,), daemon=True).start()
    return data


def _simpan(data: dict[str, Any]) -> None:
    try:
        rekap_bimtek.simpan_json(TAB, TANDA, data)
    except Exception:  # noqa: BLE001 - halaman lokal tetap jalan walau LK gagal ditulis
        _cache.pop("tersimpan", None)
        log.warning("Timeline gagal ditulis ke LK", exc_info=True)


def _bimtek(minggu: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    """Per minggu: kelompok Bimtek Pelaporan yang berlangsung (jadwal di 0-referensi/jadwal_bimtek.csv)."""
    try:
        jadwal = rekap_bimtek.baca_jadwal(rekap_bimtek.folder())
    except rekap_bimtek.RekapError:
        return [[] for _ in minggu]
    return [[{"kode": j.kode, "nama": j.tag, "mulai": j.mulai.isoformat(), "selesai": j.selesai.isoformat()}
             for j in jadwal if j.mulai.isoformat() <= m["selesai"] and j.selesai.isoformat() >= m["mulai"]]
            for m in minggu]


def _hitung_export() -> dict[str, Any]:
    files = _file()
    if not files:
        raise ValueError(f"Belum ada file export di {rekap_bimtek.folder()} (2-terbaru / 3-harian).")
    kunci = repr([(f.name, f.stat().st_mtime) for f in files])
    if _cache.get("kunci") == kunci:
        return _cache["data"]

    basis: dict[str, dict[str, datetime]] = {k: {} for k in BASIS}  # dari export terbaru
    tgl: dict[str, dict[str, datetime]] = {k: {} for k, _, _ in KOMPONEN}  # paling awal dari semua export
    for f in files:
        df = cutoff_baru.baca(f.read_bytes(), f.name)
        npsn = [cutoff_baru.npsn(v) for v in df["NPSN"]]
        for k, kol in BASIS.items():
            if kol in df.columns:
                basis[k] = {n: t for n, v in zip(npsn, df[kol]) if n and (t := rekap_bimtek._tgl(v))}
        for k, _, kol in KOMPONEN:
            if kol not in df.columns:
                continue
            for n, v in zip(npsn, df[kol]):
                t = rekap_bimtek._tgl(v)
                if n and t and (n not in tgl[k] or t < tgl[k][n]):
                    tgl[k][n] = t

    data_per = rekap_bimtek.waktu_nama(files[-1].name) or datetime.fromtimestamp(files[-1].stat().st_mtime)
    minggu, batas = [], []
    for i in range(12):
        a = MULAI + timedelta(weeks=i)
        minggu.append({"bulan": BULAN[i // 4], "w": f"W{i % 4 + 1}", "mulai": a.date().isoformat(),
                       "selesai": (a + timedelta(days=6)).date().isoformat()})
        # Kumulatif s.d. Minggu (batas = Senin berikutnya 00:00). Minggu yang belum mulai menurut data terbaru: kosong.
        batas.append(a + timedelta(days=7) if a <= data_per else None)

    hasil_basis = {k: [None if b is None else sum(t < b for t in basis[k].values()) for b in batas] for k in BASIS}
    komponen = []
    for kode, label, _ in KOMPONEN:
        per = {}
        for k in BASIS:
            per[k] = [None if b is None else sum(1 for n, t in tgl[kode].items() if t < b and n in basis[k]
                                                 and basis[k][n] < b) for b in batas]
        komponen.append({"kode": kode, "label": label, **per})

    data = {"minggu": minggu, "basis": hasil_basis, "komponen": komponen,
            "data_per": data_per.isoformat(timespec="minutes"), "file": [f.name for f in files],
            "dibuat": datetime.now().isoformat(timespec="seconds")}
    _cache.update(kunci=kunci, data=data)
    return data
