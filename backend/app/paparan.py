"""Paparan PIC: 6 slide tentang binaannya sendiri, tampil di aplikasi dan bisa dibuat menjadi Google Slides.

Isi slide disusun sekali sebagai daftar bentuk sederhana (kotak, teks, tabel) dalam koordinat 720 x 405 pt.
Daftar yang sama digambar oleh halaman Paparan (pratinjau & mode presentasi) dan dikirim ke Google Slides API,
jadi pratinjau sama dengan hasilnya.

Izin Google Slides terpisah dari login utama (token_slides.json, scope drive.file): hanya diminta saat PIC
pertama kali menekan "Buat Google Slides", dan aplikasi hanya bisa membuka file yang dibuatnya sendiri.
"""

import json
import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import komunikasi, lk_baru, paths, schedule, todo

log = logging.getLogger(__name__)

W, H = 720, 405
TINTA, TINTA2, REDUP, GARIS, LATAR = "#172033", "#344054", "#5b6474", "#e4e7ec", "#eef0f3"
BIRU, BIRU_MUDA, MERAH = "#2346a0", "#c9d4ef", "#a6282b"

# Status komunikasi, urut dari paling baik ke paling perlu ditindak (warna sama di semua slide)
KOM = (
    ("terhubung", "Sudah membalas", "#2f8f5b"),
    ("perlu_balas", "Membalas, giliran PIC", "#1f7a6c"),
    ("menunggu", "Menunggu konfirmasi", "#d9a23a"),
    ("dibaca", "Dibaca, belum membalas", "#5673bf"),
    ("terkirim", "Terkirim, belum dibaca", "#9aa8c7"),
    ("telepon", "Perlu ditelepon", "#c8484b"),
    ("belum", "Belum dihubungi", "#c4c9d2"),
)
KOM_LABEL = {k: lbl for k, lbl, _ in KOM}
KOM_WARNA = {k: w for k, _, w in KOM}
# Kode Log Komunikasi dikelompokkan, urut dari paling baik. Status fasil dalam seminggu = kode terbaiknya.
GRUP_KOM = (
    ("terhubung", "Terhubung", ("T", "TP"), "#2f8f5b"),
    ("menunggu", "Menunggu / respon lambat", ("T1", "T2"), "#d9a23a"),
    ("dibaca", "Hanya dibaca", ("R",), "#5673bf"),
    ("centang", "Centang satu", ("C",), "#c8484b"),
    ("tanpa_wa", "Tidak ada WA", ("N",), "#9b4a7f"),
    ("belum", "Belum dihubungi", (), "#c4c9d2"),
)
_GRUP_DARI = {k: g for g, _l, ks, _w in GRUP_KOM for k in ks}
_URUT_GRUP = [g for g, *_ in GRUP_KOM]
KENDALA_KOM = ("dibaca", "centang", "tanpa_wa", "menunggu")
NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat")

SLIDE = (
    ("profil", "Profil sekolah binaan"),
    ("fasil", "Fasil binaan"),
    ("komunikasi", "Distribusi komunikasi"),
    ("bottleneck", "Bottleneck"),
    ("masalah", "Fasil bermasalah"),
    ("langkah", "Langkah berikutnya"),
    ("lampiran", "Lampiran: tabel lengkap"),
)
BAWAAN_MATI = {"lampiran"}  # tidak dipaparkan kecuali dipilih
KATEGORI = (
    ("sulit", "Sulit dihubungi"),
    ("macet", "Merespons, laporan tidak bergerak"),
    ("reviu", "Reviu tertahan > 3 hari"),
    ("rendah", "Capaian komponen < 25%"),
)
_RE_KENDALA = re.compile(r"^\s*\d+\.\s*(.+)$")
SLIDE_JUDUL = dict(SLIDE)


def _n(v: float | int) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _pct(a: float, b: float) -> int:
    return round(a / b * 100) if b else 0


# ---------- data ----------

def _masalah(x: dict[str, Any], persen: int | None) -> tuple[list[str], str, list[str]]:
    """Alasan fasil masuk daftar bermasalah, saran tindak lanjut, dan kode kategorinya."""
    alasan, saran, kat = [], [], []
    if x["perlu"] and (x["kom"] in ("telepon", "dibaca", "terkirim") or x["belum_ditelepon"]):
        alasan.append("Sulit dihubungi" + (f" ({KOM_LABEL[x['kom']].lower()})" if x["kom"] != "telepon" else ""))
        saran.append("Telepon fasil; bila tetap tidak tersambung, hubungi koordinator")
        kat.append("sulit")
    if x["tanpa_progres"]:
        alasan.append("Merespons, tapi laporan tidak bergerak")
        saran.append("Tanyakan kendala spesifik atau eskalasi ke koordinator")
        kat.append("macet")
    if (x["tunggu_maks"] or 0) > 3:
        alasan.append(f"Reviu tertahan {x['tunggu_maks']:.0f} hari")
        saran.append("Ingatkan fasil mereviu laporan sekolah")
        kat.append("reviu")
    if x["perlu"] and persen is not None and persen < 25:
        alasan.append(f"Capaian komponen baru {persen}%")
        fokus = x["fokus"][0]["judul"] if x["fokus"] else ""
        saran.append(f"Dampingi bertahap, mulai dari {fokus.lower()}" if fokus else "Dampingi per komponen")
        kat.append("rendah")
    return alasan, saran[0] if saran else "", kat


