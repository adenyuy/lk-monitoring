"""LK Eskalasi: permasalahan sekolah yang perlu dijawab tim terkait, dicatat di spreadsheet LK Eskalasi milik tim.

Tab "LK Eskalasi" (judul di baris 4): satu masalah = satu baris dengan ID Masalah E-0001, E-0002, ... Satu masalah
yang mengenai beberapa sekolah ditulis satu baris per sekolah (ID sendiri-sendiri). Data sekolah (Nama, Fasilitator,
Petugas Monitoring, PTN) diisi aplikasi dari WEEK aktif LK Monitoring, cadangannya tab Master Data, karena skrip
onEdit sheet tidak jalan untuk tulisan lewat API dan Master Data tidak selalu terbaru.

Kolom berumus (Masalah Aktif, Saran Kode Tema, Tema Agregasi, Tim Tujuan, Batas Waktu, Status Waktu) tidak pernah
ditulis. Tanggal Permasalahan Selesai ditulis aplikasi saat status jadi Selesai.

Alamat sheet: LKM_ESKALASI_SHEET_ID, `eskalasi` di sheets.json, atau tab "Pengaturan" di sheet Akses
(baris `lk_eskalasi` | link), supaya admin cukup memasangnya sekali untuk semua anggota tim.
"""

import json
import os
import re
import threading
from datetime import date
from typing import Any

from . import config, paths, schedule
from .sheets import cache, clean_petugas, col_letter, gspread_client, normalize_petugas

TAB = "LK Eskalasi"
TAB_PILIHAN = "Daftar Pilihan"
TAB_AGREGASI = "Agregasi Eskalasi"
TAB_PIC = "PIC Eskalasi"
TAB_FAQ = "FAQ Eskalasi"
TAB_MASTER = "Master Data"
TAB_PENGATURAN = "Pengaturan"
BARIS_JUDUL = 4
KOLOM_AKHIR = "AZ"
MAKS_SEKOLAH = 50
SUMBER = ("Sekolah", "Fasilitator", "PTN", "Dinas/Kabupaten", "Pengawas", "Umum/Sistem")
STATUS_ESKALASI = ("Sudah Dieskalasi", "Belum Dieskalasi")
# Judul kolom (huruf kecil, tanpa isi kurung dan "?") -> field
JUDUL = {
    "id masalah": "id", "sumber masalah": "sumber", "npsn": "npsn", "nama sumber / topik": "topik",
    "nama sekolah": "nama", "fasilitator": "fasil", "petugas monitoring": "petugas", "ptn": "ptn",
    "masalah aktif di sekolah ini": "aktif", "keterangan permasalahan": "keterangan", "permasalahan": "permasalahan",
    "tingkat": "tingkat", "evidence": "evidence", "tanggal awal permasalahan": "tgl_awal",
    "perlu agregasi": "agregasi", "saran kode tema": "saran_tema", "kode tema": "kode_tema",
    "jawaban tim terkait": "jawaban", "status tindak lanjut": "status", "tanggal permasalahan selesai": "tgl_selesai",
    "pengisi jawaban": "pengisi", "status eskalasi": "status_eskalasi", "tema agregasi": "tema",
    "tim tujuan": "tim_tujuan", "batas waktu": "batas", "status waktu": "status_waktu",
}
WAJIB = ("id", "sumber", "npsn", "nama", "fasil", "petugas", "keterangan", "permasalahan", "tgl_awal", "agregasi",
         "kode_tema", "jawaban", "status", "tgl_selesai", "pengisi", "status_eskalasi")
EXCEL_NOL = date(1899, 12, 30)
_lock = threading.Lock()


class EskalasiError(Exception):
    """Pesannya ditampilkan langsung ke pengguna."""


class LinkBelumAda(EskalasiError):
    pass


def key_npsn(v: Any) -> str:
    return re.sub(r"\.0+$", "", str(v).strip())


