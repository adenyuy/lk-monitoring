"""Blast WhatsApp: kirim pesan (bebas atau dari template) ke daftar penerima pilihan petugas.

Tanpa sesi dan tanpa batas harian. Keamanan nomor diatur lewat aturan kirim yang bisa diubah petugas:
jeda acak antar pesan, dan istirahat beberapa menit setiap sekian pesan. Pengiriman berhenti sendiri bila
2 pesan gagal beruntun, WhatsApp terputus, atau keluar dari jam kirim (07.00–21.59) kecuali
petugas memilih abaikan jam kirim.
"""

import logging
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import time as jam
from typing import Callable

from . import aktivitas, db, events, schedule, store
from .sheets import message_hash
from .wa import actions
from .wa.browser import BrowserClosed

log = logging.getLogger(__name__)
AWALAN = "blast:"
JAM_MULAI, JAM_SAMPAI = jam(7, 0), jam(21, 59, 59)
ALASAN_GAGAL = {
    "nomor_tidak_terdaftar": "Nomor tidak terdaftar di WhatsApp",
    "timeout": "Chat tidak terbuka dalam 45 detik",
    "teks_tidak_terisi": "Pesan tidak terisi di kotak chat",
}


@dataclass
class Aturan:
    jeda_min: int = 20          # detik
    jeda_max: int = 45
    istirahat_setiap: int = 20  # pesan; 0 = tanpa istirahat
    istirahat_menit: int = 5

    def rapikan(self) -> "Aturan":
        a = max(5, min(600, int(self.jeda_min)))
        b = max(a, min(900, int(self.jeda_max)))
        n = max(0, min(200, int(self.istirahat_setiap)))
        m = max(1, min(60, int(self.istirahat_menit)))
        return Aturan(a, b, n, m)


def aturan_tersimpan() -> Aturan:
    d = db.get_setting("blast_aturan") or {}
    try:
        return Aturan(**{k: int(v) for k, v in d.items() if k in Aturan.__dataclass_fields__}).rapikan()
    except (TypeError, ValueError):
        return Aturan()


@dataclass
class Penerima:
    nomor: str
    nama: str
    pesan: str
    jenis: str = "fasil"   # fasil | koor | sekolah
    kunci: str = ""        # kunci fasil (untuk tahap "ditanya")


@dataclass
class State:
    running: bool = False
    paused: bool = False
    coba: bool = False
    abaikan_jam: bool = False  # bypass jam kirim 07.00–22.00
    judul: str = ""
    topik: str = ""        # komponen yang dibahas (mis. "Laporan Pendahuluan"), untuk label "sudah di-blast"
    total: int = 0
    diproses: int = 0
    terkirim: int = 0
    gagal: int = 0
    sekarang: str = ""
    berikutnya: str = ""
    berikutnya_pada: float | None = None
    istirahat_sampai: float | None = None
    stop_diminta: bool = False
    berhenti_karena: str = ""
    mulai: float | None = None
    selesai: float | None = None
    aturan: dict = field(default_factory=dict)
    hasil: list[dict] = field(default_factory=list)


class BlastError(Exception):
    """Tidak bisa mulai. Pesannya untuk pengguna."""


