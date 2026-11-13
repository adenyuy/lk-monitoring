"use client";

import { useRef, useState, type ReactNode } from "react";
import s from "./tip.module.css";

/** Penjelasan saat label di-hover atau difokus (keyboard). Posisi fixed supaya tidak terpotong tabel yang bisa digulir. */
export function Tip({ isi, children, kanan = false }: { isi: ReactNode; children: ReactNode; kanan?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number; atas: boolean } | null>(null);

  const buka = () => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const lebar = 300;
    const x = Math.max(12, Math.min(window.innerWidth - lebar - 12, kanan ? r.right - lebar : r.left));
    const atas = r.bottom + 180 > window.innerHeight && r.top > 200;
    setPos({ x, y: atas ? r.top - 8 : r.bottom + 8, atas });
  };

  return (
    <span ref={ref} className={s.pemicu} onMouseEnter={buka} onMouseLeave={() => setPos(null)}
      onFocus={buka} onBlur={() => setPos(null)}>
      {children}
      <span className={s.ikon} tabIndex={0} role="img" aria-label="Penjelasan">i</span>
      {pos && (
        <span role="tooltip" className={`${s.isi} ${pos.atas ? s.atas : ""}`} style={{ left: pos.x, top: pos.y }}>{isi}</span>
      )}
    </span>
  );
}
