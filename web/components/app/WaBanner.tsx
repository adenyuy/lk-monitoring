"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import type { WaStatus } from "@/lib/types";
import { Button } from "@/components/ui";
import s from "./app.module.css";

const KUNCI = "lkm-wa-banner-ditutup";

function bacaDitutup() {
  try {
    return sessionStorage.getItem(KUNCI);
  } catch {
    return null;
  }
}

/** Pengingat merah di bawah navbar selama WhatsApp Web belum siap. Bisa ditutup; muncul lagi bila statusnya berubah. */
export function WaBanner({ wa, onChange }: { wa: WaStatus | null; onChange: (w: WaStatus) => void }) {
  const [ditutup, setDitutup] = useState<string | null>(bacaDitutup);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!wa || wa.state === "logged_in" || wa.state === "loading" || ditutup === wa.state) return null;

  const qr = wa.state === "qr";
  const judul = qr ? "WhatsApp menunggu scan QR" : "WhatsApp belum dibuka";
  const isi = qr
    ? "Scan kode QR di jendela Chrome yang terbuka memakai HP petugas. Pesan baru bisa dikirim setelah itu."
    : "Pesan tidak bisa dikirim dan chat tidak bisa dibaca sebelum WhatsApp Web terbuka.";

  function tutup() {
    if (!wa) return;
    setDitutup(wa.state);
    try {
      sessionStorage.setItem(KUNCI, wa.state);
    } catch {
      /* cukup disembunyikan untuk halaman ini */
    }
  }

  async function buka() {
    setBusy(true);
    setError(null);
    try {
      onChange(await post<WaStatus>("/api/wa/connect"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.bannerWrap}>
      <div className={s.banner} role="alert">
        <svg className={s.bannerIcon} viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
        <div className={s.bannerText}>
          <b>{judul}</b>
          <span>{error ?? isi}</span>
        </div>
        {!qr && (
          <Button variant="danger" size="sm" loading={busy} onClick={buka}>
            {busy ? "Membuka…" : "Buka WhatsApp"}
          </Button>
        )}
        <button type="button" className={s.bannerClose} onClick={tutup} aria-label="Tutup pengingat">
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
