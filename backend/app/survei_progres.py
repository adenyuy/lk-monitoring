"""Blast Survei Progres: kirim link form survei realisasi progres fisik ke fasil binaan petugas.

Penerima diambil dari sheet LK Survey (tab "Survei Progres"): baris yang kolom PETUGAS PIC-nya sama dengan nama
petugas di aplikasi ini, dikelompokkan per nomor WhatsApp fasil (kolom NO TELP). Satu fasil menerima satu pesan
berisi daftar sekolah binaannya.

Aturan kirim sama dengan Undangan WAG: langsung ke semua fasil (tanpa jam sesi, kuota, batas harian), hanya pukul
07.00–22.00, jeda acak antarpesan. Tiap fasil dikirimi SEKALI per link form; ganti link = semua dikirimi lagi.
Kiriman dicatat dengan hash berawalan "svy:" sehingga tidak mengganggu antrean progres mingguan.
Link sheet disimpan di pengaturan lokal laptop (tidak di repo).
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import config, db
from .send_queue import Item
from .sheets import BroadcastRow, cache, normalize_nomor, normalize_petugas
from .undangan_wag import antrean_sekali, ringkasan  # noqa: F401  (ringkasan dipakai router)

KUNCI = "survei_progres"
AWALAN = "svy:"
TAB = "Survei Progres"
POLA_LINK = re.compile(r"^https://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/\S*)?$")
KOLOM = {"npsn": "NPSN", "sekolah": "SEKOLAH", "fasil": "FASIL", "telp": "NO TELP", "pic": "PETUGAS PIC"}
KOLOM_OPSIONAL = {"isian": "ISIAN PROGRES (%)", "waktu": "DIISI PADA"}

TEKS_AWAL = (
    "Selamat {salam} Bapak/Ibu {nama} 🙏\n\n"
    "Dalam rangka pemutakhiran data, kami mohon kesediaan Bapak/Ibu untuk mengisi *Survei Realisasi Progres Fisik* "
    "sekolah binaan sampai dengan minggu ini melalui tautan berikut:\n\n"
    "🔗 {link}\n\n"
    "Sekolah binaan yang perlu diisi ({jumlah} sekolah):\n"
    "{sekolah}\n\n"
    "Langkah pengisian:\n"
    "1. Buka tautan di atas, lalu masuk menggunakan nomor WhatsApp ini ({nomor}).\n"
    "2. Pilih sekolah binaan.\n"
    "3. Isikan persentase realisasi progres fisik sesuai kondisi di lapangan, lalu tekan Simpan.\n\n"
    "Apabila mengalami kendala dalam pengisian, Bapak/Ibu dapat membalas pesan ini.\n\n"
    "Atas perhatian dan kerja sama Bapak/Ibu, kami ucapkan terima kasih 🙏"
)


class SurveiError(ValueError):
    """Pengaturan survei tidak valid. Pesannya untuk pengguna."""


@dataclass
class Pengaturan:
    aktif: bool = False
    sheet: str = ""  # ID spreadsheet LK Survey
    link: str = ""  # link form pengisian
    teks: str = TEKS_AWAL

    def as_dict(self) -> dict[str, Any]:
        return {"aktif": self.aktif, "sheet": self.sheet, "link": self.link, "teks": self.teks, "teks_awal": TEKS_AWAL}


@dataclass
class Fasil:
    baris: int
    nama: str
    nomor: str  # 62…, '' bila tidak valid
    nomor_asli: str
    sekolah: list[str] = field(default_factory=list)
    isi: list[dict[str, str]] = field(default_factory=list)  # per sekolah: npsn, nama, isian, waktu


def pengaturan() -> Pengaturan:
    d = db.get_setting(KUNCI) or {}
    sheet, link = d.get("sheet", ""), d.get("link", "")
    return Pengaturan(aktif=bool(d.get("aktif")) and bool(sheet) and bool(link), sheet=sheet, link=link,
                      teks=d.get("teks") or TEKS_AWAL)


def id_sheet(nilai: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", nilai or "")
    return m.group(1) if m else (nilai or "").strip()


def rapikan_link(link: str) -> str:
    link = (link or "").strip()
    if link and not link.startswith(("http://", "https://")):
        link = "https://" + link
    return link.replace("http://", "https://", 1)


def matikan() -> None:
    d = db.get_setting(KUNCI) or {}
    if d.get("aktif"):
        db.set_setting(KUNCI, {**d, "aktif": False})


def simpan(*, aktif: bool, sheet: str, link: str, teks: str, periksa=None) -> Pengaturan:
    """Simpan pengaturan. `periksa(sheet_id)` membuka sheet untuk memastikan tab Survei Progres ada (dilewati di tes)."""
    sid = id_sheet(sheet)
    link = rapikan_link(link)
    if sid and not re.fullmatch(r"[A-Za-z0-9_-]{20,}", sid):
        raise SurveiError("Itu bukan link Google Sheets. Salin link dari address bar sheet LK Survey.")
    if link and not POLA_LINK.match(link):
        raise SurveiError("Link pengisian tidak valid, contoh https://survey-progress.netlify.app/.")
    if aktif and not (sid and link):
        raise SurveiError("Isi link sheet LK Survey dan link pengisian dulu sebelum menyalakan blast survei.")
    teks = (teks or "").strip() or TEKS_AWAL
    if "{link}" not in teks:
        raise SurveiError("Teks pesan harus memuat {link} supaya link pengisian ikut terkirim.")
    if sid and periksa is not None:
        periksa(sid)
    if aktif:  # hanya satu kampanye langsung yang aktif
        from . import undangan_wag

        d = db.get_setting(undangan_wag.KUNCI) or {}
        if d.get("aktif"):
            db.set_setting(undangan_wag.KUNCI, {**d, "aktif": False})
        db.delete_setting("kirim_semua")
    p = Pengaturan(aktif=aktif, sheet=sid, link=link, teks=teks)
    db.set_setting(KUNCI, {"aktif": p.aktif, "sheet": p.sheet, "link": p.link, "teks": p.teks})
    return p


def periksa_sheet(sid: str) -> None:
    from .google_auth import gspread_client

    try:
        judul = [w.title for w in gspread_client().open_by_key(sid).worksheets()]
    except Exception as e:
        raise SurveiError(f"Sheet tidak bisa dibuka dengan akun ini: {e}") from e
    if TAB not in judul:
        raise SurveiError(f'Sheet ini tidak punya tab "{TAB}". Pastikan link-nya LK Survey.')


def hash_link(link: str) -> str:
    return AWALAN + hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]


def nomor_lokal(nomor: str) -> str:
    """6281234567890 -> 081234567890 (ditampilkan di pesan)."""
    return "0" + nomor[2:] if nomor.startswith("62") else nomor


def parse(values: list[list[Any]], petugas: str) -> list[Fasil]:
    """Baris tab Survei Progres -> fasil binaan `petugas` (urutan sesuai sheet). Header dicari di 5 baris pertama."""
    hdr_i = next((i for i, r in enumerate(values[:5]) if any(str(c).strip().upper() == "NPSN" for c in r)), None)
    if hdr_i is None:
        raise SurveiError(f'Judul kolom tidak ditemukan di tab "{TAB}".')
    header = [str(c).strip().upper() for c in values[hdr_i]]
    idx = {}
    for k, nama in KOLOM.items():
        if nama not in header:
            raise SurveiError(f'Kolom "{nama}" tidak ditemukan di tab "{TAB}".')
        idx[k] = header.index(nama)
    for k, nama in KOLOM_OPSIONAL.items():  # hasil pengisian form (boleh belum ada)
        idx[k] = header.index(nama) if nama in header else 10**6
    target = normalize_petugas(petugas)
    per: dict[str, Fasil] = {}
    for n, r in enumerate(values[hdr_i + 1:], start=hdr_i + 2):
        sel = lambda k: str(r[idx[k]]).strip() if idx[k] < len(r) else ""  # noqa: E731
        if normalize_petugas(sel("pic")) != target or not sel("fasil"):
            continue
        asli = sel("telp")
        nomor = normalize_nomor(asli)
        kunci = nomor or "nama:" + " ".join(sel("fasil").casefold().split())
        f = per.setdefault(kunci, Fasil(n, " ".join(sel("fasil").split()), nomor, asli))
        if sel("sekolah"):
            f.sekolah.append(sel("sekolah"))
            f.isi.append({"npsn": sel("npsn"), "nama": sel("sekolah"), "isian": sel("isian"), "waktu": sel("waktu")})
    return list(per.values())


def fasil_binaan(p: Pengaturan, petugas: str) -> list[Fasil]:
    def load() -> list[list[Any]]:
        from .google_auth import gspread_client

        return gspread_client().open_by_key(p.sheet).values_get(f"'{TAB}'!A1:Z").get("values", [])

    return parse(cache.get("survei:" + p.sheet, config.LK_CACHE_SECONDS, load), petugas)


def susun(p: Pengaturan, f: Fasil) -> str:
    """Isi teks untuk satu fasil. {salam} dibiarkan, diisi saat dikirim."""
    daftar = "\n".join(f"• {s}" for s in f.sekolah) or "-"
    teks = (p.teks.replace("{nama}", f.nama).replace("{link}", p.link).replace("{jumlah}", str(len(f.sekolah)))
            .replace("{sekolah}", daftar).replace("{nomor}", nomor_lokal(f.nomor) or "yang terdaftar"))
    return re.sub(r"[ \t]+\n", "\n", teks)


def build(fasil: Iterable[Fasil], sends: Iterable[dict], p: Pengaturan) -> list[Item]:
    fasil = list(fasil)
    per_baris = {f.baris: f for f in fasil}
    rows = [BroadcastRow(f.baris, "", f.nama, f.nomor, f.nomor_asli, "", "") for f in fasil]
    return antrean_sekali(rows, sends, hash_link(p.link), lambda r: susun(p, per_baris[r.baris]))


def isi_salam(teks: str, t) -> str:
    from .undangan_wag import isi_salam as _isi

    return _isi(teks, t)


def _waktu_urut(w: str) -> str:
    """'03/11/2026 10:12' -> '2026-11-03 10:12' supaya bisa dibandingkan."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(.*)", w or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d} {m.group(4)}" if m else (w or "")


