"""Rekap pertumbuhan sekolah setelah Bimtek Pelaporan (B1, B2, ...).

Data dibaca dari folder `data-bimtek` (di LUAR repo karena export berisi data pribadi):
  0-referensi/jadwal_bimtek.csv   kelompok;tag;mulai;selesai;catatan
  0-referensi/<daftar peserta>    kolom NPSN + Tag (atau Bimtek Pelaporan)
  1-sebelum/Bn/                   kondisi sebelum bimtek kelompok n: export, salinan cutoff (JSON), atau LK lama (JSON)
  2-terbaru/                      export terbaru
Hasil hitungan (tanpa data pribadi, hanya angka per kelompok) ditulis ke tab tersembunyi "Rekap Bimtek" di LK,
supaya dashboard online dan laptop lain ikut membacanya.

Logika (lihat juga halaman Dashboard -> Bimtek):
- Pembanding = sekolah yang BELUM dibimtek saat itu: peserta bimtek berikutnya (mulai setelah bimtek ini selesai) dan
  sekolah yang tidak ada di daftar mana pun, diukur di tanggal yang sama. (Hampir semua sekolah yang wajib Laporan 50%
  ikut salah satu bimtek, jadi non-peserta murni terlalu sedikit untuk jadi pembanding.)
- Laporan 50% memakai tanggal kirim per sekolah: tanggal PALING AWAL dari semua export di folder (kolom "Tgl Kirim 50%"
  berisi kiriman terakhir; kirim ulang setelah revisi menggeser tanggalnya). Jadi bisa dihitung untuk tanggal berapa pun.
  Yang dihitung hanya sekolah yang Laporan 50%-nya sudah jatuh tempo menurut export terbaru.
- Konversi = dari sekolah yang BELUM di titik awal (T0, sehari sebelum bimtek mulai), berapa persen yang SUDAH di titik
  ukur (T1 = hari terakhir bimtek, T2 = 7 hari sesudahnya, atau data terbaru). Dampak = konversi peserta - pembanding.
- Komponen lain (Pendahuluan, Mingguan, Bulanan, Reviu 50%, progres fisik) hanya bila ada kondisi sebelum per sekolah
  di 1-sebelum/Bn; diukur dari T0 sampai data terbaru.
"""

import csv
import io
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from . import bimtek_lap, lk_baru, paths, todo
from .sheets import cache, col_letter

log = logging.getLogger(__name__)

TAB = "Rekap Bimtek"
POTONG = 40000  # karakter per sel (batas Google 50 ribu)
RE_WAKTU = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})?(\d{2})?(\d{2})?")


class RekapError(ValueError):
    """Pesannya untuk pengguna."""


def folder() -> Path:
    env = os.environ.get("LKM_BIMTEK_DIR", "").strip()
    return Path(env) if env else paths.BACKEND_DIR.parent.parent / "data-bimtek"


# ---------- baca sumber ----------

@dataclass
class Jadwal:
    kode: str
    tag: str
    mulai: date
    selesai: date
    catatan: str = ""


@dataclass
class Potret:
    """Kondisi per sekolah pada satu waktu: status komponen (todo.status) dan progres fisik."""
    sumber: str
    waktu: datetime
    jenis: str                                   # export | cutoff | lk_lama
    status: dict[str, dict[str, str]] = field(default_factory=dict)   # npsn -> {kode: selesai|belum|due|...}
    progres: dict[str, float] = field(default_factory=dict)          # npsn -> 0..100
    tgl50: dict[str, datetime] = field(default_factory=dict)         # npsn -> tanggal kirim 50% (export)
    hari_verif50: dict[str, float] = field(default_factory=dict)
    identitas: dict[str, tuple[str, str, str, str]] = field(default_factory=dict)  # npsn -> (nama, fasil, prov, kab)
    jumlah: dict[str, dict[str, float]] = field(default_factory=dict)  # npsn -> {mg/bl/...: jumlah terkirim/direviu}
    rev50: dict[str, str] = field(default_factory=dict)  # npsn -> setuju | tolak | menunggu
    tunggu50: dict[str, float] = field(default_factory=dict)  # npsn -> hari menunggu reviu 50% (yang masih menunggu)
    lengkap: bool = False  # punya identitas sekolah (export, atau salinan LK setelah cutoff) -> bisa jadi data hari ini


def baca_jadwal(d: Path) -> list[Jadwal]:
    f = d / "0-referensi" / "jadwal_bimtek.csv"
    if not f.exists():
        raise RekapError(f"Jadwal bimtek tidak ada: {f}")
    out = []
    for r in csv.DictReader(io.StringIO(f.read_text(encoding="utf-8-sig")), delimiter=";"):
        try:
            out.append(Jadwal(r["kelompok"].strip(), r["tag"].strip(), date.fromisoformat(r["mulai"].strip()),
                              date.fromisoformat(r["selesai"].strip()), (r.get("catatan") or "").strip()))
        except (KeyError, ValueError) as e:
            raise RekapError(f"Baris jadwal tidak valid: {r} ({e})") from e
    return sorted(out, key=lambda j: j.mulai)


