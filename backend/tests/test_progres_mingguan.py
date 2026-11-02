"""Blast progres mingguan: antrean dari LK, satu pesan per fasil, tahap 'Isian ditanyakan' tercentang setelah terkirim."""

import random
from datetime import date, datetime

import pytest

from app import aktivitas, db, progres_mingguan, store
from app.schedule import TZ
from app.sender import Sender
from app.sheets import Sekolah

from test_sender import Clock, FakeWA


def sek(baris, nama, fasil, nomor, progres, submit="Tidak", reviu="Tidak", prioritas="Prioritas 1", petugas="Sari Petugas"):
    return Sekolah(baris, petugas, str(baris), nama, "", fasil, nomor, prioritas, progres, submit, reviu)


LK = [
    sek(3, "SD A", "Budi", "081200000001", 32.5),
    sek(4, "SD B", "Budi", "081200000001", 62.4),
    sek(5, "SD C", "Budi", "081200000001", 78.0, submit="Ya"),
    sek(6, "SD D", "Budi", "081200000001", 90.0, submit="Ya", reviu="Ya"),
    sek(7, "SD E", "Ani", "081200000002", 10.0, prioritas="Selesai"),
    sek(8, "SD F", "Tanpa Nomor", "", 20.0),
    sek(9, "SD G", "Lain", "081299999999", 5.0, petugas="Petugas Lain"),
]


@pytest.fixture(autouse=True)
def bersih():
    with db.tx() as c:
        for t in ("sends", "aktivitas", "chat_tahap", "chat_status"):
            c.execute(f"DELETE FROM {t}")
    db.set_setting("nama_petugas", "Sari Petugas")
    db.set_setting("batas_harian", 40)
    db.set_setting("kirim_akhir_pekan", False)
    yield
    with db.tx() as c:
        for t in ("sends", "aktivitas", "chat_tahap", "chat_status"):
            c.execute(f"DELETE FROM {t}")


def test_pesan_satu_poin_per_sekolah():
    teks = progres_mingguan.susun("Budi", [s for s in LK if s.fasil == "Budi"], "2", membalas=False)
    assert teks.startswith("Selamat {salam} Bapak/Ibu Budi")
    assert "Melanjutkan pesan kami minggu lalu, berikut update progres Minggu ke-2" in teks
    assert ("1. SD A (32,5%, belum submit)\n   Kendala progres fisik: ...\n   Rencana tindak lanjut: ...\n\n"
            "2. SD B (62,4%, belum submit)\n   Kendala submit laporan 50%: ...\n   Rencana unggah: ...\n\n"
            "3. SD C (78,0%, belum direviu)\n   Kendala reviu: ...\n   Perkiraan selesai reviu: ...") in teks
    assert "SD D" not in teks  # sudah direviu
    assert "Terima kasih atas tanggapan" in progres_mingguan.susun("Budi", LK[:1], "2", membalas=True)
    assert progres_mingguan.susun("Ani", [LK[4]], "2", membalas=False) == ""  # semua selesai


def test_antrean_dari_lk():
    aktivitas.catat("6281200000001", "dibalas", "Balasan: siap", "Budi")
    with db.tx() as c:  # balasan minggu lalu
        c.execute("UPDATE aktivitas SET waktu = '2026-10-28T10:00:00'")
    rows = progres_mingguan.baris(LK, "Sari Petugas", "2", date(2026, 11, 2))
    assert [(r.nama_fasil, r.nomor) for r in rows] == [
        ("Budi", "6281200000001"), ("Ani", "6281200000002"), ("Tanpa Nomor", "")]
    assert "Terima kasih atas tanggapan" in rows[0].pesan and rows[0].hash_pesan.startswith("pm:")
    assert rows[1].pesan == ""


def test_kirim_progres_mingguan_menandai_isian_ditanyakan():
    clock = Clock(datetime(2026, 11, 2, 10, 30, tzinfo=TZ))
    wa = FakeWA()
    teks = []
    asli = wa.open_chat
    wa.open_chat = lambda n, t: (teks.append(t), asli(n, t))[1]
    s = Sender(wa=wa, sleep=clock.sleep, clock=clock, rng=random.Random(1),
               load_rows=lambda: progres_mingguan.baris(LK, "Sari Petugas", "2", date(2026, 11, 2)))
    items = s.antrean()
    assert [i.status for i in items] == ["menunggu", "dilewati", "dilewati"]
    assert items[1].keterangan == progres_mingguan.SEMUA_SELESAI
    s.start()
    s.wait(10)
    assert s.state.terkirim == 1 and wa.sent == ["6281200000001"]
    assert teks[0].startswith("Selamat pagi Bapak/Ibu Budi")
    assert store.tahap_all()["6281200000001"]["ditanya"]["nilai"] is True


def test_kirim_ke_semua_hari_ini_tanpa_sesi_dan_batas_harian():
    from test_sender import rows

    db.set_setting("batas_harian", 10)
    clock = Clock(datetime(2026, 11, 2, 8, 0, tzinfo=TZ))  # sebelum sesi 1
    wa = FakeWA()
    s = Sender(wa=wa, sleep=clock.sleep, clock=clock, rng=random.Random(1), load_rows=lambda: rows(25))
    assert s.kondisi().kode == "sebelum_sesi"
    db.set_setting("kirim_semua", {"tanggal": "2026-11-02"})
    try:
        k = s.kondisi()
        assert k.bisa_kirim and k.kode == "semua" and k.kuota == 25
        s.start()
        s.wait(10)
        assert s.state.terkirim == 25 and len(set(wa.sent)) == 25 and s.state.berhenti_karena == ""
        clock.t = datetime(2026, 11, 3, 10, 30, tzinfo=TZ)  # besok kembali ke sesi biasa
        assert s.kondisi().kode != "semua"
    finally:
        db.delete_setting("kirim_semua")
