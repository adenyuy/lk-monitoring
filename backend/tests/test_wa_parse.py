"""Logika pengenal pesan WhatsApp Web, memakai contoh struktur asli (Okt 2026)."""

from app.wa import actions
from app.wa.status import mask


def raw(labels=(), titles=(), icons=(), tail_out=False, tail_in=False, text=""):
    return {"id": "x", "text": text, "labels": list(labels), "titles": list(titles),
            "icons": list(icons), "tailOut": tail_out, "tailIn": tail_in}


def test_pesan_keluar_dibaca():
    r = raw(labels=["You:", " Read "], titles=["tail-out", "wds-ic-read"], icons=["tail-out"], tail_out=True)
    st = actions._status_of(r)
    assert st == "read" and actions._is_out(r, st)


def test_pesan_masuk():
    r = raw(labels=["Budi Santoso:"], titles=["tail-in"], icons=["tail-in"], tail_in=True)
    st = actions._status_of(r)
    assert st == "" and not actions._is_out(r, st)


def test_pesan_keluar_lanjutan_tanpa_ekor():
    r = raw(labels=[" Delivered "], titles=["wds-ic-msg-dblcheck"])
    st = actions._status_of(r)
    assert st == "delivered" and actions._is_out(r, st)


def test_status_menunggu_dan_terkirim():
    assert actions._status_of(raw(labels=["You:", " Pending "])) == "pending"
    assert actions._status_of(raw(labels=["Anda:", " Terkirim "])) == "sent"
    assert actions._status_of(raw(labels=["Anda:", " Dibaca "])) == "read"


def test_samarkan_nomor():
    assert mask("6281234567890") == "0812•••7890"
    assert mask("") == ""


def _row(out, text, status=""):
    return actions.Row("x", out, status, text)


def test_balasan_tetap_terhitung_walau_petugas_membalas_lagi():
    rows = [_row(True, "Pengumuman", "read"), _row(False, "Siap bu, segera saya ingatkan"),
            _row(True, "Terima kasih pak", "delivered")]
    info = actions.chat_info(rows)
    assert info.status == "dibalas" and info.balasan == ["Siap bu, segera saya ingatkan"]


def test_status_tanpa_balasan():
    assert actions.chat_info([_row(True, "Pengumuman", "read")]).status == "dibaca"
    assert actions.chat_info([_row(True, "Pengumuman", "delivered")]).status == "terkirim"
    assert actions.chat_info([_row(False, "Halo")]).status == "belum_ada"


def test_waktu_pesan():
    assert actions._waktu("[10:37, 26/10/2026] Budi: ") == "10.37, 26/10/2026"
    assert actions._waktu("") == ""


def test_rapikan_teks_daftar():
    teks = "Untuk sekolah berikut:\n\n\n\n1. SD A (39,6%)  \n2. SD B\n\n\n\nTerima kasih"
    assert actions.rapikan(teks) == "Untuk sekolah berikut:\n\n1. SD A (39,6%)\n2. SD B\n\nTerima kasih"
