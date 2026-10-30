from app import db, lk_otomatis, schedule, store
from tests import lk_uji

OPSI = ["0. Terhubung", "1. Nomor Tidak Terhubung Whatsapp", "2. Checklist 1", "3. Chat hanya di Read",
        "4. Salah Nomor", "5. Respon Lambat", "6. Lainnya"]
A, B, C = "6281200000001", "6281200000002", "6281200000003"


def _baris(npsn, nomor, prio, kom):
    return ["Petugas Uji", npsn, f"SD {npsn}", "Kab", f"Fasil {nomor[-1]}", nomor, prio, kom,
            0.3, "Tidak", "Tidak", 0.3, "Tidak", "Tidak"] + [""] * 12


def test_pilihan():
    assert lk_otomatis.pilihan(OPSI, lk_otomatis.TERHUBUNG) == "0. Terhubung"
    assert lk_otomatis.pilihan(OPSI, lk_otomatis.TIDAK_WA) == "1. Nomor Tidak Terhubung Whatsapp"
    assert lk_otomatis.pilihan(OPSI, lk_otomatis.HANYA_READ) == "3. Chat hanya di Read"
    assert lk_otomatis.pilihan(["Belum terhubung", "0. Terhubung"], lk_otomatis.TERHUBUNG) == "0. Terhubung"


def test_sinkron_isi_status_komunikasi(monkeypatch):
    data = lk_uji.parse([
        _baris("1", A, "Prioritas 1", ""),
        _baris("2", A, "Prioritas 3", "3. Chat hanya di Read"),  # Terhubung menimpa status otomatis
        _baris("3", A, "Selesai", ""),                           # Selesai tidak disentuh
        _baris("4", A, "Prioritas 2", "5. Respon Lambat"),       # pilihan manual tidak tertimpa
        _baris("5", B, "Prioritas 1", ""),
        _baris("6", B, "Prioritas 1", "5. Respon Lambat"),
        _baris("7", C, "Prioritas 1", ""),
    ])
    ditulis = []
    db.set_setting("nama_petugas", "Petugas Uji")
    monkeypatch.setattr(lk_otomatis, "status_minggu", lambda: {
        A: lk_otomatis.TERHUBUNG, B: lk_otomatis.HANYA_READ, C: lk_otomatis.TIDAK_WA})
    monkeypatch.setattr(lk_otomatis, "week_aktif", lambda: "1")
    monkeypatch.setattr(lk_otomatis, "read_lk", lambda week, refresh=False: data)
    monkeypatch.setattr(lk_otomatis, "read_validasi", lambda: {"komunikasi": OPSI})
    monkeypatch.setattr(lk_otomatis, "kolom_lk", lambda week, refresh=False: lk_uji.KOL)
    monkeypatch.setattr(lk_otomatis, "write_isian", lambda week, p, kol=None: ditulis.extend(p))
    assert lk_otomatis.sinkron() == 4
    assert [(s.npsn, sel["I"]) for s, sel in ditulis] == [
        ("1", "0. Terhubung"), ("2", "0. Terhubung"), ("5", "3. Chat hanya di Read"),
        ("7", "1. Nomor Tidak Terhubung Whatsapp")]
    assert data[0].komunikasi == "0. Terhubung"
    ditulis.clear()
    assert lk_otomatis.sinkron() == 0 and ditulis == []  # sudah terisi semua


def test_status_minggu_dari_chat():
    a, b, c = "6281299990001", "6281299990002", "6281299990003"
    now = schedule.now().isoformat(timespec="seconds")
    for n in (a, b):
        store.record_send(tanggal=now[:10], waktu=now, sesi=1, nama_fasil="F", nomor=n, hash_pesan="h",
                          status="terkirim")
    store.record_send(tanggal=now[:10], waktu=now, sesi=1, nama_fasil="F", nomor=c, hash_pesan="h", status="gagal",
                      keterangan="Nomor tidak terdaftar di WhatsApp (nomor_tidak_terdaftar)")
    store.save_chat_status(a, "dibalas", "siap pak", now)
    store.save_chat_status(b, "dibaca", "", now)
    st = lk_otomatis.status_minggu()
    assert (st.get(a), st.get(b), st.get(c)) == (lk_otomatis.TERHUBUNG, lk_otomatis.HANYA_READ, lk_otomatis.TIDAK_WA)
