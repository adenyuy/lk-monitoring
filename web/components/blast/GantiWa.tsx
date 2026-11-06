"use client";

// Kartu WhatsApp pengirim dan dialog ganti nomor (keluar lalu scan QR baru). Dipakai di Blast dan Blast admin.

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { WaStatus } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./blast.module.css";

/** Nomor WhatsApp pengirim + tombol Ganti. */
export function WaKartu({ jalan, onGanti }: { jalan: boolean; onGanti: () => void }) {
  const [wa, setWa] = useState<WaStatus | null>(null);
  const muat = useCallback(async () => {
    try { setWa(await api<WaStatus>("/api/wa/status")); } catch { /* status diperbarui berkala */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  usePolling(muat, 15000, true);
  const label = wa?.state === "logged_in" ? (wa.nomor_tersamar || "Terhubung")
    : wa?.state === "qr" ? "Menunggu scan QR" : wa?.state === "closed" ? "Jendela WhatsApp tertutup" : "Memeriksa…";
  return (
    <div className={s.waKartu}>
      <span className={`${s.waTitik} ${wa?.state === "logged_in" ? s.waOn : ""}`} aria-hidden="true" />
      <span><small>WhatsApp pengirim</small><b>{label}</b></span>
      <button type="button" onClick={onGanti} disabled={jalan} title={jalan ? "Hentikan blast dulu" : undefined}>
        Ganti
      </button>
    </div>
  );
}

export function GantiWa({ onTutup }: { onTutup: () => void }) {
  const [tahap, setTahap] = useState<"tanya" | "keluar" | "scan" | "selesai" | "gagal">("tanya");
  const [ket, setKet] = useState("");
  const [cara, setCara] = useState("");
  const [nomor, setNomor] = useState("");

  async function mulai() {
    setTahap("keluar");
    try {
      const r = await post<WaStatus & { cara: string }>("/api/wa/keluar");
      setCara(r.cara);
      await post("/api/wa/connect");
      setTahap("scan");
      for (let i = 0; i < 120; i++) {
        await new Promise((res) => setTimeout(res, 2500));
        const st = await api<WaStatus>("/api/wa/status");
        if (st.state === "logged_in") { setNomor(st.nomor_tersamar); setTahap("selesai"); return; }
      }
      setKet("QR belum di-scan. Tutup dialog ini, lalu scan QR di jendela WhatsApp kapan saja.");
      setTahap("gagal");
    } catch (e) {
      setKet(e instanceof Error ? e.message : String(e));
      setTahap("gagal");
    }
  }

  return (
    <div className={s.scrim} role="presentation">
      <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="ganti-wa">
        <h2 id="ganti-wa">Ganti nomor WhatsApp</h2>
        {tahap === "tanya" && (
          <>
            <p>Nomor yang tertaut sekarang akan dikeluarkan dari aplikasi ini, lalu jendela WhatsApp menampilkan QR baru.
              Scan dengan HP nomor yang ingin dipakai (WhatsApp → Perangkat tertaut → Tautkan perangkat).</p>
            <p className={s.ket}>Riwayat kirim dan status chat di aplikasi tetap tersimpan.</p>
          </>
        )}
        {tahap === "keluar" && <p className={s.tunggu}><Spinner /> Mengeluarkan nomor lama…</p>}
        {tahap === "scan" && (
          <>
            <p className={s.tunggu}><Spinner /> Scan QR di jendela Chrome WhatsApp yang terbuka dengan HP nomor baru.</p>
            {cara === "profil" && <p className={s.ket}>Nomor lama dikeluarkan dari aplikasi ini. Di HP lama, hapus juga
              perangkat ini dari WhatsApp → Perangkat tertaut supaya rapi.</p>}
          </>
        )}
        {tahap === "selesai" && <Notice tone="ok" title="WhatsApp tersambung">Sekarang mengirim dari {nomor || "nomor baru"}.</Notice>}
        {tahap === "gagal" && <Notice tone="warn">{ket}</Notice>}
        <div className={s.dialogAksi}>
          {tahap === "tanya" && <Button variant="ghost" onClick={onTutup}>Batal</Button>}
          {tahap === "tanya" && <Button variant="danger" onClick={() => void mulai()}>Keluarkan & scan nomor baru</Button>}
          {(tahap === "selesai" || tahap === "gagal" || tahap === "scan") && <Button variant="secondary" onClick={onTutup}>Tutup</Button>}
        </div>
      </div>
    </div>
  );
}