def baca_peserta(d: Path, jadwal: list[Jadwal]) -> tuple[dict[str, str], list[str]]:
    """{npsn: kode kelompok} dari semua daftar di 0-referensi (file lebih baru menang), dan nama filenya."""
    per_tag = {j.tag.casefold(): j.kode for j in jadwal} | {j.kode.casefold(): j.kode for j in jadwal}
    out: dict[str, str] = {}
    dipakai = []
    files = [f for f in (d / "0-referensi").iterdir() if f.suffix.lower() in (".csv", ".xlsx", ".xlsm")
             and f.name != "jadwal_bimtek.csv"]
    for f in sorted(files, key=lambda f: f.stat().st_mtime):
        try:
            _n, _t, peta = bimtek_lap.baca_file(f.read_bytes(), f.name)
        except bimtek_lap.BimtekLapError:
            continue
        dipakai.append(f.name)
        for n, tag in peta.items():
            k = per_tag.get(tag.strip().casefold())
            if k:
                out[n] = k
    if not out:
        raise RekapError("Daftar peserta (kolom NPSN + Tag) tidak ditemukan di 0-referensi.")
    return out, dipakai


HARIAN = "3-harian"  # arsip export dari tiap cutoff (otomatis)


def arsipkan_export(data: bytes, nama_file: str) -> Path | None:
    """Salin file export cutoff ke <folder>/3-harian. Nama dipertahankan bila sudah bertanggal (Export_..._YYYYmmdd_HHMMSS),
    bila tidak diberi cap waktu sekarang supaya urutan waktunya terbaca. None bila folder data bimtek tidak ada."""
    d = folder()
    if not d.exists() or not data:
        return None
    tujuan = d / HARIAN
    tujuan.mkdir(exist_ok=True)
    nama = Path(nama_file or "export.csv").name
    if "export" not in nama.lower() or not waktu_nama(nama):
        stem, ext = Path(nama).stem, Path(nama).suffix or ".csv"
        nama = f"Export_{re.sub(r'[^A-Za-z0-9_-]+', '_', stem)}_{datetime.now():%Y%m%d_%H%M%S}{ext}"
    f = tujuan / nama
    if not (f.exists() and f.stat().st_size == len(data)):
        f.write_bytes(data)
    return f


def baca_hotel(d: Path) -> dict[str, tuple[str, str]]:
    """{npsn: (hotel, region)} dari master_bimtek.csv (kolom Hotel, Region). Kosong bila master belum ada."""
    f = d / "0-referensi" / "master_bimtek.csv"
    if not f.exists():
        return {}
    teks = f.read_text(encoding="utf-8-sig")
    pisah = ";" if teks.split("\n", 1)[0].count(";") >= teks.split("\n", 1)[0].count(",") else ","
    out = {}
    for r in csv.DictReader(io.StringIO(teks), delimiter=pisah):
        n, h = (r.get("NPSN") or "").strip(), " ".join((r.get("Hotel") or "").split())
        if n and h:
            out[n] = (h, (r.get("Region") or "").strip())
    return out


def waktu_nama(nama: str) -> datetime | None:
    m = RE_WAKTU.search(nama)
    if not m:
        return None
    y, mo, dd, hh, mi, ss = (int(x) if x else 0 for x in m.groups())
    try:
        return datetime(y, mo, dd, hh, mi, ss)
    except ValueError:
        return None


