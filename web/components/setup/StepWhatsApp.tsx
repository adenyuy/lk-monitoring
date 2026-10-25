"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { WaStatus } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./setup.module.css";

const STATUS = {
  closed: { warna: "#98a2b3", label: "Belum terhubung", sub: "Jendela WhatsApp belum dibuka" },
  loading: { warna: "#e0a43a", label: "Memuat WhatsApp Web", sub: "Tunggu sebentar" },
  qr: { warna: "#e0a43a", label: "Menunggu scan QR", sub: "Lanjut otomatis setelah terhubung" },
  logged_in: { warna: "#1e7a4c", label: "Terhubung", sub: "" },
  error: { warna: "#a6282b", label: "Status tidak terbaca", sub: "" },
} as const;

const Icon = ({ d }: { d: React.ReactNode }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);

const HOWTO = [
  {
    judul: "Buka jendela WhatsApp",
    isi: "Tekan tombol di bawah. Chrome khusus aplikasi terbuka dan menampilkan QR.",
    icon: <Icon d={<><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></>} />,
  },
  {
    judul: "Buka Perangkat tertaut",
    isi: "Di HP: WhatsApp, menu titik tiga, lalu Perangkat tertaut dan Tautkan perangkat.",
    icon: <Icon d={<><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M11 18h2" /></>} />,
  },
  {
    judul: "Scan QR di Chrome",
    isi: "Arahkan kamera HP ke QR. Halaman ini lanjut sendiri begitu terhubung.",
    icon: <Icon d={<><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" /><path d="M7 12h10" /></>} />,
  },
];

export function StepWhatsApp({ onBack, onNext }: { onBack: () => void; onNext: () => void }) {
  const [wa, setWa] = useState<WaStatus | null>(null);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function check() {
    try {
      setWa(await api<WaStatus>("/api/wa/status"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check();
  }, []);

  // Scan QR terjadi di jendela Chrome, jadi halaman ini memantau sampai terhubung.
  const watching = !!wa && (wa.state === "qr" || wa.state === "loading");
  usePolling(check, 2000, watching);

  async function openWa() {
    setOpening(true);
    setError(null);
    try {
      setWa(await post<WaStatus>("/api/wa/connect"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpening(false);
    }
  }

  const state = wa?.state ?? "closed";
  const st = STATUS[state];
  const aktif = state === "closed" ? 0 : state === "logged_in" ? -1 : 1; // kartu yang disorot

  return (
    <>
      <h1 className={s.title}>Hubungkan WhatsApp</h1>
      <p className={s.desc}>
        Pesan dikirim dari nomor WhatsApp-mu lewat jendela Chrome khusus aplikasi ini. Login cukup sekali dan tersimpan
        di laptop ini.
      </p>

      <div className={s.status} role="status">
        <div className={s.statusLabel}>
          {wa ? <span className={s.light} style={{ background: st.warna }} /> : <Spinner label="Memeriksa" />}
          <span>
            {wa ? (state === "logged_in" ? `Terhubung ke ${wa.nomor_tersamar || "WhatsApp"}` : st.label) : "Memeriksa status"}
            {wa && st.sub && <span className={s.statusSub} style={{ display: "block", fontWeight: 400 }}>{st.sub}</span>}
          </span>
        </div>
        {watching && <Spinner label="Menunggu" />}
      </div>

      {state !== "logged_in" && (
        <ol className={s.howto} aria-label="Cara menghubungkan">
          {HOWTO.map((h, i) => (
            <li key={h.judul} className={i === aktif || (aktif === 1 && i === 2) ? s.howtoActive : undefined}>
              <div className={s.howtoTop}>
                <span className={s.howtoIcon}>{h.icon}</span>
                <span className={s.howtoNo}>{i + 1}</span>
              </div>
              <b style={{ color: "var(--ink)", fontWeight: 600 }}>{h.judul}</b>
              <span>{h.isi}</span>
            </li>
          ))}
        </ol>
      )}

      {error && <Notice tone="bad" title="WhatsApp belum bisa dibuka">{error}</Notice>}
      {state === "error" && <Notice tone="bad" title="Status WhatsApp tidak terbaca">{wa?.error}</Notice>}
      {state === "logged_in" && (
        <Notice tone="info" title="Biarkan jendela WhatsApp tetap terbuka">
          Jendela Chrome WhatsApp dipakai saat mengirim. Boleh diperkecil, jangan ditutup.
        </Notice>
      )}

      <div className={s.actions}>
        {state === "logged_in" ? (
          <Button onClick={onNext}>Lanjut ke batas harian</Button>
        ) : state === "closed" || state === "error" ? (
          <Button loading={opening} onClick={openWa}>{opening ? "Membuka Chrome…" : "Buka jendela WhatsApp"}</Button>
        ) : (
          <Button variant="secondary" loading={opening} onClick={openWa}>Tampilkan jendela WhatsApp</Button>
        )}
        <Button variant="ghost" onClick={onBack}>Kembali</Button>
      </div>
    </>
  );
}
