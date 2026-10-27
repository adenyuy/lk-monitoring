"use client";

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Spinner } from "@/components/ui";
import s from "./app.module.css";

type Info = { aktif: boolean; versi: string; versi_baru: string; ada_baru: boolean };

const BATAS_TUNGGU = 180_000; // 3 menit

/** Banner "Versi baru tersedia" + proses mulai ulang. Hanya muncul di aplikasi hasil install.bat. */
export function Pembaruan() {
  const [info, setInfo] = useState<Info | null>(null);
  const [tahap, setTahap] = useState<"diam" | "mulai" | "tunggu" | "lama">("diam");
  const [error, setError] = useState<string | null>(null);

  const cek = useCallback(async () => {
    try {
      setInfo(await api<Info>("/api/pembaruan"));
    } catch {
      /* hanya informasi */
    }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void cek();
  }, [cek]);
  usePolling(cek, 30 * 60_000, tahap === "diam");

  async function perbarui() {
    if (!info) return;
    setTahap("mulai");
    setError(null);
    try {
      await post("/api/pembaruan/pasang");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setTahap("diam");
      return;
    }
    setTahap("tunggu");
    const lama = info.versi;
    const mulai = Date.now();
    // Tunggu server lama mati lalu server baru hidup dengan versi berbeda, kemudian muat ulang halaman
    const id = window.setInterval(async () => {
      if (Date.now() - mulai > BATAS_TUNGGU) {
        window.clearInterval(id);
        setTahap("lama");
        return;
      }
      try {
        const h = await api<{ version: string }>("/api/health");
        if (h.version && h.version !== lama) {
          window.clearInterval(id);
          window.location.reload();
        }
      } catch {
        /* server sedang dimulai ulang */
      }
    }, 2000);
  }

  if (tahap === "tunggu" || tahap === "lama") {
    return (
      <div className={s.pbScrim} role="alertdialog" aria-live="assertive" aria-label="Memperbarui aplikasi">
        <div className={s.pbBox}>
          {tahap === "tunggu" ? (
            <>
              <Spinner label="Memperbarui" />
              <b>Memperbarui aplikasi…</b>
              <p>Biasanya kurang dari satu menit. Halaman ini dimuat ulang sendiri setelah selesai.</p>
            </>
          ) : (
            <>
              <b>Pembaruan belum selesai</b>
              <p>Tutup halaman ini, lalu buka lagi <b>LK Monitoring</b> dari Desktop. Bila masih gagal, klik dua kali
                stop.bat di folder aplikasi lalu buka lagi.</p>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!info?.ada_baru) return null;
  return (
    <div className={s.bannerWrap}>
      <div className={`${s.banner} ${s.bannerInfo}`} role="status">
        <div className={s.bannerText}>
          <b>Versi baru tersedia{info.versi_baru ? ` (${info.versi_baru})` : ""}</b>
          <span>
            Aplikasi dimulai ulang sekitar satu menit. Setelah itu tekan Buka WhatsApp lagi.
            {error && <> <strong>{error}</strong></>}
          </span>
        </div>
        <Button size="sm" loading={tahap === "mulai"} onClick={perbarui}>Perbarui sekarang</Button>
      </div>
    </div>
  );
}