class Mesin:
    def __init__(self, wa=None, sleep: Callable[[float], None] = time.sleep, clock=schedule.now,
                 rng: random.Random | None = None) -> None:
        if wa is None:
            from .wa.pengirim import PengirimWA  # neonize utama, WA Web cadangan

            wa = PengirimWA()
        self.wa = wa
        self.sleep = sleep
        self.clock = clock
        self.rng = rng or random.Random()
        self.state = State()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._antrian: list[Penerima] = []

    def snapshot(self) -> dict:
        d = asdict(self.state)
        d["hasil"] = d["hasil"][-30:]
        d["sisa"] = [{"nama": p.nama, "jenis": p.jenis} for p in self._antrian[self.state.diproses:][:5]]
        return d

    def di_jam_kirim(self) -> bool:
        t = self.clock().time()
        return JAM_MULAI <= t <= JAM_SAMPAI

    def start(self, penerima: list[Penerima], aturan: Aturan, judul: str, coba: bool = False,
              topik: str = "", abaikan_jam: bool = False) -> dict:
        with self._lock:
            from .sender import sender

            if self.state.running or sender.state.running:
                raise BlastError("Pengiriman lain sedang berjalan. Tunggu selesai atau hentikan dulu.")
            if not penerima:
                raise BlastError("Belum ada penerima yang dipilih.")
            if not abaikan_jam and not self.di_jam_kirim():
                raise BlastError("Blast hanya bisa dikirim pukul 07.00–22.00 supaya tidak mengganggu penerima.")
            aturan = aturan.rapikan()
            db.set_setting("blast_aturan", asdict(aturan))
            antrian = penerima[:3] if coba else penerima
            self._antrian = antrian
            self.state = State(running=True, coba=coba, abaikan_jam=abaikan_jam, judul=judul[:80], topik=topik[:80],
                               total=len(antrian), mulai=time.time(),
                               aturan=asdict(aturan))
            self._thread = threading.Thread(target=self._run, args=(antrian, aturan), name="blast", daemon=True)
            self._thread.start()
        events.publish("kirim_mulai", **self.snapshot())
        return self.snapshot()

    def jeda(self, aktif: bool) -> dict:
        if self.state.running:
            self.state.paused = aktif
            events.publish("kirim_jeda", berikutnya=self.state.berikutnya, detik=0)
        return self.snapshot()

    def stop(self) -> dict:
        if self.state.running:
            self.state.stop_diminta = True
            self.state.paused = False
            events.publish("kirim_stop_diminta")
        return self.snapshot()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ---------- loop ----------

    def _tunggu(self, detik: float) -> None:
        sisa = detik
        while sisa > 0 and not self.state.stop_diminta:
            step = min(1.0, sisa)
            self.sleep(step)
            if not self.state.paused:
                sisa -= step

    def _run(self, antrian: list[Penerima], aturan: Aturan) -> None:
        st = self.state
        beruntun = 0
        try:
            for i, p in enumerate(antrian):
                while st.paused and not st.stop_diminta:
                    self.sleep(1)
                if st.stop_diminta:
                    st.berhenti_karena = "Dihentikan oleh pengguna."
                    break
                if not st.abaikan_jam and not self.di_jam_kirim():
                    st.berhenti_karena = "Sudah di luar jam kirim (07.00–22.00). Lanjutkan besok."
                    break
                st.sekarang, st.berikutnya, st.berikutnya_pada, st.istirahat_sampai = p.nama, "", None, None
                events.publish("kirim_proses", nama=p.nama, ke=i + 1, target=st.total)
                status, ket = self._proses(p, st.coba)
                st.diproses += 1
                t = self.clock()
                store.record_send(tanggal=schedule.tanggal_str(t.date()), waktu=t.isoformat(timespec="seconds"),
                                  sesi=0, nama_fasil=p.nama, nomor=p.nomor,
                                  hash_pesan=AWALAN + message_hash(p.pesan), status=status, keterangan=ket,
                                  coba=st.coba, topik=st.topik or st.judul)
                st.hasil.append({"nama": p.nama, "jenis": p.jenis, "status": status, "keterangan": ket,
                                 "waktu": t.strftime("%H.%M")})
                events.publish("kirim_hasil", nama=p.nama, status=status, keterangan=ket)
                if status == "terkirim":
                    st.terkirim += 1
                    beruntun = 0
                    ringkas = " ".join(p.pesan.split())
                    aktivitas.catat(p.nomor, "blast", f"{st.judul}: " + (ringkas[:80] + "…" if len(ringkas) > 80
                                                                        else ringkas), p.nama)
                elif status == "dicoba":
                    beruntun = 0
                else:
                    st.gagal += 1
                    beruntun += 1
                    if beruntun >= 2:
                        st.berhenti_karena = f"2 pesan gagal beruntun. Terakhir: {ket}"
                        break
                if i + 1 >= len(antrian) or st.stop_diminta:
                    continue
                if st.coba:
                    detik = 3.0
                elif aturan.istirahat_setiap and st.diproses % aturan.istirahat_setiap == 0:
                    detik = aturan.istirahat_menit * 60.0
                    st.istirahat_sampai = time.time() + detik
                else:
                    detik = self.rng.uniform(aturan.jeda_min, aturan.jeda_max)
                st.berikutnya, st.berikutnya_pada = antrian[i + 1].nama, time.time() + detik
                events.publish("kirim_jeda", berikutnya=antrian[i + 1].nama, detik=round(detik))
                self._tunggu(detik)
        except (actions.NotLoggedIn, BrowserClosed) as e:
            st.berhenti_karena = f"WhatsApp terputus: {e} Scan ulang QR lalu mulai lagi."
        except Exception as e:
            log.exception("Blast error")
            st.berhenti_karena = f"Terjadi kesalahan: {e}"
        finally:
            st.running, st.paused, st.sekarang, st.berikutnya = False, False, "", ""
            st.berikutnya_pada = st.istirahat_sampai = None
            st.selesai = time.time()
            events.publish("kirim_selesai", **self.snapshot())
            if st.terkirim and not st.coba:
                try:  # segera baca chat penerima; Log Komunikasi diisi dari hasil bacaan itu
                    from . import chat_refresh

                    chat_refresh.trigger()
                except Exception:
                    log.exception("Pembaruan chat setelah blast gagal")

    def _proses(self, p: Penerima, coba: bool) -> tuple[str, str]:
        from .undangan_wag import isi_salam

        res = self.wa.open_chat(p.nomor, isi_salam(p.pesan, self.clock()))
        if not res.ok:
            return "gagal", ALASAN_GAGAL.get(res.alasan, res.alasan)
        if coba:
            self.sleep(2)
            self.wa.clear_draft()
            return "dicoba", "Mode coba, tidak dikirim"
        r = self.wa.send()
        return r.status, r.keterangan


mesin = Mesin()


def sibuk() -> bool:
    """Ada pengiriman berjalan (blast baru atau mesin lama)."""
    from .sender import sender

    return mesin.state.running or sender.state.running
