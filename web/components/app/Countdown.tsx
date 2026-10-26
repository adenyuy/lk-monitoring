"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import s from "./app.module.css";

type Jadwal = {
  aktif: { no: number; sampai: string; sisa_detik: number } | null;
  berikutnya: { no: number; mulai: string; hari_ini: boolean; dalam_detik: number } | null;
};

function hms(detik: number) {
  const h = Math.floor(detik / 3600);
  const m = Math.floor((detik % 3600) / 60);
  const d = detik % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(d).padStart(2, "0")}`;
}

function singkat(detik: number) {
  const m = Math.ceil(detik / 60);
  return m >= 60 ? `${Math.floor(m / 60)}j${m % 60 ? String(m % 60).padStart(2, "0") : ""}` : `${m}m`;
}

/** Hitung mundur sesi: sisa waktu sesi berjalan, atau waktu menuju sesi berikutnya. */
export function Countdown({ compact = false }: { compact?: boolean }) {
  const [j, setJ] = useState<Jadwal | null>(null);
  const [dasar, setDasar] = useState(0); // Date.now() saat data diambil
  const [now, setNow] = useState(0);

  const muat = useCallback(async () => {
    try {
      const data = await api<Jadwal>("/api/jadwal");
      setJ(data);
      setDasar(Date.now());
      setNow(Date.now());
    } catch {
      /* hitung mundur hanya informasi */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muat();
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [muat]);
  usePolling(muat, 60000, true);

  const lewat = Math.max(0, Math.round((now - dasar) / 1000));
  const berjalan = !!j?.aktif && j.aktif.sisa_detik - lewat > 0;
  const detik = !j ? 0 : berjalan ? j.aktif!.sisa_detik - lewat : Math.max(0, (j.berikutnya?.dalam_detik ?? 0) - lewat);
  const habis = !!j && detik === 0 && lewat > 1;

  // Waktunya habis: ambil ulang supaya pindah ke sesi berikutnya
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (habis) void muat();
  }, [habis, muat]);

  if (!j) return null;

  const judul = berjalan ? `Sesi ${j.aktif!.no} berjalan` : j.berikutnya
    ? `Sesi ${j.berikutnya.no} ${j.berikutnya.hari_ini ? `mulai ${j.berikutnya.mulai}` : "berikutnya"}`
    : "Tidak ada sesi";
  const ket = berjalan ? `sampai ${j.aktif!.sampai}` : j.berikutnya?.hari_ini ? "dimulai dalam" : "besok atau hari kerja berikutnya";
  // Lingkaran: sisa waktu sesi (berjalan) atau menuju sesi berikutnya, skala 2 jam
  const total = berjalan ? Math.max(detik, 2 * 3600) : 2 * 3600;
  const pct = Math.min(1, detik / total);
  const C = 2 * Math.PI * 15;

  return (
    <div className={`${s.cd} ${berjalan ? s.cdLive : ""} ${compact ? s.cdCompact : ""}`} role="timer"
      aria-label={`${judul}, ${ket} ${hms(detik)}`} data-tour="countdown">
      <span className={s.cdRing} aria-hidden="true">
        <svg width="36" height="36" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15" className={s.cdTrack} />
          <circle cx="18" cy="18" r="15" className={s.cdBar} strokeDasharray={C} strokeDashoffset={C * (1 - pct)} />
        </svg>
        <span>{singkat(detik)}</span>
      </span>
      <span className={s.cdText}>
        <b>{judul}</b>
        <small>{ket}</small>
        <span className={s.cdTime}>{hms(detik)}</span>
      </span>
    </div>
  );
}
