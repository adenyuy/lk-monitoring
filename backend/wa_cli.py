"""Alat uji manual mesin WhatsApp (Fase 4.7). Tidak dipakai oleh aplikasi.

    python wa_cli.py connect                 buka WhatsApp Web, tunggu sampai login (scan QR)
    python wa_cli.py status
    python wa_cli.py coba  <nomor> "<teks>"  buka chat + isi pesan, TIDAK dikirim (draft dihapus)
    python wa_cli.py kirim <nomor> "<teks>"  kirim sungguhan + cek terkirim
    python wa_cli.py baca  <nomor>           status pesan terakhir + balasan

Nomor boleh 08… / 62… / +62…. Gunakan nomor sendiri untuk uji, bukan fasilitator.
"""

import sys
import time

from app.sheets import normalize_nomor
from app.wa import actions, status
from app.wa.browser import worker


def need_login(b):
    b.open()
    snap = status.wait_logged_in(b, timeout=180)
    if snap["state"] != "logged_in":
        raise SystemExit(f"WhatsApp belum login (status: {snap['state']}). Jalankan: python wa_cli.py connect")
    return snap


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    t0 = time.time()

    if cmd in ("connect", "status"):
        def run(b):
            b.open()
            return status.wait_logged_in(b, timeout=180 if cmd == "connect" else 20)
        snap = worker.call(run, timeout=240)
        print(f"Status: {snap['state']}  nomor: {snap['nomor_tersamar'] or '-'}")

    elif cmd in ("coba", "kirim"):
        nomor, teks = normalize_nomor(args[0]), args[1]
        if not nomor:
            raise SystemExit("Nomor tidak valid.")

        def run(b):
            need_login(b)
            res = actions.open_chat(b, nomor, teks)
            if not res.ok:
                return f"Gagal membuka chat: {res.alasan}"
            if cmd == "coba":
                b.page.wait_for_timeout(2500)  # supaya sempat terlihat di layar
                actions.clear_draft(b)
                return "Mode coba OK: chat terbuka, pesan terisi lalu dihapus (tidak dikirim)."
            r = actions.send(b)
            return f"Kirim: {r.status} {r.keterangan}".strip()

        print(worker.call(run, timeout=300))

    elif cmd == "baca":
        nomor = normalize_nomor(args[0])

        def run(b):
            need_login(b)
            return actions.read_chat(b, nomor)

        info = worker.call(run, timeout=300)
        print(f"Status: {info.status}")
        print(f"Pesan keluar terakhir: {info.pesan_keluar_terakhir[:120]!r}")
        for m in info.balasan:
            print(f"Balasan: {m[:200]!r}")
    else:
        print(__doc__)
        return

    print(f"({time.time() - t0:.1f} dtk)")
    worker.shutdown()


if __name__ == "__main__":
    main()
