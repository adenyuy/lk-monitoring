"""Fasil binaan, kelompok (cluster) komunikasi, kode Log Komunikasi otomatis dari WhatsApp, dan tag fasil.

Kelompok fasil hari ini, urut dari yang paling perlu ditindak:
  perlu_telepon   : centang satu / nomor tidak ada WA, atau sudah lebih dari sekali hanya dibaca tanpa ditelepon
  dibaca          : chat hari ini hanya dibaca
  menunggu        : terhubung tapi masih menunggu konfirmasi / respon lambat
  belum           : belum ada catatan komunikasi hari ini
  terhubung       : hari ini terhubung (WhatsApp respon baik atau telepon)
  beres           : semua sekolah binaannya tanpa to-do
Tanda tambahan: `tanpa_progres` = sering terhubung minggu ini tapi tidak ada komponen yang bertambah selesai
sejak cutoff sebelumnya (fasil yang menjawab "ok ok" saja).
"""

import json
import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from . import db, lk_baru, schedule, todo
from .lk_baru import KODE_KOMUNIKASI, Sekolah
from .sheets import normalize_petugas

log = logging.getLogger(__name__)

KELOMPOK = (
    ("perlu_telepon", "Perlu ditelepon", "Minggu ini chat minimal 2 kali hanya dibaca tanpa balasan, atau nomor tidak ada WA"),
    ("dibaca", "Dibaca, belum membalas", "Chat hari ini sudah dibaca tapi belum dibalas"),
    ("terkirim", "Terkirim, belum dibaca", "Chat hari ini terkirim tapi belum dibaca (centang)"),
    ("menunggu", "Menunggu konfirmasi", "Sudah terhubung, jawabannya belum tuntas atau lambat"),
    ("belum", "Belum dihubungi hari ini", "Belum ada catatan di Log Komunikasi hari ini"),
    ("terhubung", "Terhubung hari ini", "Respon baik lewat WhatsApp atau sudah ditelepon"),
    ("beres", "Semua hijau", "Semua sekolah binaannya tanpa to-do"),
)
# Kolom papan LK: di komponen mana sekolah binaan seorang fasil sedang tertahan (dari to-do).
POSISI = (
    ("lp", "Lap. Pendahuluan belum dikirim", ("lp",)),
    ("lp_rev", "Reviu Lap. Pendahuluan", ("lp_rev",)),
    ("mg", "Lap. Mingguan", ("mg", "mg_rev")),
    ("bulanan", "Lap. Bulanan, BKU & BPP", ("paket_bulanan", "bl_rev")),
    ("progres", "Progres fisik", ("progres",)),
    ("l50", "Laporan 50%", ("l50", "l50_rev")),
    ("l100", "Laporan 100%", ("l100", "l100_rev")),
)
_POSISI_DARI = {t: k for k, _, ts in POSISI for t in ts}


def posisi_todo(kode: str) -> str:
    """Kolom papan LK untuk satu kode to-do ('' bila tidak masuk papan)."""
    return _POSISI_DARI.get(kode, "")

