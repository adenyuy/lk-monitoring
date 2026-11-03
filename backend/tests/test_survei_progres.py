"""Blast Survei Progres: penerima dari LK Survey (kolom PETUGAS PIC), satu pesan per fasil, sekali per link."""

import random
from datetime import datetime

import pytest

from app import db, survei_progres, undangan_wag
from app.schedule import TZ
from app.sender import Sender

from test_sender import Clock, FakeWA, rows

HEADER = ["No", "NPSN", "SEKOLAH", "KATEGORI", "PROVINSI", "PTN", "KOORDINATOR", "FASIL", "NO TELP", "PETUGAS PIC",
          "CAPAIAN APLIKASI", "ISIAN PROGRES (%)"]
SHEET = [
    ["SURVEI CEPAT PROGRES FISIK SEKOLAH"], ["keterangan"], HEADER,
    ["1", "101", "SD A", "Bencana", "Prov. Aceh", "PT", "Koor", "Budi", "0812-0000-0001", "*Sari Petugas*", "0,5", ""],
    ["2", "102", "SD B", "Bencana", "Prov. Aceh", "PT", "Koor", "Budi", "6281200000001", "Sari Petugas", "0,4", ""],
    ["3", "103", "SD C", "TNI", "Prov. Aceh", "PT", "Koor", "Ani", "", "Sari Petugas", "0,1", ""],
    ["4", "104", "SD D", "Bencana", "Prov. Aceh", "PT", "Koor", "Lain", "081299999999", "Petugas Lain", "0,9", ""],
    ["5", "105", "SD E", "TNI", "Prov. Aceh", "", "", "", "", "Sari Petugas", "0", ""],
]
P = survei_progres.Pengaturan(aktif=True, sheet="X" * 30, link="https://survey-progress.netlify.app/")


@pytest.fixture(autouse=True)
def bersih():
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    for k in (survei_progres.KUNCI, undangan_wag.KUNCI, "kirim_semua"):
        db.delete_setting(k)
    db.set_setting("nama_petugas", "Sari Petugas")
    yield
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    for k in (survei_progres.KUNCI, undangan_wag.KUNCI, "kirim_semua"):
        db.delete_setting(k)


def test_penerima_dari_kolom_petugas_pic_per_nomor():
    f = survei_progres.parse(SHEET, "Sari Petugas")
    assert [(x.nama, x.nomor, x.sekolah) for x in f] == [
        ("Budi", "6281200000001", ["SD A", "SD B"]), ("Ani", "", ["SD C"])]


def test_pesan_sopan_berisi_link_nomor_dan_daftar_sekolah():
    budi = survei_progres.parse(SHEET, "Sari Petugas")[0]
    teks = survei_progres.susun(P, budi)
    assert teks.startswith("Selamat {salam} Bapak/Ibu Budi")
    assert "🔗 https://survey-progress.netlify.app/" in teks
    assert "Sekolah binaan yang perlu diisi (2 sekolah):\n• SD A\n• SD B" in teks
    assert "nomor WhatsApp ini (081200000001)" in teks
    assert "{" not in teks.replace("{salam}", "")


def test_sekali_per_link_dan_nomor_kosong_dilewati():
    f = survei_progres.parse(SHEET, "Sari Petugas")
    items = survei_progres.build(f, [], P)
    assert [i.status for i in items] == ["menunggu", "dilewati"]
    kirim = [{"nomor": "6281200000001", "hash_pesan": survei_progres.hash_link(P.link), "status": "terkirim",
              "waktu": "2026-11-03T09:00:00", "keterangan": ""}]
    assert survei_progres.build(f, kirim, P)[0].status == "terkirim"
    baru = survei_progres.Pengaturan(aktif=True, sheet=P.sheet, link="https://survey-progress.netlify.app/v2")
    assert survei_progres.build(f, kirim, baru)[0].status == "menunggu"  # link baru = kirim lagi


