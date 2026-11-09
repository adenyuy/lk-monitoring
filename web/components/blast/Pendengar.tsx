"use client";

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./blast.module.css";

export type PendengarStatus = {
  status: "mati" | "menghubungkan" | "qr" | "tersambung" | "putus" | "keluar" | "galat";
  tertaut: boolean; sehat: boolean; qr_svg: string; akun: string; galat: string; sejak: string; terakhir: string;
};

/** Kartu kecil di halaman Blast: status chat dibaca langsung (neonize) atau lewat WA Web (cadangan). */
export function PendengarKartu({ onUbah }: { onUbah?: (p: PendengarStatus) => void }) {
  const [p, setP] = useState<PendengarStatus | null>(null);
  const [buka, setBuka] = useState(false);

  const muat = useCallback(async () => {
    try {
      const r = await api<PendengarStatus>("/api/pendengar");
      setP(r);
      onUbah?.(r);
    } catch { /* diperbarui berkala */ }
  }, [onUbah]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  usePolling(muat, buka ? 2000 : 20000, true);

  const label = !p ? "Memeriksa…"
    : p.status === "tersambung" ? `Langsung${p.akun ? ` · ${p.akun}` : ""}`
    : p.sehat ? "Menyambung ulang…"
    : p.tertaut ? "Terputus · pakai WA Web" : "Lewat WA Web (cadangan)";

  return (
    <>
      <div className={s.waKartu}>
        <span className={`${s.waTitik} ${p?.status === "tersambung" ? s.waOn : p?.sehat ? s.waTunggu : ""}`}
          aria-hidden="true" />
        <span><small>Status chat</small><b>{label}</b></span>
        <button type="button" onClick={() => setBuka(true)}>{p?.tertaut ? "Atur" : "Tautkan"}</button>
      </div>
      {buka && p && <DialogPendengar p={p} onMuat={muat} onTutup={() => setBuka(false)} />}
    </>
  );
}

function DialogPendengar({ p, onMuat, onTutup }: { p: PendengarStatus; onMuat: () => Promise<void>; onTutup: () => void }) {
  const [jalan, setJalan] = useState(false);
  const [yakin, setYakin] = useState(false);
  const [galat, setGalat] = useState("");

  const tautkan = async () => {
    setGalat("");
    setJalan(true);
    try { await post("/api/pendengar/tautkan"); await onMuat(); } catch (e) { setGalat(e instanceof Error ? e.message : String(e)); }
    finally { setJalan(false); }
  };
  const lepas = async () => {
    setJalan(true);
    try { await post("/api/pendengar/lepas"); await onMuat(); setYakin(false); } catch (e) { setGalat(e instanceof Error ? e.message : String(e)); }
    finally { setJalan(false); }
  };

  const tersambung = p.status === "tersambung";
  return (
    <div className={s.scrim} role="presentation" onClick={(e) => { if (e.target === e.currentTarget) onTutup(); }}>
      <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="pendengar-judul">
        <h2 id="pendengar-judul">Status chat langsung</h2>
        <p>
          Aplikasi ditautkan sebagai perangkat tambahan di WhatsApp kamu, <b>hanya untuk mendengar</b>: pesan yang
          terkirim (dari aplikasi maupun HP), centang dibaca, dan balasan fasil masuk seketika. Chat tidak perlu dibuka
          satu per satu, jadi pesan fasil tidak ikut berubah jadi centang biru. Kirim pesan tetap lewat jendela WhatsApp.
        </p>

        {tersambung && (
          <Notice tone="ok" title={`Tersambung${p.akun ? ` · ${p.akun}` : ""}`}>
            Status chat, Log Komunikasi, dan blast lewat HP terbaca otomatis.
          </Notice>
        )}
        {!tersambung && p.status === "qr" && p.qr_svg && (
          <div className={s.qrBox}>
            <div className={s.qr} dangerouslySetInnerHTML={{ __html: p.qr_svg }} />
            <ol>
              <li>Buka WhatsApp di HP nomor pengirim (nomor yang dipakai blast).</li>
              <li>Ketuk <b>Perangkat tertaut</b> → <b>Tautkan perangkat</b>.</li>
              <li>Scan QR ini. Perangkat akan muncul sebagai <b>LK Monitoring</b>.</li>
            </ol>
          </div>
        )}
        {!tersambung && (p.status === "menghubungkan" || (jalan && !p.qr_svg)) && (
          <p className={s.tunggu}><Spinner /> Menyambung ke WhatsApp…</p>
        )}
        {!tersambung && p.status !== "qr" && !p.tertaut && p.status !== "menghubungkan" && (
          <Notice tone="info" title="Belum ditautkan">
            Sementara ini status chat dibaca dengan membuka chat di jendela WhatsApp (lebih lambat). Tautkan supaya
            langsung.
          </Notice>
        )}
        {p.tertaut && !p.sehat && p.status !== "menghubungkan" && (
          <Notice tone="warn" title="Terputus">
            Status chat sementara dibaca lewat jendela WhatsApp. Pastikan internet tersambung; aplikasi menyambung ulang
            sendiri.
          </Notice>
        )}
        {(p.galat || galat) && <Notice tone="bad">{galat || p.galat}</Notice>}

        <div className={s.dialogAksi}>
          {p.tertaut && !yakin && <Button variant="ghost" onClick={() => setYakin(true)} disabled={jalan}>Lepas perangkat</Button>}
          {yakin && (
            <Button variant="danger" onClick={() => void lepas()} loading={jalan}>Ya, lepas</Button>
          )}
          <Button variant="secondary" onClick={onTutup}>Tutup</Button>
          {!tersambung && p.status !== "qr" && p.status !== "menghubungkan" && (
            <Button onClick={() => void tautkan()} loading={jalan}>{p.tertaut ? "Sambung ulang" : "Tampilkan QR"}</Button>
          )}
        </div>
      </div>
    </div>
  );
}
