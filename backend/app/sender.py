"""Mesin kirim WA Blast: satu sesi, satu thread, bisa dihentikan.

Alur (FLOW.md §6): ambil antrean -> untuk tiap fasil: buka chat berisi pesan -> kirim
(atau mode coba) -> catat -> jeda acak -> ulangi sampai kuota sesi / batas harian habis,
antrean habis, Stop ditekan, atau berhenti total (WA logout, 2 gagal beruntun, sesi berakhir).
"""

import logging
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol

from . import config, db, events, schedule, send_queue, store, tagging, undangan_wag
from .sheets import BroadcastRow, filter_petugas, read_broadcast
from .wa import actions
from .wa.browser import BrowserClosed, worker

log = logging.getLogger(__name__)

ALASAN_GAGAL = {
    "nomor_tidak_terdaftar": "Nomor tidak terdaftar di WhatsApp (nomor_tidak_terdaftar)",
    "timeout": "Chat tidak terbuka dalam 45 detik",
    "teks_tidak_terisi": "Pesan tidak terisi di kotak chat",
}


class NotAllowed(Exception):
    """Tidak boleh mulai kirim sekarang. Pesannya untuk pengguna."""


class WA(Protocol):
    def open_chat(self, nomor: str, teks: str) -> actions.OpenResult: ...
    def send(self) -> actions.SendResult: ...
    def clear_draft(self) -> None: ...


class WorkerWA:
    """Adaptor ke thread worker Playwright."""

    def open_chat(self, nomor: str, teks: str) -> actions.OpenResult:
        def run(b):
            b.open()  # tidak membuka dua kali bila sudah terbuka
            return actions.open_chat(b, nomor, teks)

        return worker.call(run, timeout=120)

    def send(self) -> actions.SendResult:
        return worker.call(actions.send, timeout=90)

    def clear_draft(self) -> None:
        worker.call(actions.clear_draft, timeout=30)


@dataclass
class State:
    running: bool = False
    coba: bool = False
    sesi: int | None = None
    target: int = 0
    dicoba: int = 0  # jumlah fasil yang sudah diproses di putaran ini
    terkirim: int = 0
    gagal: int = 0
    sekarang: str = ""  # nama fasil yang sedang diproses
    berikutnya: str = ""
    berikutnya_pada: float | None = None  # epoch detik
    stop_diminta: bool = False
    berhenti_karena: str = ""
    mulai: float | None = None
    selesai: float | None = None
    hasil: list[dict] = field(default_factory=list)
    bypass: bool = False  # dikirim lewat bypass sesi (tanpa jam & kuota sesi)


