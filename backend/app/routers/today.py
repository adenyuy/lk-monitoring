"""Layar Hari ini: ringkasan, rel sesi, isi sesi, detail fasilitator."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import aktivitas, config, db, schedule, send_queue, store, tahap
from ..schedule import jam
from ..sender import NotAllowed, sender
from ..sheets import filter_petugas, nomor_key, read_broadcast, read_lk, sekolah_per_fasil
from ..wa.status import mask
from .deps import require_feature, require_login

from ..sheets import week_aktif  # noqa: E402

router = APIRouter(prefix="/api")
wa_blast = require_feature("wa_blast")

RAIL_MULAI, RAIL_SAMPAI = 10 * 60, 22 * 60  # menit, untuk posisi penanda "sekarang"


def _menit(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _sekolah_map() -> dict[str, list]:
    """{nomor_key: [Sekolah]} milik petugas dari LK WEEK n. Kosong bila LK tidak terbaca."""
    try:
        petugas = db.get_setting("nama_petugas") or ""
        return sekolah_per_fasil(read_lk(week_aktif()), petugas)
    except Exception:
        return {}


def _status_tampil(send_status: str, nomor: str, chats: dict) -> str:
    if send_status == "terkirim":
        c = chats.get(nomor, {}).get("status")
        return {"dibalas": "Dibalas", "dibaca": "Dibaca"}.get(c, "Terkirim")
    return {"gagal": "Gagal", "dilewati": "Dilewati", "dicoba": "Dicoba"}.get(send_status, send_status.title())


def _sesi_status(sesi: config.Sesi, now: datetime, terkirim: int, aktif_no: int | None, berikutnya_no: int | None,
                 libur: bool) -> str:
    if libur:
        return "Libur"
    t = now.hour * 60 + now.minute
    if t > _menit(sesi.sampai):
        return "Selesai"
    if aktif_no == sesi.no:
        return "Kuota habis" if terkirim >= sesi.kuota else "Berjalan"
    return "Berikutnya" if berikutnya_no == sesi.no else "Belum"


def _context() -> dict[str, Any]:
    try:
        items = sender.antrean()
        k = sender.kondisi(items)
    except NotAllowed as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Sheet Broadcast tidak bisa dibaca: {e}") from e
    now = schedule.now()
    tanggal = schedule.tanggal_str(now.date())
    total, per = store.counts(tanggal)
    return {"items": items, "kondisi": k, "now": now, "tanggal": tanggal, "total": total, "per": per}


def _lk(sekolah: list) -> dict[str, int]:
    """Ringkasan LK satu fasil: jumlah sekolah dan sebaran prioritas."""
    out = {"jumlah": len(sekolah), "p1": 0, "p2": 0, "p3": 0, "selesai": 0}
    for s in sekolah:
        p = (s.prioritas or "").strip().lower()
        key = {"prioritas 1": "p1", "prioritas 2": "p2", "prioritas 3": "p3", "selesai": "selesai"}.get(p)
        if key:
            out[key] += 1
    return out


def _rencana(ctx: dict[str, Any], no: int) -> list[send_queue.Item]:
    """Perkiraan fasil yang akan dikirimi di sesi `no` hari ini (antrean dipotong per kuota sesi)."""
    now, k = ctx["now"], ctx["kondisi"]
    sesi = schedule.sesi_by_no(no)
    t = now.hour * 60 + now.minute
    if t > _menit(sesi.sampai) or k.kode in ("akhir_pekan", "batas_harian"):
        return []
    eligible = send_queue.eligible(ctx["items"])
    batas = int(db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT))
    sisa_harian = max(0, batas - ctx["total"])
    offset = 0
    for s in config.SESI:
        if s.no >= no:
            break
        if t <= _menit(s.sampai):  # sesi lebih awal yang masih/akan berjalan memakai antrean lebih dulu
            offset += max(0, s.kuota - ctx["per"].get(s.no, 0))
    kapasitas = max(0, min(sesi.kuota - ctx["per"].get(no, 0), sisa_harian - offset))
    return eligible[offset: offset + kapasitas]


MAKS_TINDAK_LANJUT = 8


def _pengingat(ctx: dict[str, Any], libur: bool) -> list[dict[str, Any]]:
    """Pengingat di Hari ini: sesi terlewat, lanjutan dari hari sebelumnya, chat yang perlu ditindaklanjuti."""
    now, k, items = ctx["now"], ctx["kondisi"], ctx["items"]
    out: list[dict[str, Any]] = []
    t = now.hour * 60 + now.minute
    belum = len(send_queue.eligible(items))
    batas = int(db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT))
    sisa_harian = max(0, batas - ctx["total"])
    hari = schedule.HARI

    if not libur and belum and sisa_harian:
        lewat = [s for s in config.SESI if t > _menit(s.sampai) and ctx["per"].get(s.no, 0) < s.kuota]
        kapasitas = sum(max(0, s.kuota - ctx["per"].get(s.no, 0)) for s in config.SESI if t <= _menit(s.sampai))
        bisa = min(sisa_harian, kapasitas, belum)
        if lewat:
            kosong = sum(s.kuota - ctx["per"].get(s.no, 0) for s in lewat)
            nama = ", ".join(str(s.no) for s in lewat)
            if bisa:
                isi = (f"{kosong} slot pesan di sesi itu tidak terpakai. Fasil yang belum dikirimi tidak hilang: "
                       f"mereka tetap di antrean dan ikut di sesi berikutnya. Hari ini masih bisa {bisa} pesan lagi.")
            else:
                besok = hari[k.mulai_berikutnya.weekday()] if k.mulai_berikutnya else "hari kerja berikutnya"
                isi = (f"Hari ini sudah tidak ada sesi lagi. {belum} fasil yang belum dikirimi lanjut {besok} "
                       f"mulai sesi 1.")
            out.append({"jenis": "terlewat", "judul": f"Sesi {nama} terlewat", "isi": isi})
        elif ctx["total"] == 0 and t <= _menit(config.SESI[-1].sampai):
            minggu = send_queue.senin(now.date())
            sudah_minggu_ini = any(
                x["status"] == "terkirim" and send_queue.senin(datetime.fromisoformat(x["waktu"]).date()) == minggu
                for x in store.sends_real()
            )
            if sudah_minggu_ini:
                out.append({"jenis": "lanjut", "judul": f"Lanjutan dari kemarin: {belum} fasil belum dikirimi",
                            "isi": "Mereka ikut di sesi hari ini. Fasil yang sudah dikirimi minggu ini tidak dikirimi "
                                   "lagi sampai Senin, kecuali Anda menekan Kirim ulang."})
            elif now.weekday() == 0:
                out.append({"jenis": "minggu_baru", "judul": "Minggu baru dimulai",
                            "isi": f"Semua {belum} fasil di Broadcast masuk antrean lagi. Isian LK minggu ini "
                                   f"mulai di sesi Senin–Rabu (kolom P–U)."})

    if not libur and not belum and items and any(i.status == "terkirim" for i in items):
        out.append({"jenis": "broadcast_selesai", "judul": "Broadcast minggu ini sudah terkirim ke semua fasil",
                     "isi": "Sisa minggu ini untuk tindak lanjut: chat fasil yang belum membalas dan lengkapi isian "
                            "LK. Senin depan Broadcast dikirim lagi dengan data progres terbaru."})

    # Chat yang perlu ditindaklanjuti: sudah dikirimi minggu ini, isian LK belum lengkap
    smap = _sekolah_map()
    if smap:
        chats = store.chat_status_all()
        manual = store.tahap_all()
        blok = tahap.blok_hari_ini()
        minggu = send_queue.senin(now.date())
        terkirim = {x["nomor"] for x in store.sends_real() if x["status"] == "terkirim"
                    and send_queue.senin(datetime.fromisoformat(x["waktu"]).date()) == minggu}
        daftar: list[dict[str, Any]] = []
        for it in items:
            n = it.nomor
            man = manual.get(n, {})
            if not n or not (n in terkirim or man.get("terkirim", {}).get("nilai")):
                continue
            perlu = [s for s in smap.get(nomor_key(n), []) if tahap.perlu_isian(s)]
            if not perlu or all(tahap.sekolah_lengkap(s, blok) for s in perlu):
                continue
            st = chats.get(n, {}).get("status", "")
            dibalas = st == "dibalas" or man.get("dibalas", {}).get("nilai")
            daftar.append({"nomor": n, "nama": it.nama_fasil, "dibalas": bool(dibalas),
                           "alasan": "Sudah membalas, isian LK belum lengkap" if dibalas
                           else ("Sudah dibaca, belum membalas" if st == "dibaca" else "Belum membalas")})
        if daftar:
            daftar.sort(key=lambda x: (not x["dibalas"], x["nama"].casefold()))
            n_balas = sum(1 for x in daftar if x["dibalas"])
            judul = (f"{n_balas} fasil sudah membalas, isian LK-nya belum lengkap" if n_balas
                     else f"{len(daftar)} fasil belum membalas")
            isi = "Chat dan isi LK bisa kapan saja, tidak terikat jam sesi. Klik nama fasil untuk melanjutkan."
            if n_balas and len(daftar) > n_balas:
                isi = f"{len(daftar) - n_balas} lainnya belum membalas. " + isi
            out.append({"jenis": "tindak_lanjut", "judul": judul, "isi": isi, "total": len(daftar),
                        "fasil": daftar[:MAKS_TINDAK_LANJUT]})
    return out


@router.get("/today")
def today(_=Depends(wa_blast)) -> dict[str, Any]:
    ctx = _context()
    now, k, items = ctx["now"], ctx["kondisi"], ctx["items"]
    akhir_pekan_ok = bool(db.get_setting("kirim_akhir_pekan", False))
    libur = schedule.is_weekend(now.date()) and not akhir_pekan_ok
    aktif = schedule.sesi_at(now)
    berikutnya = k.sesi_berikutnya if k.mulai_berikutnya and k.mulai_berikutnya.date() == now.date() else None

    sends_today = store.sends_on(ctx["tanggal"])
    chats = store.chat_status_all()
    nomor_hari_ini = {s["nomor"] for s in sends_today if s["status"] == "terkirim" and not s["coba"]}
    dibalas = sum(1 for n in nomor_hari_ini if chats.get(n, {}).get("status") == "dibalas")

    menit_now = now.hour * 60 + now.minute
    pct = (menit_now - RAIL_MULAI) / (RAIL_SAMPAI - RAIL_MULAI) * 100
    batas = int(db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT))
    sisa_menit = (_menit(aktif.sampai) - menit_now + 1) if aktif else None
    menuju = None
    if k.mulai_berikutnya and not k.bisa_kirim:
        menuju = max(0, int((k.mulai_berikutnya - now).total_seconds() // 60))

    return {
        "tanggal": ctx["tanggal"],
        "tanggal_panjang": schedule.tanggal_panjang(now.date()),
        "jam_sekarang": now.strftime("%H.%M"),
        "posisi_sekarang": max(0.0, min(100.0, round(pct, 2))),
        "kondisi": k.as_dict(),
        "sesi_aktif": aktif.no if aktif else None,
        "sisa_menit_sesi": sisa_menit,
        "menit_ke_berikutnya": menuju,
        "batas_harian": batas,
        "terkirim_hari_ini": ctx["total"],
        "dibalas_hari_ini": dibalas,
        "belum_dikirim": len(send_queue.eligible(items)),
        "total_fasil": len(items),
        "sesi": [
            {
                "no": s.no, "mulai": jam(s.mulai), "sampai": jam(s.sampai), "kuota": s.kuota,
                "terkirim": ctx["per"].get(s.no, 0),
                "perkiraan": len(_rencana(ctx, s.no)),
                "durasi_menit": _menit(s.sampai) - _menit(s.mulai) + 1,
                "status": _sesi_status(s, now, ctx["per"].get(s.no, 0), aktif.no if aktif else None,
                                       berikutnya.no if berikutnya else None, libur),
            }
            for s in config.SESI
        ],
        "pengiriman": sender.snapshot(),
    }


@router.get("/pengingat")
def pengingat(_=Depends(wa_blast)) -> dict[str, Any]:
    """Notifikasi untuk tombol bulat: sesi terlewat, lanjutan, tindak lanjut chat."""
    ctx = _context()
    akhir_pekan_ok = bool(db.get_setting("kirim_akhir_pekan", False))
    libur = schedule.is_weekend(ctx["now"].date()) and not akhir_pekan_ok
    return {"tanggal": ctx["tanggal"], "items": _pengingat(ctx, libur)}


@router.get("/sessions/{no}")
def session_detail(no: int, _=Depends(wa_blast)) -> dict[str, Any]:
    if no not in {s.no for s in config.SESI}:
        raise HTTPException(404, "Sesi tidak ada.")
    ctx = _context()
    k = ctx["kondisi"]
    sesi = schedule.sesi_by_no(no)
    sekolah = _sekolah_map()
    chats = store.chat_status_all()

    def lk(nomor: str) -> dict[str, int]:
        return _lk(sekolah.get(nomor_key(nomor), []))

    # Yang sudah diproses di sesi ini hari ini (terbaru di atas)
    sudah = []
    for s in store.sends_on(ctx["tanggal"]):
        if s["sesi"] != no:
            continue
        sudah.append({
            "jam": datetime.fromisoformat(s["waktu"]).strftime("%H.%M"),
            "nama_fasil": s["nama_fasil"], "nomor": s["nomor"], "lk": lk(s["nomor"]),
            "status": _status_tampil(s["status"], s["nomor"], chats) if not s["coba"] else "Dicoba",
            "keterangan": s["keterangan"],
        })
    sudah.reverse()

    aktif_no = k.sesi.no if k.sesi else None
    akan = [
        {
            "jam": "", "nama_fasil": it.nama_fasil, "nomor": it.nomor, "lk": lk(it.nomor),
            "status": "Berikutnya" if (j == 0 and no == aktif_no) else "Menunggu",
            "keterangan": "Kirim ulang diminta" if it.diulang else ("Akan dicoba ulang" if it.status == "gagal" else ""),
        }
        for j, it in enumerate(_rencana(ctx, no))
    ]

    return {
        "no": no, "mulai": jam(sesi.mulai), "sampai": jam(sesi.sampai), "kuota": sesi.kuota,
        "terkirim": ctx["per"].get(no, 0),
        "aktif": bool(k.sesi and k.sesi.no == no and k.bisa_kirim),
        "kondisi": k.as_dict(),
        "sudah": sudah,
        "akan": akan,
    }


@router.get("/fasil/{nomor}")
def fasil_detail(nomor: str, _=Depends(wa_blast)) -> dict[str, Any]:
    petugas = db.get_setting("nama_petugas") or ""
    try:
        rows = [r for r in filter_petugas(read_broadcast(), petugas) if r.nomor == nomor]
    except Exception as e:
        raise HTTPException(502, f"Sheet Broadcast tidak bisa dibaca: {e}") from e
    row = rows[0] if rows else None

    sends = [s for s in store.sends_real() if s["nomor"] == nomor]
    last = sends[-1] if sends else None
    chat = store.chat_status_all().get(nomor)
    sekolah = _sekolah_map().get(nomor_key(nomor), [])

    if last and last["status"] == "terkirim":
        status = {"dibalas": "Sudah membalas", "dibaca": "Dibaca, belum membalas"}.get(
            (chat or {}).get("status", ""), "Terkirim, belum dibaca")
    elif last and last["status"] == "gagal":
        status = f"Gagal: {last['keterangan']}"
    else:
        status = "Belum dikirim"

    blok = tahap.blok_hari_ini()
    nama_lk = sekolah[0].fasil if sekolah else ""
    minggu = send_queue.senin(schedule.now().date())
    terkirim_minggu_ini = [x for x in sends if x["status"] == "terkirim"
                           and send_queue.senin(datetime.fromisoformat(x["waktu"]).date()) == minggu]
    diminta = store.ulang_all().get(nomor, "")
    ulang_aktif = bool(diminta and terkirim_minggu_ini and diminta > terkirim_minggu_ini[-1]["waktu"])
    return {
        "nama_fasil": row.nama_fasil if row else (last["nama_fasil"] if last else (nama_lk or "Fasilitator")),
        "di_broadcast": row is not None,
        "kirim_ulang": {"bisa": bool(terkirim_minggu_ini) and row is not None, "diminta": ulang_aktif},
        "blok": {"no": blok, "label": tahap.BLOK_LABEL[blok], "kolom": tahap.BLOK_KOLOM_LABEL[blok]},
        "tahap": tahap.hitung(nomor, sekolah, sends, chat, store.tahap_all().get(nomor, {}), blok),
        "nomor_tersamar": mask(nomor),
        "status": status,
        "pesan": row.pesan if row else "",
        "waktu_kirim": datetime.fromisoformat(last["waktu"]).strftime("%d/%m %H.%M") if last else "",
        "status_kirim": last["status"] if last else "",
        "balasan": (chat or {}).get("balasan_terakhir", ""),
        "waktu_balasan": (chat or {}).get("waktu_balasan", ""),
        "sekolah": [
            {"npsn": s.npsn, "nama": s.nama, "progres": s.progres, "prioritas": s.prioritas,
             "submit": s.submit, "reviu": s.reviu, "komunikasi": s.komunikasi,
             "isian": {str(b): v for b, v in s.isian.items()}}
            for s in sorted(sekolah, key=lambda x: (x.prioritas or "Z", x.nama))
        ],
    }


class TahapReq(BaseModel):
    kode: str
    selesai: bool | None  # None = kembalikan ke deteksi otomatis


@router.post("/fasil/{nomor}/tahap")
def fasil_tahap(nomor: str, req: TahapReq, _=Depends(wa_blast)) -> dict[str, Any]:
    if req.kode not in {k for k, _ in tahap.TAHAP} or req.kode == "lk_lengkap":
        raise HTTPException(400, "Tahap ini tidak bisa dicentang manual.")
    label = dict(tahap.TAHAP)[req.kode]
    if req.selesai is None:
        store.delete_tahap(nomor, req.kode)
        aktivitas.catat(nomor, "tahap", f"Centang manual “{label}” dihapus, kembali otomatis")
    else:
        store.set_tahap(nomor, req.kode, req.selesai, "manual", schedule.now().isoformat(timespec="seconds"))
        aktivitas.catat(nomor, "tahap", f"“{label}” ditandai {'selesai' if req.selesai else 'belum'} secara manual")
    return fasil_detail(nomor)


class UlangReq(BaseModel):
    aktif: bool


@router.post("/fasil/{nomor}/kirim-ulang")
def fasil_kirim_ulang(nomor: str, req: UlangReq, _=Depends(wa_blast)) -> dict[str, Any]:
    """Minta pesan Broadcast dikirim ulang ke fasil ini di sesi berikutnya (sekali)."""
    store.set_ulang(nomor, schedule.now().isoformat(timespec="seconds") if req.aktif else None)
    aktivitas.catat(nomor, "ulang", "Kirim ulang Broadcast diminta" if req.aktif else "Permintaan kirim ulang dibatalkan")
    return fasil_detail(nomor)


@router.get("/jadwal")
def jadwal(_=Depends(require_login)) -> dict[str, Any]:
    """Ringan (tanpa baca sheet): untuk hitung mundur sesi di menu samping."""
    now = schedule.now()
    akhir_pekan_ok = bool(db.get_setting("kirim_akhir_pekan", False))
    aktif = None if (schedule.is_weekend(now.date()) and not akhir_pekan_ok) else schedule.sesi_at(now)
    out: dict[str, Any] = {"aktif": None, "berikutnya": None}
    if aktif:
        h, m = map(int, aktif.sampai.split(":"))
        selesai = now.replace(hour=h, minute=m, second=59, microsecond=0)
        out["aktif"] = {"no": aktif.no, "sampai": jam(aktif.sampai),
                        "sisa_detik": max(0, int((selesai - now).total_seconds()))}
    sesi, mulai = schedule.next_sesi(now, akhir_pekan_ok)
    out["berikutnya"] = {"no": sesi.no, "mulai": jam(sesi.mulai), "hari_ini": mulai.date() == now.date(),
                         "dalam_detik": max(0, int((mulai - now).total_seconds()))}
    return out
