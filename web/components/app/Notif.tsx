"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { Pengingat } from "@/lib/types";
import s from "./app.module.css";

const KUNCI_TUTUP = "lkm-pengingat-ditutup";
const KUNCI_LIHAT = "lkm-notif-dilihat";

export type Notif = Pengingat & { kunci: string; href?: string };

function baca<T>(kunci: string, awal: T): T {
  try {
    const raw = localStorage.getItem(kunci);
    return raw ? (JSON.parse(raw) as T) : awal;
  } catch {
    return awal;
  }
}

function tulis(kunci: string, nilai: unknown) {
  try {
    localStorage.setItem(kunci, JSON.stringify(nilai));
  } catch {
    /* hanya kenyamanan */
  }
}

/** Notifikasi untuk tombol bulat: pengingat dari server + perubahan data baru. */
export function useNotif(adaBaru: boolean) {
  const [data, setData] = useState<{ tanggal: string; items: Pengingat[] } | null>(null);
  const [tutup, setTutup] = useState<string[]>([]);
  const [dilihat, setDilihat] = useState<string[]>([]);

  const muat = useCallback(async () => {
    try {
      const r = await api<{ tanggal: string; items: Pengingat[] }>("/api/pengingat");
      setData(r);
      const t = baca<{ tanggal?: string; judul?: string[] }>(KUNCI_TUTUP, {});
      setTutup(t.tanggal === r.tanggal ? t.judul ?? [] : []);
    } catch {
      /* notifikasi hanya pelengkap */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDilihat(baca<string[]>(KUNCI_LIHAT, []));
    void muat();
  }, [muat]);
  usePolling(muat, 60000, true);

  const items: Notif[] = [
    ...(adaBaru ? [{
      jenis: "lanjut" as const, judul: "Ada perubahan data baru",
      isi: "Broadcast atau LK berubah sejak terakhir Anda membuka Log.", kunci: "log-baru", href: "/log/",
    }] : []),
    ...(data?.items ?? [])
      .filter((x) => x.jenis === "tindak_lanjut" || !tutup.includes(x.judul))
      .map((x) => ({ ...x, kunci: `${data?.tanggal}|${x.jenis}|${x.judul}` })),
  ];
  const baru = items.filter((x) => !dilihat.includes(x.kunci)).length;

  const tandaiDilihat = () => {
    const k = items.map((x) => x.kunci);
    setDilihat(k);
    tulis(KUNCI_LIHAT, k);
  };

  const sembunyikan = (judul: string) => {
    const baruTutup = [...tutup, judul];
    setTutup(baruTutup);
    tulis(KUNCI_TUTUP, { tanggal: data?.tanggal, judul: baruTutup });
  };

  return { items, baru, tandaiDilihat, sembunyikan, muat };
}

function Ikon({ jenis }: { jenis: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {jenis === "tindak_lanjut"
        ? <path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" />
        : <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>}
    </svg>
  );
}

/** Daftar notifikasi di menu tombol bulat. */
export function NotifList({ items, onFasil, onTutup, onLink }: {
  items: Notif[]; onFasil: (nomor: string) => void; onTutup: (judul: string) => void; onLink: () => void;
}) {
  if (!items.length) {
    return <p className={s.nfEmpty}>Tidak ada notifikasi. Semua aman.</p>;
  }
  return (
    <ul className={s.nfList}>
      {items.map((x) => (
        <li key={x.kunci} className={`${s.nf} ${s[`nf_${x.jenis}`] ?? ""}`}>
          <span className={s.nfIco}><Ikon jenis={x.jenis} /></span>
          <div className={s.nfBody}>
            <b>{x.judul}</b>
            <p>{x.isi}</p>
            {x.fasil && (
              <ul className={s.nfChips}>
                {x.fasil.map((f) => (
                  <li key={f.nomor}>
                    <button type="button" onClick={() => onFasil(f.nomor)} title={f.alasan}>
                      <i className={f.dibalas ? s.chipBalas : undefined} aria-hidden="true" />
                      {f.nama}
                      <span className="sr-only">, {f.alasan}</span>
                    </button>
                  </li>
                ))}
                {!!x.total && x.total > x.fasil.length && (
                  <li><Link href="/rekap/" onClick={onLink}>+{x.total - x.fasil.length} lainnya</Link></li>
                )}
              </ul>
            )}
            <div className={s.nfAksi}>
              {x.href && <Link href={x.href} onClick={onLink}>Buka Log</Link>}
              {(x.jenis === "terlewat" || x.jenis === "lanjut") && !x.href && (
                <Link href="/faq/#sesi-terlewat" onClick={onLink}>Kenapa begini?</Link>
              )}
              {x.jenis !== "tindak_lanjut" && !x.href && (
                <button type="button" onClick={() => onTutup(x.judul)}>Mengerti</button>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