def _tgl(v: Any) -> datetime | None:
    t = str(v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


# Laporan berulang: tiap minggu/bulan ada yang baru jatuh tempo, jadi "selesai semua" jarang tercapai. Untuk komponen
# ini sekolah dihitung BERGERAK bila jumlah terkirim/direviu bertambah setelah bimtek (walau belum lengkap).
BERULANG = ("mg", "mg_rev", "bl", "bl_rev")


def _status_dari_nilai(nilai: dict[str, Any]) -> dict[str, str]:
    return {k.kode: todo.status(k.kode, nilai.get(k.kode, "")).status for k in lk_baru.KOMPONEN}


def _jumlah_dari_nilai(nilai: dict[str, Any]) -> dict[str, float]:
    out = {}
    for k in BERULANG:
        st = todo.status(k, nilai.get(k, ""))
        if st.rasio:
            out[k] = st.rasio[0]
    return out


def _progres(v: Any) -> float | None:
    s = todo.status("progres", v)
    return s.persen


def baca_export(f: Path) -> Potret:
    from . import cutoff_baru

    df = cutoff_baru.baca(f.read_bytes(), f.name)
    p = Potret(f.name, waktu_nama(f.name) or datetime.fromtimestamp(f.stat().st_mtime), "export", lengkap=True)
    for n, x in cutoff_baru.olah(df).items():
        nilai = {}
        for judul, v in x.items():
            k = lk_baru.komponen_dari_judul(judul)
            if k:
                nilai[k.kode] = v
        p.status[n] = _status_dari_nilai(nilai)
        p.jumlah[n] = _jumlah_dari_nilai(nilai)
        p.identitas[n] = (x.get("Nama Sekolah", ""), x.get("Fasilitator", ""),
                          str(x.get("Provinsi", "")).replace("Prov. ", ""), x.get("Kab/Kota", ""))
        pr = _progres(nilai.get("progres", ""))
        if pr is not None:
            p.progres[n] = pr
    if "Laporan 50% - Status Reviu" in df.columns:
        for n, v in zip(df["NPSN"], df["Laporan 50% - Status Reviu"]):
            n, v = cutoff_baru.npsn(n), str(v).strip().casefold()
            hasil = ("setuju" if v.startswith(("selesai", "disetujui")) else "tolak" if v.startswith("dikembalikan")
                     else "menunggu" if v.startswith("belum direviu") else "")
            if n and hasil:
                p.rev50[n] = hasil
    if "Tgl Kirim 50%" in df.columns:
        for n, t, h in zip(df["NPSN"], df["Tgl Kirim 50%"], df.get("Hari Verif 50%", [""] * len(df))):
            n = cutoff_baru.npsn(n)
            w = _tgl(t)
            if n and w:
                p.tgl50[n] = w
                try:
                    p.hari_verif50[n] = float(str(h).replace(",", "."))
                except ValueError:
                    pass
    for n, v in p.rev50.items():
        if v == "menunggu" and n in p.tgl50:
            p.tunggu50[n] = float((p.waktu - p.tgl50[n]).days)
    return p


# Nilai Reviu Laporan 50% di LK -> setuju | tolak | menunggu
REV50_LK = {"sudah": "setuju", "belum ttd koor": "setuju", "dikembalikan": "tolak", "belum": "menunggu"}
PREFIKS_LK = "lk_cutoff_"


def simpan_lk_harian(d: Path) -> Path | None:
    """Salin isi LK setelah cutoff terakhir (siapa pun yang menariknya) ke <folder>/3-harian/lk_cutoff_<waktu>.json.
    Waktu = cap waktu file export di Log Tarik. Dilewati bila salinan cutoff itu sudah ada."""
    from . import cutoff_baru

    log_tarik = lk_baru._ss().values_get(f"'{cutoff_baru.TAB_LOG}'!A2:F").get("values", [])
    if not log_tarik:
        return None
    akhir = log_tarik[-1] + [""] * 6
    w = waktu_nama(akhir[2]) or datetime.strptime(akhir[0][:16], "%Y-%m-%d %H:%M")
    tujuan = d / HARIAN
    f = tujuan / f"{PREFIKS_LK}{w:%Y%m%d_%H%M%S}.json"
    if f.exists():
        return f
    sekolah = {}
    for x in lk_baru.baca_semua(refresh=True):
        sekolah[x.npsn] = {"nilai": {k: (v if isinstance(v, (int, float, str)) else str(v)) for k, v in x.nilai.items()},
                           "tunggu": x.tunggu, "nama": x.nama, "fasil": x.fasil, "prov": x.provinsi, "kab": x.kab}
    tujuan.mkdir(exist_ok=True)
    f.write_text(json.dumps({"waktu": w.isoformat(timespec="seconds"), "file": akhir[2], "week": akhir[1],
                             "oleh": akhir[5], "sekolah": sekolah}, ensure_ascii=False), encoding="utf-8")
    return f


def baca_lk_cutoff(f: Path) -> Potret:
    x = json.loads(f.read_text(encoding="utf-8"))
    w = datetime.fromisoformat(x["waktu"])
    p = Potret(f"LK setelah cutoff ({x.get('file', '')})", w, "cutoff", lengkap=True)
    for n, s in x.get("sekolah", {}).items():
        nilai = s.get("nilai", {})
        p.status[n] = _status_dari_nilai(nilai)
        p.jumlah[n] = _jumlah_dari_nilai(nilai)
        p.identitas[n] = (s.get("nama", ""), s.get("fasil", ""), str(s.get("prov", "")).replace("Prov. ", ""), s.get("kab", ""))
        pr = _progres(nilai.get("progres", ""))
        if pr is not None:
            p.progres[n] = pr
        r = REV50_LK.get(str(nilai.get("l50_rev", "")).strip().casefold())
        if r:
            p.rev50[n] = r
            t = s.get("tunggu", {}).get("l50_rev")
            if r == "menunggu" and isinstance(t, (int, float)):
                p.tunggu50[n] = float(t)
    return p


def baca_cutoff_json(f: Path) -> Potret:
    x = json.loads(f.read_text(encoding="utf-8"))
    m = re.search(r"\((\d{1,2})/(\d{1,2})\)", x.get("cutoff", ""))
    w = datetime(2026, int(m.group(2)), int(m.group(1)), 23, 59) if m else datetime.fromtimestamp(f.stat().st_mtime)
    p = Potret(f"{f.name} ({x.get('cutoff', '')})", w, "cutoff")
    for n, s in x.get("sekolah", {}).items():
        p.status[n] = _status_dari_nilai(s.get("nilai", {}))
        p.jumlah[n] = _jumlah_dari_nilai(s.get("nilai", {}))
        pr = _progres(s.get("nilai", {}).get("progres", ""))
        if pr is not None:
            p.progres[n] = pr
    return p


def baca_lk_lama(f: Path) -> Potret:
    """Baseline WEEK 2 LK lama (tarik 2 Nov 07.09): submit & reviu 50% (Ya/Tidak) dan progres fisik baseline."""
    x = json.loads(f.read_text(encoding="utf-8"))
    log_tarik = x.get("log_tarik", [])
    w = next((datetime.fromisoformat(r[0][:19]) for r in log_tarik[1:] if len(r) > 2 and r[1] == "mingguan"
              and r[2] == "2"), datetime(2026, 11, 2, 7, 9))
    p = Potret(f"{f.name} (baseline WEEK 2 LK lama)", w, "lk_lama")
    wk = x.get("WEEK 2", {})
    judul = wk.get("judul", [])

    def i(nama: str) -> int:
        return next(j for j, h in enumerate(judul) if h.strip().casefold() == nama.casefold())

    i_n, i_p, i_s, i_r = i("NPSN"), i("% Progress Fisik Baseline"), i("Status Submit 50% Baseline"), i("Status Reviu 50% Baseline")
    for r in wk.get("baris", []):
        r = r + [""] * (len(judul) - len(r))
        n = re.sub(r"\.0+$", "", r[i_n].strip())
        if not n:
            continue
        sudah = r[i_s].strip().casefold() == "ya"
        reviu = r[i_r].strip().casefold() == "ya"
        # reviu hanya berlaku untuk sekolah yang sudah mengirim 50% ("kosong" = belum ada laporan untuk direviu)
        p.status[n] = {"l50": "selesai" if sudah else "belum",
                       "l50_rev": "selesai" if reviu else "belum" if sudah else "kosong"}
        try:
            p.progres[n] = float(r[i_p].replace("%", "").replace(",", ".").strip())
        except ValueError:
            pass
    return p


def baca_potret(f: Path) -> Potret | None:
    nama = f.name.lower()
    try:
        if nama.endswith((".csv", ".xlsx", ".xls")) and "export" in nama:
            return baca_export(f)
        if nama.endswith(".json") and nama.startswith(PREFIKS_LK):
            return baca_lk_cutoff(f)
        if nama.endswith(".json") and nama.startswith("cutoff"):
            return baca_cutoff_json(f)
        if nama.endswith(".json") and nama.startswith("lk_lama"):
            return baca_lk_lama(f)
    except Exception:
        log.exception("File rekap bimtek tidak terbaca: %s", f)
    return None


# ---------- hitung ----------

def _pct(a: int, b: int) -> float | None:
    return round(a / b * 100, 1) if b else None


def _kurang(a: float | None, b: float | None) -> float | None:
    return round(a - b, 1) if a is not None and b is not None else None


def konversi(belum: set[str], sudah_pada: dict[str, datetime], batas: datetime) -> float | None:
    """Persen dari `belum` yang sudah (tanggal <= batas)."""
    return _pct(sum(1 for n in belum if n in sudah_pada and sudah_pada[n] <= batas), len(belum))


def hitung(d: Path | None = None) -> dict[str, Any]:
    d = d or folder()
    if not d.exists():
        raise RekapError(f"Folder data bimtek tidak ada: {d}")
    jadwal = baca_jadwal(d)
    peserta, file_peserta = baca_peserta(d, jadwal)
    try:
        simpan_lk_harian(d)
    except Exception:  # noqa: BLE001 - tanpa salinan LK, rekap tetap jalan dari file yang ada
        log.warning("Salinan LK setelah cutoff gagal dibuat", exc_info=True)

    # semua potret (export di mana pun di folder; cutoff/LK lama per kelompok)
    potret_semua: list[tuple[str | None, Potret]] = []
    sudah: dict[tuple[str, int], Potret] = {}  # file kembar (mis. export yang sama di 1-sebelum/B4 dan 2-terbaru) dibaca sekali
    for f in sorted(d.rglob("*")):
        if not f.is_file() or "0-referensi" in f.parts:
            continue
        kunci = (f.name, f.stat().st_size)
        p = sudah.get(kunci) or baca_potret(f)
        if p:
            sudah[kunci] = p
            grup = next((x for x in f.parts if re.fullmatch(r"B\d+", x)), None)
            potret_semua.append((grup, p))
    export = list({id(p): p for _g, p in potret_semua if p.jenis == "export"}.values())
    if not export:
        raise RekapError("Belum ada file export di folder (2-terbaru/).")
    ex = max(export, key=lambda p: p.waktu)          # export terbaru: tanggal kirim & hari verif 50%
    lengkap = list({id(p): p for _g, p in potret_semua if p.lengkap}.values())
    terbaru = max(lengkap, key=lambda p: (p.waktu, p.jenis == "export"))   # data hari ini (bisa salinan LK)
    sekarang = terbaru.waktu

    # tanggal kirim 50% paling awal dari semua export
    tgl50: dict[str, datetime] = {}
    for p in export:
        for n, w in p.tgl50.items():
            if n not in tgl50 or w < tgl50[n]:
                tgl50[n] = w
    # sekolah yang mengirim setelah export terakhir: pakai waktu salinan LK pertama yang mencatatnya sudah kirim
    for p in sorted((p for p in lengkap if p.jenis != "export" and p.waktu > ex.waktu), key=lambda p: p.waktu):
        for n, st in p.status.items():
            if st.get("l50") == "selesai" and n not in tgl50:
                tgl50[n] = p.waktu
    st_akhir = terbaru.status
    try:
        mundur = lk_baru.npsn_mundur(refresh=True)
    except Exception:  # noqa: BLE001
        mundur = frozenset()
    sekolah = set(st_akhir) - mundur                     # sekolah di data terbaru, tanpa yang mengundurkan diri
    wajib50 = {n for n in sekolah if st_akhir[n].get("l50") in ("selesai", "belum")}

    def anggota(kode: str) -> set[str]:
        return {n for n, k in peserta.items() if k == kode and n in sekolah}

    pic = _peta_pic()
    hotel = baca_hotel(d)
    hasil = []
    mulai_kode = {j.kode: j.mulai for j in jadwal}

    def rev50_pada(n: str, w: datetime) -> str:
        """Reviu Lap. 50% pada waktu w, direkonstruksi dari tanggal: selesai bila di data terbaru sudah selesai (sama dengan
        definisi aplikasi) dan tanggal kirim terakhir + Hari Verif 50% <= w. Belum kirim di w -> due (reviu belum berlaku)."""
        if not (n in tgl50 and tgl50[n] <= w):
            return "due"
        akhir_kirim, h = ex.tgl50.get(n), ex.hari_verif50.get(n)
        if (ex.status.get(n, {}).get("l50_rev") == "selesai" and akhir_kirim and akhir_kirim <= w and h is not None
                and akhir_kirim + timedelta(days=h) <= w):
            return "selesai"
        return "belum"
    for j in jadwal:
        ang = anggota(j.kode)
        # pembanding: belum dibimtek sampai bimtek ini selesai
        non = {n for n in sekolah if n not in peserta or mulai_kode.get(peserta[n], date.max) > j.selesai}
        t0 = datetime.combine(j.mulai, datetime.min.time()) - timedelta(seconds=1)
        t1 = datetime.combine(j.selesai, datetime.max.time().replace(microsecond=0))
        t2 = t1 + timedelta(days=7)
        mulai_sudah = sekarang.date() >= j.mulai
        tahap = "akan datang" if not mulai_sudah else "berjalan" if sekarang <= t1 else "selesai"
        out: dict[str, Any] = {
            "kode": j.kode, "tag": j.tag, "mulai": j.mulai.isoformat(), "selesai": j.selesai.isoformat(),
            "catatan": j.catatan, "tahap": tahap, "sekolah": len(ang), "t0": t0.isoformat(timespec="minutes"),
            "t1": t1.isoformat(timespec="minutes"), "t2": t2.isoformat(timespec="minutes"),
            "t2_tersedia": sekarang >= t2,
            "peserta_daftar": sum(1 for k in peserta.values() if k == j.kode),
        }
        # hotel tempat bimtek (dari master): semua peserta di daftar, termasuk yang tidak ada di export
        isi = [hotel[n] for n, k in peserta.items() if k == j.kode and n in hotel]
        per_hotel = Counter(h for h, _rg in isi)
        region = {h: Counter(rg for h2, rg in isi if h2 == h).most_common(1)[0][0] for h in per_hotel}  # region terbanyak
        out["hotel"] = [{"nama": h, "region": region[h], "sekolah": c}
                        for h, c in sorted(per_hotel.items(), key=lambda x: (-x[1], x[0]))]
        # --- Laporan 50% dari tanggal kirim ---
        a50, b50 = ang & wajib50, non & wajib50
        belum_a = {n for n in a50 if not (n in tgl50 and tgl50[n] <= t0)}
        belum_b = {n for n in b50 if not (n in tgl50 and tgl50[n] <= t0)}
        titik = {"t1": t1, "t2": t2, "sekarang": sekarang}
        l50: dict[str, Any] = {
            "wajib": len(a50), "wajib_banding": len(b50),
            "awal": _pct(len(a50) - len(belum_a), len(a50)), "awal_banding": _pct(len(b50) - len(belum_b), len(b50)),
            "belum_awal": len(belum_a), "belum_awal_banding": len(belum_b),
            "n_awal": len(a50) - len(belum_a),  # jumlah sekolah yang sudah kirim (angka riil di balik persen)
        }
        for nama, w in titik.items():
            if w > sekarang and nama != "sekarang":
                l50[nama] = None
                continue
            w = min(w, sekarang)
            ka, kb = konversi(belum_a, tgl50, w), konversi(belum_b, tgl50, w)
            na = sum(1 for n in a50 if n in tgl50 and tgl50[n] <= w)
            nb = sum(1 for n in b50 if n in tgl50 and tgl50[n] <= w)
            l50[nama] = {"pct": _pct(na, len(a50)), "pct_banding": _pct(nb, len(b50)), "n": na, "n_banding": nb,
                         "konversi": ka, "konversi_banding": kb, "dampak": _kurang(ka, kb)}
        # kecepatan verifikasi untuk kiriman sejak bimtek mulai (export terbaru)
        hv = lambda grup: [ex.hari_verif50[n] for n in grup if n in ex.hari_verif50  # noqa: E731
                           and n in ex.tgl50 and ex.tgl50[n] > t0]
        va, vb = hv(ang), hv(non)
        l50["verif_median"] = median(va) if va else None
        l50["verif_median_banding"] = median(vb) if vb else None
        out["l50"] = l50

        # --- semua komponen: sebelum (T0) -> data terbaru, peserta vs non-peserta ---
        awal = awal_potret(potret_semua, j.kode, t0)
        if awal:
            out["awal"] = {"sumber": awal.sumber, "waktu": awal.waktu.isoformat(timespec="minutes"), "jenis": awal.jenis}

        def st_awal(n: str, kode: str) -> str | None:
            if kode == "l50":  # dari tanggal kirim: tersedia untuk semua kelompok
                if n in tgl50 and tgl50[n] <= t0:
                    return "selesai"
                return "belum" if n in wajib50 else "due"
            if kode == "l50_rev":
                return rev50_pada(n, t0)
            if not awal or n not in awal.status or kode not in awal.status[n]:
                return None
            return awal.status[n][kode]

        def st_akhir_(n: str, kode: str) -> str | None:
            return st_akhir.get(n, {}).get(kode)

        def bergerak(n: str, kode: str) -> bool:
            """Dari belum di T0: selesai di data terbaru, atau (laporan berulang) jumlah terkirim/direviu bertambah."""
            if st_akhir_(n, kode) == "selesai":
                return True
            if kode in BERULANG and awal:
                a, z = awal.jumlah.get(n, {}).get(kode), terbaru.jumlah.get(n, {}).get(kode)
                return a is not None and z is not None and z > a
            return False

        komp, cap = [], {"awal_s": 0, "awal_d": 0, "akhir_s": 0, "awal_s_b": 0, "awal_d_b": 0, "akhir_s_b": 0}
        for kode in KOMP_URUT:
            label = LABEL_KOMP[kode]
            ada = any(st_awal(n, kode) is not None for n in ang)
            if not ada:
                komp.append({"kode": kode, "label": label, "ada": False})
                continue
            r: dict[str, Any] = {"kode": kode, "label": label, "ada": True}
            for akhiran, grup in (("", ang), ("_banding", non)):
                due = [n for n in grup if st_awal(n, kode) in ("selesai", "belum")]
                s_awal = sum(1 for n in due if st_awal(n, kode) == "selesai")
                s_akhir = sum(1 for n in due if st_akhir_(n, kode) == "selesai")
                belum = [n for n in due if st_awal(n, kode) == "belum"]
                jadi = sum(1 for n in belum if bergerak(n, kode))
                r |= {f"due{akhiran}": len(due), f"awal_pct{akhiran}": _pct(s_awal, len(due)),
                      f"akhir_pct{akhiran}": _pct(s_akhir, len(due)), f"belum_awal{akhiran}": len(belum),
                      f"jadi_selesai{akhiran}": jadi, f"konversi{akhiran}": _pct(jadi, len(belum))}
                k_ = "" if not akhiran else "_b"
                cap[f"awal_s{k_}"] += s_awal
                cap[f"awal_d{k_}"] += len(due)
                cap[f"akhir_s{k_}"] += s_akhir
            r["dampak"] = _kurang(r["konversi"], r["konversi_banding"])
            komp.append(r)
        out["komponen"] = komp
        out["capaian"] = {
            "awal": _pct(cap["awal_s"], cap["awal_d"]), "akhir": _pct(cap["akhir_s"], cap["awal_d"]),
            "awal_banding": _pct(cap["awal_s_b"], cap["awal_d_b"]), "akhir_banding": _pct(cap["akhir_s_b"], cap["awal_d_b"]),
            "komponen": [x["kode"] for x in komp if x.get("ada")],
        }
        c = out["capaian"]
        c["naik"] = _kurang(c["akhir"], c["awal"])
        c["naik_banding"] = _kurang(c["akhir_banding"], c["awal_banding"])
        if awal:
            pa = [terbaru.progres[n] - awal.progres[n] for n in ang if n in awal.progres and n in terbaru.progres]
            pb = [terbaru.progres[n] - awal.progres[n] for n in non if n in awal.progres and n in terbaru.progres]
            if pa:
                ra = round(sum(pa) / len(pa), 1)
                rb = round(sum(pb) / len(pb), 1) if pb else None
                out["progres"] = {"naik": ra, "naik_banding": rb, "dampak": _kurang(ra, rb),
                                  "naik5": _pct(sum(1 for x in pa if x >= 5), len(pa)),
                                  "naik5_banding": _pct(sum(1 for x in pb if x >= 5), len(pb)), "n": len(pa)}
        akhir1 = akhir_potret(potret_semua, t1) if sekarang >= t1 else None
        if akhir1:
            out["akhir1"] = {"sumber": akhir1.sumber, "waktu": akhir1.waktu.isoformat(timespec="minutes"), "jenis": akhir1.jenis}

        def st_t1(n: str, kode: str) -> str | None:
            """Status di hari terakhir bimtek. Lap. 50% dari tanggal kirim; komponen lain dari potret akhir1."""
            if sekarang < t1:
                return None
            if kode == "l50":
                if n in tgl50 and tgl50[n] <= t1:
                    return "selesai"
                return "belum" if n in wajib50 else "due"
            if kode == "l50_rev" and not (akhir1 and n in akhir1.status and "l50_rev" in akhir1.status[n]):
                return rev50_pada(n, t1)
            if not akhir1 or n not in akhir1.status:
                return None
            return akhir1.status[n].get(kode)

        out["sekolah_baris"] = _baris_sekolah(ang, wajib50, tgl50, t0, t1, terbaru, awal, pic, st_awal, bergerak,
                                              hotel, st_t1, sekarang)
        hasil.append(out)

    # --- kurva harian % kirim 50% (sekolah wajib 50%) ---
    awal_kurva = min(j.mulai for j in jadwal) - timedelta(days=14)
    hari = [awal_kurva + timedelta(days=i) for i in range((sekarang.date() - awal_kurva).days + 1)]
    grup = {j.kode: anggota(j.kode) & wajib50 for j in jadwal}
    grup = {k: v for k, v in grup.items() if v}
    hari_kirim = {k: Counter(tgl50[n].date() for n in v if n in tgl50) for k, v in grup.items()}
    seri = []
    for k, v in grup.items():
        sebelum = sum(1 for n in v if n in tgl50 and tgl50[n].date() < awal_kurva)
        nilai, jalan = [], sebelum
        for h in hari:
            jalan += hari_kirim[k].get(h, 0)
            nilai.append(_pct(jalan, len(v)))
        seri.append({"kode": k, "sekolah": len(v), "nilai": nilai})

    return {
        "dibuat": datetime.now().isoformat(timespec="minutes"),
        "data_terbaru": {"sumber": terbaru.sumber, "waktu": sekarang.isoformat(timespec="minutes")},
        "file_peserta": file_peserta,
        "peserta": dict(Counter(peserta[n] for n in peserta if n in sekolah)),
        "sekolah_total": len(sekolah), "non_peserta": len({n for n in sekolah if n not in peserta}), "wajib50": len(wajib50),
        "sumber_export": sorted({p.sumber for p in export}),
        "kelompok": hasil,
        "kurva": {"tanggal": [h.isoformat() for h in hari], "seri": seri},
        "kolom_sekolah": KOLOM_SEKOLAH, "komponen_urut": KOMP_URUT,
    }


KOLOM_SEKOLAH = ["npsn", "nama", "pic", "fasil", "prov", "kab", "tgl50", "kategori", "progres_awal", "progres",
                 "verif50", "awal_kode", "akhir_kode", "hotel", "rev50", "tunggu50", "t1_kode", "koor", "ptn", "angkatan"]
# t1_kode = status per komponen di hari terakhir bimtek ("-" bila tidak ada potret); rev50 = setuju|tolak|menunggu;
# tunggu50 = hari sejak kiriman 50% terakhir bila masih menunggu reviu
# urutan komponen di awal_kode / akhir_kode: satu huruf per komponen
KOMP_URUT = ["lp", "lp_rev", "mg", "mg_rev", "bl", "bl_rev", "l50", "l50_rev", "l100"]
LABEL_KOMP = {"lp": "Lap. Pendahuluan", "lp_rev": "Reviu Lap. Pendahuluan", "mg": "Lap. Mingguan",
              "mg_rev": "Reviu Lap. Mingguan", "bl": "Lap. Bulanan", "bl_rev": "Reviu Lap. Bulanan", "l50": "Lap. 50%",
              "l50_rev": "Reviu Lap. 50%", "l100": "Lap. 100%"}
HURUF = {"selesai": "S", "belum": "B"}  # lainnya (belum jatuh tempo, belum ada laporan) = D; tanpa data = -
# akhir_kode "P" = masih belum lengkap tapi bergerak (laporan berulang: ada kiriman/reviu baru setelah bimtek)


def _peta_pic() -> dict[str, tuple[str, str, str, str]]:
    """NPSN -> (PIC, koordinator, PTN, angkatan) dari LK (export tidak memuat PIC). Kosong bila LK tidak terbaca."""
    try:
        return {s.npsn: (s.petugas, s.koor, s.ptn, s.angkatan) for s in lk_baru.baca_semua()}
    except Exception:
        log.warning("PIC untuk rekap bimtek tidak terbaca dari LK", exc_info=True)
        return {}


def awal_potret(potret_semua: list[tuple[str | None, "Potret"]], kode: str, t0: datetime) -> "Potret | None":
    # hanya kondisi SEBELUM bimtek (toleransi 12 jam untuk export pagi hari pertama); file sesudahnya tidak dipakai
    # dari folder 1-sebelum/<kode> atau arsip umum (3-harian, 2-terbaru); file di folder bimtek lain tidak dipakai
    kandidat = [p for g, p in potret_semua if g in (kode, None) and p.waktu <= t0 + timedelta(hours=12)]
    if not kandidat:
        return None
    urut = {"export": 0, "cutoff": 1, "lk_lama": 2}
    # yang paling dekat ke T0 (hari yang sama), lalu jenis export > cutoff > LK lama
    return sorted(kandidat, key=lambda p: (-p.waktu.date().toordinal(), urut[p.jenis], -p.waktu.timestamp()))[0]


def akhir_potret(potret_semua: list[tuple[str | None, "Potret"]], t1: datetime) -> "Potret | None":
    """Kondisi di hari terakhir bimtek: export/cutoff paling awal antara akhir hari terakhir dan 2 hari sesudahnya."""
    kandidat = [p for _g, p in potret_semua if p.jenis in ("export", "cutoff") and t1 - timedelta(hours=6) <= p.waktu
                <= t1 + timedelta(days=2)]
    return min(kandidat, key=lambda p: p.waktu) if kandidat else None


def kategori50(n: str, wajib: set[str], tgl50: dict[str, datetime], t0: datetime, t1: datetime) -> str:
    """sebelum | saat | sesudah (kirim 50% relatif terhadap bimtek) | belum (wajib, belum kirim) | belum_due."""
    if n in tgl50:
        w = tgl50[n]
        return "sebelum" if w <= t0 else "saat" if w <= t1 else "sesudah"
    return "belum" if n in wajib else "belum_due"


def _kode(st: str | None) -> str:
    return "-" if st is None or st == "tanpa_data" else HURUF.get(st, "D")


def _baris_sekolah(ang: set[str], wajib: set[str], tgl50: dict[str, datetime], t0: datetime, t1: datetime,
                   terbaru: "Potret", awal: "Potret | None", pic: dict[str, tuple[str, str, str, str]], st_awal, bergerak,
                   hotel: dict[str, tuple[str, str]], st_t1, sekarang: datetime) -> list[list[Any]]:
    out = []
    for n in sorted(ang):
        nama, fasil, prov, kab = terbaru.identitas.get(n, ("", "", "", ""))
        st = terbaru.status.get(n, {})
        pa = awal.progres.get(n) if awal else None
        pn = terbaru.progres.get(n)
        p_, koor, ptn, angkatan = pic.get(n, ("", "", "", ""))
        out.append([n, nama, p_, fasil, prov, kab,
                    tgl50[n].isoformat(timespec="minutes") if n in tgl50 else "", kategori50(n, wajib, tgl50, t0, t1),
                    round(pa, 1) if pa is not None else None, round(pn, 1) if pn is not None else None,
                    terbaru.hari_verif50.get(n),
                    "".join(_kode(st_awal(n, k)) for k in KOMP_URUT),
                    "".join("P" if st_awal(n, k) == "belum" and st.get(k) != "selesai" and bergerak(n, k) else _kode(st.get(k))
                            for k in KOMP_URUT),
                    hotel.get(n, ("", ""))[0], terbaru.rev50.get(n, ""),
                    terbaru.tunggu50.get(n) if terbaru.rev50.get(n) == "menunggu" else None,
                    "".join(_kode(st_t1(n, k)) for k in KOMP_URUT), koor, ptn, angkatan])
    return out


# ---------- simpan & baca dari LK ----------

def simpan(data: dict[str, Any]) -> int:
    """Tulis hasil ke tab tersembunyi 'Rekap Bimtek' (JSON dipotong per sel di kolom A)."""
    teks = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    potong = [teks[i:i + POTONG] for i in range(0, len(teks), POTONG)]
    ss = lk_baru._ss()
    if TAB not in [w.title for w in ss.worksheets()]:
        w = ss.add_worksheet(TAB, rows=max(50, len(potong) + 10), cols=2)
        ss.batch_update({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": w.id, "hidden": True}, "fields": "hidden"}}]})
    w = ss.worksheet(TAB)
    if w.row_count < len(potong) + 2:
        w.add_rows(len(potong) + 10 - w.row_count)
    ss.values_batch_clear(body={"ranges": [f"'{TAB}'!A1:B"]})
    ss.values_update(f"'{TAB}'!A1", params={"valueInputOption": "RAW"},
                     body={"values": [["rekap_bimtek_v1", data["dibuat"]]] + [[x] for x in potong]})
    cache.clear()
    return len(teks)


def baca() -> dict[str, Any] | None:
    def load() -> dict[str, Any] | None:
        try:
            v = lk_baru._ss().values_get(f"'{TAB}'!A1:{col_letter(1)}").get("values", [])
        except Exception:
            return None
        if not v or not v[0] or v[0][0] != "rekap_bimtek_v1":
            return None
        try:
            return json.loads("".join(r[0] for r in v[1:] if r))
        except ValueError:
            log.exception("Rekap Bimtek di LK rusak")
            return None

    return cache.get("lk2_rekap_bimtek", 600, load)


def hitung_dan_simpan() -> dict[str, Any]:
    data = hitung()
    simpan(data)
    return data


# ---------- hitung di latar (beberapa menit untuk belasan ribu sekolah per export) ----------

_status: dict[str, Any] = {"jalan": False, "mulai": "", "error": "", "selesai": ""}


def status() -> dict[str, Any]:
    return dict(_status)


def mulai_hitung() -> None:
    import threading

    if _status["jalan"]:
        return

    def run() -> None:
        try:
            hitung_dan_simpan()
            _status.update(error="", selesai=datetime.now().isoformat(timespec="minutes"))
        except RekapError as e:
            _status["error"] = str(e)
        except Exception as e:
            log.exception("Rekap bimtek gagal")
            _status["error"] = f"Rekap gagal: {e}"
        finally:
            _status["jalan"] = False

    _status.update(jalan=True, mulai=datetime.now().isoformat(timespec="minutes"), error="")
    threading.Thread(target=run, name="rekap-bimtek", daemon=True).start()


# ---------- hitung otomatis bila ada cutoff baru di LK (cutoff bisa ditarik dari laptop lain) ----------

_otomatis_untuk: datetime | None = None


def cutoff_terakhir() -> datetime | None:
    """Waktu data cutoff terakhir di LK (cap waktu file export di Log Tarik). Disimpan 5 menit."""
    from . import cutoff_baru

    def load() -> str:
        r = lk_baru._ss().values_get(f"'{cutoff_baru.TAB_LOG}'!A2:C").get("values", [])
        if not r:
            return ""
        akhir = r[-1] + ["", "", ""]
        w = waktu_nama(akhir[2]) or datetime.strptime(akhir[0][:16], "%Y-%m-%d %H:%M")
        return w.isoformat(timespec="seconds")

    try:
        v = cache.get("lk2_cutoff_terakhir", 300, load)
    except Exception:  # noqa: BLE001
        return None
    return datetime.fromisoformat(v) if v else None


def hitung_bila_ada_cutoff_baru(rekap: dict[str, Any] | None) -> bool:
    """Mulai hitung ulang di latar bila LK punya cutoff yang lebih baru dari data rekap. Sekali per cutoff."""
    global _otomatis_untuk
    w = cutoff_terakhir()
    if not w or _status["jalan"] or _otomatis_untuk == w or not folder().exists():
        return False
    data = datetime.fromisoformat(rekap["data_terbaru"]["waktu"]) if rekap else None
    if data and data >= w - timedelta(minutes=1):
        return False
    _otomatis_untuk = w
    mulai_hitung()
    return True


def tag_dimulai(hari: date | None = None) -> set[str] | None:
    """Tag (casefold) bimtek yang tanggal mulainya sudah lewat atau hari ini. None bila rekap belum ada/tidak terbaca."""
    try:
        r = baca()
    except Exception:  # noqa: BLE001
        log.warning("Rekap bimtek tidak terbaca untuk saringan bimtek", exc_info=True)
        return None
    if not r:
        return None
    h = (hari or datetime.now().date()).isoformat()
    return {str(k.get("tag", "")).casefold() for k in r.get("kelompok", []) if str(k.get("mulai", "9999")) <= h}


def bimtek_aktif(hari: date | None = None) -> dict[str, dict[str, Any]]:
    """{tag casefold: {tag, kode, mulai, selesai, hotel: {npsn: hotel}}} untuk bimtek yang berlangsung hari ini (kalender).
    Dibaca dari rekap di LK; kosong bila rekap belum ada atau tidak terbaca."""
    try:
        r = baca()
    except Exception:  # noqa: BLE001
        log.warning("Rekap bimtek tidak terbaca untuk tanda bimtek berlangsung", exc_info=True)
        return {}
    if not r:
        return {}
    h = hari or datetime.now().date()
    kol = r.get("kolom_sekolah", [])
    i_n, i_h = (kol.index("npsn") if "npsn" in kol else -1), (kol.index("hotel") if "hotel" in kol else -1)
    out = {}
    for k in r.get("kelompok", []):
        try:
            mulai, selesai = date.fromisoformat(k["mulai"]), date.fromisoformat(k["selesai"])
        except (KeyError, ValueError):
            continue
        if not (mulai <= h <= selesai):
            continue
        hotel = ({str(x[i_n]): str(x[i_h]) for x in k.get("sekolah_baris", []) if x[i_h]} if i_n >= 0 and i_h >= 0 else {})
        out[str(k.get("tag", "")).casefold()] = {"tag": k.get("tag", ""), "kode": k["kode"], "mulai": k["mulai"],
                                                 "selesai": k["selesai"], "hotel": hotel}
    return out

