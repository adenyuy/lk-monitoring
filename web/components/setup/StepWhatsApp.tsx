"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { WaStatus } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./setup.module.css";

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

  // Pantau terus sampai login (scan QR terjadi di jendela Chrome, bukan di halaman ini)
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

  const state = wa?.state;

  return (
    <>
      <h1 className={s.title}>Hubungkan WhatsApp</h1>
      <p className={s.desc}>
        Pesan dikirim dari nomor WhatsApp-mu lewat jendela Chrome khusus aplikasi ini. Login cukup sekali dan tersimpan
        di laptop ini.
      </p>

      {error && <Notice tone="bad" title="WhatsApp belum bisa dibuka">{error}</Notice>}
      {state === "error" && <Notice tone="bad" title="Status WhatsApp tidak terbaca">{wa?.error}</Notice>}

      {!wa && !error && (
        <div className={s.waiting}>
          <Spinner label="Memeriksa" />
          <span>Memeriksa status WhatsApp…</span>
        </div>
      )}

      {state === "closed" && (
        <div className={s.actions}>
          <Button loading={opening} onClick={openWa}>{opening ? "Membuka Chrome…" : "Buka WhatsApp Web"}</Button>
          <Button variant="ghost" onClick={onBack}>Kembali</Button>
        </div>
      )}

      {state === "loading" && (
        <div className={s.waiting}>
          <Spinner label="Memuat" />
          <span>Memuat WhatsApp Web di jendela Chrome…</span>
        </div>
      )}

      {state === "qr" && (
        <>
          <div className={s.qrSteps}>
            <div className={s.qrBox}>QR tampil di jendela Chrome yang baru terbuka</div>
            <ol className={s.ol}>
              <li>Buka WhatsApp di HP yang nomornya dipakai untuk kirim.</li>
              <li>Ketuk menu, pilih <b>Perangkat tertaut</b>, lalu <b>Tautkan perangkat</b>.</li>
              <li>Arahkan kamera HP ke QR di jendela Chrome.</li>
            </ol>
          </div>
          <div className={s.waiting}>
            <Spinner label="Menunggu scan" />
            <span>Menunggu scan QR. Halaman ini lanjut otomatis setelah terhubung.</span>
          </div>
          <div className={s.actions}>
            <Button variant="secondary" size="sm" loading={opening} onClick={openWa}>Tampilkan jendela WhatsApp</Button>
            <Button variant="ghost" size="sm" onClick={onBack}>Kembali</Button>
          </div>
        </>
      )}

      {state === "logged_in" && (
        <>
          <Notice tone="ok" title={`Terhubung ke ${wa?.nomor_tersamar || "WhatsApp"}`}>
            Biarkan jendela Chrome WhatsApp tetap terbuka saat mengirim. Boleh diperkecil.
          </Notice>
          <div className={s.actions}>
            <Button onClick={onNext}>Lanjut</Button>
            <Button variant="ghost" onClick={onBack}>Kembali</Button>
          </div>
        </>
      )}
    </>
  );
}
