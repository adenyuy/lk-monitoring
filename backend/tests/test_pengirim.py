"""Pengirim: neonize utama, WA Web cadangan. Memakai klien WhatsApp palsu (tidak ada pesan sungguhan)."""

from types import SimpleNamespace

import pytest

from app import db
from app.wa import pendengar, pengirim
from app.wa.actions import OpenResult, SendResult

try:  # neonize hanya terpasang di Windows; CI Linux dan Mac tanpa status mengetik
    import neonize.utils.enum  # noqa: F401
    ADA_NEONIZE = True
except ImportError:
    ADA_NEONIZE = False


class KlienPalsu:
    def __init__(self, terdaftar=("6281200000001",), gagal_cek=False, gagal_kirim=False):
        self.terdaftar, self.gagal_cek, self.gagal_kirim = set(terdaftar), gagal_cek, gagal_kirim
        self.terkirim: list[tuple[str, str]] = []
        self.presence: list[str] = []

    def is_on_whatsapp(self, nomor):
        if self.gagal_cek:
            raise RuntimeError("koneksi putus")
        return [SimpleNamespace(IsIn=nomor in self.terdaftar, JID=SimpleNamespace(User=nomor, Server="s.whatsapp.net"))]

    def send_chat_presence(self, jid, state, media):
        self.presence.append(str(state))

    def send_message(self, jid, teks):
        if self.gagal_kirim:
            raise RuntimeError("ditolak")
        self.terkirim.append((jid.User, teks))
        return SimpleNamespace(ID=f"ID{len(self.terkirim)}", Timestamp=1_762_740_000)


class WebPalsu:
    def __init__(self):
        self.dibuka: list[str] = []
        self.dikirim = 0

    def open_chat(self, nomor, teks):
        self.dibuka.append(nomor)
        return OpenResult(True)

    def send(self):
        self.dikirim += 1
        return SendResult("terkirim", centang="delivered")

    def clear_draft(self):
        pass


@pytest.fixture
def neo(monkeypatch):
    k = KlienPalsu()
    monkeypatch.setattr(pendengar, "_klien", k)
    monkeypatch.setattr(pendengar.keadaan, "status", "tersambung")
    monkeypatch.setattr(pendengar, "antrekan", lambda n: None)
    monkeypatch.setattr(pengirim, "TUNGGU_CENTANG", 0)
    pengirim._cek.clear()
    db.set_setting("kirim_lewat", "neonize")
    return k


def test_kirim_lewat_neonize_bila_tersambung(neo):
    web = WebPalsu()
    p = pengirim.PengirimWA(web, sleep=lambda s: None)
    assert p.open_chat("6281200000001", "Halo") == OpenResult(True)
    r = p.send()
    assert r.status == "terkirim"
    assert neo.terkirim == [("6281200000001", "Halo")]
    assert web.dibuka == [] and web.dikirim == 0
    if ADA_NEONIZE:  # CI Linux / Mac tanpa neonize: tanpa status mengetik
        assert any("COMPOSING" in x for x in neo.presence)  # "sedang mengetik…" dulu
    # pesan tersimpan sebagai pesan keluar supaya chat & Log Komunikasi ikut terisi
    rows = pendengar.baris_chat("6281200000001")
    assert rows and rows[-1].out and rows[-1].text == "Halo"


def test_nomor_tidak_terdaftar_tidak_dikirim(neo):
    p = pengirim.PengirimWA(WebPalsu(), sleep=lambda s: None)
    assert p.open_chat("6281299999999", "Halo") == OpenResult(False, "nomor_tidak_terdaftar")
    assert neo.terkirim == []


def test_mode_coba_tidak_mengirim(neo):
    p = pengirim.PengirimWA(WebPalsu(), sleep=lambda s: None)
    assert p.open_chat("6281200000001", "Halo").ok
    p.clear_draft()  # mesin blast memanggil ini pada mode coba, bukan send()
    assert neo.terkirim == []


def test_cadangan_wa_web_bila_neonize_putus(neo, monkeypatch):
    monkeypatch.setattr(pendengar.keadaan, "status", "putus")
    web = WebPalsu()
    p = pengirim.PengirimWA(web, sleep=lambda s: None)
    assert p.open_chat("6281200000001", "Halo").ok
    assert p.send().status == "terkirim"
    assert web.dibuka == ["6281200000001"] and web.dikirim == 1
    assert neo.terkirim == []


def test_cadangan_wa_web_bila_cek_nomor_gagal(neo):
    neo.gagal_cek = True
    web = WebPalsu()
    p = pengirim.PengirimWA(web, sleep=lambda s: None)
    p.open_chat("6281200000001", "Halo")
    p.send()
    assert web.dikirim == 1 and p.jalur == "waweb"


def test_pilihan_waweb_dihormati(neo):
    db.set_setting("kirim_lewat", "waweb")
    web = WebPalsu()
    p = pengirim.PengirimWA(web, sleep=lambda s: None)
    p.open_chat("6281200000001", "Halo")
    p.send()
    assert web.dikirim == 1 and neo.terkirim == []
    assert pengirim.mesin_aktif() == "waweb"


def test_gagal_kirim_tidak_dicoba_ulang_lewat_wa_web(neo):
    neo.gagal_kirim = True
    web = WebPalsu()
    p = pengirim.PengirimWA(web, sleep=lambda s: None)
    p.open_chat("6281200000001", "Halo")
    r = p.send()
    assert r.status == "gagal"
    assert web.dikirim == 0  # jangan sampai fasil menerima pesan ganda


def test_lama_ketik_dibatasi():
    assert pengirim.lama_ketik("hai") == pengirim.KETIK_MIN
    assert pengirim.lama_ketik("x" * 5000) == pengirim.KETIK_MAKS