def test_simpan_validasi_dan_hanya_satu_kampanye_aktif():
    with pytest.raises(survei_progres.SurveiError):
        survei_progres.simpan(aktif=True, sheet="", link=P.link, teks="")
    with pytest.raises(survei_progres.SurveiError):
        survei_progres.simpan(aktif=False, sheet=P.sheet, link=P.link, teks="tanpa tautan")
    undangan_wag.simpan(aktif=True, link="https://chat.whatsapp.com/AbCdEf123456", tim="", teks="")
    survei_progres.simpan(aktif=True, sheet="https://docs.google.com/spreadsheets/d/" + P.sheet + "/edit", link=P.link,
                          teks="")
    assert survei_progres.pengaturan().aktif and survei_progres.pengaturan().sheet == P.sheet
    assert not undangan_wag.pengaturan().aktif
    undangan_wag.simpan(aktif=True, link="https://chat.whatsapp.com/AbCdEf123456", tim="", teks="")
    assert not survei_progres.pengaturan().aktif


def test_blast_survei_kirim_langsung_dan_tidak_mengganggu_progres_mingguan(monkeypatch):
    monkeypatch.setattr(survei_progres, "fasil_binaan", lambda p, petugas: survei_progres.parse(SHEET, petugas))
    db.set_setting("batas_harian", 0)
    survei_progres.simpan(aktif=True, sheet=P.sheet, link=P.link, teks="")
    clock = Clock(datetime(2026, 11, 3, 8, 0, tzinfo=TZ))  # sebelum sesi 1
    wa = FakeWA()
    teks = []
    asli = wa.open_chat
    wa.open_chat = lambda n, t: (teks.append(t), asli(n, t))[1]
    s = Sender(wa=wa, sleep=clock.sleep, clock=clock, rng=random.Random(1), load_rows=lambda: rows(3))
    k = s.kondisi()
    assert k.bisa_kirim and k.kode == "undangan" and "Survei progres" in k.judul
    s.start()
    s.wait(10)
    assert wa.sent == ["6281200000001"] and teks[0].startswith("Selamat pagi Bapak/Ibu Budi")
    survei_progres.matikan()
    assert all(i.status == "menunggu" for i in s.antrean())  # kiriman survei tidak dihitung progres mingguan


def test_status_pemantauan_per_fasil():
    data = [r[:] for r in SHEET]
    data[2] = HEADER + ["DIISI PADA"]
    data[3] = data[3][:11] + ["35", "03/11/2026 10:12"]
    f = survei_progres.parse(data, "Sari Petugas")
    from app import aktivitas

    kirim = [{"nomor": "6281200000001", "hash_pesan": survei_progres.hash_link(P.link), "status": "terkirim",
              "waktu": "2026-11-03T09:00:00", "keterangan": ""}]
    items = survei_progres.build(f, kirim, P)
    with db.tx() as c:
        c.execute("DELETE FROM aktivitas")
        c.execute("DELETE FROM chat_status")
    aktivitas.catat("6281200000001", "dibalas", "Balasan: lama", "Budi")
    with db.tx() as c:  # balasan SEBELUM link terkirim tidak dihitung
        c.execute("UPDATE aktivitas SET waktu = '2026-11-02T10:00:00'")
    assert survei_progres.kontak_sejak(items)["6281200000001"]["dibalas"] is False
    aktivitas.catat("6281200000001", "dibalas", "Balasan: siap, sudah saya isi", "Budi")
    with db.tx() as c:
        c.execute("UPDATE aktivitas SET waktu = '2026-11-03T11:00:00' WHERE ringkasan LIKE '%siap%'")
    st = survei_progres.status(f, items, survei_progres.kontak_sejak(items))
    budi, ani = st["fasil"]
    assert (budi["terisi"], budi["total"], budi["wa"], budi["terakhir_isi"]) == (1, 2, "dibalas", "03/11/2026 10:12")
    assert ani["kirim"] == "tanpa_nomor"
    assert budi["balasan"] == "siap, sudah saya isi" and budi["kirim"] == "terkirim"
    assert st["ringkasan"] == {"fasil": 2, "terkirim": 1, "dibaca": 1, "dibalas": 1, "sekolah": 3, "terisi": 1, "tuntas": 0}
    with db.tx() as c:
        c.execute("DELETE FROM aktivitas")
