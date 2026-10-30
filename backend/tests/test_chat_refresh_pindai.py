from datetime import date, datetime

from app import chat_refresh, db, store, tahap
from app.wa import actions


def _row(out, text, waktu, status=""):
    return actions.Row(id=text, out=out, status=status, text=text, waktu=waktu)


def test_tanggal_pesan_dua_format(monkeypatch):
    monkeypatch.setattr(chat_refresh.schedule, "now", lambda: datetime(2026, 10, 30, 12))
    assert chat_refresh.tanggal_pesan("15.50, 10/30/2026") == date(2026, 10, 30)
    assert chat_refresh.tanggal_pesan("10.37, 26/10/2026") == date(2026, 10, 26)
    assert chat_refresh.tanggal_pesan("09.00, 10/5/2026") == date(2026, 10, 5)  # 5 Okt, bukan 10 Mei
    assert chat_refresh.tanggal_pesan("") is None


def test_chat_dari_hp_masuk_kelompok():
    try:
        _cek_chat_dari_hp()
    finally:  # jangan mengganggu tes lain yang memakai database yang sama
        with db.tx() as c:
            for t in ("aktivitas", "chat_status"):
                c.execute(f"DELETE FROM {t} WHERE nomor LIKE '62812777700%'")


def _cek_chat_dari_hp():
    now = chat_refresh.schedule.now()
    senin = date.fromisoformat(tahap.senin_iso())
    hari = f"{now.day}/{now.month}/{now.year}"
    a, b, c = "6281277770001", "6281277770002", "6281277770003"
    # a: kita chat dari HP minggu ini lalu fasil membalas; b: hanya dibaca; c: chat terakhir minggu lalu
    assert chat_refresh.catat_dari_chat(a, [_row(True, "Halo pak", f"08.00, {hari}", "read"),
                                            _row(False, "Siap pak", f"08.10, {hari}")], senin) == "dibalas"
    assert chat_refresh.catat_dari_chat(b, [_row(True, "Halo bu", f"08.00, {hari}", "read")], senin) == "dibaca"
    assert chat_refresh.catat_dari_chat(c, [_row(True, "Halo", "08.00, 1/1/2020", "read")], senin) == ""
    k = tahap.kontak_minggu()
    assert k[a]["terkirim"] and k[a]["dibalas"]
    assert k[b]["terkirim"] and k[b]["dibaca"] and not k[b]["dibalas"]
    assert c not in k or not k[c]["terkirim"]
    assert store.chat_status_all()[a]["status"] == "dibalas"
