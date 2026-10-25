"""Mesin kirim dengan WhatsApp & jam tiruan (tidak ada yang benar-benar dikirim)."""

import random
from datetime import datetime, timedelta

import pytest

from app import db, schedule, store
from app.schedule import TZ
from app.sender import NotAllowed, Sender
from app.sheets import BroadcastRow, message_hash
from app.wa.actions import NotLoggedIn, OpenResult, SendResult


class FakeWA:
    def __init__(self, invalid=(), send_fail=(), logout_at=None):
        self.invalid, self.send_fail, self.logout_at = set(invalid), set(send_fail), logout_at
        self.opened, self.sent, self.cleared = [], [], 0
        self._current = None

    def open_chat(self, nomor, teks):
        if self.logout_at is not None and len(self.opened) == self.logout_at:
            raise NotLoggedIn("WhatsApp Web meminta scan QR ulang.")
        self.opened.append(nomor)
        self._current = nomor
        return OpenResult(False, "nomor_tidak_terdaftar") if nomor in self.invalid else OpenResult(True)

    def send(self):
        if self._current in self.send_fail:
            return SendResult("gagal", "Pesan tidak muncul di chat setelah menekan kirim.")
        self.sent.append(self._current)
        return SendResult("terkirim")

    def clear_draft(self):
        self.cleared += 1


class Clock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += timedelta(seconds=s)


def rows(n):
    return [BroadcastRow(i + 2, "Sari Petugas", f"Fasil {i}", f"62811000000{i:02d}", "", f"Halo {i}",
                         message_hash(f"Halo {i}")) for i in range(n)]


@pytest.fixture(autouse=True)
def bersih():
    with db.tx() as c:
        c.execute("DELETE FROM sends")
    db.set_setting("nama_petugas", "Sari Petugas")
    db.set_setting("batas_harian", 40)
    db.set_setting("kirim_akhir_pekan", False)
    yield


def make(wa, start="2026-10-26 14:00", n=15):
    clock = Clock(datetime.strptime(start, "%Y-%m-%d %H:%M").replace(tzinfo=TZ))
    s = Sender(wa=wa, sleep=clock.sleep, clock=clock, load_rows=lambda: rows(n), rng=random.Random(7))
    return s, clock


def run(s, coba=False):
    s.start(coba=coba)
    s.wait(10)
    return s.state


def test_kirim_sampai_kuota_sesi_dengan_jeda():
    wa = FakeWA()
    s, clock = make(wa)
    st = run(s)
    assert st.terkirim == 10 and len(wa.sent) == 10  # kuota sesi 2 = 10
    assert not st.running and st.berhenti_karena == ""
    total, per = store.counts("2026-10-26")
    assert total == 10 and per == {2: 10}
    # 9 jeda di antara 10 pesan, masing-masing 45–120 detik
    elapsed = (clock.t - datetime(2026, 10, 26, 14, 0, tzinfo=TZ)).total_seconds()
    assert 9 * 45 <= elapsed <= 9 * 120 + 30


def test_antrean_berlanjut_dan_tidak_dobel():
    wa = FakeWA()
    s, clock = make(wa)
    run(s)
    clock.t = datetime(2026, 10, 26, 16, 0, tzinfo=TZ)  # sesi 3, kuota 15, sisa antrean 5
    st = run(s)
    assert st.terkirim == 5
    assert len(set(wa.sent)) == 15  # tidak ada nomor dikirim dua kali


def test_mode_coba_tidak_mengurangi_kuota():
    wa = FakeWA()
    s, _ = make(wa)
    st = run(s, coba=True)
    assert st.dicoba == 10 and wa.sent == [] and wa.cleared == 10
    assert store.counts("2026-10-26")[0] == 0


def test_dua_gagal_beruntun_berhenti():
    wa = FakeWA(send_fail={"6281100000001", "6281100000002"})
    s, _ = make(wa)
    st = run(s)
    assert st.terkirim == 1 and st.gagal == 2
    assert "2 pesan gagal beruntun" in st.berhenti_karena


def test_nomor_tidak_terdaftar_dilewati_lanjut():
    wa = FakeWA(invalid={"6281100000001"})
    s, _ = make(wa)
    st = run(s)
    assert st.gagal == 1 and st.terkirim == 10  # tetap mengisi kuota 10


def test_whatsapp_logout_berhenti_total():
    wa = FakeWA(logout_at=3)
    s, _ = make(wa)
    st = run(s)
    assert st.terkirim == 3 and "WhatsApp terputus" in st.berhenti_karena


def test_stop_berhenti_setelah_pesan_berjalan():
    wa = FakeWA()
    s, clock = make(wa)
    orig = clock.sleep

    def sleep_lalu_stop(sec):
        orig(sec)
        if len(wa.sent) == 2:
            s.stop()

    s.sleep = sleep_lalu_stop
    st = run(s)
    assert st.terkirim == 2 and st.berhenti_karena == "Dihentikan oleh pengguna."


def test_batas_harian_membatasi():
    db.set_setting("batas_harian", 13)
    wa = FakeWA()
    s, clock = make(wa)
    run(s)  # sesi 2: 10
    clock.t = datetime(2026, 10, 26, 16, 0, tzinfo=TZ)
    st = run(s)  # sisa batas harian 3
    assert st.terkirim == 3


def test_tidak_boleh_mulai_di_luar_jam_atau_akhir_pekan():
    s, _ = make(FakeWA(), start="2026-10-26 08:00")
    with pytest.raises(NotAllowed, match="Sesi 1 mulai 10.00"):
        s.start()
    s, _ = make(FakeWA(), start="2026-10-31 14:00")
    with pytest.raises(NotAllowed, match="Akhir pekan"):
        s.start()


def test_sesi_berakhir_di_tengah_jalan():
    wa = FakeWA()
    s, _ = make(wa, start="2026-10-26 15:56")  # 4 menit sebelum sesi 2 habis: maks ±6 pesan
    st = run(s)
    assert 0 < st.terkirim < 10 and "sudah berakhir" in st.berhenti_karena


def test_tanggal_dari_jam_wib():
    assert schedule.tanggal_str(datetime(2026, 10, 26, 23, 59, tzinfo=TZ).date()) == "2026-10-26"
