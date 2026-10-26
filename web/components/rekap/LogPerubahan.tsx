"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Perubahan } from "@/lib/types";
import s from "./rekap.module.css";

export const KUNCI_DILIHAT = "lkm-perubahan-dilihat"; // dibaca juga oleh AppShell

function waktu(iso: string) {
  const d = new Date(iso);
  const tgl = `${d.getDate()}/${d.getMonth() + 1}`;
  return `${tgl} ${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Log perubahan Broadcast & LK, terbaru di atas. Rincian dibuka per baris. */
export function LogPerubahan() {
  const [items, setItems] = useState<Perubahan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buka, setBuka] = useState<number | null>(null);
  const [semua, setSemua] = useState(false);

  useEffect(() => {
    api<{ items: Perubahan[] }>("/api/perubahan?batas=50")
      .then((r) => {
        setItems(r.items);
        try {
          if (r.items[0]) localStorage.setItem(KUNCI_DILIHAT, String(r.items[0].id));
          window.dispatchEvent(new Event("lkm-perubahan-dilihat"));
        } catch {
          /* penanda "sudah dilihat" hanya kenyamanan */
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  const tampil = items ? (semua ? items : items.slice(0, 5)) : [];

  return (
    <section className={s.card} aria-labelledby="h-log" id="perubahan" data-tour="log">
      <div className={s.cardHead}>
        <h2 id="h-log">Perubahan data</h2>
        <span>Dicek setiap Broadcast dan LK dibaca ulang (paling lama 5–10 menit)</span>
      </div>
      {error && <p className={s.note}>{error}</p>}
      {items && items.length === 0 && (
        <p className={s.note}>Belum ada perubahan sejak aplikasi pertama kali membaca Broadcast dan LK.</p>
      )}
      {tampil.length > 0 && (
        <ul className={s.log}>
          {tampil.map((x) => (
            <li key={x.id}>
              <button type="button" className={s.logRow} aria-expanded={buka === x.id}
                onClick={() => setBuka(buka === x.id ? null : x.id)}>
                <span className={s.logTime}>{waktu(x.waktu)}</span>
                <span className={`${s.logSrc} ${x.sumber === "lk" ? s.logLk : s.logBc}`}>{x.judul}</span>
                <span className={s.logSum}>{x.ringkasan}</span>
                <span className={s.logMore}>{buka === x.id ? "Tutup" : `${x.rincian.length} rincian`}</span>
              </button>
              {buka === x.id && (
                <ul className={s.logDetail}>
                  {x.rincian.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
      {items && items.length > 5 && (
        <button type="button" className={s.linkMore} onClick={() => setSemua(!semua)}>
          {semua ? "Tampilkan 5 terbaru" : `Tampilkan semua (${items.length})`}
        </button>
      )}
    </section>
  );
}