def hitung() -> dict[str, Any]:
    """Semua angka untuk 6 slide, dari data yang sama dengan halaman LK dan Dashboard."""
    from .routers import dashboard, lkb

    saya = komunikasi.petugas_saya()
    lk = lkb.ringkasan(False, None)
    dash = dashboard.ambil(saya)
    sekolah = komunikasi.sekolah_saya()
    fasil_obj = komunikasi.kelompokkan(sekolah)
    try:
        logkom = lk_baru.baca_log_kom()
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    status = {s.npsn: todo.semua_status(s) for s in sekolah}

    # fasil binaan
    per_fasil_komp: dict[str, tuple[int, int, float | None]] = {}
    for kunci, f in fasil_obj.items():
        st = [status[s.npsn] for s in f.sekolah]
        sel = sum(1 for x in st for v in x.values() if v.status == "selesai")
        rel = sum(1 for x in st for v in x.values() if v.status in ("selesai", "belum"))
        p = [x["progres"].persen for x in st if x["progres"].persen is not None]
        per_fasil_komp[kunci] = (sel, rel, round(sum(p) / len(p), 1) if p else None)
    fasil = []
    for x in lk["fasil"]:
        sel, rel, prog = per_fasil_komp.get(x["kunci"], (0, 0, None))
        alasan, saran, kat = _masalah(x, _pct(sel, rel) if rel else None)
        fasil.append({"nama": x["nama"], "ptn": x["ptn"], "koor": x["koor"], "sekolah": x["sekolah"],
                      "perlu": x["perlu"], "todo": x["todo"], "selesai": sel, "relevan": rel,
                      "persen": _pct(sel, rel) if rel else None, "progres": prog, "kom": x["kom"],
                      "masalah": alasan, "saran": saran, "kategori": kat})
    fasil.sort(key=lambda f: (f["persen"] if f["persen"] is not None else 101, f["nama"].casefold()))

    # bottleneck: di komponen mana sekolah paling banyak tertahan
    kendala: Counter[str] = Counter()
    for s in sekolah:
        isi = set()
        for blok in s.isian.values():
            for k, _tl in blok.values():
                m = _RE_KENDALA.match(k or "")
                if m and not m.group(1).casefold().startswith("tidak ada kendala"):
                    isi.add(" ".join(m.group(1).split()))
        kendala.update(isi)

    masalah = [f for f in fasil if f["masalah"]]
    masalah.sort(key=lambda f: (-len(f["masalah"]), -(f["todo"]), f["nama"].casefold()))
    di = dash["distribusi"]
    return {
        "pic": saya,
        "week": lk["week"],
        "cutoff": lk.get("cutoff", ""),
        "tanggal": schedule.tanggal_panjang(schedule.now().date()),
        "dibuat": schedule.now().strftime("%d/%m %H.%M"),
        "profil": {k: di[k] for k in ("sekolah", "fasil", "koor", "jml_ptn", "jml_kab", "rata_sekolah_per_fasil",
                                     "maks_sekolah_per_fasil", "angkatan", "provinsi", "kab", "ptn")},
        "fasil": fasil,
        "komunikasi": komunikasi_mingguan(fasil_obj, logkom, schedule.now().date()),
        "bottleneck": {
            "posisi": [{"kode": p["kode"], "label": p["label"], "sekolah": p["sekolah"], "fasil": p["fasil"]}
                       for p in lk["posisi"]],
            "reviu": {k: dash["reviu"][k] for k in ("rata", "lewat3", "menunggu")},
            "kendala": [{"teks": k, "sekolah": v} for k, v in kendala.most_common(6)],
            "sekolah_todo": sum(x["perlu"] for x in lk["fasil"]),
            "sekolah": len(sekolah),
        },
        "masalah": masalah,
        "kategori": [{"kode": k, "label": lbl, "fasil": sum(1 for f in masalah if k in f["kategori"])}
                     for k, lbl in KATEGORI],
        "sebaran_fasil": [{"nama": n, "jumlah": sum(1 for f in fasil if f["persen"] is not None and a <= f["persen"] < b)}
                          for n, a, b in (("0–24%", 0, 25), ("25–49%", 25, 50), ("50–74%", 50, 75),
                                          ("75–99%", 75, 100), ("100%", 100, 101))],
    }


def _status_minggu(kode: dict[str, str], hari: list[str]) -> str:
    grup = {_GRUP_DARI.get(kode.get(d, ""), "") for d in hari} - {""}
    return min(grup, key=_URUT_GRUP.index) if grup else "belum"


def _rentang(hari: list[str]) -> str:
    a, b = date.fromisoformat(hari[0]), date.fromisoformat(hari[-1])
    return f"{a:%d/%m}" if a == b else f"{a:%d/%m}–{b:%d/%m}"