class Sender:
    def __init__(
        self,
        wa: WA | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], object] = schedule.now,
        load_rows: Callable[[], list[BroadcastRow]] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.wa = wa or WorkerWA()
        self.sleep = sleep
        self.clock = clock
        self.load_rows = load_rows or (lambda: read_broadcast(refresh=True))
        self.rng = rng or random.Random()
        self.state = State()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ---------- info ----------

    def snapshot(self) -> dict:
        d = asdict(self.state)
        d["hasil"] = d["hasil"][-20:]
        return d

    def _settings(self) -> tuple[str, int, bool]:
        petugas = db.get_setting("nama_petugas")
        if not petugas:
            raise NotAllowed("Nama petugas belum dipilih.")
        return (
            petugas,
            int(db.get_setting("batas_harian", config.BATAS_HARIAN_DEFAULT)),
            bool(db.get_setting("kirim_akhir_pekan", False)),
        )

    def antrean(self) -> list[send_queue.Item]:
        petugas, _, _ = self._settings()
        rows = filter_petugas(self.load_rows(), petugas)
        sends = store.sends_real()
        wag = undangan_wag.pengaturan()
        if wag.aktif:  # mode Undangan WAG: pesan undangan grup, bukan pesan Broadcast
            return undangan_wag.build(rows, sends, wag)
        bc = [x for x in sends if not x["hash_pesan"].startswith(undangan_wag.AWALAN)]
        return send_queue.build(rows, bc, self.clock().date(), store.ulang_all())

    def kondisi(self, items: list[send_queue.Item] | None = None) -> schedule.Kondisi:
        _, batas, akhir_pekan = self._settings()
        items = items if items is not None else self.antrean()
        t = self.clock()
        total, per = store.counts(schedule.tanggal_str(t.date()))
        return schedule.kondisi(t, batas, akhir_pekan, total, per, len(send_queue.eligible(items)),
                                bypass=self.bypass_aktif())

    def bypass_aktif(self) -> bool:
        """Bypass sesi hanya berlaku di hari dinyalakan."""
        b = db.get_setting("bypass_sesi") or {}
        return b.get("tanggal") == schedule.tanggal_str(self.clock().date())

    # ---------- kontrol ----------

    def start(self, coba: bool = False) -> dict:
        with self._lock:
            if self.state.running:
                raise NotAllowed("Pengiriman sedang berjalan.")
            items = self.antrean()
            k = self.kondisi(items)
            if not k.bisa_kirim:
                raise NotAllowed(k.judul)
            todo = send_queue.eligible(items)
            bypass = k.kode == "bypass"
            self.state = State(running=True, coba=coba, sesi=0 if bypass else k.sesi.no, target=k.kuota,
                               mulai=time.time(), bypass=bypass)
            self._thread = threading.Thread(target=self._run, args=(todo, k.sesi), name="sender", daemon=True)
            self._thread.start()
        events.publish("kirim_mulai", **self.snapshot())
        return self.snapshot()

    def stop(self) -> dict:
        if self.state.running:
            self.state.stop_diminta = True
            events.publish("kirim_stop_diminta")
        return self.snapshot()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ---------- loop ----------

    def _halt(self, alasan: str) -> None:
        self.state.berhenti_karena = alasan
        log.warning("Pengiriman berhenti: %s", alasan)

    def _run(self, todo: list[send_queue.Item], sesi: config.Sesi | None) -> None:
        st = self.state
        gagal_beruntun = 0
        max_percobaan = st.target * 2  # gagal tidak mengurangi kuota; cegah loop panjang
        try:
            for idx, item in enumerate(todo):
                if st.stop_diminta:
                    self._halt("Dihentikan oleh pengguna.")
                    break
                if st.dicoba >= max_percobaan:
                    break
                sisa = self._sisa_kuota(sesi)
                if sisa is None:
                    self._halt("Bypass sesi sudah tidak berlaku." if st.bypass else f"Sesi {sesi.no} sudah berakhir.")
                    break
                if sisa <= 0:
                    break

                st.sekarang, st.berikutnya, st.berikutnya_pada = item.nama_fasil, "", None
                events.publish("kirim_proses", nama=item.nama_fasil, ke=st.dicoba + 1, target=st.target)
                status, ket = self._proses(item, st.coba)
                st.dicoba += 1

                t = self.clock()
                store.record_send(
                    tanggal=schedule.tanggal_str(t.date()), waktu=t.isoformat(timespec="seconds"),
                    sesi=self._no_sesi(t, sesi), nama_fasil=item.nama_fasil, nomor=item.nomor, hash_pesan=item.hash_pesan,
                    status=status, keterangan=ket, coba=st.coba,
                )
                st.hasil.append({"nama": item.nama_fasil, "status": status, "keterangan": ket,
                                 "waktu": t.strftime("%H.%M")})
                events.publish("kirim_hasil", nama=item.nama_fasil, status=status, keterangan=ket)

                if status == "terkirim":
                    st.terkirim += 1
                    gagal_beruntun = 0
                elif status == "dicoba":
                    gagal_beruntun = 0
                else:
                    st.gagal += 1
                    gagal_beruntun += 1
                    if gagal_beruntun >= 2:
                        self._halt(f"2 pesan gagal beruntun. Terakhir: {ket}")
                        break

                masih_ada = idx + 1 < len(todo)
                cukup = (st.dicoba >= st.target) if st.coba else (self._sisa_kuota(sesi) or 0) <= 0
                if not masih_ada or cukup or st.stop_diminta:
                    continue
                self._jeda(todo[idx + 1].nama_fasil, st.coba)
        except (actions.NotLoggedIn, BrowserClosed) as e:
            self._halt(f"WhatsApp terputus: {e} Scan ulang QR lalu mulai lagi.")
        except Exception as e:  # jangan biarkan thread mati diam-diam
            log.exception("Pengiriman error")
            self._halt(f"Terjadi kesalahan: {e}")
        finally:
            st.running, st.sekarang, st.berikutnya, st.berikutnya_pada = False, "", "", None
            st.selesai = time.time()
            events.publish("kirim_selesai", **self.snapshot())

    def _no_sesi(self, t, sesi: config.Sesi | None) -> int:
        """Nomor sesi untuk catatan kirim; lewat bypass di luar jam sesi = 0."""
        if not self.state.bypass:
            return sesi.no
        aktif = schedule.sesi_at(t)
        return aktif.no if aktif else 0

    def _sisa_kuota(self, sesi: config.Sesi | None) -> int | None:
        """Sisa kuota sekarang; None bila sesi (atau bypass) sudah berakhir."""
        t = self.clock()
        if self.state.bypass:
            if not self.bypass_aktif() or not (schedule.BYPASS_MULAI <= t.time() <= schedule.BYPASS_SAMPAI):
                return None
            if self.state.coba:
                return self.state.target - self.state.dicoba
            _, batas, _ = self._settings()
            total, _ = store.counts(schedule.tanggal_str(t.date()))
            return max(0, batas - total)
        aktif = schedule.sesi_at(t)
        if aktif is None or aktif.no != sesi.no:
            return None
        if self.state.coba:
            return self.state.target - self.state.dicoba
        _, batas, _ = self._settings()
        total, per = store.counts(schedule.tanggal_str(t.date()))
        return schedule.kuota_efektif(sesi, per.get(sesi.no, 0), batas, total, 10**6)

    def _proses(self, item: send_queue.Item, coba: bool) -> tuple[str, str]:
        teks = item.pesan
        if item.hash_pesan.startswith(undangan_wag.AWALAN):
            teks = undangan_wag.isi_salam(teks, self.clock())
        res = self.wa.open_chat(item.nomor, teks)
        if not res.ok:
            if res.alasan == "nomor_tidak_terdaftar" and not coba:
                tagging.tandai(item.nomor, "merah")
            return "gagal", ALASAN_GAGAL.get(res.alasan, res.alasan)
        if coba:
            self.sleep(2)  # supaya terlihat di layar
            self.wa.clear_draft()
            return "dicoba", "Mode coba, tidak dikirim"
        r = self.wa.send()
        if r.status == "terkirim":
            tagging.tandai(item.nomor, tagging.warna_kirim(getattr(r, "centang", "")))
        return r.status, r.keterangan

    def _jeda(self, nama_berikutnya: str, coba: bool) -> None:
        detik = 3 if coba else self.rng.uniform(config.JEDA_MIN_DETIK, config.JEDA_MAX_DETIK)
        st = self.state
        st.berikutnya, st.berikutnya_pada = nama_berikutnya, time.time() + detik
        events.publish("kirim_jeda", berikutnya=nama_berikutnya, detik=round(detik))
        sisa = detik
        while sisa > 0 and not st.stop_diminta:
            step = min(1.0, sisa)
            self.sleep(step)
            sisa -= step


sender = Sender()
