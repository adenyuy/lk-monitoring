"""Warna sel tab WEEK ditulis langsung oleh aplikasi (format statis), bukan conditional formatting.

Dengan 19 ribu sekolah, puluhan aturan conditional formatting (banyak yang berupa rumus) membuat sheet berat.
Nilai komponen dan keterangan Kendala/TL berasal dari cutoff, jadi warnanya cukup dihitung sekali saat cutoff
(dan saat WEEK baru dibuat / isian ditulis dari aplikasi). Aturan warnanya sama dengan conditional formatting lama.
"""

import json
import logging
import secrets
from typing import Any

from . import lk_baru, todo
from .lk_baru import Sekolah, Tata

log = logging.getLogger(__name__)

POTONG = 400  # baris per permintaan updateCells (payload kecil supaya tidak diputus Google)


def _rgb(r: float, g: float, b: float) -> dict[str, float]:
    return {"red": r, "green": g, "blue": b}


TEKS_DASAR = _rgb(0.102, 0.133, 0.2)
TEKS_ABU = _rgb(0.541, 0.576, 0.651)
PUTIH = _rgb(1, 1, 1)


def _f(bg: dict | None, fg: dict = TEKS_DASAR, italic: bool = False, bold: bool = False) -> dict[str, Any]:
    # Ringkas (jutaan sel per cutoff): field yang tidak dikirim tetapi ada di FIELDS kembali ke bawaan
    # (tanpa latar, tidak miring, tidak tebal).
    tf: dict[str, Any] = {"foregroundColor": fg}
    if italic:
        tf["italic"] = True
    if bold:
        tf["bold"] = True
    out: dict[str, Any] = {"textFormat": tf}
    if bg is not None:
        out["backgroundColor"] = bg
    return out


# kolom komponen (N..AE)
HIJAU = _f(_rgb(0.843, 0.937, 0.875), _rgb(0.082, 0.451, 0.278))
MERAH = _f(_rgb(0.973, 0.843, 0.827), _rgb(0.706, 0.137, 0.094))
MERAH_TEBAL = _f(_rgb(0.973, 0.843, 0.827), _rgb(0.706, 0.137, 0.094), bold=True)
OREN = _f(_rgb(1, 0.949, 0.8), _rgb(0.541, 0.353, 0))
ABU = _f(_rgb(0.933, 0.941, 0.957), TEKS_ABU)
POLOS = _f(None)                       # tanpa latar: banding tabel terlihat
# kolom Kendala/Tindak Lanjut
ISI_SELESAI = _f(_rgb(0.91, 0.961, 0.925), TEKS_ABU, italic=True)
ISI_ABU = _f(_rgb(0.933, 0.941, 0.957), TEKS_ABU, italic=True)
ISI_OTOMATIS = _f(_rgb(0.929, 0.937, 0.957), TEKS_ABU, italic=True)
ISI_POLOS = _f(PUTIH)

FIELDS = ",".join(f"userEnteredFormat.{x}" for x in (
    "backgroundColor", "textFormat.foregroundColor", "textFormat.italic", "textFormat.bold"))

_TEKS_ABU_OTOMATIS = {todo.TANPA_DATA, todo.BERJALAN} | todo.MENUNGGU


def _angka(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


def warna_komponen(kode: str, v: Any) -> dict[str, Any]:
    t = str(v if v is not None else "").strip()
    k = t.casefold()
    if k in ("-", "belum due"):
        return ABU
    if k == "dikembalikan":
        return MERAH
    if k in ("belum ttd koor", "revisi"):
        return OREN
    if kode == "progres":
        p = todo.status("progres", v).persen  # cara baca angka sama dengan to-do
        if p is None:
            return POLOS
        return MERAH if p < 50 else OREN if p < 100 else HIJAU
    if "/" in t:
        try:
            a, b = (float(x) for x in t.split("/", 1))
        except ValueError:
            return POLOS
        return HIJAU if a >= b else MERAH
    if k == "sudah":
        return HIJAU
    if k == "belum":
        return MERAH
    return POLOS


def warna_tunggu(v: Any) -> dict[str, Any]:
    n = _angka(v)
    return MERAH_TEBAL if n is not None and n > 3 else POLOS


def warna_isian(kode: str, nilai_komponen: Any, teks: str) -> dict[str, Any]:
    if (teks or "").strip() in _TEKS_ABU_OTOMATIS:
        return ISI_OTOMATIS
    st = todo.status(kode, nilai_komponen).status
    if st == "selesai":
        return ISI_SELESAI
    if st in ("due", "kosong"):
        return ISI_ABU
    return ISI_POLOS


def peta_kolom(t: Tata) -> dict[int, tuple[str, str, int]]:
    """{kolom: (jenis, kode komponen, blok)}; jenis = komponen | tunggu | kendala | tl."""
    out: dict[int, tuple[str, str, int]] = {}
    for k, i in t.komponen.items():
        out[i] = ("komponen", k, 0)
    for k, i in t.tunggu.items():
        out[i] = ("tunggu", k, 0)
    for b, d in t.isian.items():
        for k, (a, c) in d.items():
            out[a] = ("kendala", k, b)
            out[c] = ("tl", k, b)
    return out


def format_baris(s: Sekolah, peta: dict[int, tuple[str, str, int]], a0: int, a1: int) -> list[dict[str, Any]]:
    """Format kolom a0..a1 satu sekolah."""
    out = []
    for j in range(a0, a1 + 1):
        jenis, kode, blok = peta.get(j, ("", "", 0))
        if jenis == "komponen":
            f = warna_komponen(kode, s.nilai.get(kode, ""))
        elif jenis == "tunggu":
            f = warna_tunggu(s.tunggu.get(kode, ""))
        elif jenis in ("kendala", "tl"):
            pasangan = s.isian.get(blok, {}).get(kode, ("", ""))
            f = warna_isian(kode, s.nilai.get(kode, ""), pasangan[0 if jenis == "kendala" else 1])
        else:
            f = POLOS
        out.append({"userEnteredFormat": f})
    return out


def _sel(sheet_id: int, baris: int, kolom: int, sel: list[dict[str, Any]]) -> dict[str, Any]:
    return {"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": baris - 1, "columnIndex": kolom},
                            "rows": [{"values": sel}], "fields": FIELDS}}


