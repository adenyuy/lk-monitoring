from datetime import datetime

from app import config, db, schedule, send_queue
from app.routers import today
from app.sheets import Sekolah


def _item(n, nama):
    return send_queue.Item(baris=2, nama_fasil=nama, nomor=n, pesan="Halo", hash_pesan="h", status="menunggu")


def _ctx(waktu, items, per, total):
    now = datetime.strptime(waktu, "%Y-%m-%d %H:%M").replace(tzinfo=schedule.TZ)
    k = schedule.kondisi(now, 40, False, total, per, len(items))
    return {"now": now, "kondisi": k, "items": items, "total": total, "per": per,
            "tanggal": now.date().isoformat()}


def _bersih(monkeypatch):
    monkeypatch.setattr(today, "_sekolah_map", lambda: {})
    monkeypatch.setattr(today.store, "sends_real", lambda: [])
    db.set_setting("batas_harian", 40)


def test_sesi_terlewat_masih_bisa_dikejar(monkeypatch):
    _bersih(monkeypatch)
    items = [_item(f"62812000000{i:02d}", f"Fasil {i}") for i in range(30)]
    p = today._pengingat(_ctx("2026-10-27 14:10", items, {1: 4}, 4), libur=False)
    assert p[0]["jenis"] == "terlewat"
    assert p[0]["judul"] == "Sesi 1 terlewat"
    assert "6 slot" in p[0]["isi"]
    assert "masih bisa 30 pesan" in p[0]["isi"]  # 30 di antrean, kapasitas sisa 50, batas sisa 36


def test_setelah_sesi_terakhir_lanjut_besok(monkeypatch):
    _bersih(monkeypatch)
    items = [_item("6281200000001", "Fasil A")]
    p = today._pengingat(_ctx("2026-10-27 22:30", items, {1: 10, 2: 10}, 20), libur=False)
    assert p[0]["jenis"] == "terlewat"
    assert "lanjut Rabu" in p[0]["isi"]


def test_lanjutan_kemarin_dan_minggu_baru(monkeypatch):
    _bersih(monkeypatch)
    items = [_item("6281200000001", "Fasil A")]
    monkeypatch.setattr(today.store, "sends_real", lambda: [
        {"nomor": "6281200000009", "status": "terkirim", "waktu": "2026-10-26T10:05:00"}])
    p = today._pengingat(_ctx("2026-10-27 09:30", items, {}, 0), libur=False)
    assert p[0]["jenis"] == "lanjut"
    monkeypatch.setattr(today.store, "sends_real", lambda: [])
    p = today._pengingat(_ctx("2026-10-26 09:30", items, {}, 0), libur=False)
    assert p[0]["jenis"] == "minggu_baru"
    assert today._pengingat(_ctx("2026-10-31 11:00", items, {}, 0), libur=True) == []


def test_tindak_lanjut_yang_membalas_didahulukan(monkeypatch):
    _bersih(monkeypatch)
    a, b = "6281200000001", "6281200000002"
    items = [_item(a, "Fasil A"), _item(b, "Fasil B")]
    sek = Sekolah(baris=3, petugas="Petugas Uji", npsn="1", nama="SD SATU", kab_kota="Kab", fasil="x",
                  nomor_fasil="", prioritas="Prioritas 1", progres=40, submit="Tidak", reviu="Tidak")
    monkeypatch.setattr(today, "_sekolah_map", lambda: {a[-9:]: [sek], b[-9:]: [sek]})
    monkeypatch.setattr(today.store, "sends_real", lambda: [
        {"nomor": n, "status": "terkirim", "waktu": "2026-10-26T10:05:00"} for n in (a, b)])
    monkeypatch.setattr(today.store, "chat_status_all", lambda: {b: {"status": "dibalas"}})
    monkeypatch.setattr(today.store, "tahap_all", lambda: {})
    p = [x for x in today._pengingat(_ctx("2026-10-27 15:00", items, {1: 10}, 10), libur=False)
         if x["jenis"] == "tindak_lanjut"][0]
    assert [f["nama"] for f in p["fasil"]] == ["Fasil B", "Fasil A"]
    assert p["judul"] == "1 fasil sudah membalas, isian LK-nya belum lengkap"
    assert config.SESI[0].kuota == 10