def kontak_sejak(items: list[Item]) -> dict[str, dict[str, Any]]:
    """WhatsApp dibaca/dibalas SETELAH link survei terkirim ke fasil itu (bukan pesan lain sebelumnya)."""
    kirim = {i.nomor: i.waktu for i in items if i.status == "terkirim" and i.nomor and i.waktu}
    out: dict[str, dict[str, Any]] = {n: {"dibaca": False, "dibalas": False, "balasan": ""} for n in kirim}
    if not kirim:
        return out
    awal = min(kirim.values())
    for r in db.query("SELECT nomor, jenis, waktu, ringkasan FROM aktivitas WHERE waktu >= ? ORDER BY waktu", (awal,)):
        x, t = out.get(r["nomor"]), kirim.get(r["nomor"], "")
        if not x or r["waktu"] < t:
            continue
        if r["jenis"] in ("dibaca", "dibalas"):
            x["dibaca"] = True
        if r["jenis"] == "dibalas":
            x["dibalas"] = True
            x["balasan"] = re.sub(r"^Balasan:\s*", "", r["ringkasan"])
    for r in db.query("SELECT nomor, status, balasan_terakhir, waktu_balasan, dicek FROM chat_status"):
        x, t = out.get(r["nomor"]), kirim.get(r["nomor"], "")
        if not x:
            continue
        if r["status"] in ("dibaca", "dibalas") and (r["dicek"] or "") >= t:
            x["dibaca"] = True
        if r["status"] == "dibalas" and (r["waktu_balasan"] or "") >= t:
            x["dibaca"] = x["dibalas"] = True
            x["balasan"] = r["balasan_terakhir"] or x["balasan"]
    return out