def komunikasi_mingguan(fasil: dict[str, komunikasi.Fasil], logkom: lk_baru.LogKom, hari_ini: date,
                        maks_minggu: int = 3) -> dict[str, Any]:
    """Distribusi status komunikasi fasil dari Log Komunikasi, minggu ini (Senin s.d. hari ini) dibanding minggu
    sebelumnya pada rentang hari yang sama."""
    ke = min(hari_ini.weekday(), 4)
    senin = hari_ini - timedelta(days=hari_ini.weekday())
    kode = {k: komunikasi.kode_fasil(f, logkom) for k, f in fasil.items()}
    minggu = []
    for i in range(maks_minggu):
        s0 = senin - timedelta(weeks=i)
        hari = [(s0 + timedelta(days=j)).isoformat() for j in range(ke + 1)]
        if i and not any(d in logkom.tanggal for d in hari):
            break
        status = {k: _status_minggu(kode[k], hari) for k in fasil}
        c = Counter(status.values())
        minggu.append({
            "label": "Minggu ini" if i == 0 else ("Minggu lalu" if i == 1 else f"{i} minggu lalu"),
            "rentang": _rentang(hari), "ada_log": any(d in logkom.tanggal for d in hari),
            "grup": {g: c.get(g, 0) for g in _URUT_GRUP},
            "dihubungi": len(fasil) - c.get("belum", 0),
            "contoh": {g: sorted((fasil[k].nama for k, v in status.items() if v == g), key=str.casefold)[:3]
                       for g in KENDALA_KOM},
        })
    ini, lalu = minggu[0], (minggu[1] if len(minggu) > 1 else None)
    return {
        "fasil": len(fasil),
        "sampai": NAMA_HARI[ke],
        "minggu": minggu,
        "grup": [{"kode": g, "label": lbl, "warna": w} for g, lbl, _ks, w in GRUP_KOM],
        "kendala": [{"kode": g, "label": next(x[1] for x in GRUP_KOM if x[0] == g), "jumlah": ini["grup"][g],
                     "lalu": lalu["grup"][g] if lalu else None, "contoh": ini["contoh"][g]} for g in KENDALA_KOM],
    }


def _selisih(kini: int, lalu: int | None) -> str:
    if lalu is None:
        return ""
    s = kini - lalu
    if s == 0:
        return "sama dengan minggu lalu"
    return f"{'+' if s > 0 else '−'}{abs(s)} dari minggu lalu"


def langkah_awal(d: dict[str, Any]) -> list[str]:
    """Usulan langkah berikutnya dari data; PIC bisa mengubahnya sebelum memaparkan."""
    out = []
    pos = sorted(d["bottleneck"]["posisi"], key=lambda p: -p["sekolah"])
    if pos and pos[0]["sekolah"]:
        out.append(f"Fokus {pos[0]['label'].lower()}: {pos[0]['sekolah']} sekolah dari {pos[0]['fasil']} fasil "
                   "masih tertahan.")
    g = d["komunikasi"]["minggu"][0]["grup"]
    sulit = g["dibaca"] + g["centang"] + g["tanpa_wa"]
    if sulit:
        out.append(f"Telepon {sulit} fasil yang chatnya hanya dibaca, centang satu, atau tidak ada WA.")
    if g["belum"]:
        out.append(f"Hubungi {g['belum']} fasil yang belum dihubungi minggu ini.")
    r = d["bottleneck"]["reviu"]
    if r["lewat3"]:
        out.append(f"Ingatkan reviu: {r['lewat3']} laporan sekolah menunggu direviu lebih dari 3 hari.")
    macet = [f for f in d["masalah"] if any(a.startswith("Merespons") for a in f["masalah"])]
    if macet:
        out.append(f"Eskalasi ke koordinator untuk {len(macet)} fasil yang merespons tapi laporannya tidak bergerak.")
    return out or ["Pertahankan ritme komunikasi; semua fasil dalam kondisi baik."]


def catatan_awal(d: dict[str, Any]) -> dict[str, str]:
    """Catatan pembicara bawaan per slide."""
    p = d["profil"]
    km = d["komunikasi"]
    ini = km["minggu"][0]
    lalu = km["minggu"][1] if len(km["minggu"]) > 1 else None
    ken = [k for k in km["kendala"] if k["jumlah"]]
    sel = sum(f["selesai"] for f in d["fasil"])
    rel = sum(f["relevan"] for f in d["fasil"])
    rendah = [f["nama"] for f in d["fasil"] if f["persen"] is not None][:3]
    pos = sorted(d["bottleneck"]["posisi"], key=lambda x: -x["sekolah"])
    ken_isian = d["bottleneck"]["kendala"]
    prov = p["provinsi"][0]["nama"] if p["provinsi"] else "-"
    return {
        "profil": f"Binaan saya {p['sekolah']} sekolah dengan {p['fasil']} fasil dan {p['koor']} koordinator, "
                  f"tersebar di {p['jml_kab']} kab/kota. Terbanyak di {prov}.",
        "fasil": f"Secara keseluruhan {_pct(sel, rel)}% komponen sudah selesai. "
                 + (f"Capaian terendah: {', '.join(rendah)}." if rendah else ""),
        "komunikasi": f"Sampai {km['sampai']}, {ini['dihubungi']} dari {km['fasil']} fasil sudah dihubungi dan "
                      f"{ini['grup']['terhubung']} terhubung"
                      + (f" (minggu lalu pada hari yang sama: {lalu['dihubungi']} dihubungi, "
                         f"{lalu['grup']['terhubung']} terhubung)" if lalu else "") + ". "
                      + ("Kendala: " + ", ".join(f"{k['jumlah']} {k['label'].lower()}" for k in ken) + "."
                         if ken else ""),
        "bottleneck": (f"Sekolah paling banyak tertahan di {pos[0]['label'].lower()} ({pos[0]['sekolah']} sekolah). "
                       if pos and pos[0]["sekolah"] else "")
                      + (f"Kendala yang paling sering: {ken_isian[0]['teks'].lower()}." if ken_isian else ""),
        "masalah": f"{len(d['masalah'])} fasil perlu perhatian khusus: "
                   + ", ".join(f"{k['fasil']} {k['label'].lower()}" for k in d["kategori"] if k["fasil"]) + "."
                   if d["masalah"]
                   else "Tidak ada fasil bermasalah minggu ini.",
        "langkah": "Rencana minggu depan dan dukungan yang dibutuhkan.",
        "lampiran": "Tabel lengkap untuk menjawab pertanyaan; tidak perlu dipaparkan.",
    }


