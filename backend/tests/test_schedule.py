from datetime import datetime

from app import schedule
from app.schedule import TZ


def t(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


# 2026-10-26 = Senin, 2026-10-31 = Sabtu
def test_batas_jam_sesi():
    assert schedule.sesi_at(t("2026-10-26 09:59")) is None
    assert schedule.sesi_at(t("2026-10-26 10:00")).no == 1
    assert schedule.sesi_at(t("2026-10-26 13:59")).no == 1
    assert schedule.sesi_at(t("2026-10-26 14:00")).no == 2
    assert schedule.sesi_at(t("2026-10-26 22:00")).no == 5
    assert schedule.sesi_at(t("2026-10-26 22:01")) is None


def kondisi(waktu, batas=40, akhir_pekan=False, hari=0, per=None, sisa=49):
    return schedule.kondisi(t(waktu), batas, akhir_pekan, hari, per or {}, sisa)


def test_berjalan_dan_kuota_efektif():
    k = kondisi("2026-10-26 14:20", hari=14, per={1: 10, 2: 4})
    assert k.kode == "berjalan" and k.bisa_kirim and k.kuota == 6
    assert k.judul == "Sesi 2 sedang berjalan, sampai 15.59"
    # dibatasi sisa batas harian
    assert kondisi("2026-10-26 16:30", batas=40, hari=37, per={3: 2}).kuota == 3
    # dibatasi sisa antrean
    assert kondisi("2026-10-26 16:30", sisa=2).kuota == 2


def test_kuota_sesi_habis():
    k = kondisi("2026-10-26 15:10", hari=20, per={1: 10, 2: 10})
    assert k.kode == "kuota_sesi_habis" and not k.bisa_kirim
    assert k.judul == "Kuota sesi 2 habis. Sesi 3 mulai 16.00"


def test_sebelum_dan_sesudah_jam_kirim():
    assert kondisi("2026-10-26 08:00").judul == "Sesi 1 mulai 10.00"
    k = kondisi("2026-10-26 22:30")
    assert k.kode == "selesai_hari" and "Sesi 1 mulai 10.00, Selasa" in k.judul


def test_batas_harian_tercapai():
    k = kondisi("2026-10-26 19:30", batas=40, hari=40, per={1: 10, 2: 10, 3: 15, 4: 5})
    assert k.kode == "batas_harian" and not k.bisa_kirim


def test_akhir_pekan():
    k = kondisi("2026-10-31 14:00")
    assert k.kode == "akhir_pekan" and "Senin" in k.judul
    assert kondisi("2026-10-31 14:00", akhir_pekan=True).kode == "berjalan"
    # Jumat malam: sesi berikutnya Senin
    assert "Senin" in kondisi("2026-10-30 23:00").judul


def test_antrean_habis():
    assert kondisi("2026-10-26 14:20", sisa=0).kode == "antrean_habis"


def test_tanggal_panjang():
    assert schedule.tanggal_panjang(t("2026-10-27 10:00").date()) == "Selasa, 27 Oktober 2026"


def test_bypass_sesi_abaikan_jam_dan_kuota_tapi_tidak_batas_harian():
    def kb(waktu, **kw):
        kw.setdefault("sisa", 49)
        return schedule.kondisi(t(waktu), kw.get("batas", 40), False, kw.get("hari", 0), kw.get("per", {}),
                                kw["sisa"], bypass=True)

    k = kb("2026-10-26 08:30")  # sebelum sesi 1
    assert k.kode == "bypass" and k.bisa_kirim and k.kuota == 40
    assert kb("2026-10-26 15:10", hari=20, per={1: 10, 2: 10}).kuota == 20  # kuota sesi 2 habis, tetap jalan
    assert kb("2026-10-26 15:10", hari=40).kode == "batas_harian"
    assert kb("2026-10-26 06:30").kode == "bypass_jam"
    assert kb("2026-10-26 22:30").kode == "bypass_jam"
    assert kb("2026-10-31 11:00").kode == "akhir_pekan"  # Sabtu