def status(fasil: list[Fasil], items: list[Item], kontak: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Pemantauan per fasil: link terkirim?, WhatsApp dibaca/dibalas sejak link terkirim, sekolah yang sudah diisi."""
    from .wa.status import mask

    per_nomor = {i.nomor: i for i in items if i.nomor}
    out = []
    for f in fasil:
        it = per_nomor.get(f.nomor)
        k = kontak.get(f.nomor, {})
        terisi = [x for x in f.isi if x["isian"]]
        waktu_isi = [x["waktu"] for x in terisi if x["waktu"]]
        terkirim = bool(it and it.status == "terkirim")
        wa = "dibalas" if k.get("dibalas") else "dibaca" if k.get("dibaca") else "terkirim" if terkirim else "belum"
        out.append({
            "nama": f.nama, "nomor": f.nomor, "nomor_tersamar": mask(f.nomor),
            "kirim": it.status if it and f.nomor else "tanpa_nomor",
            "kirim_waktu": it.waktu if it else "", "kirim_ket": it.keterangan if it else "",
            "wa": wa if f.nomor else "belum", "balasan": k.get("balasan", ""),
            "total": len(f.isi), "terisi": len(terisi),
            "terakhir_isi": max(waktu_isi, key=_waktu_urut) if waktu_isi else "",
            "sekolah": f.isi,
        })
    return {
        "ringkasan": {
            "fasil": len(out),
            "terkirim": sum(1 for x in out if x["kirim"] == "terkirim"),
            "dibaca": sum(1 for x in out if x["wa"] in ("dibaca", "dibalas")),
            "dibalas": sum(1 for x in out if x["wa"] == "dibalas"),
            "sekolah": sum(x["total"] for x in out),
            "terisi": sum(x["terisi"] for x in out),
            "tuntas": sum(1 for x in out if x["total"] and x["terisi"] >= x["total"]),
        },
        "fasil": out,
    }
