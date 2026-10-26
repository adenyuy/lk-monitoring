"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui";
import s from "./app.module.css";

export function LockIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

/** Popup: petugas tanpa fitur 'cutoff' di sheet Akses. */
export function NoAccess({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className={s.modalScrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={s.modal} role="alertdialog" aria-modal="true" aria-labelledby="na-judul" aria-describedby="na-isi">
        <span className={s.modalIcon}><LockIcon size={22} /></span>
        <h2 id="na-judul">Anda tidak punya akses Tarik Cutoff</h2>
        <p id="na-isi">
          Fitur ini hanya untuk admin cutoff. Bila Anda perlu menarik data cutoff, minta koordinator
          menambahkan fitur <b>cutoff</b> untuk email Anda di sheet Akses.
        </p>
        <Button autoFocus onClick={onClose}>Mengerti</Button>
      </div>
    </div>
  );
}