def hapus_conditional_format(ss, sheet_id: int) -> int:
    """Buang semua aturan conditional formatting di tab ini (warnanya kini ditulis aplikasi)."""
    meta = ss.fetch_sheet_metadata(params={"fields": "sheets(properties(sheetId),conditionalFormats(ranges(sheetId)))"})
    sh = next((x for x in meta["sheets"] if x["properties"]["sheetId"] == sheet_id), {})
    n = len(sh.get("conditionalFormats", []))
    if n:
        ss.batch_update({"requests": [{"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
                                      for i in range(n - 1, -1, -1)]})
    return n


KUNCI_META = "lkm_warna"
BATAS_SEL = 10000  # sel per panggilan batch_update (~1,7 MB, ~5 s; kiriman 4 MB sempat timeout)


def nama_format() -> dict[int, str]:
    return {id(v): k for k, v in globals().items() if isinstance(v, dict) and "textFormat" in v}


def _berkas_cache(week: int):
    from . import paths

    return paths.DATA_DIR / f"warna_week{week}.json"


def _baca_cache(week: int) -> dict[str, Any]:
    try:
        return json.loads(_berkas_cache(week).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - tidak ada / rusak: tulis semua
        return {}


def _token_sheet(ss, sheet_id: int) -> str:
    meta = ss.fetch_sheet_metadata(params={"fields": "sheets(properties(sheetId),developerMetadata)"})
    sh = next((x for x in meta["sheets"] if x["properties"]["sheetId"] == sheet_id), {})
    return next((m.get("metadataValue", "") for m in sh.get("developerMetadata", [])
                 if m.get("metadataKey") == KUNCI_META), "")


def _pasang_token(ss, sheet_id: int, token: str) -> None:
    ss.batch_update({"requests": [
        {"deleteDeveloperMetadata": {"dataFilter": {"developerMetadataLookup": {
            "metadataKey": KUNCI_META, "metadataLocation": {"sheetId": sheet_id}}}}},
        {"createDeveloperMetadata": {"developerMetadata": {
            "metadataKey": KUNCI_META, "metadataValue": token, "location": {"sheetId": sheet_id},
            "visibility": "DOCUMENT"}}}]})


def rencana_tulis(baris: list[tuple[int, str, list[str]]], lama: dict[str, list[str]],
                  a0: int) -> list[tuple[int, int, int]]:
    """[(baris, kolom awal, kolom akhir)] yang perlu ditulis: semua kolom untuk sekolah yang belum tercatat,
    selain itu rentang dari sel berubah pertama sampai terakhir. Baris berurutan dengan rentang sama digabung."""
    out: list[list[int]] = []
    for b, npsn, nama in baris:
        prev = lama.get(npsn)
        if prev is None or len(prev) != len(nama):
            j0, j1 = 0, len(nama) - 1
        else:
            beda = [j for j, (x, y) in enumerate(zip(prev, nama)) if x != y]
            if not beda:
                continue
            j0, j1 = beda[0], beda[-1]
        c0, c1 = a0 + j0, a0 + j1
        if out and out[-1][1] == c0 and out[-1][2] == c1 and out[-1][0] + out[-1][3] == b:
            out[-1][3] += 1
        else:
            out.append([b, c0, c1, 1])
    return [(b, c0, c1, n) for b, c0, c1, n in out]


def warnai_semua(week: int, semua: list[Sekolah], kemajuan=None, paksa: bool = False,
                 dari_week: int | None = None) -> dict[str, int]:
    """Tulis warna sel komponen dan Kendala/TL di tab WEEK, lalu buang conditional formatting lama.

    Warna terakhir per NPSN dicatat di laptop (warna_weekN.json) bersama token yang juga disimpan di metadata tab:
    cutoff berikutnya hanya mengirim sel yang warnanya berubah (warna ikut pindah saat baris diurutkan). Bila token
    tidak cocok (cutoff terakhir dari laptop lain) atau belum ada catatan, semua sel ditulis.
    `dari_week`: tab ini hasil duplikat WEEK itu (warnanya sama), jadi catatan WEEK itu dipakai sebagai awal."""
    ss = lk_baru._ss()
    t = lk_baru.tata(week)
    w = ss.worksheet(lk_baru.tab_week(week))
    peta = peta_kolom(t)
    a0, a1 = min(peta), max(peta)
    nama = nama_format()
    urut = sorted(semua, key=lambda s: s.baris)
    fmt = {s.baris: format_baris(s, peta, a0, a1) for s in urut}
    grid = [(s.baris, s.npsn, [nama[id(x["userEnteredFormat"])] for x in fmt[s.baris]]) for s in urut]

    asal = dari_week if dari_week is not None else week
    cache = {} if paksa else _baca_cache(asal)
    w_asal = w if asal == week else ss.worksheet(lk_baru.tab_week(asal))
    tanda = f"{a0}:{a1}:" + ",".join(f"{j}={peta[j][0]}/{peta[j][1]}" for j in sorted(peta))
    sah = bool(cache.get("tanda") == tanda and cache.get("sheet") == w_asal.id and cache.get("token")
               and cache.get("token") == _token_sheet(ss, w_asal.id))
    lama = cache.get("npsn", {}) if sah else {}
    rencana = rencana_tulis(grid, lama, a0)
    try:
        _berkas_cache(week).unlink(missing_ok=True)  # tulisan setengah jalan -> lain kali tulis semua
    except OSError:
        pass

    # potong rentang panjang (mis. tulis semua: 19 ribu baris berurutan) supaya tiap kiriman kecil
    potong = []
    for b, c0, c1, n in rencana:
        maks = max(1, BATAS_SEL // (c1 - c0 + 1))
        potong += [(b + i, c0, c1, min(maks, n - i)) for i in range(0, n, maks)]
    total = sum(n * (c1 - c0 + 1) for _, c0, c1, n in potong)
    req, sel, terkirim = [], 0, 0
    for k, (b, c0, c1, n) in enumerate(potong):
        rows = [{"values": fmt[b + i][c0 - a0:c1 - a0 + 1]} for i in range(n)]
        req.append({"updateCells": {"start": {"sheetId": w.id, "rowIndex": b - 1, "columnIndex": c0},
                                    "rows": rows, "fields": FIELDS}})
        sel += n * (c1 - c0 + 1)
        nanti = potong[k + 1] if k + 1 < len(potong) else None
        if nanti is None or sel + nanti[3] * (nanti[2] - nanti[1] + 1) > BATAS_SEL:
            ss.batch_update({"requests": req})
            terkirim += sel
            req, sel = [], 0
            if kemajuan:
                kemajuan(terkirim, total)
    dihapus = hapus_conditional_format(ss, w.id)

    token = secrets.token_hex(8)
    _pasang_token(ss, w.id, token)
    try:
        _berkas_cache(week).write_text(json.dumps({"tanda": tanda, "sheet": w.id, "token": token,
                                                   "npsn": {n: g for _, n, g in grid}}), encoding="utf-8")
    except OSError:
        log.warning("Catatan warna tidak tersimpan", exc_info=True)
    return {"baris": len(urut), "sel": terkirim, "semua": int(not sah), "aturan_dihapus": dihapus}


def warnai_isian(week: int, isi: list[tuple[Sekolah, int, str, str, str]], hanya_tl: bool = False) -> None:
    """Warna sel Kendala/TL yang baru ditulis dari aplikasi (teks otomatis abu-abu bisa jadi isian petugas)."""
    t = lk_baru.tata(week)
    w = lk_baru._ss().worksheet(lk_baru.tab_week(week))
    req = []
    for s, blok, kode, kendala, tl in isi:
        a, c = t.isian[blok][kode]
        nilai = s.nilai.get(kode, "")
        if hanya_tl:
            req.append(_sel(w.id, s.baris, c, [{"userEnteredFormat": warna_isian(kode, nilai, tl)}]))
        else:
            req.append(_sel(w.id, s.baris, a, [{"userEnteredFormat": warna_isian(kode, nilai, kendala)},
                                                {"userEnteredFormat": warna_isian(kode, nilai, tl)}]))
    if req:
        lk_baru._ss().batch_update({"requests": req})
