"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import { Button } from "@/components/ui";
import s from "./app.module.css";

function inisial(nama: string) {
  const k = nama.trim().split(/\s+/);
  return ((k[0]?.[0] ?? "") + (k[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Profil petugas: status WhatsApp, batas harian, dan keluar / ganti akun Google. */
export function UserMenu({ nama, email, waLabel, waDot, batas, ringkas = false }: {
  nama: string;
  email: string;
  waLabel: string;
  waDot: string;
  batas: number;
  ringkas?: boolean;
}) {
  const [buka, setBuka] = useState(false);
  const [konfirmasi, setKonfirmasi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!buka) return;
    const tutup = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setBuka(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setBuka(false); };
    document.addEventListener("mousedown", tutup);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", tutup);
      document.removeEventListener("keydown", esc);
    };
  }, [buka]);

  async function keluar() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/auth/logout");
      // Muat ulang penuh (bukan router.push) supaya semua data akun lama di memori ikut dibuang
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/setup/";
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className={`${s.userWrap} ${ringkas ? s.userRingkas : ""}`} ref={ref}>
      {buka && (
        <div className={s.userMenu} role="menu">
          <div className={s.userHead}>
            <b>{nama}</b>
            <small>{email}</small>
            <small><i className={s.dot} style={{ background: waDot }} /> {waLabel}</small>
          </div>
          <Link href="/setup/" role="menuitem" className={s.menuItem} onClick={() => setBuka(false)}>
            Ubah batas harian <span>{batas} pesan</span>
          </Link>
          <button type="button" role="menuitem" className={`${s.menuItem} ${s.menuDanger}`}
            onClick={() => { setBuka(false); setKonfirmasi(true); }}>
            Keluar / ganti akun Google
          </button>
        </div>
      )}
      <button type="button" className={s.user} onClick={() => setBuka(!buka)} aria-expanded={buka} aria-haspopup="menu"
        data-tour="wa" title={ringkas ? `${nama}. ${waLabel}` : undefined}>
        <span className={s.avatar} aria-hidden="true">
          {inisial(nama)}
          <i style={{ background: waDot }} />
        </span>
        {!ringkas && (
          <span className={s.lbl}>
            <b>{nama}</b>
            <small>{waLabel}</small>
          </span>
        )}
      </button>

      {konfirmasi && (
        <div className={s.modalScrim} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) setKonfirmasi(false); }}>
          <div className={s.modal} role="alertdialog" aria-modal="true" aria-labelledby="out-judul" aria-describedby="out-isi">
            <h2 id="out-judul">Keluar dari {email || "akun ini"}?</h2>
            <p id="out-isi">
              Setelah keluar, masuk lagi dengan akun Google dan pilih nama petugas. Riwayat kirim di laptop ini tetap tersimpan.
            </p>
            {error && <p className={s.modalErr}>{error}</p>}
            <div className={s.modalActions}>
              <Button variant="secondary" disabled={busy} onClick={() => setKonfirmasi(false)}>Batal</Button>
              <Button variant="danger" loading={busy} onClick={() => void keluar()}>Keluar</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
