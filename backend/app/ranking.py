"""Ranking PIC: komponen sudah diisi / yang seharusnya, isian Kendala/TL, dan Log Komunikasi per PIC.

Dipakai dashboard offline (/api/dashboard/ranking) dan online (dasbor_online). Hanya admin yang boleh melihat.
`bimtek`: hanya sekolah kelompok Bimtek Pelaporan itu ('' = semua, '-' = bukan peserta).
"""

import threading
import time
from collections import Counter
from datetime import date, timedelta
from typing import Any

from . import bimtek_lap, komunikasi, lk_baru, schedule, todo
from .sheets import normalize_petugas

SIMPAN_DETIK = 600
_simpan: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def hitung(bimtek: str = "") -> dict[str, Any]:
    """Per PIC: komponen sudah diisi / yang seharusnya (sudah due), per komponen dan total, plus pengisian
    Log Komunikasi. Satu kali baca data nasional untuk semua PIC."""
    sekolah = [s for s in lk_baru.baca_semua() if bimtek_lap.cocok(s, bimtek)]
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    hari_ini = schedule.now().date().isoformat()
    # Hari = hari kerja WEEK aktif sampai hari ini, supaya filter hari berlaku juga untuk isian Kendala/TL
    # (isian per sesi di tab WEEK aktif; isian minggu lalu ada di tab WEEK sebelumnya)
    hari_d = schedule.now().date()
    senin = (hari_d - timedelta(days=hari_d.weekday())).isoformat()
    tanggal = [d for d in sorted(logkom.tanggal) if senin <= d <= hari_ini]
    sesi = lk_baru.sesi_hari()
    blok_urut = sorted(sesi)
    blok_hari = [lk_baru.blok_untuk(date.fromisoformat(d), sesi) for d in tanggal]

    per_pic: dict[str, tuple[str, list[lk_baru.Sekolah]]] = {}
    for s in sekolah:
        if s.petugas:
            per_pic.setdefault(normalize_petugas(s.petugas), (s.petugas, []))[1].append(s)

    # komponen yang punya kolom Kendala/TL di WEEK ini
    berkolom = {kode for s in sekolah[:50] for isi in s.isian.values() for kode in isi}

    def diisi(v: Any) -> bool:
        """Isian petugas (termasuk 'Tidak ada kendala'); keterangan otomatis aplikasi tidak dihitung."""
        t = str(v or "").strip()
        return bool(t) and not todo.otomatis(t)

    def kom_terakhir(x: dict[str, str]) -> str:
        """Kode terakhir dalam HARI_RANKING hari kerja terakhir ('' = belum ada)."""
        return next((x[d] for d in reversed(tanggal) if x.get(d)), "")

    def rinci_fasil(fasil: dict[str, Any], kode_f: dict[str, dict[str, str]], st_by: dict[int, Any]) -> list[dict[str, Any]]:
        """Per fasil, untuk filter gabungan di halaman: kode Log Komunikasi per hari (urut `tanggal`) dan per
        komponen [belum, selesai, harus, kendala terisi semua sesi, TL semua sesi, lalu kendala & TL per sesi
        (urut `blok_urut`)] dari sekolah binaannya. Isian dihitung dari sekolah yang belum."""
        out = []
        for key, f in fasil.items():
            k: dict[str, list[int]] = {}
            for kp in lk_baru.KOMPONEN:
                b = sel = 0
                isi = [0] * (2 + 2 * len(blok_urut))
                for sk in f.sekolah:
                    stt = st_by[id(sk)][kp.kode].status
                    if stt == "selesai":
                        sel += 1
                    elif stt == "belum":
                        b += 1
                        per = [sk.isian.get(bl, {}).get(kp.kode, ("", "")) for bl in blok_urut]
                        isi[0] += any(diisi(x[0]) for x in per)
                        isi[1] += any(diisi(x[1]) for x in per)
                        for j, x in enumerate(per):
                            isi[2 + 2 * j] += diisi(x[0])
                            isi[3 + 2 * j] += diisi(x[1])
                if sel + b:
                    k[kp.kode] = [b, sel, sel + b, *isi]
            out.append({"n": f.nama, "s": len(f.sekolah), "h": [kode_f[key].get(d, "") for d in tanggal], "k": k})
        out.sort(key=lambda x: x["n"].casefold())
        return out

    def hitung(nama: str, daftar: list[lk_baru.Sekolah], rinci: bool = True) -> dict[str, Any]:
        st = [todo.semua_status(s) for s in daftar]
        # Komunikasi dihitung per FASIL (menghubungi fasil = semua sekolahnya); kode fasil per hari = kode
        # terbanyak di antara sekolahnya hari itu
        fasil = komunikasi.kelompokkan(daftar)
        kode_f = {k: komunikasi.kode_fasil(f, logkom) for k, f in fasil.items()}
        akhir_f = {k: kom_terakhir(x) or "-" for k, x in kode_f.items()}
        semua_fasil_belum: set[str] = set()
        komp = []
        tot_a = tot_b = 0
        tot_belum = tot_k = tot_tl = 0
        for k in lk_baru.KOMPONEN:
            a = sum(1 for x in st if x[k.kode].status == "selesai")
            belum = [s for s, x in zip(daftar, st) if x[k.kode].status == "belum"]
            b = a + len(belum)
            tot_a += a
            tot_b += b
            # sekolah yang belum: Kendala/TL sudah diisi petugas (sesi mana pun di WEEK ini) dan komunikasinya
            ada = k.kode in berkolom
            n_k = sum(1 for s in belum if any(diisi(i.get(k.kode, ("", ""))[0]) for i in s.isian.values())) if ada else None
            n_tl = sum(1 for s in belum if any(diisi(i.get(k.kode, ("", ""))[1]) for i in s.isian.values())) if ada else None
            fasil_belum = {komunikasi.kunci_fasil(s) for s in belum}
            semua_fasil_belum |= fasil_belum
            kom = Counter(akhir_f[f] for f in fasil_belum)
            if ada:
                tot_belum += len(belum)
                tot_k += n_k or 0
                tot_tl += n_tl or 0
            komp.append({"kode": k.kode, "label": k.label, "selesai": a, "harus": b,
                         "persen": round(a / b * 100, 1) if b else None,
                         "belum": len(belum), "fasil_belum": len(fasil_belum), "kendala": n_k, "tl": n_tl,
                         "kom": dict(kom)})
        tot_kom = Counter(akhir_f[f] for f in semua_fasil_belum)
        log_hari = []
        for d in tanggal:
            c = Counter(x.get(d, "") for x in kode_f.values())
            kosong = c.pop("", 0)
            log_hari.append({"tanggal": d, "isi": len(kode_f) - kosong, "slot": len(kode_f), "kode": dict(c)})
        akhir = log_hari[-1] if log_hari else {"isi": 0, "slot": 0, "kode": {}}
        isi, slot, log_kode = akhir["isi"], akhir["slot"], akhir["kode"]
        p = [x["progres"].persen for x in st if x["progres"].persen is not None]
        return {"nama": nama, "sekolah": len(daftar), "fasil": len(fasil),
                "selesai": tot_a, "harus": tot_b, "persen": round(tot_a / tot_b * 100, 1) if tot_b else None,
                "komponen": komp,
                "belum": tot_belum, "kendala": tot_k, "tl": tot_tl, "kom": dict(tot_kom),
                "log_isi": isi, "log_slot": slot, "log_persen": round(isi / slot * 100, 1) if slot else None,
                "log_kode": dict(log_kode), "log_hari": log_hari,
                "rinci": rinci_fasil(fasil, kode_f, {id(sk): x for sk, x in zip(daftar, st)}) if rinci else [],
                "progres": round(sum(p) / len(p), 1) if p else None}

    pic = [hitung(n, d) for n, d in per_pic.values()]
    pic.sort(key=lambda x: (-(x["persen"] or 0), x["nama"].casefold()))
    for i, x in enumerate(pic, 1):
        x["peringkat"] = i
    return {"pic": pic, "nasional": hitung("Nasional", sekolah, rinci=False), "hari_log": tanggal,
            "komponen": [{"kode": k.kode, "label": k.label} for k in lk_baru.KOMPONEN],
            "kode_kom": komunikasi.kode_label(), "berkolom": sorted(berkolom),
            "blok": [{"blok": b, "label": lk_baru.label_blok(b, sesi)} for b in blok_urut], "blok_hari": blok_hari,
            "bimtek": bimtek, "dibuat": schedule.now().strftime("%d/%m %H.%M")}


def ambil(bimtek: str = "") -> dict[str, Any]:
    """Hasil disimpan 10 menit per filter bimtek."""
    k = bimtek.casefold()
    with _lock:
        ada = _simpan.get(k)
        if ada and time.time() - ada[0] < SIMPAN_DETIK:
            return ada[1]
        d = hitung(bimtek)
        _simpan[k] = (time.time(), d)
        return d