# ---------- tata letak slide (720 x 405 pt) ----------

def _teks(x, y, w, h, teks, size=11, warna=TINTA, tebal=False, rata="START", poin=False, ubah=""):
    b = {"t": "text", "x": x, "y": y, "w": w, "h": h, "text": teks, "size": size, "color": warna, "bold": tebal,
         "align": rata}
    if poin:
        b["bullets"] = True
    if ubah:
        b["ubah"] = ubah
    return b


def _kotak(x, y, w, h, warna, bulat=False):
    return {"t": "rect", "x": x, "y": y, "w": w, "h": h, "fill": warna, "round": bulat}


def _kepala(judul: str, d: dict[str, Any], hal: str = "") -> list[dict]:
    sub = f"{d['pic']}  |  WEEK {d['week']}" + (f"  |  {d['cutoff']}" if d["cutoff"] else "")
    return [
        _kotak(36, 26, 28, 4, BIRU),
        _teks(30, 34, 560, 34, judul + (f" ({hal})" if hal else ""), 22, TINTA, True),
        _teks(30, 66, 600, 20, sub, 10.5, REDUP),
        _teks(430, 380, 260, 16, f"LK Monitoring  |  {d['tanggal']}", 8, REDUP, rata="END"),
    ]


def _batang(x, y, w, data: list[tuple[str, float, str]], lebar_label=None, tinggi=22, maks=None,
            akhiran="") -> list[dict]:
    """Daftar batang mendatar: label | batang | angka."""
    out = []
    lbl = lebar_label or w * 0.42
    maks = maks or max([v for _, v, _ in data] + [1])
    jalur = w - lbl - 44
    for i, (nama, v, warna) in enumerate(data):
        yy = y + i * tinggi
        out.append(_teks(x, yy, lbl, tinggi, nama, 9.5, TINTA2))
        out.append(_kotak(x + lbl, yy + tinggi / 2 - 4, jalur, 8, LATAR, True))
        if v:
            out.append(_kotak(x + lbl, yy + tinggi / 2 - 4, max(4, jalur * v / maks), 8, warna, True))
        out.append(_teks(x + lbl + jalur, yy, 44, tinggi, f"{_n(v)}{akhiran}", 9.5, TINTA, True, "END"))
    return out


def _angka_besar(x, y, w, angka: str, label: str, warna=TINTA) -> list[dict]:
    return [_teks(x, y, w, 34, angka, 24, warna, True), _teks(x, y + 32, w, 28, label, 9, REDUP)]


_SINGKAT = (("Universitas Islam Negeri", "UIN"), ("Universitas", "Univ."), ("Kepulauan", "Kep."))


def _singkat(v: str) -> str:
    for a, b in _SINGKAT:
        v = v.replace(a, b)
    return v


def _slide_profil(d):
    p = d["profil"]
    b = _kepala("Profil sekolah binaan", d)
    kpi = [(_n(p["sekolah"]), "sekolah binaan"), (_n(p["fasil"]), "fasil"), (_n(p["koor"]), "koordinator"),
           (_n(p["jml_kab"]), "kab/kota"), (_n(p["jml_ptn"]), "PTN pendamping"),
           (str(p["rata_sekolah_per_fasil"]).replace(".", ","), "rata-rata sekolah/fasil")]
    for i, (a, l) in enumerate(kpi):
        b += _angka_besar(36 + i * 110, 98, 104, a, l, BIRU if i == 0 else TINTA)
    b.append(_kotak(36, 160, 648, 1, GARIS))
    kol = [("Provinsi", p["provinsi"][:7]), ("Angkatan", p["angkatan"][:7]), ("PTN", p["ptn"][:7])]
    for i, (j, isi) in enumerate(kol):
        x = 36 + i * 222
        b.append(_teks(x - 6, 170, 200, 18, j, 10.5, TINTA, True))
        b += _batang(x, 192, 204, [(_singkat(r["nama"]), r["jumlah"], BIRU) for r in isi], lebar_label=112, tinggi=26)
    return b


def _slide_fasil(d):
    b = _kepala("Fasil binaan", d)
    sel = sum(f["selesai"] for f in d["fasil"])
    rel = sum(f["relevan"] for f in d["fasil"])
    b += _angka_besar(36, 96, 150, f"{_pct(sel, rel)}%", "komponen selesai, semua fasil", BIRU)
    b += _angka_besar(196, 96, 120, _n(len(d["fasil"])), "fasil binaan")
    b.append(_teks(30, 160, 290, 18, "Sebaran fasil per capaian komponen", 10.5, TINTA, True))
    warna = ["#c8484b", "#d9a23a", "#9aa8c7", "#5673bf", "#2f8f5b"]
    b += _batang(36, 184, 280, [(r["nama"], r["jumlah"], warna[i]) for i, r in enumerate(d["sebaran_fasil"])],
                 lebar_label=70, tinggi=30)
    b.append(_teks(344, 94, 340, 18, "10 fasil dengan capaian terendah", 10.5, TINTA, True))
    rows = [[f["nama"], str(f["sekolah"]), f"{f['persen']}%" if f["persen"] is not None else "-",
             KOM_LABEL.get(f["kom"], "-")] for f in d["fasil"][:10]]
    b.append({"t": "table", "x": 350, "y": 116, "w": 334, "size": 8.5,
              "cols": [{"label": "Fasil", "w": 136}, {"label": "Sekolah", "w": 46, "align": "END"},
                       {"label": "Selesai", "w": 46, "align": "END"}, {"label": "Komunikasi", "w": 106}],
              "rows": rows})
    return b


