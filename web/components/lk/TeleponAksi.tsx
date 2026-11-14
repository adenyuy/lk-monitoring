"use client";

import { useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { TeleponInfo } from "@/lib/lk";
import s from "./lk.module.css";

function waktuSingkat(iso: string): string {
  const t = new Date(iso);
  const hari = t.toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "numeric" });
  return `${hari} ${t.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Tanda "perlu telepon / koordinator" + tombol mencatat hasil telepon (diangkat -> TP, tidak diangkat -> TX di Log
 *  Komunikasi hari ini). */
export function TeleponAksi({ kunci, info, onCatat }: { kunci: string; info?: TeleponInfo; onCatat: () => void }) {
  const [buka, setBuka] = useState(false);
  const [jalan, setJalan] = useState("");
  const [galat, setGalat] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!buka) return;
    const tutup = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setBuka(false); };
    document.addEventListener("mousedown", tutup);
    return () => document.removeEventListener("mousedown", tutup);
  }, [buka]);

  const catat = async (hasil: "diangkat" | "tidak") => {
    setJalan(hasil);
    setGalat("");
    try {
      await post("/api/lk2/telepon", { kunci, hasil });
      setBuka(false);
      onCatat();
    } catch (e) {
      setGalat(e instanceof Error ? e.message : String(e));
    } finally {
      setJalan("");
    }
  };

  const t = info?.terakhir;
  return (
    <div className={s.telepon} ref={ref}>
      {info?.dicoba && <span className={s.teleponDicoba}>Sudah dicoba telepon hari ini</span>}
      <button type="button" className={`${s.teleponBtn} ${info?.perlu ? s.teleponBtnPenting : ""}`}
        aria-haspopup="menu" aria-expanded={buka} onClick={() => setBuka(!buka)}
        title={[info?.perlu ? `Perlu telepon atau hubungi koordinator: ${info.alasan}` : "",
          t ? `Telepon terakhir: ${waktuSingkat(t.waktu)} · ${t.label}${t.sumber === "wa" ? " (WhatsApp)" : ""}` : "Belum ada catatan telepon"]
          .filter(Boolean).join(" · ")}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          strokeLinejoin="round" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" /></svg>
        Catat telepon
      </button>
      {buka && (
        <div className={s.teleponMenu} role="menu">
          <p>{info?.perlu ? `${info.alasan}. Telepon fasil, atau hubungi koordinatornya lewat tab Koordinator. ` : ""}Hasil telepon ke fasil hari ini:</p>
          <button type="button" role="menuitem" disabled={!!jalan} onClick={() => void catat("diangkat")}>
            <b>{jalan === "diangkat" ? "Menyimpan…" : "Diangkat"}</b>
            <small>Tulis TP (terhubung lewat telepon) di Log Komunikasi hari ini</small>
          </button>
          <button type="button" role="menuitem" disabled={!!jalan} onClick={() => void catat("tidak")}>
            <b>{jalan === "tidak" ? "Menyimpan…" : "Tidak diangkat"}</b>
            <small>Tulis TX di Log Komunikasi hari ini; pengingat muncul lagi besok bila belum ada kabar</small>
          </button>
          {t && <small className={s.teleponTerakhir}>Terakhir: {waktuSingkat(t.waktu)} · {t.label}{t.sumber === "wa" ? " (WhatsApp)" : ""}</small>}
          {galat && <small className={s.teleponGalat}>{galat}</small>}
        </div>
      )}
    </div>
  );
}
