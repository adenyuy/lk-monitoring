"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { FasilTindakLanjut, Pengingat } from "@/lib/types";
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

const KUNCI_DESKTOP = "lkm-notif-desktop";

/** Notifikasi Windows saat ada fasil baru yang membalas (hanya bila diizinkan dan halaman app terbuka). */
function kabariDesktop(fasil: FasilTindakLanjut[]) {
  const kunci = fasil.map((f) => `${f.nomor}|${f.alasan}`);
  const lama = baca<string[] | null>(KUNCI_DESKTOP, null);
  tulis(KUNCI_DESKTOP, kunci);
  if (lama === null || typeof Notification === "undefined" || Notification.permission !== "granted") return;
  for (const f of fasil) {
    if (lama.includes(`${f.nomor}|${f.alasan}`)) continue;
    try {
      const n = new Notification(`${f.nama} membalas`, { body: f.alasan, tag: f.nomor });
      n.onclick = () => {
        window.focus();
        // Di luar React (handler notifikasi): muat ulang penuh ke Hari ini memang disengaja
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = `/today/?fasil=${encodeURIComponent(f.nomor)}`;
      };
    } catch {
      /* browser menolak: abaikan */
    }
  }
}

/** Tombol izin notifikasi desktop (muncul sekali sampai diizinkan atau ditolak). */
export function IzinDesktop() {
  const [izin, setIzin] = useState<string>("granted");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIzin(typeof Notification === "undefined" ? "denied" : Notification.permission);
  }, []);
  if (izin !== "default") return null;
  return (
    <button type="button" className={s.nfIzin}
      onClick={() => void Notification.requestPermission().then(setIzin)}>
      Nyalakan notifikasi desktop
    </button>
  );
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
      kabariDesktop(r.items.find((x) => x.jenis === "perlu_balas")?.fasil ?? []);
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
      .filter((x) => x.jenis === "tindak_lanjut" || x.jenis === "chat_manual" || x.jenis === "perlu_balas"
        || !tutup.includes(x.judul))
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
      {jenis === "tindak_lanjut" || jenis === "chat_manual" || jenis === "perlu_balas"
        ? <path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" />
        : <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>}
    </svg>
  );
}

/** Daftar notifikasi di menu tombol bulat. */
export function NotifList({ items, onDaftar, onTutup, onLink }: {
  items: Notif[]; onDaftar: (x: Notif) => void; onTutup: (judul: string) => void; onLink: () => void;
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
            <div className={s.nfAksi}>
              {x.fasil && x.fasil.length > 0 && (
                <button type="button" className={s.nfDaftar} onClick={() => onDaftar(x)}>
                  Lihat daftar ({x.fasil.length})
                </button>
              )}
              {x.href && <Link href={x.href} onClick={onLink}>Buka Log</Link>}
              {(x.jenis === "terlewat" || x.jenis === "lanjut") && !x.href && (
                <Link href="/faq/#sesi-terlewat" onClick={onLink}>Kenapa begini?</Link>
              )}
              {!x.fasil && !x.href && (
                <button type="button" onClick={() => onTutup(x.judul)}>Mengerti</button>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

const KATEGORI: Record<FasilTindakLanjut["kategori"], string> = {
  balas: "Menunggu balasan Anda",
  membalas: "Sudah membalas, LK belum lengkap",
  menunggu: "Belum membalas",
  manual: "Di luar Broadcast, belum dihubungi",
  bimtek: "Peserta bimtek, belum direviu",
};

/** Popup daftar fasil dari notifikasi, tiap baris menuju panel fasil di Hari ini. */
export function DaftarFasil({ item, onBuka, onClose }: {
  item: Notif; onBuka: (nomor: string) => void; onClose: () => void;
}) {
  const ada = (Object.keys(KATEGORI) as FasilTindakLanjut["kategori"][])
    .filter((k) => item.fasil?.some((f) => f.kategori === k));
  const [kat, setKat] = useState<FasilTindakLanjut["kategori"] | "semua">("semua");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const tampil = (item.fasil ?? []).filter((f) => kat === "semua" || f.kategori === kat);
  return (
    <div className={s.dfWrap}>
      <div className={s.amBackdrop} onClick={onClose} />
      <div className={s.dfPanel} role="dialog" aria-modal="true" aria-labelledby="df-judul">
        <div className={s.dfHead}>
          <div>
            <h2 id="df-judul">{item.judul}</h2>
            <p>Klik fasil untuk membuka LK dan chat-nya di Hari ini.</p>
          </div>
          <button type="button" className={s.dfX} onClick={onClose} aria-label="Tutup">×</button>
        </div>
        {ada.length > 1 && (
          <div className={s.dfTabs} role="group" aria-label="Saring">
            <button type="button" aria-pressed={kat === "semua"} onClick={() => setKat("semua")}>
              Semua <span>{item.fasil?.length}</span>
            </button>
            {ada.map((k) => (
              <button key={k} type="button" aria-pressed={kat === k} onClick={() => setKat(k)}>
                {KATEGORI[k]} <span>{item.fasil?.filter((f) => f.kategori === k).length}</span>
              </button>
            ))}
          </div>
        )}
        <ul className={s.dfList}>
          {tampil.map((f) => (
            <li key={f.nomor}>
              <button type="button" onClick={() => onBuka(f.nomor)}>
                <i className={f.kategori === "membalas" || f.kategori === "balas" ? s.chipBalas : f.kategori === "manual" ? s.chipManual : f.kategori === "bimtek" ? s.chipBimtek : undefined}
                  aria-hidden="true" />
                <span className={s.dfNama}>
                  <b>{f.nama}</b>
                  <small>{f.alasan}</small>
                </span>
                <span className={s.dfPrio}>
                  {f.kategori === "balas" && <em className={s.prBalas}>Perlu dibalas</em>}
                  {f.p1 > 0 && <em className={s.pr1}>P1 {f.p1}</em>}
                  {f.p2 > 0 && <em className={s.pr2}>P2 {f.p2}</em>}
                  {f.p3 > 0 && <em className={s.pr3}>P3 {f.p3}</em>}
                </span>
                <span className={s.dfLk}>LK {f.lengkap}/{f.perlu}</span>
                <span className={s.dfGo} aria-hidden="true">›</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