def _lampiran_fasil(d, baris: list[dict], hal: str):
    b = _kepala("Lampiran: semua fasil binaan", d, hal)
    rows = []
    for f in baris:
        rows.append([f["nama"], f["ptn"] or "-", str(f["sekolah"]),
                     f"{f['persen']}%" if f["persen"] is not None else "-",
                     f"{f['progres']:.0f}%".replace(".", ",") if f["progres"] is not None else "-",
                     KOM_LABEL.get(f["kom"], "-")])
    b.append({"t": "table", "x": 36, "y": 96, "w": 648, "size": 9,
              "cols": [{"label": "Fasil", "w": 170}, {"label": "PTN", "w": 150},
                       {"label": "Sekolah", "w": 52, "align": "END"},
                       {"label": "Komponen selesai", "w": 86, "align": "END"},
                       {"label": "Progres fisik", "w": 70, "align": "END"},
                       {"label": "Komunikasi", "w": 120}],
              "rows": rows})
    return b


def _slide_komunikasi(d):
    k = d["komunikasi"]
    b = _kepala("Distribusi komunikasi", d)
    nf = k["fasil"] or 1
    ini = k["minggu"][0]
    lalu = k["minggu"][1] if len(k["minggu"]) > 1 else None
    kpi = [(f"{ini['dihubungi']}/{nf}", "fasil sudah dihubungi", "dihubungi", BIRU),
           (_n(ini["grup"]["terhubung"]), "fasil terhubung", "terhubung", TINTA),
           (_n(ini["grup"]["belum"]), "belum dihubungi", "belum", MERAH if ini["grup"]["belum"] else TINTA)]
    for i, (angka, label, kunci, warna) in enumerate(kpi):
        kini = ini["dihubungi"] if kunci == "dihubungi" else ini["grup"][kunci]
        dulu = (lalu["dihubungi"] if kunci == "dihubungi" else lalu["grup"][kunci]) if lalu else None
        b.append(_teks(30 + i * 140, 92, 136, 34, angka, 24, warna, True))
        b.append(_teks(30 + i * 140, 124, 136, 16, label, 9, REDUP))
        if dulu is not None:
            b.append(_teks(30 + i * 140, 138, 136, 16, _selisih(kini, dulu), 8.5, TINTA2))
    if not ini["ada_log"]:
        b.append(_teks(30, 160, 420, 30, "Log Komunikasi minggu ini belum terisi.", 10, REDUP))

    # perbandingan per minggu: batang 100% bertumpuk
    b.append(_teks(30, 166, 420, 18, f"Perbandingan per minggu, Senin s.d. {k['sampai']}", 10.5, TINTA, True))
    x0, w0 = 150, 250
    for i, m in enumerate(k["minggu"][:3]):
        y = 190 + i * 42
        b.append(_teks(30, y, 118, 16, m["label"], 9.5, TINTA, True))
        b.append(_teks(30, y + 14, 118, 16, m["rentang"], 8.5, REDUP))
        x = x0
        for g in k["grup"]:
            v = m["grup"][g["kode"]]
            if not v:
                continue
            w = w0 * v / nf
            b.append(_kotak(x, y + 6, max(w - 1.5, 1), 16, g["warna"]))
            x += w
        b.append(_teks(x0 + w0 + 2, y + 2, 50, 22, f"{_pct(m['dihubungi'], nf)}%", 10, TINTA, True, "END"))
    for i, g in enumerate(k["grup"]):
        x, y = 36 + (i % 3) * 140, 324 + (i // 3) * 18
        b.append(_kotak(x, y + 5, 8, 8, g["warna"], True))
        b.append(_teks(x + 6, y, 130, 18, g["label"], 8.5, TINTA2))

    # kendala komunikasi minggu ini
    b.append(_kotak(462, 96, 1, 270, GARIS))
    b.append(_teks(470, 92, 220, 18, "Kendala komunikasi minggu ini", 10.5, TINTA, True))
    for i, kd in enumerate(k["kendala"]):
        y = 116 + i * 64
        warna = next(g["warna"] for g in k["grup"] if g["kode"] == kd["kode"])
        b.append(_kotak(476, y + 6, 8, 8, warna, True))
        b.append(_teks(484, y, 150, 18, kd["label"], 9.5, TINTA, True))
        b.append(_teks(634, y, 50, 18, _n(kd["jumlah"]), 10, TINTA, True, "END"))
        sub = _selisih(kd["jumlah"], kd["lalu"])
        if sub:
            b.append(_teks(484, y + 15, 200, 15, sub, 8, REDUP))
        if kd["contoh"]:
            lebih = kd["jumlah"] - len(kd["contoh"])
            b.append(_teks(484, y + 29, 200, 28, ", ".join(kd["contoh"]) + (f", +{lebih} lainnya" if lebih > 0 else ""),
                           8, TINTA2))
    return b


def _slide_bottleneck(d):
    bt = d["bottleneck"]
    b = _kepala("Bottleneck", d)
    pos = bt["posisi"]
    maks = max([p["sekolah"] for p in pos] + [1])
    puncak = max(pos, key=lambda p: p["sekolah"]) if pos else None
    b.append(_teks(30, 94, 380, 18, "Sekolah yang tertahan per komponen", 10.5, TINTA, True))
    b += _batang(36, 116, 380, [(p["label"], p["sekolah"],
                                 MERAH if puncak and p is puncak and p["sekolah"] else BIRU_MUDA) for p in pos],
                 lebar_label=160, tinggi=28, maks=maks)
    if puncak and puncak["sekolah"]:
        b.append(_teks(30, 320, 390, 44, f"Bottleneck utama: {puncak['label']} ({puncak['sekolah']} sekolah, "
                                         f"{puncak['fasil']} fasil)", 12, MERAH, True))
    r = bt["reviu"]
    b += _angka_besar(450, 96, 110, _n(r["lewat3"]), "reviu menunggu > 3 hari", MERAH if r["lewat3"] else TINTA)
    b += _angka_besar(570, 96, 114, (f"{r['rata']:.1f}".replace(".", ",") + " hr") if r["rata"] else "-",
                      "rata-rata tunggu reviu")
    b.append(_kotak(450, 158, 234, 1, GARIS))
    b.append(_teks(444, 166, 240, 18, "Kendala yang paling sering diisi", 10.5, TINTA, True))
    if bt["kendala"]:
        y = 190
        for k in bt["kendala"][:6]:
            b.append(_teks(444, y, 200, 30, k["teks"], 9, TINTA2))
            b.append(_teks(640, y, 44, 30, f"{k['sekolah']}", 9.5, TINTA, True, "END"))
            y += 30
    else:
        b.append(_teks(444, 190, 240, 30, "Isian kendala minggu ini belum ada.", 9.5, REDUP))
    return b


def _slide_masalah(d):
    b = _kepala("Fasil bermasalah", d)
    m = d["masalah"]
    if not m:
        b.append(_teks(30, 150, 640, 40, "Tidak ada fasil bermasalah minggu ini.", 16, TINTA2))
        return b
    b += _angka_besar(36, 94, 140, _n(len(m)), f"dari {len(d['fasil'])} fasil perlu perhatian", MERAH)
    for i, k in enumerate(d["kategori"]):
        b += _angka_besar(196 + i * 124, 94, 120, _n(k["fasil"]), k["label"].lower())
    b.append(_kotak(36, 152, 648, 1, GARIS))
    judul = "Prioritas tindak lanjut" + (f" (6 teratas dari {len(m)}, sisanya di lampiran)" if len(m) > 6 else "")
    b.append(_teks(30, 158, 640, 18, judul, 10.5, TINTA, True))
    b.append({"t": "table", "x": 36, "y": 180, "w": 648, "size": 8.5,
              "cols": [{"label": "Fasil", "w": 150}, {"label": "Koordinator", "w": 110},
                       {"label": "Masalah", "w": 200}, {"label": "Tindak lanjut", "w": 188}],
              "rows": [[f["nama"], f["koor"] or "-", "; ".join(f["masalah"]), f["saran"]] for f in m[:6]]})
    return b


def _lampiran_masalah(d, baris: list[dict], hal: str):
    b = _kepala("Lampiran: semua fasil bermasalah", d, hal)
    b.append({"t": "table", "x": 36, "y": 96, "w": 648, "size": 9,
              "cols": [{"label": "Fasil", "w": 160}, {"label": "Koordinator", "w": 120},
                       {"label": "Masalah", "w": 190}, {"label": "Tindak lanjut", "w": 178}],
              "rows": [[f["nama"], f["koor"] or "-", "; ".join(f["masalah"]), f["saran"]] for f in baris]})
    return b


def _slide_langkah(d, langkah: list[str]):
    b = _kepala("Langkah berikutnya", d)
    b.append(_teks(30, 100, 640, 270, "\n".join(langkah) or "-", 14, TINTA, poin=True, ubah="langkah"))
    return b


def _potong(xs: list, n: int) -> list[list]:
    return [xs[i:i + n] for i in range(0, len(xs), n)] or [[]]


def susun(d: dict[str, Any], urutan: list[str] | None = None, langkah: list[str] | None = None,
          catatan: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Daftar slide (urut, hanya yang dipilih). Tabel panjang dipecah menjadi beberapa slide."""
    urutan = [k for k in (urutan if urutan is not None else [k for k, _ in SLIDE]) if k in SLIDE_JUDUL]
    cat = {**catatan_awal(d), **{k: v for k, v in (catatan or {}).items() if k in SLIDE_JUDUL}}
    lk = langkah if langkah is not None else langkah_awal(d)
    out = []
    for k in urutan:
        if k == "lampiran":
            hf = _potong(d["fasil"], 12)
            hm = _potong(d["masalah"], 7) if d["masalah"] else []
            badan = [_lampiran_fasil(d, h, f"{i + 1}/{len(hf)}" if len(hf) > 1 else "") for i, h in enumerate(hf)]
            badan += [_lampiran_masalah(d, h, f"{i + 1}/{len(hm)}" if len(hm) > 1 else "") for i, h in enumerate(hm)]
        elif k == "langkah":
            badan = [_slide_langkah(d, lk)]
        else:
            badan = [{"profil": _slide_profil, "fasil": _slide_fasil, "komunikasi": _slide_komunikasi,
                      "bottleneck": _slide_bottleneck, "masalah": _slide_masalah}[k](d)]
        for i, bentuk in enumerate(badan):
            out.append({"kunci": k, "judul": SLIDE_JUDUL[k], "lanjutan": i > 0, "bentuk": bentuk,
                        "catatan": cat.get(k, "") if i == 0 else ""})
    return out


def terapkan_ubahan(slides: list[dict[str, Any]], ubahan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Teks yang diedit PIC di pratinjau. Tiap ubahan menyebut slide (kunci + halaman), nomor bentuk, sel tabel
    (baris -1 = judul kolom), teks asli, dan teks baru. Ubahan dilewati bila teks aslinya sudah berubah karena data
    diperbarui, supaya tidak menimpa angka baru dengan angka lama."""
    halaman: Counter[str] = Counter()
    letak = {}
    for s in slides:
        letak[(s["kunci"], halaman[s["kunci"]])] = s
        halaman[s["kunci"]] += 1
    for u in ubahan:
        s = letak.get((u.get("kunci"), u.get("halaman", 0)))
        try:
            b = s["bentuk"][int(u["bentuk"])] if s else None
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        baru = str(u.get("baru", ""))[:2000]
        if not b or b.get("ubah"):
            continue
        if b["t"] == "text" and b["text"] == u.get("asli"):
            b["text"] = baru
        elif b["t"] == "table" and u.get("sel"):
            r, c = u["sel"]
            if r == -1 and 0 <= c < len(b["cols"]) and b["cols"][c]["label"] == u.get("asli"):
                b["cols"][c]["label"] = baru
            elif 0 <= r < len(b["rows"]) and 0 <= c < len(b["rows"][r]) and b["rows"][r][c] == u.get("asli"):
                b["rows"][r][c] = baru
    return slides


# ---------- izin Google Slides (terpisah dari login utama) ----------

SCOPES_SLIDES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_SLIDES = paths.DATA_DIR / "token_slides.json"


@dataclass
class IzinState:
    status: str = "idle"  # idle | running | done | error
    error: str = ""


izin_state = IzinState()
_izin_lock = threading.Lock()


def _creds_slides() -> Credentials | None:
    if not TOKEN_SLIDES.exists():
        return None
    try:
        c = Credentials.from_authorized_user_file(str(TOKEN_SLIDES), SCOPES_SLIDES)
    except (ValueError, json.JSONDecodeError):
        return None
    if not c.valid:
        if not (c.expired and c.refresh_token):
            return None
        try:
            c.refresh(Request())
            TOKEN_SLIDES.write_text(c.to_json(), encoding="utf-8")
        except RefreshError:
            return None
    return c


def punya_izin() -> bool:
    return _creds_slides() is not None


def _jalan_izin(email: str) -> None:
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(paths.CREDENTIALS_FILE), SCOPES_SLIDES)
        c = flow.run_local_server(port=0, open_browser=True, authorization_prompt_message="",
                                  success_message="Izin Google Slides diberikan. Tutup tab ini dan kembali ke "
                                                  "LK Monitoring.",
                                  login_hint=email or None)
        TOKEN_SLIDES.write_text(c.to_json(), encoding="utf-8")
        izin_state.status, izin_state.error = "done", ""
    except Exception as e:
        izin_state.status, izin_state.error = "error", f"Izin gagal: {e}"


def minta_izin(email: str) -> IzinState:
    with _izin_lock:
        if izin_state.status != "running":
            izin_state.status, izin_state.error = "running", ""
            threading.Thread(target=_jalan_izin, args=(email,), name="izin-slides", daemon=True).start()
    return izin_state


def cabut_izin() -> None:
    if TOKEN_SLIDES.exists():
        TOKEN_SLIDES.unlink()
    izin_state.status, izin_state.error = "idle", ""


# ---------- Google Slides API ----------

API = "https://slides.googleapis.com/v1/presentations"


class SlidesError(Exception):
    pass


def _rgb(hexa: str) -> dict[str, float]:
    h = hexa.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def _pt(v: float) -> dict[str, Any]:
    return {"magnitude": round(v, 2), "unit": "PT"}


def _letak(page: str, x, y, w, h) -> dict[str, Any]:
    return {"pageObjectId": page, "size": {"width": _pt(w), "height": _pt(h)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": round(x, 2), "translateY": round(y, 2), "unit": "PT"}}


def _gaya_teks(oid: str, size: float, warna: str, tebal: bool, cell: dict | None = None) -> dict:
    r = {"objectId": oid, "textRange": {"type": "ALL"},
         "style": {"fontFamily": "IBM Plex Sans", "fontSize": _pt(size), "bold": tebal,
                   "foregroundColor": {"opaqueColor": {"rgbColor": _rgb(warna)}}},
         "fields": "fontFamily,fontSize,bold,foregroundColor"}
    if cell:
        r["cellLocation"] = cell
    return {"updateTextStyle": r}


def _permintaan(page: str, bentuk: list[dict], nomor: list[int]) -> list[dict]:
    req: list[dict] = []

    def oid() -> str:
        nomor[0] += 1
        return f"{page}_{nomor[0]}"

    for b in bentuk:
        if b["t"] == "rect":
            o = oid()
            req.append({"createShape": {"objectId": o, "shapeType": "ROUND_RECTANGLE" if b.get("round") else "RECTANGLE",
                                        "elementProperties": _letak(page, b["x"], b["y"], b["w"], b["h"])}})
            req.append({"updateShapeProperties": {"objectId": o, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                                  "shapeProperties": {
                                                      "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": _rgb(b["fill"])}}},
                                                      "outline": {"propertyState": "NOT_RENDERED"}}}})
        elif b["t"] == "text":
            if not b["text"]:
                continue
            o = oid()
            req.append({"createShape": {"objectId": o, "shapeType": "TEXT_BOX",
                                        "elementProperties": _letak(page, b["x"], b["y"], b["w"], b["h"])}})
            req.append({"insertText": {"objectId": o, "text": b["text"]}})
            req.append(_gaya_teks(o, b["size"], b["color"], b["bold"]))
            req.append({"updateParagraphStyle": {"objectId": o, "textRange": {"type": "ALL"},
                                                 "style": {"alignment": b["align"], "lineSpacing": 115 if b.get("bullets") else 100,
                                                           "spaceBelow": _pt(8 if b.get("bullets") else 0)},
                                                 "fields": "alignment,lineSpacing,spaceBelow"}})
            if b.get("bullets"):
                req.append({"createParagraphBullets": {"objectId": o, "textRange": {"type": "ALL"},
                                                       "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        elif b["t"] == "table":
            o = oid()
            cols, rows = b["cols"], b["rows"]
            req.append({"createTable": {"objectId": o, "rows": len(rows) + 1, "columns": len(cols),
                                        "elementProperties": {"pageObjectId": page,
                                                              "transform": {"scaleX": 1, "scaleY": 1, "translateX": b["x"],
                                                                            "translateY": b["y"], "unit": "PT"}}}})
            for j, c in enumerate(cols):
                req.append({"updateTableColumnProperties": {"objectId": o, "columnIndices": [j],
                                                            "tableColumnProperties": {"columnWidth": _pt(c["w"])},
                                                            "fields": "columnWidth"}})
            req.append({"updateTableRowProperties": {"objectId": o, "rowIndices": list(range(len(rows) + 1)),
                                                     "tableRowProperties": {"minRowHeight": _pt(b["size"] * 2.3)},
                                                     "fields": "minRowHeight"}})
            req.append({"updateTableCellProperties": {
                "objectId": o, "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1,
                                              "columnSpan": len(cols)},
                "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": _rgb(BIRU)}}}},
                "fields": "tableCellBackgroundFill.solidFill.color"}})
            req.append({"updateTableBorderProperties": {
                "objectId": o, "borderPosition": "ALL",
                "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": len(rows) + 1,
                               "columnSpan": len(cols)},
                "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": {"rgbColor": _rgb(GARIS)}}},
                                          "weight": _pt(0.75), "dashStyle": "SOLID"},
                "fields": "tableBorderFill.solidFill.color,weight,dashStyle"}})
            for i, baris in enumerate([[c["label"] for c in cols]] + rows):
                for j, isi in enumerate(baris):
                    if not isi:
                        continue
                    cell = {"rowIndex": i, "columnIndex": j}
                    req.append({"insertText": {"objectId": o, "cellLocation": cell, "text": str(isi)}})
                    req.append(_gaya_teks(o, b["size"], "#ffffff" if i == 0 else TINTA, i == 0, cell))
                    if cols[j].get("align") == "END":
                        req.append({"updateParagraphStyle": {"objectId": o, "cellLocation": cell,
                                                             "textRange": {"type": "ALL"}, "style": {"alignment": "END"},
                                                             "fields": "alignment"}})
    return req


