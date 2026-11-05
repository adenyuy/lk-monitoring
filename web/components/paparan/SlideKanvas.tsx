"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import s from "./paparan.module.css";

// Satu bentuk dalam koordinat 720 x 405 pt; sama persis dengan yang dikirim ke Google Slides.
export type Bentuk =
  | { t: "rect"; x: number; y: number; w: number; h: number; fill: string; round?: boolean }
  | { t: "text"; x: number; y: number; w: number; h: number; text: string; size: number; color: string; bold: boolean;
      align: "START" | "CENTER" | "END"; bullets?: boolean; ubah?: string }
  | { t: "table"; x: number; y: number; w: number; size: number;
      cols: { label: string; w: number; align?: "END" }[]; rows: string[][] };

export type Slide = { kunci: string; judul: string; lanjutan: boolean; bentuk: Bentuk[]; catatan: string; halaman?: number };

/** Teks yang diedit PIC: kunci `${slide}:${halaman}:${bentuk}` atau `...:${baris}:${kolom}` (baris -1 = judul kolom). */
export type Ubahan = Record<string, { asli: string; baru: string }>;

export const LEBAR = 720;
export const TINGGI = 405;
const RATA = { START: "left", CENTER: "center", END: "right" } as const;

export const awalan = (x: Slide) => `${x.kunci}:${x.halaman ?? 0}`;

type Props = {
  slide: Slide; langkah?: string[]; muat?: boolean;
  ubahan?: Ubahan; edit?: boolean; onUbah?: (kunci: string, asli: string, baru: string) => void;
};

/** Gambar satu slide, diskalakan mengikuti lebar wadahnya (atau `muat` = muat di layar penuh). */
export function SlideKanvas({ slide, langkah, muat = false, ubahan, edit = false, onUbah }: Props) {
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

  const pre = awalan(slide);
  const tampil = (kunci: string, asli: string) => {
    const u = ubahan?.[kunci];
    return u && u.asli === asli ? u.baru : asli;
  };
  // teks yang bisa diedit: simpan saat fokus lepas; Enter = baris baru, Esc = batal
  const bisaEdit = (kunci: string, asli: string) => (edit && onUbah ? {
    contentEditable: true, suppressContentEditableWarning: true, className: s.bisaEdit, spellCheck: false,
    onBlur: (e: React.FocusEvent<HTMLElement>) => {
      const v = e.currentTarget.innerText.replace(/\n+$/, "");
      if (v !== tampil(kunci, asli)) onUbah(kunci, asli, v);
    },
    onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => {
      if (e.key === "Escape") { e.currentTarget.innerText = tampil(kunci, asli); e.currentTarget.blur(); }
    },
  } : {});

  return (
    <div ref={ref} className={muat ? s.kanvasMuat : s.kanvas}>
      <div className={`${s.halaman} ${edit ? s.halamanEdit : ""}`} role={edit ? undefined : "img"} aria-label={slide.judul}
        style={{ transform: `translate(${ukuran.x}px, ${ukuran.y}px) scale(${ukuran.k})` }}>
        {slide.bentuk.map((b, i) => {
          if (b.t === "rect") {
            return <span key={i} className={s.kotak} style={{ left: b.x, top: b.y, width: b.w, height: b.h,
              background: b.fill, borderRadius: b.round ? Math.min(b.h, b.w) / 2 : 0 }} />;
          }
          if (b.t === "text") {
            const gaya: CSSProperties = { left: b.x, top: b.y, width: b.w, height: b.h, fontSize: b.size, color: b.color,
              fontWeight: b.bold ? 600 : 400, textAlign: RATA[b.align] };
            if (b.bullets) {
              const teks = b.ubah === "langkah" && langkah ? langkah.join("\n") : b.text;
              return (
                <ul key={i} className={`${s.teks} ${s.poin}`} style={gaya}>
                  {teks.split("\n").filter((x) => x.trim()).map((x, j) => <li key={j}>{x}</li>)}
                </ul>
              );
            }
            const k = `${pre}:${i}`;
            const isi = tampil(k, b.text);
            return <div key={`${k}:${isi}`} style={gaya} {...bisaEdit(k, b.text)}
              className={`${s.teks} ${edit ? s.bisaEdit : ""}`}>{isi}</div>;
          }
          const sel = (r: number, c: number, asli: string, akhir: boolean) => {
            const k = `${pre}:${i}:${r}:${c}`;
            const isi = tampil(k, asli);
            const Tag = r === -1 ? "th" : "td";
            return <Tag key={`${c}:${isi}`} style={{ textAlign: akhir ? "right" : "left" }} {...bisaEdit(k, asli)}
              className={edit ? s.bisaEdit : undefined}>{isi}</Tag>;
          };
          return (
            <table key={i} className={s.tabel} style={{ left: b.x, top: b.y, width: b.w, fontSize: b.size }}>
              <colgroup>{b.cols.map((c, j) => <col key={j} style={{ width: c.w }} />)}</colgroup>
              <thead><tr>{b.cols.map((c, j) => sel(-1, j, c.label, c.align === "END"))}</tr></thead>
              <tbody>
                {b.rows.map((r, j) => <tr key={j}>{r.map((v, c) => sel(j, c, v, b.cols[c]?.align === "END"))}</tr>)}
              </tbody>
            </table>
          );
        })}
      </div>
    </div>
  );
}
