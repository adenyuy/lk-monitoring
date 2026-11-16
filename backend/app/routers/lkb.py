"""Halaman LK (format baru): kelompok fasil, to-do per sekolah, isian Kendala/TL, Log Komunikasi, tag."""

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import aktivitas, bimtek_lap, db, komunikasi, lk_baru, schedule, todo
from ..access import Access
from ..sheets import cache, daftar_nomor
from ..wa.status import mask
from .deps import require_access, require_admin

router = APIRouter(prefix="/api/lk2")


def blok_hari_ini() -> int:
    """Sesi isian hari ini, mengikuti rentang hari di judul SESI tab WEEK aktif (Senin–Rabu / Kamis–Sabtu)."""
    return lk_baru.blok_untuk(schedule.now().date())


def _jalan(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except lk_baru.LinkBelumAda as e:
        raise HTTPException(428, str(e)) from e
    except lk_baru.LkError as e:
        raise HTTPException(400, str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"LK tidak bisa dibaca: {e}") from e


def _konteks(refresh: bool = False) -> dict[str, Any]:
    if not komunikasi.petugas_saya():
        raise HTTPException(400, "Nama petugas belum dipilih.")
    sekolah = _jalan(komunikasi.sekolah_saya, refresh)
    fasil = komunikasi.kelompokkan(sekolah)
    rencana = {s.npsn: todo.rencana(s) for s in sekolah}
    try:
        logkom = lk_baru.baca_log_kom(refresh)
    except Exception:
        logkom = lk_baru.LogKom({}, {}, {})
    try:
        delta = komunikasi.jejak(sekolah, rencana)
    except Exception:
        delta = {}
    return {"sekolah": sekolah, "fasil": fasil, "rencana": rencana, "logkom": logkom, "delta": delta,
            "hari": schedule.now().date().isoformat(), "blok": blok_hari_ini(), "tag": komunikasi.tag_semua()}


def _info(k: dict[str, Any]) -> dict[str, Any]:
    hari = k["hari"]
    tgl = sorted(k["logkom"].tanggal)
    return {
        "week": _jalan(lk_baru.week_aktif),
        "hari": hari,
        "tanggal_panjang": schedule.tanggal_panjang(schedule.now().date()),
        "blok": k["blok"], "blok_label": lk_baru.label_blok(k["blok"]),
        "log_hari_ini": hari in k["logkom"].tanggal,
        "log_rentang": [tgl[0], tgl[-1]] if tgl else [],
        "wa_otomatis": komunikasi.wa_otomatis(),
        "cutoff": komunikasi.label_cutoff(),
        "kode": komunikasi.kode_label(),
    }


@router.get("")
def ringkasan(refresh: bool = False, _=Depends(require_access)) -> dict[str, Any]:
    k = _konteks(refresh)
    from . import dashboard

    dashboard.mulai_latar()  # siapkan dashboard di latar supaya langsung terbuka saat dipilih
    daftar = [komunikasi.ringkasan_fasil(f, k["rencana"], k["logkom"], k["hari"], k["blok"], k["tag"], k["delta"])
              for f in k["fasil"].values()]
    from .. import tahap as _tahap

    chat = komunikasi.peta_chat(_tahap.senin_iso())
    belum_balas = _koor_belum_balas([x["kunci"] for x in daftar])
    for x in daftar:
        x["tag_auto"] = [komunikasi.TAG_KOOR] if x["kunci"] in belum_balas else []
        c = chat.get(x["nomor"]) if x["nomor"] else None
        x["kom"] = komunikasi.status_kom(x, c)
        x["balasan"] = " ".join((c or {}).get("balasan", "").split())[:120]
        x["waktu_balasan"] = (c or {}).get("waktu", "")
    urut = {kode: i for i, (kode, *_r) in enumerate(komunikasi.KELOMPOK)}
    daftar.sort(key=lambda x: (urut[x["kelompok"]], -(x["perlu"] - x["lengkap"]), x["nama"].casefold()))
    n = Counter(x["kelompok"] for x in daftar)
    perlu = sum(x["perlu"] for x in daftar)
    lengkap = sum(x["lengkap"] for x in daftar)
    tahap = Counter(r.tahap for r in k["rencana"].values())
    fokus = Counter(r.fokus.judul for r in k["rencana"].values() if r.fokus)
    semua_tag = sorted({t for x in daftar for t in x["tag"]}, key=str.casefold)
    posisi = [{"kode": kode, "label": lbl,
               "fasil": sum(1 for x in daftar if x["posisi"].get(kode)),
               "sekolah": sum(x["posisi"].get(kode, 0) for x in daftar)} for kode, lbl, _ in komunikasi.POSISI]
    return {
        **_info(k),
        "total": {"fasil": len(daftar), "sekolah": len(k["sekolah"]), "perlu": perlu, "lengkap": lengkap,
                  "dihubungi": sum(1 for x in daftar if x["kode_hari_ini"]),
                  "todo": sum(len(r.todo) for r in k["rencana"].values())},
        "kelompok": [{"kode": kode, "label": lbl, "arti": arti, "jumlah": n.get(kode, 0)}
                     for kode, lbl, arti in komunikasi.KELOMPOK],
        "tahap": [{"kode": t, "jumlah": tahap.get(t, 0)} for t in ("pendahuluan", "berkala", "l50", "l100", "selesai")],
        "fokus": [{"judul": j, "jumlah": v} for j, v in fokus.most_common(8)],
        "indikator": komunikasi.indikator(daftar),
        "posisi": posisi,
        "kom": [{"kode": kode, "label": lbl, "arti": arti, "jumlah": sum(1 for x in daftar if x["kom"] == kode)}
                for kode, lbl, arti in komunikasi.STATUS_KOM],
        "tag": semua_tag,
        "bimtek": sorted({b for x in daftar for b in x["bimtek"]}, key=bimtek_lap.urut),
        "fasil": daftar,
    }


@router.get("/fasil/{kunci}")
def detail(kunci: str, _=Depends(require_access)) -> dict[str, Any]:
    k = _konteks()
    f = k["fasil"].get(kunci)
    if not f:
        raise HTTPException(404, "Fasil ini tidak ada di sekolah binaan Anda (mungkin data LK baru diperbarui).")
    r = komunikasi.ringkasan_fasil(f, k["rencana"], k["logkom"], k["hari"], k["blok"], k["tag"], k["delta"])
    sekolah = sorted(f.sekolah, key=lambda s: (not k["rencana"][s.npsn].todo, k["rencana"][s.npsn].tahap, s.nama))
    return {
        **_info(k),
        **r,
        "nomor_tersamar": mask(f.nomor) if f.nomor else "",
        "nomor_lain": [mask(n) for n in f.nomor_lain],
        "hp_koor": bool(f.hp_koor),
        "nomor_koor": (daftar_nomor(f.hp_koor) or [""])[0],
        "koor_tersamar": mask((daftar_nomor(f.hp_koor) or [""])[0]) if f.hp_koor else "",
        "tag_auto": [komunikasi.TAG_KOOR] if f.kunci in _koor_belum_balas([f.kunci]) else [],
        "koor_fasil": _koor_fasil(k, f),
        "sekolah_detail": [{**todo.ringkas(s, k["rencana"][s.npsn], k["blok"]), "kepsek": s.kepsek,
                            "punya_hp_kepsek": bool(s.hp_kepsek),
                            **_kepsek_chat(s),
                            "delta": k["delta"].get(s.npsn)} for s in sekolah],
    }


def _kepsek_chat(s) -> dict[str, Any]:
    """Nomor kepala sekolah + status chat terakhir dengannya (untuk tab Sekolah di panel fasil)."""
    n = (daftar_nomor(s.hp_kepsek) or [""])[0]
    st = db.query_one("SELECT status, waktu_balasan, dicek FROM chat_status WHERE nomor = ?", (n,)) if n else None
    return {"nomor_kepsek": n, "kepsek_tersamar": mask(n) if n else "",
            "kepsek_chat": {"status": st["status"], "waktu": st["waktu_balasan"] or st["dicek"]} if st else None}


@router.get("/opsi")
def opsi(_=Depends(require_access)) -> dict[str, Any]:
    return {"kendala": _jalan(lk_baru.opsi_kendala),
            "komponen": [{"kode": x.kode, "label": x.label, "tahap": x.tahap, "pelaku": x.pelaku}
                         for x in lk_baru.KOMPONEN]}


class IsiItem(BaseModel):
    npsn: str = Field(min_length=1, max_length=20)
    kode: str
    kendala: str = Field("", max_length=500)
    tl: str = Field("", max_length=1000)


class IsiReq(BaseModel):
    isi: list[IsiItem] = Field(min_length=1, max_length=300)
    blok: int | None = Field(None, ge=1, le=2)
    kunci: str = ""


@router.post("/isi")
def isi(req: IsiReq, _=Depends(require_access)) -> dict[str, Any]:
    blok = req.blok or blok_hari_ini()
    sekolah = {s.npsn: s for s in _jalan(komunikasi.sekolah_saya)}
    tulis = []
    for x in req.isi:
        s = sekolah.get(x.npsn.strip())
        if not s:
            raise HTTPException(403, f"NPSN {x.npsn} bukan sekolah binaan Anda.")
        if x.kode not in lk_baru.KOMP:
            raise HTTPException(400, f"Komponen {x.kode} tidak dikenal.")
        tulis.append((s, blok, x.kode, " ".join(x.kendala.split()), x.tl.strip()))
    week = _jalan(lk_baru.week_aktif)
    _jalan(lk_baru.tulis_isian, week, tulis)
    nama = sorted({s.nama for s, *_ in tulis})
    s0 = tulis[0][0]
    nomor = s0.nomor_fasil()
    aktivitas.catat(nomor[0] if nomor else f"nama:{s0.fasil}", "lk",
                    f"Kendala/TL {len(tulis)} isian ({lk_baru.label_blok(blok)}): " + ", ".join(nama[:3])
                    + (f", +{len(nama) - 3} lagi" if len(nama) > 3 else ""), s0.fasil)
    return {"ok": True, "ditulis": len(tulis), "blok": blok}


class TeleponReq(BaseModel):
    kunci: str
    hasil: str = Field(pattern="^(diangkat|tidak)$")


@router.post("/telepon")
def catat_telepon(req: TeleponReq, _=Depends(require_access)) -> dict[str, Any]:
    """Catat telepon ke fasil. Diangkat -> TP di Log Komunikasi hari ini; tidak diangkat -> hanya dicatat."""
    from .. import telepon

    fasil = _jalan(komunikasi.fasil_saya).get(req.kunci)
    if not fasil:
        raise HTTPException(404, "Fasil tidak ditemukan.")
    return {"ok": True, **_jalan(komunikasi.catat_telepon, fasil, req.hasil), "riwayat": telepon.riwayat(fasil.nomor)}


class KomReq(BaseModel):
    kunci: str
    kode: str = Field("", max_length=3)
    tanggal: str | None = None


@router.post("/komunikasi")
def set_komunikasi(req: KomReq, _=Depends(require_access)) -> dict[str, Any]:
    kode = req.kode.strip().upper()
    if kode and kode not in lk_baru.KODE_KOMUNIKASI:
        raise HTTPException(400, "Kode komunikasi tidak dikenal.")
    hari = req.tanggal or schedule.now().date().isoformat()
    fasil = _jalan(komunikasi.fasil_saya).get(req.kunci)
    if not fasil:
        raise HTTPException(404, "Fasil tidak ditemukan.")
    npsn = [s.npsn for s in fasil.sekolah]
    n = _jalan(lk_baru.tulis_log_kom, hari, {x: kode for x in npsn})
    komunikasi.lupakan_auto(hari, npsn)
    aktivitas.catat(fasil.nomor or f"nama:{fasil.nama}", "kom",
                    f"{kode or 'Dikosongkan'}" + (f" · {lk_baru.KODE_KOMUNIKASI[kode]}" if kode else "")
                    + f" ({hari[8:10]}/{hari[5:7]}, {n} sekolah)", fasil.nama)
    return {"ok": True, "ditulis": n}


def _koor_belum_balas(kunci: list[str]) -> set[str]:
    try:
        return komunikasi.koor_belum_balas(kunci)
    except Exception:  # noqa: BLE001 - tag hanya penanda; jangan menggagalkan halaman
        return set()


def _koor_fasil(k: dict[str, Any], f) -> list[dict[str, Any]]:
    """Fasil binaan Anda yang koordinatornya sama dengan `f`, dengan tanda sulit dihubungi (untuk template koordinator
    "semua fasil binaan yang sulit dihubungi"). Fasil `f` sendiri ikut, paling atas."""
    from .. import telepon

    if not f.koor:
        return []
    kk = komunikasi.normalize_petugas(f.koor)
    mulai = min(k["logkom"].tanggal, default="")
    out = []
    for g in k["fasil"].values():
        if komunikasi.normalize_petugas(g.koor or "") != kk:
            continue
        kode = komunikasi.kode_fasil(g, k["logkom"])
        perlu, alasan = telepon.perlu(kode, k["hari"], mulai)
        akhir = kode.get(k["hari"], "") or next((kode[d] for d in sorted(kode, reverse=True) if d <= k["hari"]), "")
        sulit = perlu or akhir.upper() in telepon.SULIT
        out.append({"kunci": g.kunci, "nama": g.nama, "ptn": g.ptn, "kode": akhir, "sulit": sulit,
                    "alasan": alasan or (telepon.ARTI_SULIT.get(akhir.upper(), "") if sulit else ""),
                    "sekolah": len(g.sekolah), "ini": g.kunci == f.kunci})
    out.sort(key=lambda x: (not x["ini"], not x["sulit"], x["nama"].casefold()))
    return out


class KoorReq(BaseModel):
    kunci: list[str] = Field(min_length=1, max_length=60)


@router.post("/koor-dihubungi")
def koor_dihubungi(req: KoorReq, _=Depends(require_access)) -> dict[str, Any]:
    """Pesan ke koordinator soal fasil-fasil ini terkirim dari aplikasi: K di Log Komunikasi hari ini."""
    k = _konteks()
    daftar = [k["fasil"][x] for x in dict.fromkeys(req.kunci) if x in k["fasil"]]
    if not daftar:
        raise HTTPException(404, "Fasil tidak ada di sekolah binaan Anda.")
    nomor = (daftar_nomor(daftar[0].hp_koor) or [""])[0]
    return _jalan(komunikasi.catat_koor, daftar, nomor)


class UbahFasilReq(BaseModel):
    kunci: str = Field(max_length=200)
    nama: str = Field(max_length=120)
    nomor_baru: str = Field("", max_length=40)


@router.post("/fasil-ubah")
def ubah_fasil(req: UbahFasilReq, _=Depends(require_access)) -> dict[str, Any]:
    """Ubah nama / nomor WhatsApp fasil di LK WEEK aktif (hanya sekolah binaan petugas ini)."""
    from .. import ubah_fasil_lk

    def jalan() -> dict[str, Any]:
        try:
            return ubah_fasil_lk.ubah(req.kunci, req.nama, req.nomor_baru)
        except ubah_fasil_lk.UbahFasilError as e:
            raise HTTPException(400, str(e)) from e

    return _jalan(jalan)


class TagReq(BaseModel):
    kunci: str
    tag: list[str] = Field(default_factory=list, max_length=6)


@router.post("/tag")
def set_tag(req: TagReq, _=Depends(require_access)) -> dict[str, Any]:
    return {"tag": komunikasi.set_tag(req.kunci, req.tag)}


class WaReq(BaseModel):
    aktif: bool


@router.post("/wa-otomatis")
def wa_otomatis(req: WaReq, _=Depends(require_access)) -> dict[str, Any]:
    db.set_setting("wa_otomatis", req.aktif)
    if not req.aktif:
        try:
            from ..wa.browser import worker

            if worker.browser_open():
                worker.shutdown()
        except Exception:
            pass
    return {"wa_otomatis": req.aktif}


@router.post("/muat-ulang")
def muat_ulang(_=Depends(require_access)) -> dict[str, Any]:
    cache.clear()
    return {"ok": True}


class LinkReq(BaseModel):
    link: str = Field(min_length=10, max_length=500)


@router.get("/link")
def link_info(acc: Access = Depends(require_access)) -> dict[str, Any]:
    try:
        sid = lk_baru.sheet_id()
    except lk_baru.LinkBelumAda:
        return {"terpasang": False, "admin": acc.admin}
    return {"terpasang": True, "admin": acc.admin, "link": f"https://docs.google.com/spreadsheets/d/{sid}/edit"}


@router.post("/link")
def pasang_link(req: LinkReq, acc: Access = Depends(require_access)) -> dict[str, Any]:
    _jalan(lk_baru.pasang_link, req.link, acc.admin)
    return {"ok": True, "untuk_tim": acc.admin}


@router.get("/admin/petugas")
def semua_petugas(_=Depends(require_admin)) -> dict[str, Any]:
    return {"petugas": _jalan(lk_baru.daftar_petugas)}


# ---------- tombol bulat & notifikasi ----------

def _fasil_notif(x: dict[str, Any], alasan: str, kategori: str) -> dict[str, Any]:
    return {"nomor": x["kunci"], "nama": x["nama"], "kategori": kategori, "alasan": alasan,
            "dibalas": kategori == "balas", "di_broadcast": True, "p1": 0, "p2": 0, "p3": 0,
            "lengkap": x["lengkap"], "perlu": x["perlu"]}


@router.get("/pengingat")
def pengingat(_=Depends(require_access)) -> dict[str, Any]:
    """Notifikasi menu cepat: fasil menunggu balasan, belum tercatat di Log Komunikasi, perlu ditelepon,
    dan isian sesi yang belum lengkap."""
    from .. import blast, store, tahap

    k = _konteks()
    daftar = {f.kunci: komunikasi.ringkasan_fasil(f, k["rencana"], k["logkom"], k["hari"], k["blok"], k["tag"],
                                                  k["delta"]) for f in k["fasil"].values()}
    items: list[dict[str, Any]] = []
    perlu = store.perlu_dibalas(tahap.senin_iso())
    balas = []
    for x in perlu:
        f = daftar.get(x["nomor"])
        if not f:
            continue
        cuplik = " ".join((x["balasan_terakhir"] or "").split())
        cuplik = cuplik if len(cuplik) <= 60 else cuplik[:59] + "…"
        balas.append(_fasil_notif(f, f"Membalas {x['waktu_balasan'][11:16].replace(':', '.')}: “{cuplik}”", "balas"))
    if balas:
        items.append({"jenis": "perlu_balas", "judul": f"{len(balas)} fasil menunggu balasan Anda",
                      "isi": "Mereka sudah membalas dan belum dibalas lagi.", "total": len(balas), "fasil": balas})
    hari_kerja = schedule.now().weekday() < 6  # Log Komunikasi Senin–Sabtu
    if hari_kerja and k["hari"] in k["logkom"].tanggal:
        belum = [f for f in daftar.values() if f["kelompok"] == "belum"]
        if belum:
            items.append({"jenis": "tindak_lanjut", "judul": f"{len(belum)} fasil belum dicatat di Log Komunikasi hari ini",
                          "isi": "Hubungi lalu catat kodenya (T, T1, T2, TP, R, C, N) di halaman LK.",
                          "total": len(belum),
                          "fasil": [_fasil_notif(f, f"{f['perlu']} sekolah masih punya to-do", "menunggu") for f in belum]})
    telp = [f for f in daftar.values() if f["kelompok"] == "perlu_telepon" or f["belum_ditelepon"]]
    if telp:
        items.append({"jenis": "chat_manual", "judul": f"{len(telp)} fasil perlu ditelepon",
                      "isi": "2 hari kerja hanya dibaca atau tidak sampai. Telepon, lalu tekan Catat telepon di halaman fasil.",
                      "total": len(telp), "fasil": [_fasil_notif(f, "Chat tidak sampai / hanya dibaca", "manual")
                                                    for f in telp]})
    total_perlu = sum(f["perlu"] for f in daftar.values())
    lengkap = sum(f["lengkap"] for f in daftar.values())
    if hari_kerja and total_perlu > lengkap:
        items.append({"jenis": "lanjut", "judul": f"Isian sesi {lk_baru.label_blok(k['blok'])}: {lengkap}/{total_perlu} sekolah",
                      "isi": "Kendala dan Tindak Lanjut cukup diisi di komponen yang jadi to-do; sisanya terisi otomatis."})
    st = blast.mesin.state
    if st.running:
        items.insert(0, {"jenis": "lanjut", "judul": f"Blast berjalan: {st.diproses}/{st.total}",
                         "isi": f"{st.judul}. {st.terkirim} terkirim, {st.gagal} gagal."})
    return {"tanggal": k["hari"], "items": items}


@router.get("/bubble")
def bubble(_=Depends(require_access)) -> dict[str, Any]:
    """Ringkasan untuk lingkaran tombol bulat: isian sesi hari ini dan Log Komunikasi hari ini."""
    from .. import blast

    k = _konteks()
    daftar = [komunikasi.ringkasan_fasil(f, k["rencana"], k["logkom"], k["hari"], k["blok"], k["tag"], k["delta"])
              for f in k["fasil"].values()]
    perlu = sum(x["perlu"] for x in daftar)
    st = blast.mesin.state
    return {"blok_label": lk_baru.label_blok(k["blok"]), "perlu": perlu, "lengkap": sum(x["lengkap"] for x in daftar),
            "fasil": len(daftar), "dicatat": sum(1 for x in daftar if x["kode_hari_ini"]),
            "log_hari_ini": k["hari"] in k["logkom"].tanggal,
            "blast": {"berjalan": st.running, "diproses": st.diproses, "total": st.total, "jeda": st.paused}}