def _panggil(sesi: AuthorizedSession, method: str, url: str, body: dict | None = None) -> dict:
    r = sesi.request(method, url, json=body, timeout=90)
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        pesan = err.get("message", r.text[:300])
        if r.status_code == 401:
            cabut_izin()
            raise SlidesError("Izin Google Slides kedaluwarsa. Tekan Buat Google Slides lagi untuk memberi izin.")
        if "SERVICE_DISABLED" in r.text or "has not been used" in pesan or "is disabled" in pesan:
            raise SlidesError("Google Slides API belum diaktifkan di project Google Cloud aplikasi ini. Minta admin "
                              "mengaktifkannya (APIs & Services → Library → Google Slides API → Enable), lalu coba lagi.")
        raise SlidesError(f"Google Slides menolak permintaan ({r.status_code}): {pesan}")
    return r.json() if r.content else {}


def buat_slides(d: dict[str, Any], slides: list[dict[str, Any]]) -> dict[str, str]:
    c = _creds_slides()
    if c is None:
        raise SlidesError("Belum ada izin Google Slides.")
    sesi = AuthorizedSession(c)
    judul = f"Paparan {d['pic']} - WEEK {d['week']}" + (f" - {d['cutoff']}" if d["cutoff"] else "")
    pres = _panggil(sesi, "POST", API, {"title": judul})
    pid = pres["presentationId"]
    awal = [s["objectId"] for s in pres.get("slides", [])]
    req: list[dict] = []
    nomor = [0]
    for i, s in enumerate(slides):
        page = f"lkm{i:02d}"
        req.append({"createSlide": {"objectId": page, "insertionIndex": i,
                                    "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        req += _permintaan(page, s["bentuk"], nomor)
    req += [{"deleteObject": {"objectId": o}} for o in awal]
    for i in range(0, len(req), 400):
        _panggil(sesi, "POST", f"{API}/{pid}:batchUpdate", {"requests": req[i:i + 400]})
    # catatan pembicara: id kotaknya baru diketahui setelah slide dibuat
    try:
        isi = _panggil(sesi, "GET", f"{API}/{pid}?fields=slides(objectId,slideProperties.notesPage.notesProperties)")
        catat = []
        for s, meta in zip(slides, isi.get("slides", [])):
            sid = meta.get("slideProperties", {}).get("notesPage", {}).get("notesProperties", {}).get("speakerNotesObjectId")
            if sid and s["catatan"].strip():
                catat.append({"insertText": {"objectId": sid, "text": s["catatan"].strip()}})
        if catat:
            _panggil(sesi, "POST", f"{API}/{pid}:batchUpdate", {"requests": catat})
    except SlidesError:
        log.warning("Catatan pembicara tidak terpasang", exc_info=True)
    return {"id": pid, "url": f"https://docs.google.com/presentation/d/{pid}/edit", "judul": judul}
