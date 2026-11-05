"use client";

import { useEffect, useRef, useState } from "react";
import { KODE_WARNA } from "@/lib/lk";
import s from "./lk.module.css";

/** Tombol kecil kode Log Komunikasi hari ini; diklik membuka pilihan T, T1, T2, TP, R, C, N. */
export function KodePicker({ nilai, kode, onPilih, label, besar }: {
  nilai: string;
  kode: { kode: string; arti: string }[];
  onPilih: (kode: string) => void;
  label: string;
  besar?: boolean;
}) {
  const [buka, setBuka] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!buka) return;
    const tutup = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setBuka(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setBuka(false); };
    window.addEventListener("mousedown", tutup);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("mousedown", tutup); window.removeEventListener("keydown", esc); };
  }, [buka]);

  const w = KODE_WARNA[nilai];
  if (besar) {
    return (
      <div className={s.kodeGrid} role="radiogroup" aria-label={label}>
        {kode.map((k) => {
          const c = KODE_WARNA[k.kode];
          const aktif = nilai === k.kode;
          return (
            <button key={k.kode} type="button" role="radio" aria-checked={aktif} title={k.arti}
              className={s.kodeOpsi} style={aktif ? { background: c.bg, color: c.fg, borderColor: c.fg } : undefined}
              onClick={() => onPilih(aktif ? "" : k.kode)}>
              <b style={{ color: c.fg }}>{k.kode}</b>
              <span>{k.arti}</span>
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <div className={s.kodeWrap} ref={ref}>
      <button type="button" className={s.kodeBtn} aria-haspopup="listbox" aria-expanded={buka} title={label}
        style={w ? { background: w.bg, color: w.fg, borderColor: "transparent" } : undefined}
        onClick={(e) => { e.stopPropagation(); setBuka(!buka); }}>
        {nilai || "Catat"}
        <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {buka && (
        <ul className={s.kodeMenu} role="listbox" aria-label={label}>
          {kode.map((k) => {
            const c = KODE_WARNA[k.kode];
            return (
              <li key={k.kode} role="option" aria-selected={nilai === k.kode}>
                <button type="button" onClick={() => { onPilih(k.kode); setBuka(false); }}>
                  <b style={{ background: c.bg, color: c.fg }}>{k.kode}</b>
                  <span>{k.arti}</span>
                </button>
              </li>
            );
          })}
          {nilai && (
            <li><button type="button" className={s.kodeHapus} onClick={() => { onPilih(""); setBuka(false); }}>Kosongkan</button></li>
          )}
        </ul>
      )}
    </div>
  );
}
