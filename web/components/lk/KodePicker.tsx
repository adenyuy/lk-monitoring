"use client";

import { KODE_WARNA } from "@/lib/lk";
import s from "./lk.module.css";

/** Dropdown kode Log Komunikasi hari ini (T, T1, T2, TP, R, C, N). Warnanya mengikuti kode yang dipilih.
 *  Yang terlihat hanya ringkasannya; pilihan lengkap (kode + arti) muncul di dropdown bawaan browser. */
export function KodePicker({ nilai, kode, onPilih, label, besar, disabled }: {
  nilai: string;
  kode: { kode: string; arti: string }[];
  onPilih: (kode: string) => void;
  label: string;
  besar?: boolean;
  disabled?: boolean;
}) {
  const w = KODE_WARNA[nilai];
  const arti = kode.find((k) => k.kode === nilai)?.arti;
  return (
    <span className={`${s.kodeSelect} ${besar ? s.kodeSelectBesar : ""} ${nilai ? s.kodeSelectIsi : ""}`}
      style={w ? { background: w.bg, color: w.fg } : undefined}>
      <span className={s.kodeTampil} aria-hidden="true">
        {nilai ? <><b>{nilai}</b>{besar && arti ? <span>{arti}</span> : null}</> : <span>{besar ? "Pilih kode komunikasi hari ini" : "Catat"}</span>}
      </span>
      <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <select value={nilai} aria-label={label} title={nilai ? `${nilai}: ${arti}` : label} disabled={disabled}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => onPilih(e.target.value)}>
        <option value="">— Belum dicatat —</option>
        {kode.map((k) => (
          <option key={k.kode} value={k.kode}>{k.kode} · {k.arti}</option>
        ))}
      </select>
    </span>
  );
}