def _id_dari(nilai: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", nilai)
    return m.group(1) if m else nilai.strip()


def sheet_id() -> str:
    env = os.environ.get("LKM_ESKALASI_SHEET_ID")
    if env:
        return env
    f = paths.DATA_DIR / "sheets.json"
    try:
        lokal = json.loads(f.read_text(encoding="utf-8")).get("eskalasi") if f.exists() else ""
    except (ValueError, OSError):
        lokal = ""
    if lokal:
        return _id_dari(str(lokal))

    def load() -> str:
        ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
        try:
            baris = ss.values_get(f"'{TAB_PENGATURAN}'!A1:B50").get("values", [])
        except Exception:
            return ""
        for r in baris:
            if len(r) > 1 and str(r[0]).strip().casefold() == "lk_eskalasi":
                return _id_dari(str(r[1]))
        return ""

    sid = cache.get("eskalasi_id", 600, load)
    if not sid:
        raise LinkBelumAda('Link LK Eskalasi belum dipasang admin. Tambahkan baris "lk_eskalasi" berisi link sheet '
                            'di tab Pengaturan pada sheet Akses.')
    return sid


def pasang_link(link: str, untuk_tim: bool) -> str:
    """Simpan link LK Eskalasi di laptop ini; admin (`untuk_tim`) juga menulisnya ke tab Pengaturan sheet Akses
    supaya seluruh tim langsung memakainya."""
    sid = _id_dari(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", sid):
        raise EskalasiError("Itu bukan link Google Sheets. Salin link dari address bar sheet LK Eskalasi.")
    try:
        judul = [w.title for w in gspread_client().open_by_key(sid).worksheets()]
    except Exception as e:
        raise EskalasiError(f"Sheet tidak bisa dibuka dengan akun ini: {e}") from e
    if TAB not in judul:
        raise EskalasiError(f'Sheet ini tidak punya tab "{TAB}". Pastikan link-nya LK Eskalasi.')
    f = paths.DATA_DIR / "sheets.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (ValueError, OSError):
        data = {}
    data["eskalasi"] = sid
    paths.ensure_dirs()
    f.write_text(json.dumps(data), encoding="utf-8")
    if untuk_tim:
        ss = gspread_client().open_by_key(config.ACCESS_SHEET_ID)
        if TAB_PENGATURAN not in [w.title for w in ss.worksheets()]:
            ss.add_worksheet(TAB_PENGATURAN, rows=20, cols=3)
            ss.values_update(f"'{TAB_PENGATURAN}'!A1:C1", params={"valueInputOption": "RAW"},
                             body={"values": [["kunci", "nilai", "keterangan"]]})
        baris = ss.values_get(f"'{TAB_PENGATURAN}'!A1:A50").get("values", [])
        n = next((i + 1 for i, r in enumerate(baris) if r and str(r[0]).strip().casefold() == "lk_eskalasi"),
                 len(baris) + 1)
        ss.values_update(f"'{TAB_PENGATURAN}'!A{n}:C{n}", params={"valueInputOption": "RAW"},
                         body={"values": [["lk_eskalasi", f"https://docs.google.com/spreadsheets/d/{sid}/edit",
                                           "Sheet LK Eskalasi untuk tombol Butuh bantuan di aplikasi"]]})
    cache.clear()
    return sid


def _ss():
    return gspread_client().open_by_key(sheet_id())


# ---------- tata letak tab LK Eskalasi ----------

def _kunci_judul(h: Any) -> str:
    """'Sumber Masalah (asal/penyebab)' -> 'sumber masalah'; 'Perlu Agregasi?' -> 'perlu agregasi'."""
    return " ".join(re.sub(r"\(.*?\)", "", str(h)).replace("?", "").lower().split())


def parse_judul(header: list[Any]) -> tuple[dict[str, int], list[str]]:
    """Baris judul -> ({field: indeks kolom}, nama tim tujuan berurutan). Tim tujuan = kolom centang di antara
    "Perlu Agregasi?" dan "Saran Kode Tema"/"Kode Tema"; field-nya 'tim:<nama>'."""
    pos: dict[str, int] = {}
    for i, v in enumerate(header):
        f = JUDUL.get(_kunci_judul(v))
        if f and f not in pos:
            pos[f] = i
    hilang = [f for f in WAJIB if f not in pos]
    if hilang:
        nama = {v: k for k, v in JUDUL.items()}
        raise EskalasiError(f"Judul kolom LK Eskalasi tidak ketemu di baris {BARIS_JUDUL}: "
                            f"{', '.join(nama[f] for f in hilang)}. Kemungkinan judulnya diganti.")
    tim: list[str] = []
    akhir = min(pos.get("saran_tema", pos["kode_tema"]), pos["kode_tema"])
    for i in range(pos["agregasi"] + 1, akhir):
        nama_tim = " ".join(str(header[i]).split()) if i < len(header) else ""
        if nama_tim:
            tim.append(nama_tim)
            pos[f"tim:{nama_tim}"] = i
    return pos, tim


def tanggal(v: Any) -> str:
    """Serial tanggal Sheets atau teks dd/mm/yyyy -> 'YYYY-MM-DD' (teks lain apa adanya)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        return date.fromordinal(EXCEL_NOL.toordinal() + int(v)).isoformat()
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        except ValueError:
            return s
    return s


def serial(iso: str) -> int:
    return (date.fromisoformat(iso) - EXCEL_NOL).days


RE_DRIVE = re.compile(r"(?:/d/|[?&]id=)([A-Za-z0-9_-]{20,})")


def pecah_evidence(teks: str) -> tuple[list[str], list[str]]:
    """Isi kolom Evidence -> (id foto Google Drive, tautan lain)."""
    foto: list[str] = []
    tautan: list[str] = []
    for b in re.split(r"[\s,]+", teks or ""):
        if not b.startswith("http"):
            continue
        m = RE_DRIVE.search(b)
        if m and "drive.google.com" in b:
            if m[1] not in foto:
                foto.append(m[1])
        elif b not in tautan:
            tautan.append(b)
    return foto, tautan


def link_foto(fid: str) -> str:
    return f"https://drive.google.com/file/d/{fid}/view"


def _teks(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v if v is not None else "").strip()


def parse_baris(values: list[list[Any]], pos: dict[str, int], tim: list[str], baris_awal: int) -> list[dict[str, Any]]:
    """Baris data (mulai `baris_awal`) -> daftar masalah. Baris tanpa ID dan tanpa keterangan dilewati."""
    out = []
    for n, r in enumerate(values, start=baris_awal):
        def sel(f: str) -> Any:
            i = pos.get(f, -1)
            return r[i] if 0 <= i < len(r) and r[i] is not None else ""

        mid, ket = _teks(sel("id")), _teks(sel("keterangan"))
        if not mid and not ket:
            continue
        evidence = _teks(sel("evidence"))
        foto, tautan = pecah_evidence(evidence)
        aktif = sel("aktif")
        out.append({
            "baris": n, "id": mid, "sumber": _teks(sel("sumber")), "npsn": key_npsn(sel("npsn")),
            "topik": _teks(sel("topik")), "nama": _teks(sel("nama")), "fasil": _teks(sel("fasil")),
            "petugas": _teks(sel("petugas")), "ptn": _teks(sel("ptn")),
            "aktif": int(aktif) if isinstance(aktif, (int, float)) and not isinstance(aktif, bool) else None,
            "keterangan": ket, "permasalahan": _teks(sel("permasalahan")), "tingkat": _teks(sel("tingkat")),
            "evidence": evidence, "foto": foto, "tautan": tautan, "tgl_awal": tanggal(sel("tgl_awal")),
            "agregasi": _teks(sel("agregasi")), "tim": [t for t in tim if sel(f"tim:{t}") is True],
            "saran_tema": _teks(sel("saran_tema")), "kode_tema": _teks(sel("kode_tema")),
            "jawaban": _teks(sel("jawaban")), "status": _teks(sel("status")),
            "tgl_selesai": tanggal(sel("tgl_selesai")), "pengisi": _teks(sel("pengisi")),
            "status_eskalasi": _teks(sel("status_eskalasi")), "tema": _teks(sel("tema")),
            "tim_tujuan": _teks(sel("tim_tujuan")), "batas": tanggal(sel("batas")),
            "status_waktu": _teks(sel("status_waktu")),
            "sidik": sidik(sel("npsn"), ket),
        })
    return out


def sidik(npsn: Any, keterangan: Any) -> str:
    """Penanda baris yang tidak ikut bergeser seperti ID Masalah (ID di sheet sebagian berupa rumus yang nilainya
    bisa berubah saat sheet menghitung ulang): NPSN + awal keterangan."""
    return f"{key_npsn(npsn)}|{' '.join(str(keterangan or '').split())[:120]}"


def _isi_baris(r: list[Any], pos: dict[str, int]) -> bool:
    return any(0 <= pos.get(f, -1) < len(r) and _teks(r[pos[f]])
               for f in ("id", "sumber", "npsn", "topik", "keterangan"))


def _baca() -> dict[str, Any]:
    try:
        got = _ss().values_get(f"'{TAB}'!A{BARIS_JUDUL}:{KOLOM_AKHIR}",
                               params={"valueRenderOption": "UNFORMATTED_VALUE"})
    except EskalasiError:
        raise
    except Exception as e:
        raise EskalasiError(f'Tab "{TAB}" di LK Eskalasi tidak bisa dibaca: {e}') from e
    nilai = got.get("values", [])
    if not nilai:
        raise EskalasiError(f'Tab "{TAB}" kosong.')
    pos, tim = parse_judul(nilai[0])
    data = nilai[1:]
    terakhir = BARIS_JUDUL
    for n, r in enumerate(data, start=BARIS_JUDUL + 1):
        if _isi_baris(r, pos):
            terakhir = n
    return {"pos": pos, "tim": tim, "masalah": parse_baris(data, pos, tim, BARIS_JUDUL + 1), "terakhir": terakhir}


def baca(refresh: bool = False) -> dict[str, Any]:
    return cache.get("esk_baris", 60, _baca, refresh)


def semua(refresh: bool = False) -> list[dict[str, Any]]:
    """Seluruh masalah, terbaru dulu."""
    return sorted(baca(refresh)["masalah"], key=lambda m: (m["tgl_awal"], m["baris"]), reverse=True)


def daftar(npsn: list[str]) -> list[dict[str, Any]]:
    """Masalah untuk sekolah-sekolah ini, terbaru dulu."""
    mau = {key_npsn(x) for x in npsn}
    return [m for m in semua() if m["npsn"] in mau]


# ---------- pilihan (Daftar Pilihan, Agregasi Eskalasi, PIC Eskalasi, FAQ Eskalasi) ----------

def _kolom(g: dict[str, Any]) -> list[str]:
    return [str(r[0]).strip() for r in g.get("values", []) if r and str(r[0]).strip()]


def parse_pic(values: list[list[Any]]) -> dict[str, str]:
    """Tabel Pemetaan Tim - PIC (kolom A:B mulai baris 5) -> {tim: PIC}. Berhenti di baris CATATAN."""
    pic: dict[str, str] = {}
    for r in values:
        a = " ".join(str(r[0]).split()) if r else ""
        if a.upper().startswith("CATATAN"):
            break
        b = " ".join(str(r[1]).split()) if len(r) > 1 else ""
        if a and b:
            pic[a] = b
    return pic


def opsi(refresh: bool = False) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        rng = [f"'{TAB_PILIHAN}'!A2:A", f"'{TAB_PILIHAN}'!C2:C", f"'{TAB_PILIHAN}'!G2:G",
               f"'{TAB_AGREGASI}'!A5:B", f"'{TAB_PIC}'!A5:B40"]
        got = _ss().values_batch_get(rng).get("valueRanges", [])
        got += [{}] * (len(rng) - len(got))
        tema = [{"kode": str(r[0]).strip(), "tema": str(r[1]).strip() if len(r) > 1 else ""}
                for r in got[3].get("values", []) if r and re.fullmatch(r"T\d+", str(r[0]).strip())]
        return {"sumber": list(SUMBER), "permasalahan": _kolom(got[0]), "status": _kolom(got[1]),
                "tingkat": _kolom(got[2]), "tema": tema, "pic": parse_pic(got[4].get("values", [])),
                "tim": baca()["tim"], "status_eskalasi": list(STATUS_ESKALASI)}

    return cache.get("esk_opsi", 300, load, refresh)


def parse_faq(values: list[list[Any]]) -> list[dict[str, str]]:
    out = []
    for r in values:
        r = [str(x).strip() for x in r] + [""] * (7 - len(r))
        if re.fullmatch(r"T\d+", r[0]) and r[2]:
            out.append({"kode": r[0], "kelompok": r[1], "pertanyaan": r[2], "jawaban": r[3], "jumlah": r[4],
                        "tim": r[5], "tgl_selesai": tanggal(r[6])})
    return out


def faq_resmi(refresh: bool = False) -> list[dict[str, str]]:
    """Tab FAQ Eskalasi: tema Selesai yang sudah punya jawaban resmi (diisi rumus sheet)."""
    def load() -> list[dict[str, str]]:
        try:
            return parse_faq(_ss().values_get(f"'{TAB_FAQ}'!A5:G").get("values", []))
        except Exception:  # noqa: BLE001 - tab FAQ opsional
            return []

    return cache.get("esk_faq", 300, load, refresh)


# ---------- data sekolah dari NPSN (LK WEEK aktif, cadangan Master Data) ----------

MEDAN_SEKOLAH = ("npsn", "nama", "petugas", "fasil", "ptn")


def peta_sekolah(kol: list[list[Any]]) -> dict[str, dict[str, str]]:
    """Kolom-kolom (urutan MEDAN_SEKOLAH) -> {npsn: {npsn, nama, petugas, fasil, ptn}}; NPSN pertama yang menang."""
    out: dict[str, dict[str, str]] = {}
    for i in range(max(map(len, kol), default=0)):
        v = {f: _teks(kol[j][i]) if j < len(kol) and i < len(kol[j]) else "" for j, f in enumerate(MEDAN_SEKOLAH)}
        k = key_npsn(v["npsn"])
        if k and k not in out:
            v["npsn"] = k
            v["petugas"] = clean_petugas(v["petugas"])
            out[k] = v
    return out


def _peta_lk() -> dict[str, dict[str, str]]:
    from . import lk_baru

    def load() -> dict[str, dict[str, str]]:
        w = lk_baru.week_aktif()
        t = lk_baru.tata(w)
        rng = [f"'{lk_baru.tab_week(w)}'!{c}{lk_baru.BARIS_DATA}:{c}"
               for c in (col_letter(t.identitas[f]) for f in MEDAN_SEKOLAH)]
        got = lk_baru._ss().values_batch_get(rng).get("valueRanges", [])
        return peta_sekolah([[(r[0] if r else "") for r in g.get("values", [])] for g in got])

    return cache.get("esk_peta_lk", 600, load)


def _peta_master() -> dict[str, dict[str, str]]:
    def load() -> dict[str, dict[str, str]]:
        got = _ss().values_get(f"'{TAB_MASTER}'!B4:F").get("values", [])
        # Master Data: NPSN | Nama Sekolah | Petugas | Fasilitator | PTN
        return peta_sekolah([[r[i] if i < len(r) else "" for r in got] for i in range(5)])

    return cache.get("esk_peta_master", 600, load)


def sekolah(npsn: str) -> dict[str, str] | None:
    """{npsn, nama, petugas, fasil, ptn, asal}. WEEK aktif LK dulu (selalu terbaru), lalu Master Data."""
    k = key_npsn(npsn)
    try:
        v = _peta_lk().get(k)
        if v:
            return {**v, "asal": "LK"}
    except Exception:  # noqa: BLE001 - LK tidak terbaca: pakai Master Data
        pass
    try:
        v = _peta_master().get(k)
    except Exception:  # noqa: BLE001
        v = None
    return {**v, "asal": "Master Data"} if v else None


# ---------- tulis ----------

def id_berikut(masalah: list[dict[str, Any]]) -> int:
    return max((int(m[1]) for m in (re.fullmatch(r"E-(\d+)", x["id"]) for x in masalah) if m), default=0) + 1


def rentang(baris: int, sel: dict[int, Any]) -> list[dict[str, Any]]:
    """{indeks kolom: nilai} satu baris -> rentang bersambung untuk values_batch_update (kolom lain tidak disentuh)."""
    out: list[dict[str, Any]] = []
    for i in sorted(sel):
        if out and i == out[-1]["_akhir"] + 1:
            out[-1]["values"][0].append(sel[i])
            out[-1]["_akhir"] = i
        else:
            out.append({"_awal": i, "_akhir": i, "values": [[sel[i]]]})
    return [{"range": f"'{TAB}'!{col_letter(r['_awal'])}{baris}:{col_letter(r['_akhir'])}{baris}",
             "values": r["values"]} for r in out]


def _hari_ini() -> str:
    return schedule.now().date().isoformat()


def _cek_pilihan(nilai: Any, daftar: list[str], label: str, wajib: bool = False) -> str:
    nilai = str(nilai or "").strip()
    if not nilai:
        if wajib:
            raise EskalasiError(f"{label} wajib dipilih.")
        return ""
    if daftar and nilai not in daftar:
        raise EskalasiError(f'{label} "{nilai}" tidak ada di daftar pilihan LK Eskalasi.')
    return nilai


def _cek_tanggal(iso: str, label: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError as e:
        raise EskalasiError(f"{label} tidak valid.") from e
    if d > schedule.now().date():
        raise EskalasiError(f"{label} tidak boleh setelah hari ini.")
    return iso


def _evidence(daftar: list[str]) -> str:
    """Id foto Drive / tautan -> isi kolom Evidence (satu tautan per baris)."""
    out = []
    for x in daftar:
        x = (x or "").strip()
        if not x:
            continue
        if re.fullmatch(r"[A-Za-z0-9_-]{20,}", x):
            x = link_foto(x)
        if not re.match(r"https?://", x):
            raise EskalasiError("Evidence harus berupa foto atau tautan (http…).")
        out.append(x)
    return "\n".join(dict.fromkeys(out))


def _baca_sidik(ss, pos: dict[str, int], awal: int, akhir: int) -> list[str]:
    """Sidik baris awal..akhir dibaca langsung dari sheet (kolom NPSN dan Keterangan)."""
    rng = [f"'{TAB}'!{col_letter(pos[f])}{awal}:{col_letter(pos[f])}{akhir}" for f in ("npsn", "keterangan")]
    got = ss.values_batch_get(rng).get("valueRanges", [])
    kol = [[(r[0] if r else "") for r in g.get("values", [])] for g in got] + [[], []]
    n = akhir - awal + 1
    return [sidik(kol[0][i] if i < len(kol[0]) else "", kol[1][i] if i < len(kol[1]) else "") for i in range(n)]


def cari(masalah: list[dict[str, Any]], mid: str, baris: int | None, sidik_: str | None) -> dict[str, Any]:
    """Baris yang dimaksud pengguna. ID saja tidak cukup (ID rumus di sheet bisa bergeser/dobel), jadi dicocokkan
    dengan sidik yang dilihat pengguna: baris yang sama dulu, lalu sidik yang sama di baris lain (baris bergeser)."""
    if sidik_:
        if baris:
            m = next((x for x in masalah if x["baris"] == baris and x["sidik"] == sidik_), None)
            if m:
                return m
        sama = [x for x in masalah if x["sidik"] == sidik_]
        if len(sama) == 1:
            return sama[0]
        sama_id = [x for x in sama if x["id"] == mid]
        if len(sama_id) == 1:
            return sama_id[0]
        raise EskalasiError(f"Masalah {mid} tidak ditemukan lagi (baris di sheet berubah). Muat ulang lalu coba lagi.")
    kandidat = [x for x in masalah if x["id"] == mid]
    if len(kandidat) != 1:
        raise EskalasiError(f"Masalah {mid} {'tidak ditemukan' if not kandidat else 'dobel'} di LK Eskalasi. Muat ulang lalu coba lagi.")
    return kandidat[0]


def catat(isi: dict[str, Any], npsn: list[str], pembuat: str) -> list[dict[str, Any]]:
    """Tulis satu permasalahan; satu sekolah terdampak = satu baris (ID Masalah sendiri-sendiri).

    `isi`: sumber, topik, keterangan, permasalahan, tingkat, evidence (list id foto/tautan), tgl_awal (ISO),
    agregasi (Ya/Tidak), tim (list), dan opsional jawaban, status, pengisi."""
    pil = opsi()
    sumber = _cek_pilihan(isi.get("sumber"), pil["sumber"], "Sumber masalah", wajib=True)
    keterangan = str(isi.get("keterangan") or "").strip()
    if len(keterangan) < 10:
        raise EskalasiError("Keterangan permasalahan minimal 10 huruf. Jelaskan masalahnya dengan jelas.")
    permasalahan = _cek_pilihan(isi.get("permasalahan"), pil["permasalahan"], "Permasalahan", wajib=True)
    tingkat = _cek_pilihan(isi.get("tingkat"), pil["tingkat"], "Tingkat")
    agregasi = str(isi.get("agregasi") or "Ya").strip()
    if agregasi not in ("Ya", "Tidak"):
        raise EskalasiError("Perlu Agregasi harus Ya atau Tidak.")
    tim = [t for t in pil["tim"] if t in (isi.get("tim") or [])] if agregasi == "Ya" else []
    if agregasi == "Ya" and not tim:
        raise EskalasiError("Perlu agregasi: centang minimal satu tim tujuan.")
    if tingkat.startswith("Tingkat 3") and not keterangan.upper().startswith("PRIORITAS TINGGI"):
        keterangan = f"PRIORITAS TINGGI: {keterangan}"  # Panduan bagian 4: Tingkat 3 diawali PRIORITAS TINGGI
    topik = str(isi.get("topik") or "").strip()[:200]
    tgl_awal = _cek_tanggal(str(isi.get("tgl_awal") or _hari_ini()), "Tanggal awal permasalahan")
    evidence = _evidence(isi.get("evidence") or [])
    status = (_cek_pilihan(isi.get("status"), pil["status"], "Status tindak lanjut")
              or (pil["status"][0] if pil["status"] else ""))
    jawaban = str(isi.get("jawaban") or "").strip()
    pengisi = str(isi.get("pengisi") or "").strip() or (pembuat if jawaban else "")

    daftar_npsn = list(dict.fromkeys(key_npsn(x) for x in npsn if key_npsn(x)))
    if sumber == "Sekolah" and not daftar_npsn:
        raise EskalasiError("Sumber masalah Sekolah: isi NPSN sekolahnya.")
    if not daftar_npsn and not topik:
        raise EskalasiError("Tanpa NPSN, isi Nama Sumber / Topik.")
    if len(daftar_npsn) > MAKS_SEKOLAH:
        raise EskalasiError(f"Maksimal {MAKS_SEKOLAH} sekolah sekali catat.")
    identitas = []
    for x in daftar_npsn:
        s = sekolah(x)
        if not s:
            raise EskalasiError(f"NPSN {x} tidak ditemukan di LK maupun Master Data.")
        identitas.append(s)
    if not identitas:
        identitas = [{"npsn": "", "nama": "", "fasil": "", "petugas": pembuat, "ptn": ""}]

    with _lock:
        b = baca(refresh=True)
        pos = b["pos"]
        ss = _ss()
        no = id_berikut(b["masalah"])
        mulai = b["terakhir"] + 1
        try:
            maks = ss.worksheet(TAB).row_count
        except Exception:  # noqa: BLE001
            maks = 0
        if maks and mulai + len(identitas) - 1 > maks:
            raise EskalasiError(f'Tab "{TAB}" sudah penuh ({maks} baris). Minta admin menambah baris di bawah tabel.')
        data, hasil = [], []
        for k, s in enumerate(identitas):
            mid = f"E-{no + k:04d}"
            nilai: dict[str, Any] = {
                "id": mid, "sumber": sumber, "npsn": s["npsn"], "topik": topik, "nama": s["nama"],
                "fasil": s["fasil"], "petugas": s["petugas"] or pembuat, "ptn": s["ptn"], "keterangan": keterangan,
                "permasalahan": permasalahan, "tingkat": tingkat, "evidence": evidence, "tgl_awal": serial(tgl_awal),
                "agregasi": agregasi, "jawaban": jawaban, "status": status, "pengisi": pengisi,
                "status_eskalasi": STATUS_ESKALASI[1],
                **{f"tim:{t}": t in tim for t in pil["tim"]},
            }
            if status == "Selesai":
                nilai["tgl_selesai"] = serial(_hari_ini())
            data += rentang(mulai + k, {pos[f]: v for f, v in nilai.items() if f in pos})
            hasil.append({"id": mid, "npsn": s["npsn"], "nama": s["nama"], "fasil": s["fasil"], "baris": mulai + k})
        ss.values_batch_update({"valueInputOption": "RAW", "data": data})
        cache.drop("esk_baris")
        tulis = _baca_sidik(ss, pos, mulai, mulai + len(hasil) - 1)
        if tulis != [sidik(h["npsn"], keterangan) for h in hasil]:
            raise EskalasiError("Baris LK Eskalasi berubah saat ditulis (mungkin petugas lain menulis bersamaan). "
                                "Muat ulang lalu periksa apakah masalahnya sudah tercatat.")
    return hasil


MEDAN_PETUGAS = frozenset({"sumber", "topik", "keterangan", "permasalahan", "tingkat", "evidence", "tgl_awal",
                           "agregasi", "tim", "jawaban", "status", "pengisi", "tgl_selesai"})
MEDAN_PIC = frozenset({"kode_tema", "status_eskalasi"})


def boleh_ubah(m: dict[str, Any], saya: str, pic: bool) -> bool:
    """PIC Eskalasi/admin boleh semua baris; petugas hanya baris yang Petugas Monitoring-nya dia."""
    return pic or (bool(saya) and normalize_petugas(m["petugas"]) == normalize_petugas(saya))


def ubah(mid: str, perubahan: dict[str, Any], saya: str, pic: bool, baris: int | None = None,
         sidik_: str | None = None) -> dict[str, Any]:
    """Ubah sebagian kolom satu masalah (lihat `cari`: dicocokkan lewat sidik, bukan ID saja)."""
    perubahan = {k: v for k, v in perubahan.items() if v is not None}
    asing = set(perubahan) - MEDAN_PETUGAS - MEDAN_PIC
    if asing:
        raise EskalasiError(f"Kolom tidak dikenal: {', '.join(sorted(asing))}.")
    if not perubahan:
        raise EskalasiError("Tidak ada yang diubah.")
    if set(perubahan) & MEDAN_PIC and not pic:
        raise EskalasiError("Kode Tema dan Status Eskalasi hanya diisi PIC Eskalasi.")
    pil = opsi()
    with _lock:
        b = baca(refresh=True)
        m = cari(b["masalah"], mid, baris, sidik_)
        if not boleh_ubah(m, saya, pic):
            raise EskalasiError(f"Masalah {mid} milik {m['petugas'] or 'petugas lain'}. Hanya petugasnya atau "
                                "PIC Eskalasi yang boleh mengubah.")
        nilai: dict[str, Any] = {}
        agregasi = perubahan.get("agregasi", m["agregasi"])
        if agregasi == "Tidak":
            if perubahan.get("tim"):
                raise EskalasiError("Tidak perlu agregasi: tim tujuan tidak dipilih.")
            if "agregasi" in perubahan:
                perubahan = {**perubahan, "tim": None}
                nilai.update({f"tim:{t}": False for t in b["tim"]})
        perubahan = {k: v for k, v in perubahan.items() if v is not None}
        for f, v in perubahan.items():
            if f == "tim":
                tim = [t for t in b["tim"] if t in v]
                if not tim:
                    raise EskalasiError("Centang minimal satu tim tujuan.")
                nilai.update({f"tim:{t}": t in tim for t in b["tim"]})
            elif f == "evidence":
                nilai["evidence"] = _evidence(v)
            elif f == "tgl_awal":
                nilai["tgl_awal"] = serial(_cek_tanggal(str(v), "Tanggal awal permasalahan"))
            elif f == "tgl_selesai":
                nilai["tgl_selesai"] = serial(_cek_tanggal(str(v), "Tanggal selesai")) if v else ""
            elif f == "sumber":
                nilai["sumber"] = _cek_pilihan(v, pil["sumber"], "Sumber masalah", wajib=True)
            elif f == "permasalahan":
                nilai["permasalahan"] = _cek_pilihan(v, pil["permasalahan"], "Permasalahan", wajib=True)
            elif f == "tingkat":
                nilai["tingkat"] = _cek_pilihan(v, pil["tingkat"], "Tingkat")
            elif f == "status":
                nilai["status"] = _cek_pilihan(v, pil["status"], "Status tindak lanjut", wajib=True)
            elif f == "agregasi":
                if v not in ("Ya", "Tidak"):
                    raise EskalasiError("Perlu Agregasi harus Ya atau Tidak.")
                nilai["agregasi"] = v
            elif f == "kode_tema":
                nilai["kode_tema"] = _cek_pilihan(v, [t["kode"] for t in pil["tema"]], "Kode tema")
            elif f == "status_eskalasi":
                nilai["status_eskalasi"] = _cek_pilihan(v, list(STATUS_ESKALASI), "Status eskalasi", wajib=True)
            elif f == "keterangan":
                if len(str(v).strip()) < 10:
                    raise EskalasiError("Keterangan permasalahan minimal 10 huruf.")
                nilai["keterangan"] = str(v).strip()
            else:
                nilai[f] = str(v).strip()
        if "status" in nilai and "tgl_selesai" not in nilai:
            if nilai["status"] == "Selesai" and not m["tgl_selesai"]:
                nilai["tgl_selesai"] = serial(_hari_ini())
            elif nilai["status"] != "Selesai" and m["tgl_selesai"]:
                nilai["tgl_selesai"] = ""
        if nilai.get("jawaban") and not nilai.get("pengisi") and not m["pengisi"]:
            nilai["pengisi"] = saya
        pos = b["pos"]
        ss = _ss()
        if _baca_sidik(ss, pos, m["baris"], m["baris"]) != [m["sidik"]]:
            raise EskalasiError("Baris LK Eskalasi baru saja bergeser. Muat ulang lalu coba lagi.")
        ss.values_batch_update({"valueInputOption": "RAW",
                                "data": rentang(m["baris"], {pos[f]: v for f, v in nilai.items() if f in pos})})
        cache.drop("esk_baris")
    return next((x for x in baca(refresh=True)["masalah"] if x["baris"] == m["baris"] and x["sidik"] == m["sidik"]), m)
