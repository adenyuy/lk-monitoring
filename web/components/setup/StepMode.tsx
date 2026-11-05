"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { Button, Notice } from "@/components/ui";
import s from "./setup.module.css";

/** Langkah terakhir: cara kerja dengan WhatsApp. Bisa diubah lagi kapan saja lewat saklar di halaman LK. */
export function StepMode({ awal, waTerhubung, onBack, onDone }: {
  awal: boolean; waTerhubung: boolean; onBack: () => void; onDone: () => void;
}) {
  const [otomatis, setOtomatis] = useState(awal && waTerhubung);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function simpan() {
    setSaving(true);
    setError(null);
    try {
      await post("/api/settings", { wa_otomatis: otomatis, setup_selesai: true });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const pilihan = [
    { nilai: true, judul: "WhatsApp otomatis di laptop ini",
      isi: "Chat fasil dibaca otomatis, kode Log Komunikasi terisi sendiri, dan Blast bisa dipakai.", mati: !waTerhubung },
    { nilai: false, judul: "WhatsApp di HP sendiri, aplikasi untuk LK saja",
      isi: "Chat tidak dibaca aplikasi. Kode komunikasi dicatat manual, template pesan tinggal disalin.", mati: false },
  ];
  return (
    <>
      <h1 className={s.title}>Cara kerja dengan WhatsApp</h1>
      <p className={s.desc}>Pilih yang sesuai kebiasaan Anda. Bisa diganti kapan saja lewat saklar di halaman LK.</p>
      <div className={s.modeList} role="radiogroup" aria-label="Cara kerja">
        {pilihan.map((p) => (
          <label key={String(p.nilai)} className={`${s.modeItem} ${otomatis === p.nilai ? s.modeAktif : ""}`}
            aria-disabled={p.mati || undefined}>
            <input type="radio" name="mode" checked={otomatis === p.nilai} disabled={p.mati}
              onChange={() => setOtomatis(p.nilai)} />
            <span><b>{p.judul}</b><small>{p.mati ? "Hubungkan WhatsApp dulu di langkah sebelumnya." : p.isi}</small></span>
          </label>
        ))}
      </div>
      {error && <Notice tone="bad" title="Belum tersimpan">{error}</Notice>}
      <div className={s.actions}>
        <Button loading={saving} onClick={() => void simpan()}>Mulai pakai</Button>
        <Button variant="ghost" onClick={onBack}>Kembali</Button>
      </div>
    </>
  );
}
