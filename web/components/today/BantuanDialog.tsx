"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { EskalasiSekolah } from "@/components/eskalasi/EskalasiSekolah";

type SekolahPilih = { npsn: string; nama: string };
/** Isian awal form eskalasi (dari to-do / kelompok fasil). */
export type IsiEskalasi = { npsn: string[]; keterangan: string };
import { Button, Notice, Spinner } from "@/components/ui";
import type { Teman } from "./TemanPanel";
import s from "./eskalasi.module.css";


/** Popup "Butuh bantuan": tanya teman PIC lewat WhatsApp, atau eskalasi ke stream lain lewat LK Eskalasi. */
export function BantuanDialog({ namaFasil, sekolah, terusan, onPilihTeman, onClose, awal, tabAwal, hanyaEskalasi }: {
  namaFasil: string;
  /** Hanya form eskalasi ke tim/stream lain (tanpa tanya teman) */
  hanyaEskalasi?: boolean;
  sekolah: SekolahPilih[];
  awal?: IsiEskalasi;
  tabAwal?: "teman" | "eskalasi";
  /** Pesan fasil yang akan diteruskan ke teman (dari tombol "Teruskan ke teman"); "" bila dibuka biasa */
  terusan: string;
  onPilihTeman?: (t: Teman) => void;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"teman" | "eskalasi">(hanyaEskalasi ? "eskalasi" : tabAwal ?? "teman");
  const tutupRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    tutupRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopImmediatePropagation(); onClose(); } // jangan ikut menutup panel fasil
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="esk-judul">
        <header className={s.head}>
          <div>
            <h2 id="esk-judul">{hanyaEskalasi ? "Eskalasi ke tim lain" : terusan ? "Teruskan ke teman PIC" : "Butuh bantuan"}</h2>
            <p>{hanyaEskalasi ? `Kasus fasil ${namaFasil} yang harus dijawab tim lain? Catat di LK Eskalasi; sekolah dan keterangannya sudah terisi dari to-do, data sekolah terisi dari LK.`
              : terusan ? "Pilih teman. Chat-nya dibuka di panel kanan dengan pesan fasil sudah dikutip."
              : `Pertanyaan fasil ${namaFasil} belum bisa Anda jawab? Tanya teman dulu. Kasus unik yang harus dijawab stream lain? Catat di LK Eskalasi.`}</p>
          </div>
          <button ref={tutupRef} type="button" className={s.close} onClick={onClose} aria-label="Tutup">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        {terusan && <blockquote className={s.terusan}>{terusan}</blockquote>}
        {!terusan && !hanyaEskalasi && <div className={s.tabs} role="tablist">
          <button type="button" role="tab" aria-selected={tab === "teman"} onClick={() => setTab("teman")}>Tanya teman PIC</button>
          <button type="button" role="tab" aria-selected={tab === "eskalasi"} onClick={() => setTab("eskalasi")}>Eskalasi ke stream lain</button>
        </div>}
        <div className={s.body}>
          {(tab === "teman" || terusan) && onPilihTeman ? <TanyaTeman onPilih={onPilihTeman} /> : <FormEskalasi sekolah={sekolah} awal={awal} />}
        </div>
      </div>
    </div>
  );
}

/** Teman petugas dari tab Kontak PIC (sheet Broadcast). Chat dibuka di panel kanan aplikasi. */
function TanyaTeman({ onPilih }: { onPilih: (t: Teman) => void }) {
  const [kontak, setKontak] = useState<Teman[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cari, setCari] = useState("");

  useEffect(() => {
    api<{ kontak: Teman[] }>("/api/eskalasi/kontak")
      .then((d) => setKontak(d.kontak))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <Notice tone="bad" title="Kontak PIC tidak terbaca">{error}</Notice>;
  if (!kontak) return <div className={s.muted}><Spinner label="Memuat" /> Membaca Kontak PIC…</div>;
  const q = cari.trim().toLowerCase();
  const daftar = kontak.filter((k) => !q || k.nama.toLowerCase().includes(q));
  return (
    <>
      <label className={s.field}>
        <span className={s.label}>Cari teman</span>
        <input type="search" value={cari} onChange={(e) => setCari(e.target.value)} placeholder="Ketik nama" />
      </label>
      <ul className={s.teman}>
        {daftar.map((k) => (
          <li key={k.nomor}>
            <span className={s.avatar} aria-hidden="true">{k.nama.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span>
            <b>{k.nama}</b>
            <Button variant="secondary" size="sm" onClick={() => onPilih(k)}>Chat</Button>
          </li>
        ))}
        {daftar.length === 0 && <li className={s.muted}>Tidak ada nama yang cocok.</li>}
      </ul>
      <p className={s.hint}>Nomor dari tab Kontak PIC di sheet Broadcast.</p>
    </>
  );
}

function FormEskalasi({ sekolah, awal }: { sekolah: SekolahPilih[]; awal?: IsiEskalasi }) {
  return <EskalasiSekolah sekolah={sekolah} awal={awal} />;
}
