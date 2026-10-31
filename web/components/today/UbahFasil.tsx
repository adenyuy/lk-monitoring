"use client";

import { useEffect, useState } from "react";
import { post } from "@/lib/api";
import { Button } from "@/components/ui";
import s from "./wag.module.css";

/** Popup ubah nama / nomor WhatsApp fasil (ditulis ke Broadcast dan LK WEEK aktif). */
export function UbahFasilDialog({ nomor, nama, nomorTersamar, onClose, onSaved }: {
  nomor: string;
  nama: string;
  nomorTersamar: string;
  onClose: () => void;
  onSaved: (nomorBaru: string) => void;
}) {
  const [namaBaru, setNamaBaru] = useState(nama);
  const [nomorBaru, setNomorBaru] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const digit = nomorBaru.replace(/\D/g, "");
  const nomorSalah = nomorBaru.trim() !== "" && (digit.length < 9 || digit.length > 15);
  const berubah = namaBaru.trim() !== nama.trim() || nomorBaru.trim() !== "";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        e.stopImmediatePropagation(); // jangan ikut menutup panel fasil
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [busy, onClose]);

  async function simpan() {
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ nomor: string }>(`/api/fasil/${nomor}/ubah`, { nama: namaBaru, nomor_baru: nomorBaru });
      onSaved(r.nomor);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className={`${s.modal} ${s.modalKecil}`} role="dialog" aria-modal="true" aria-labelledby="uf-judul">
        <div className={s.kepala}>
          <h2 id="uf-judul">Ubah data fasil</h2>
          <p>Disimpan ke sheet Broadcast dan ke sekolah binaan fasil ini di LK minggu ini. Riwayat chat di aplikasi
            ikut pindah ke nomor baru.</p>
        </div>
        <form className={s.form} onSubmit={(e) => { e.preventDefault(); if (berubah && !nomorSalah) void simpan(); }}>
          <label className={s.field}>
            <span>Nama fasil</span>
            <input value={namaBaru} onChange={(e) => setNamaBaru(e.target.value)} autoComplete="off" autoFocus />
          </label>
          <label className={s.field}>
            <span>Nomor WhatsApp baru <i>(kosongkan bila tidak berubah)</i></span>
            <input value={nomorBaru} onChange={(e) => setNomorBaru(e.target.value)} inputMode="tel"
              placeholder="Contoh: 081234567890" autoComplete="off" aria-invalid={nomorSalah} />
            <small className={nomorSalah ? s.salah : undefined}>
              {nomorSalah ? "Nomor terlalu pendek atau terlalu panjang." : `Nomor sekarang: ${nomorTersamar}`}
            </small>
          </label>
          {error && <p className={s.err}>{error}</p>}
          <div className={s.aksi}>
            <Button variant="ghost" disabled={busy} onClick={onClose}>Batal</Button>
            <Button type="submit" loading={busy} disabled={!berubah || nomorSalah || !namaBaru.trim()}>Simpan</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
