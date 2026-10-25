"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { BATAS, type Petugas } from "@/lib/types";
import { Button, Notice } from "@/components/ui";
import s from "./setup.module.css";

function nada(batas: number) {
  if (batas > BATAS.merah)
    return {
      tone: "bad" as const,
      judul: "Terlalu tinggi untuk satu nomor",
      isi: "Nomor tim pernah diblokir sehari setelah pesan ke-51. Turunkan ke 50 atau kurang.",
    };
  if (batas > BATAS.kuning)
    return {
      tone: "warn" as const,
      judul: "Mendekati batas aman",
      isi: "Bisa dipakai. Pastikan nomor fasilitator sudah tersimpan di kontak HP dan perhatikan peringatan dari WhatsApp.",
    };
  return {
    tone: "ok" as const,
    judul: "Batas aman",
    isi: "Disarankan 40 atau kurang. Kuota per sesi tetap mengikuti jadwal tim: 10, 10, 15, 15, 10.",
  };
}

export function StepBatas({
  awal,
  namaPetugas,
  jumlahFasilAwal,
  onBack,
  onDone,
}: {
  awal: number;
  namaPetugas: string | null;
  jumlahFasilAwal: number | null;
  onBack: () => void;
  onDone: () => void;
}) {
  const [batas, setBatas] = useState(awal);
  const [jumlahFasil, setJumlahFasil] = useState<number | null>(jumlahFasilAwal);

  // Langkah ini bisa dibuka langsung (mis. dari "Batas harian" di header), jadi ambil sendiri jumlah fasilnya.
  useEffect(() => {
    if (jumlahFasil !== null || !namaPetugas) return;
    const key = namaPetugas.toLowerCase();
    api<{ petugas: Petugas[] }>("/api/petugas")
      .then((d) => setJumlahFasil(d.petugas.find((p) => p.nama.toLowerCase() === key)?.jumlah_fasil ?? null))
      .catch(() => undefined); // perkiraan hanya pelengkap
  }, [jumlahFasil, namaPetugas]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const n = nada(batas);
  const posisi = ((batas - BATAS.min) / (BATAS.max - BATAS.min)) * 100;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await post("/api/settings", { batas_harian: batas, setup_selesai: true });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  return (
    <>
      <h1 className={s.title}>Batas pesan per hari</h1>
      <p className={s.desc}>
        Aplikasi berhenti mengirim saat angka ini tercapai, lalu melanjutkan sisanya besok. Berlaku untuk nomormu saja
        dan bisa diubah kapan saja.
      </p>

      <div className={s.batasRow}>
        <div className={s.stepper} role="group" aria-label="Batas pesan per hari">
          <button type="button" className={s.stepBtn} aria-label={`Kurangi ${BATAS.langkah}`}
            disabled={batas <= BATAS.min} onClick={() => setBatas(Math.max(BATAS.min, batas - BATAS.langkah))}>−</button>
          <output className={s.stepValue} aria-live="polite">{batas}</output>
          <button type="button" className={s.stepBtn} aria-label={`Tambah ${BATAS.langkah}`}
            disabled={batas >= BATAS.max} onClick={() => setBatas(Math.min(BATAS.max, batas + BATAS.langkah))}>+</button>
        </div>
        <p className={s.estimasi}>
          pesan per hari.
          {jumlahFasil ? (
            <> Dengan batas ini, <b>{jumlahFasil} fasilitator</b> selesai dalam <b>{Math.ceil(jumlahFasil / batas)} hari kerja</b>.</>
          ) : null}
        </p>
      </div>

      <div aria-hidden="true">
        <div className={s.scale} style={{ position: "relative" }}>
          <div><span style={{ background: "#bfe0cb" }} />{BATAS.min}</div>
          <div><span style={{ background: "#f1d7a6" }} />{BATAS.kuning}</div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div style={{ flex: 1 }}><span style={{ background: "#f2c7c8" }} />{BATAS.merah}</div>
            <div style={{ alignSelf: "flex-end" }}>{BATAS.max}</div>
          </div>
          <i style={{ position: "absolute", top: -3, left: `calc(${posisi}% - 6px)`, width: 12, height: 12,
            borderRadius: "50%", background: "var(--ink)", border: "2px solid #fff", boxShadow: "0 0 0 1px var(--ink)" }} />
        </div>
      </div>

      <Notice tone={n.tone} title={n.judul}>{n.isi}</Notice>
      {error && <Notice tone="bad" title="Belum tersimpan">{error}</Notice>}

      <div className={s.actions}>
        <Button loading={saving} onClick={save}>Simpan batas {batas} dan mulai</Button>
        <Button variant="ghost" onClick={onBack}>Kembali</Button>
      </div>
    </>
  );
}
