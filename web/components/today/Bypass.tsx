"use client";

import { useEffect, useState } from "react";
import { post } from "@/lib/api";
import { BATAS, KALIMAT_RISIKO } from "@/lib/types";
import { Button } from "@/components/ui";
import s from "./today.module.css";

/** Popup menyalakan bypass sesi: wajib mengetik kalimat risiko. Berlaku sampai akhir hari. */
export function BypassModal({ batas, onClose, onDone }: { batas: number; onClose: () => void; onDone: () => void }) {
  const [teks, setTeks] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cocok = teks.trim().toLowerCase().split(/\s+/).join(" ") === KALIMAT_RISIKO;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function nyalakan() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/send/bypass", { aktif: true, konfirmasi: teks });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className={s.bpScrim} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className={s.bpModal} role="alertdialog" aria-modal="true" aria-labelledby="bp-judul" aria-describedby="bp-isi">
        <h2 id="bp-judul">Kirim di luar jadwal sesi?</h2>
        <div id="bp-isi">
          <p>Bypass sesi mengabaikan jam sesi dan kuota per sesi, sehingga pesan bisa dikirim lebih rapat dari jadwal
            tim. Risiko nomor WhatsApp dibatasi atau diblokir naik.</p>
          <ul>
            <li>Tetap berlaku: batas harian <b>{batas}</b> pesan, jeda acak 45–120 detik, tidak ada kirim dobel dalam
              seminggu.</li>
            <li>Hanya pukul 07.00–22.00, hari kerja.</li>
            <li>Berlaku hari ini saja, besok kembali mengikuti sesi. Bisa dimatikan kapan saja.</li>
            {batas > BATAS.merah && <li>Batas harian Anda di atas {BATAS.merah}: risikonya jauh lebih tinggi.</li>}
          </ul>
        </div>
        <label htmlFor="bp-kalimat" className={s.bpLabel}>
          Bila nomor diblokir, risiko ditanggung sendiri. Ketik <b>{KALIMAT_RISIKO}</b> untuk melanjutkan:
        </label>
        <input id="bp-kalimat" className={s.bpInput} value={teks} onChange={(e) => setTeks(e.target.value)}
          placeholder={KALIMAT_RISIKO} autoComplete="off" spellCheck={false} autoFocus
          aria-invalid={teks.length > 0 && !cocok} />
        {error && <p className={s.bpErr}>{error}</p>}
        <div className={s.bpActions}>
          <Button variant="secondary" disabled={busy} onClick={onClose}>Batal</Button>
          <Button variant="danger" loading={busy} disabled={!cocok} onClick={() => void nyalakan()}>
            Nyalakan bypass hari ini
          </Button>
        </div>
      </div>
    </div>
  );
}