TERHUBUNG = {"T", "TP"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS fasil_tag (
    kunci  TEXT PRIMARY KEY,
    tag    TEXT NOT NULL DEFAULT '[]',
    waktu  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kom_auto (
    tanggal TEXT NOT NULL,
    npsn    TEXT NOT NULL,
    kode    TEXT NOT NULL,
    PRIMARY KEY (tanggal, npsn)
);
CREATE TABLE IF NOT EXISTS lk_jejak (
    cutoff  TEXT NOT NULL,
    npsn    TEXT NOT NULL,
    selesai INTEGER NOT NULL,
    PRIMARY KEY (cutoff, npsn)
);
"""
_siap = False
_lock = threading.Lock()


def _db() -> None:
    global _siap
    if not _siap:
        with db.tx() as c:
            c.executescript(SCHEMA)
        _siap = True


# ---------- fasil binaan ----------

@dataclass
class Fasil:
    kunci: str               # nomor 62… atau 'nama:<nama>' bila nomor kosong
    nama: str
    nomor: str
    nomor_lain: list[str]
    koor: str
    hp_koor: str
    ptn: str
    sekolah: list[Sekolah] = field(default_factory=list)


def kunci_fasil(s: Sekolah) -> str:
    n = s.nomor_fasil()
    return n[0] if n else "nama:" + normalize_petugas(s.fasil or "tanpa fasil")


def kelompokkan(sekolah: list[Sekolah]) -> dict[str, Fasil]:
    out: dict[str, Fasil] = {}
    for s in sekolah:
        k = kunci_fasil(s)
        f = out.get(k)
        if not f:
            n = s.nomor_fasil()
            f = out[k] = Fasil(k, s.fasil or "(tanpa nama fasil)", n[0] if n else "", n[1:], s.koor,
                               s.hp_koor, s.ptn)
        f.sekolah.append(s)
    return out


def petugas_saya() -> str:
    return db.get_setting("nama_petugas") or ""


def sekolah_saya(refresh: bool = False) -> list[Sekolah]:
    return lk_baru.baca_petugas(petugas_saya(), refresh=refresh)


def fasil_saya(refresh: bool = False) -> dict[str, Fasil]:
    return kelompokkan(sekolah_saya(refresh))


# ---------- jejak progres antar-cutoff ----------

def label_cutoff() -> str:
    """Label cutoff terakhir dari judul Log Progres, mis. 'Cutoff 2 (06/11)'. Kosong bila belum ada."""
    from .sheets import cache

    def load() -> str:
        try:
            r = lk_baru._ss().values_get(f"'{lk_baru.TAB_LOG_PROGRES}'!A2:Z2").get("values", [[]])[0]
        except Exception:
            return ""
        isi = [x for x in r if str(x).startswith("Cutoff") and "(" in str(x)]
        return str(isi[-1]) if isi else ""

    return cache.get("lk2_cutoff_label", 600, load)


def jejak(sekolah: list[Sekolah], rencana: dict[str, todo.Rencana]) -> dict[str, int | None]:
    """{npsn: tambahan komponen selesai sejak cutoff sebelumnya} (None bila belum ada pembanding).
    Jumlah komponen selesai disimpan per cutoff di laptop ini."""
    _db()
    lbl = label_cutoff()
    if not lbl:
        return {}
    sekarang = {s.npsn: sum(1 for x in rencana[s.npsn].status.values() if x.status == "selesai") for s in sekolah}
    with db.tx() as c:
        c.executemany("INSERT OR IGNORE INTO lk_jejak(cutoff, npsn, selesai) VALUES(?,?,?)",
                      [(lbl, k, v) for k, v in sekarang.items()])
    sebelum = db.query("SELECT cutoff FROM lk_jejak WHERE cutoff != ? GROUP BY cutoff ORDER BY MAX(rowid) DESC "
                       "LIMIT 1", (lbl,))
    if not sebelum:
        return {k: None for k in sekarang}
    lama = {r["npsn"]: r["selesai"] for r in db.query("SELECT npsn, selesai FROM lk_jejak WHERE cutoff = ?",
                                                      (sebelum[0]["cutoff"],))}
    return {k: (v - lama[k]) if k in lama else None for k, v in sekarang.items()}


# ---------- tag ----------

def tag_semua() -> dict[str, list[str]]:
    _db()
    out = {}
    for r in db.query("SELECT kunci, tag FROM fasil_tag"):
        try:
            out[r["kunci"]] = [str(x) for x in json.loads(r["tag"])]
        except ValueError:
            continue
    return out


def set_tag(kunci: str, tag: list[str]) -> list[str]:
    _db()
    bersih = list(dict.fromkeys(" ".join(t.split())[:30] for t in tag if t.strip()))[:6]
    with db.tx() as c:
        c.execute("INSERT INTO fasil_tag(kunci, tag, waktu) VALUES(?,?,?) ON CONFLICT(kunci) DO UPDATE SET "
                  "tag = excluded.tag, waktu = excluded.waktu",
                  (kunci, json.dumps(bersih), schedule.now().isoformat(timespec="seconds")))
    return bersih


# ---------- kelompok ----------

def kode_fasil(f: Fasil, logkom: lk_baru.LogKom) -> dict[str, str]:
    """{tanggal: kode} untuk fasil: kode paling sering di antara sekolah binaannya per hari."""
    per: dict[str, Counter] = {}
    for s in f.sekolah:
        for d, k in logkom.kode.get(s.npsn, {}).items():
            per.setdefault(d, Counter())[k] += 1
    return {d: c.most_common(1)[0][0] for d, c in per.items()}


def minggu_ini(hari: date) -> list[str]:
    senin = hari - timedelta(days=hari.weekday())
    return [(senin + timedelta(days=i)).isoformat() for i in range(6)]


def tentukan(kode: dict[str, str], hari: str, semua_hijau: bool, minggu: list[str]) -> str:
    if semua_hijau:
        return "beres"
    k = kode.get(hari, "")
    lalu = [kode[d] for d in minggu if d <= hari and d in kode]
    if not k:
        return "belum"
    if k == "N":
        return "perlu_telepon"  # nomor tidak ada WhatsApp: hanya bisa ditelepon
    if k == "C":
        return "terkirim"
    if k == "R":
        # perlu ditelepon hanya bila minggu ini minimal 2 kali hanya dibaca dan belum pernah membalas/ditelepon
        membalas = any(x in TERHUBUNG or x in ("T1", "T2") for x in lalu)
        return "perlu_telepon" if lalu.count("R") >= 2 and not membalas else "dibaca"
    if k in ("T1", "T2"):
        return "menunggu"
    return "terhubung"


# ---------- kode otomatis dari WhatsApp ----------

def kode_wa_hari_ini(nomor: str, hari: str) -> str:
    """Kode komunikasi hari ini dari catatan kirim + status chat lokal; '' bila belum ada kontak hari ini."""
    if not nomor:
        return ""
    kirim = db.query("SELECT status, keterangan, waktu FROM sends WHERE coba = 0 AND nomor = ? "
                     "AND substr(waktu, 1, 10) = ? ORDER BY waktu", (nomor, hari))
    balas = db.query("SELECT waktu FROM aktivitas WHERE nomor = ? AND jenis = 'balas' AND substr(waktu, 1, 10) = ?",
                     (nomor, hari))
    chat = db.query_one("SELECT status, waktu_balasan, dicek FROM chat_status WHERE nomor = ?", (nomor,))
    terkirim = any(x["status"] == "terkirim" for x in kirim) or bool(balas)
    if not terkirim:
        if any("tidak terdaftar" in (x["keterangan"] or "").lower() for x in kirim):
            return "N"
        return ""
    if chat:
        if chat["status"] == "dibalas" and (chat["waktu_balasan"] or "")[:10] == hari:
            return "T"
        if (chat["dicek"] or "")[:10] == hari:
            return "R" if chat["status"] in ("dibaca", "dibalas") else "C"
    # chat belum dicek sejak dikirim: belum tahu dibaca/dibalas, jangan tebak "C"
    return ""


def sinkron_wa(hari: str | None = None) -> int:
    """Tulis kode Log Komunikasi hari ini dari WhatsApp (hanya bila WA otomatis menyala).
    Sel yang diisi petugas sendiri tidak ditimpa; sel yang dulu diisi aplikasi boleh diperbarui."""
    if not wa_otomatis():
        return 0
    _db()
    hari = hari or schedule.now().date().isoformat()
    with _lock:
        try:
            fasil = fasil_saya()
            logkom = lk_baru.baca_log_kom(refresh=True)
        except Exception:
            log.exception("Log Komunikasi tidak terbaca untuk sinkron WA")
            return 0
        if hari not in logkom.tanggal:
            return 0
        auto = {r["npsn"]: r["kode"] for r in db.query("SELECT npsn, kode FROM kom_auto WHERE tanggal = ?", (hari,))}
        tulis: dict[str, str] = {}
        for f in fasil.values():
            k = kode_wa_hari_ini(f.nomor, hari)
            for s in f.sekolah:
                lama = logkom.kode.get(s.npsn, {}).get(hari, "")
                if lama == k:
                    continue
                if not k and auto.get(s.npsn) != lama:
                    continue  # tidak ada kode baru; hanya kode tebakan aplikasi yang dihapus
                if lama and auto.get(s.npsn) != lama:
                    continue  # diisi petugas sendiri
                tulis[s.npsn] = k
        if not tulis:
            return 0
        try:
            n = lk_baru.tulis_log_kom(hari, tulis)
        except Exception:
            log.exception("Kode komunikasi otomatis gagal ditulis")
            return 0
        with db.tx() as c:
            c.executemany("INSERT INTO kom_auto(tanggal, npsn, kode) VALUES(?,?,?) ON CONFLICT(tanggal, npsn) "
                          "DO UPDATE SET kode = excluded.kode", [(hari, k, v) for k, v in tulis.items()])
        return n


def lupakan_auto(hari: str, npsn: list[str]) -> None:
    """Petugas mengubah kode sendiri: sel itu tidak lagi diperbarui otomatis."""
    _db()
    with db.tx() as c:
        c.executemany("DELETE FROM kom_auto WHERE tanggal = ? AND npsn = ?", [(hari, n) for n in npsn])


def wa_otomatis() -> bool:
    return bool(db.get_setting("wa_otomatis", True))


# ---------- ringkasan untuk halaman LK ----------

def ringkasan_fasil(f: Fasil, rencana: dict[str, todo.Rencana], logkom: lk_baru.LogKom, hari: str,
                    blok: int, tags: dict[str, list[str]], delta: dict[str, int | None]) -> dict[str, Any]:
    minggu = minggu_ini(date.fromisoformat(hari))
    kode = kode_fasil(f, logkom)
    perlu = [s for s in f.sekolah if rencana[s.npsn].todo]
    lengkap = sum(1 for s in perlu if todo.lengkap(s, rencana[s.npsn], blok))
    kel = tentukan(kode, hari, not perlu, minggu)
    tambah = [delta.get(s.npsn) for s in f.sekolah]
    ada_banding = any(x is not None for x in tambah)
    progres_naik = sum(x for x in tambah if x)
    hubung = sum(1 for d in minggu if kode.get(d) in TERHUBUNG | {"T1", "T2"})
    dibaca_saja = sum(1 for d in minggu if kode.get(d) == "R")
    membalas = any(kode.get(d) in TERHUBUNG | {"T1", "T2"} for d in minggu)
    fokus = Counter(rencana[s.npsn].fokus.judul for s in perlu if rencana[s.npsn].fokus)
    tunggu = [t.tunggu for s in perlu for t in rencana[s.npsn].todo if t.pelaku == "fasil" and t.tunggu]
    posisi: Counter[str] = Counter()
    for s in perlu:
        posisi.update({_POSISI_DARI[t.kode] for t in rencana[s.npsn].todo if t.kode in _POSISI_DARI})
    return {
        "kunci": f.kunci, "nama": f.nama, "nomor": f.nomor, "ptn": f.ptn, "koor": f.koor,
        "punya_nomor": bool(f.nomor),
        "kelompok": kel,
        "kode_hari_ini": kode.get(hari, ""),
        "kode_minggu": [{"tanggal": d, "kode": kode.get(d, "")} for d in minggu],
        "sekolah": len(f.sekolah), "perlu": len(perlu), "lengkap": lengkap,
        "todo": sum(len(rencana[s.npsn].todo) for s in f.sekolah),
        "todo_fasil": sum(1 for s in f.sekolah for t in rencana[s.npsn].todo if t.pelaku == "fasil"),
        "fokus": [{"judul": j, "jumlah": n} for j, n in fokus.most_common(3)],
        "tunggu_maks": max(tunggu) if tunggu else None,
        "tag": tags.get(f.kunci, []),
        "tanpa_progres": bool(perlu) and ada_banding and progres_naik == 0 and hubung >= 2,
        "belum_ditelepon": dibaca_saja >= 2 and not membalas,
        "progres_naik": progres_naik if ada_banding else None,
        "posisi": dict(posisi),
    }


def indikator(daftar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insight singkat untuk petugas, dari ringkasan semua fasil."""
    out = []
    telp = [x for x in daftar if x["belum_ditelepon"]]
    if telp:
        out.append({"kode": "belum_ditelepon", "nada": "warn", "jumlah": len(telp),
                    "judul": f"{len(telp)} fasil belum pernah ditelepon",
                    "isi": "Minggu ini chatnya berkali-kali hanya dibaca atau tidak sampai. Coba telepon lalu catat TP."})
    ok = [x for x in daftar if x["tanpa_progres"]]
    if ok:
        out.append({"kode": "tanpa_progres", "nada": "warn", "jumlah": len(ok),
                    "judul": f"{len(ok)} fasil merespons tapi laporannya tidak bergerak",
                    "isi": "Sering terhubung minggu ini, tapi tidak ada komponen yang bertambah selesai sejak cutoff "
                           "sebelumnya. Tanyakan kendalanya lebih spesifik, atau eskalasi ke koordinator."})
    lama = [x for x in daftar if (x["tunggu_maks"] or 0) > 3]
    if lama:
        out.append({"kode": "reviu_lama", "nada": "info", "jumlah": len(lama),
                    "judul": f"{len(lama)} fasil punya reviu yang menunggu lebih dari 3 hari",
                    "isi": "Laporan sekolah sudah masuk tapi belum direviu fasil. Ingatkan untuk mereviu."})
    return out


def kode_label() -> list[dict[str, str]]:
    return [{"kode": k, "arti": v} for k, v in KODE_KOMUNIKASI.items()]


def nomor_bersih(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def nomor_milik() -> set[str]:
    """Nomor yang boleh dibaca/dikirimi dari aplikasi: fasil, koordinator, kepala sekolah binaan petugas."""
    from .sheets import daftar_nomor

    out: set[str] = set()
    for s in sekolah_saya():
        out.update(s.nomor_fasil())
        out.update(daftar_nomor(s.hp_koor))
        out.update(daftar_nomor(s.hp_kepsek))
    return out


def nama_nomor() -> dict[str, str]:
    """{nomor: nama} untuk riwayat."""
    from .sheets import daftar_nomor

    out: dict[str, str] = {}
    try:
        for s in sekolah_saya():
            for n in s.nomor_fasil():
                out.setdefault(n, s.fasil)
            for n in daftar_nomor(s.hp_koor):
                out.setdefault(n, f"{s.koor} (koordinator)")
            for n in daftar_nomor(s.hp_kepsek):
                out.setdefault(n, f"Kepsek {s.nama}")
    except Exception:
        pass
    return out


# ---------- status komunikasi minggu ini (papan kedua di LK) ----------

STATUS_KOM = (
    ("perlu_balas", "Sudah membalas, giliran Anda", "Fasil membalas dan belum dibalas lagi"),
    ("telepon", "Perlu ditelepon", "Centang satu, tidak ada WA, atau berulang kali hanya dibaca"),
    ("dibaca", "Dibaca, belum membalas", "Sapa lagi, atau telepon bila berulang"),
    ("terkirim", "Terkirim, belum dibaca", "Tunggu dibaca"),
    ("menunggu", "Menunggu konfirmasi", "Terhubung, tapi jawabannya belum tuntas atau lambat"),
    ("terhubung", "Sudah membalas", "Respon baik lewat WhatsApp atau sudah ditelepon"),
    ("belum", "Belum dihubungi", "Belum ada chat atau kode komunikasi minggu ini"),
)


def peta_chat(senin_iso: str) -> dict[str, dict[str, Any]]:
    """{nomor: {status, perlu_balas, balasan, waktu}} dari chat yang dibaca/terkirim sejak Senin."""
    out: dict[str, dict[str, Any]] = {}
    try:
        for r in db.query("SELECT nomor, status, balasan_terakhir, waktu_balasan, dicek, perlu_balas FROM chat_status "
                          "WHERE dicek >= ? OR waktu_balasan >= ?", (senin_iso, senin_iso)):
            out[r["nomor"]] = {"status": r["status"], "perlu_balas": bool(r["perlu_balas"]),
                               "balasan": r["balasan_terakhir"] if (r["waktu_balasan"] or "") >= senin_iso else "",
                               "waktu": r["waktu_balasan"] if (r["waktu_balasan"] or "") >= senin_iso else ""}
        for r in db.query("SELECT DISTINCT nomor FROM sends WHERE coba = 0 AND status = 'terkirim' AND waktu >= ?",
                          (senin_iso,)):
            out.setdefault(r["nomor"], {"status": "terkirim", "perlu_balas": False, "balasan": "", "waktu": ""})
    except Exception:
        log.exception("Status chat tidak terbaca")
    return out


def status_kom(r: dict[str, Any], chat: dict[str, Any] | None) -> str:
    """Satu status komunikasi per fasil: dari chat WhatsApp minggu ini dan kode Log Komunikasi hari ini."""
    if chat and chat.get("perlu_balas"):
        return "perlu_balas"
    if r["kelompok"] == "perlu_telepon" or r["belum_ditelepon"]:
        return "telepon"
    k = r["kode_hari_ini"]
    if k in TERHUBUNG:
        return "terhubung"
    if k in ("T1", "T2"):
        return "menunggu"
    if k == "R":
        return "dibaca"
    st = (chat or {}).get("status", "")
    if st == "dibalas":
        return "terhubung"
    if st == "dibaca":
        return "dibaca"
    if st == "terkirim":
        return "terkirim"
    if any(d["kode"] in TERHUBUNG for d in r["kode_minggu"]):
        return "terhubung"
    return "belum"
