"""Layar Hari ini: ringkasan, rel sesi, isi sesi, detail fasilitator."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import config, db, schedule, send_queue, store
from ..schedule import jam
from ..sender import NotAllowed, sender
from ..sheets import filter_petugas, nomor_key, read_broadcast, read_lk, sekolah_per_fasil
from ..wa.status import mask
from .deps import require_feature

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
        return sekolah_per_fasil(read_lk(db.get_setting("week", "1")), petugas)
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

    return {
        "tanggal": ctx["tanggal"],
        "tanggal_panjang": schedule.tanggal_panjang(now.date()),
        "jam_sekarang": now.strftime("%H.%M"),
        "posisi_sekarang": max(0.0, min(100.0, round(pct, 2))),
        "kondisi": k.as_dict(),
        "sesi_aktif": aktif.no if aktif else None,
        "batas_harian": batas,
        "terkirim_hari_ini": ctx["total"],
        "dibalas_hari_ini": dibalas,
        "belum_dikirim": len(send_queue.eligible(items)),
        "total_fasil": len(items),
        "sesi": [
            {
                "no": s.no, "mulai": jam(s.mulai), "sampai": jam(s.sampai), "kuota": s.kuota,
                "terkirim": ctx["per"].get(s.no, 0),
                "durasi_menit": _menit(s.sampai) - _menit(s.mulai) + 1,
                "status": _sesi_status(s, now, ctx["per"].get(s.no, 0), aktif.no if aktif else None,
                                       berikutnya.no if berikutnya else None, libur),
            }
            for s in config.SESI
        ],
        "pengiriman": sender.snapshot(),
    }


@router.get("/sessions/{no}")
def session_detail(no: int, _=Depends(wa_blast)) -> dict[str, Any]:
    if no not in {s.no for s in config.SESI}:
        raise HTTPException(404, "Sesi tidak ada.")
    ctx = _context()
    now, items, k = ctx["now"], ctx["items"], ctx["kondisi"]
    sesi = schedule.sesi_by_no(no)
    sekolah = _sekolah_map()
    chats = store.chat_status_all()
    nama_by_nomor = {i.nomor: i.nama_fasil for i in items}

    def jumlah_sekolah(nomor: str) -> int:
        return len(sekolah.get(nomor_key(nomor), []))

    # Yang sudah diproses di sesi ini hari ini
    baris = []
    for s in store.sends_on(ctx["tanggal"]):
        if s["sesi"] != no:
            continue
        baris.append({
            "jam": datetime.fromisoformat(s["waktu"]).strftime("%H.%M"),
            "nama_fasil": s["nama_fasil"], "nomor": s["nomor"],
            "jumlah_sekolah": jumlah_sekolah(s["nomor"]),
            "status": _status_tampil(s["status"], s["nomor"], chats) if not s["coba"] else "Dicoba",
            "keterangan": s["keterangan"],
        })
    baris.reverse()  # terbaru di atas

    # Perkiraan siapa yang akan dikirimi (sesi berjalan / mendatang)
    t = now.hour * 60 + now.minute
    akan = []
    if t <= _menit(sesi.sampai) and k.kode not in ("akhir_pekan", "batas_harian"):
        eligible = send_queue.eligible(items)
        batas = int(db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT))
        sisa_harian = max(0, batas - ctx["total"])
        offset = 0
        for s in config.SESI:
            if s.no >= no:
                break
            if t <= _menit(s.sampai):  # sesi lebih awal yang masih/akan berjalan
                offset += max(0, s.kuota - ctx["per"].get(s.no, 0))
        kapasitas = max(0, min(sesi.kuota - ctx["per"].get(no, 0), sisa_harian - offset))
        for j, it in enumerate(eligible[offset: offset + kapasitas]):
            akan.append({
                "jam": "", "nama_fasil": it.nama_fasil, "nomor": it.nomor,
                "jumlah_sekolah": jumlah_sekolah(it.nomor),
                "status": "Berikutnya" if (j == 0 and no == (k.sesi.no if k.sesi else None)) else "Menunggu",
                "keterangan": "Akan dicoba ulang" if it.status == "gagal" else "",
            })

    return {
        "no": no, "mulai": jam(sesi.mulai), "sampai": jam(sesi.sampai), "kuota": sesi.kuota,
        "terkirim": ctx["per"].get(no, 0),
        "aktif": bool(k.sesi and k.sesi.no == no and k.bisa_kirim),
        "kondisi": k.as_dict(),
        "sudah": baris,
        "akan": akan,
        "nama_fasil": nama_by_nomor,
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

    return {
        "nama_fasil": row.nama_fasil if row else (last["nama_fasil"] if last else "Fasilitator"),
        "nomor_tersamar": mask(nomor),
        "status": status,
        "pesan": row.pesan if row else "",
        "waktu_kirim": datetime.fromisoformat(last["waktu"]).strftime("%d/%m %H.%M") if last else "",
        "status_kirim": last["status"] if last else "",
        "balasan": (chat or {}).get("balasan_terakhir", ""),
        "waktu_balasan": (chat or {}).get("waktu_balasan", ""),
        "sekolah": [
            {"npsn": s.npsn, "nama": s.nama, "progres": s.progres, "prioritas": s.prioritas,
             "submit": s.submit, "reviu": s.reviu}
            for s in sorted(sekolah, key=lambda x: (x.prioritas or "Z", x.nama))
        ],
    }
