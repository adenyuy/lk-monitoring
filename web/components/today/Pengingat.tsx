"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Pengingat as P } from "@/lib/types";
import s from "./today.module.css";

const KUNCI = "lkm-pengingat-ditutup";

function IkonJam() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
    </svg>
  );
}

function IkonChat() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" />
    </svg>
  );
}

/** Pengingat di bawah kartu Sekarang. Info sesi bisa ditutup untuk hari ini; daftar tindak lanjut selalu tampil. */
export function Pengingat({ items, tanggal, onPick }: { items: P[]; tanggal: string; onPick: (nomor: string) => void }) {
  const [tutup, setTutup] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = JSON.parse(localStorage.getItem(KUNCI) ?? "{}") as { tanggal?: string; judul?: string[] };
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw.tanggal === tanggal) setTutup(raw.judul ?? []);
    } catch {
      /* hanya kenyamanan */
    }
  }, [tanggal]);

  function sembunyikan(judul: string) {
    const baru = [...tutup, judul];
    setTutup(baru);
    try {
      localStorage.setItem(KUNCI, JSON.stringify({ tanggal, judul: baru }));
    } catch {
      /* hanya kenyamanan */
    }
  }

  const tampil = items.filter((x) => x.jenis === "tindak_lanjut" || !tutup.includes(x.judul));
  if (!tampil.length) return null;

  return (
    <div className={s.ingat} data-tour="pengingat">
      {tampil.map((x) =>
        x.jenis === "tindak_lanjut" ? (
          <section key={x.jenis} className={`${s.ingatCard} ${s.ingatTl}`} aria-label="Perlu ditindaklanjuti">
            <span className={s.ingatIco}><IkonChat /></span>
            <div className={s.ingatBody}>
              <b>{x.judul}</b>
              <p>{x.isi}</p>
              <ul className={s.ingatChips}>
                {x.fasil?.map((f) => (
                  <li key={f.nomor}>
                    <button type="button" onClick={() => onPick(f.nomor)} title={f.alasan}>
                      <i className={f.dibalas ? s.chipBalas : s.chipBelum} aria-hidden="true" />
                      {f.nama}
                      <span className="sr-only">, {f.alasan}</span>
                    </button>
                  </li>
                ))}
                {!!x.total && x.fasil && x.total > x.fasil.length && (
                  <li><Link href="/rekap/" className={s.ingatMore}>+{x.total - x.fasil.length} lainnya di Rekap</Link></li>
                )}
              </ul>
            </div>
          </section>
        ) : (
          <section key={x.judul} className={`${s.ingatCard} ${x.jenis === "terlewat" ? s.ingatWarn : s.ingatInfo}`}
            role="status">
            <span className={s.ingatIco}><IkonJam /></span>
            <div className={s.ingatBody}>
              <b>{x.judul}</b>
              <p>{x.isi} <Link href="/faq/#sesi-terlewat">Kenapa begini?</Link></p>
            </div>
            <button type="button" className={s.ingatX} onClick={() => sembunyikan(x.judul)}>
              Mengerti
            </button>
          </section>
        ),
      )}
    </div>
  );
}
