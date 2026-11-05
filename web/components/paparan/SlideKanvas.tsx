"use client";

import { useEffect, useRef, useState } from "react";
import s from "./paparan.module.css";

// Satu bentuk dalam koordinat 720 x 405 pt; sama persis dengan yang dikirim ke Google Slides.
export type Bentuk =
  | { t: "rect"; x: number; y: number; w: number; h: number; fill: string; round?: boolean }
  | { t: "text"; x: number; y: number; w: number; h: number; text: string; size: number; color: string; bold: boolean;
      align: "START" | "CENTER" | "END"; bullets?: boolean; ubah?: string }
  | { t: "table"; x: number; y: number; w: number; size: number;
      cols: { label: string; w: number; align?: "END" }[]; rows: string[][] };

export type Slide = { kunci: string; judul: string; lanjutan: boolean; bentuk: Bentuk[]; catatan: string };

export const LEBAR = 720;
export const TINGGI = 405;
const RATA = { START: "left", CENTER: "center", END: "right" } as const;

/** Gambar satu slide, diskalakan mengikuti lebar wadahnya (atau `muat` = muat di layar penuh). */
export function SlideKanvas({ slide, langkah, muat = false }: { slide: Slide; langkah?: string[]; muat?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [ukuran, setUkuran] = useState({ k: 1, x: 0, y: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ukur = () => {
      const r = el.getBoundingClientRect();
      const k = muat ? Math.min(r.width / LEBAR, r.height / TINGGI) : r.width / LEBAR;
      setUkuran({ k, x: muat ? (r.width - LEBAR * k) / 2 : 0, y: muat ? (r.height - TINGGI * k) / 2 : 0 });
    };
    ukur();
    const ro = new ResizeObserver(ukur);
    ro.observe(el);
    return () => ro.disconnect();
  }, [muat]);

  return (
    <div ref={ref} className={muat ? s.kanvasMuat : s.kanvas}>
      <div className={s.halaman} style={{ transform: `translate(${ukuran.x}px, ${ukuran.y}px) scale(${ukuran.k})` }} aria-label={slide.judul} role="img">
        {slide.bentuk.map((b, i) => {
          if (b.t === "rect") {
            return <span key={i} className={s.kotak} style={{ left: b.x, top: b.y, width: b.w, height: b.h,
              background: b.fill, borderRadius: b.round ? Math.min(b.h, b.w) / 2 : 0 }} />;
          }
          if (b.t === "text") {
            const teks = b.ubah === "langkah" && langkah ? langkah.join("\n") : b.text;
            const gaya = { left: b.x, top: b.y, width: b.w, height: b.h, fontSize: b.size, color: b.color,
              fontWeight: b.bold ? 600 : 400, textAlign: RATA[b.align] };
            if (b.bullets) {
              return (
                <ul key={i} className={`${s.teks} ${s.poin}`} style={gaya}>
                  {teks.split("\n").filter((x) => x.trim()).map((x, j) => <li key={j}>{x}</li>)}
                </ul>
              );
            }
            return <div key={i} className={s.teks} style={gaya}>{teks}</div>;
          }
          return (
            <table key={i} className={s.tabel} style={{ left: b.x, top: b.y, width: b.w, fontSize: b.size }}>
              <colgroup>{b.cols.map((c, j) => <col key={j} style={{ width: c.w }} />)}</colgroup>
              <thead>
                <tr>{b.cols.map((c, j) => <th key={j} style={{ textAlign: c.align === "END" ? "right" : "left" }}>{c.label}</th>)}</tr>
              </thead>
              <tbody>
                {b.rows.map((r, j) => (
                  <tr key={j}>
                    {r.map((v, k) => <td key={k} style={{ textAlign: b.cols[k]?.align === "END" ? "right" : "left" }}>{v}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        })}
      </div>
    </div>
  );
}
