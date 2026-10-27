"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import data from "@/lib/jawaban.json";
import s from "./today.module.css";

type Item = { id: string; tanya: string; kata: string[]; jawab: string };
type Kategori = { id: string; judul: string; items: Item[] };

const KATEGORI = data.kategori as Kategori[];

/** Cari jawaban berbasis panduan (folder knowledge). Memilih jawaban mengisi kotak balasan, bisa diedit dulu. */
export function JawabPicker({ nama, onPilih, onClose }: {
  nama: string; onPilih: (teks: string) => void; onClose: () => void;
}) {
  const [cari, setCari] = useState("");
  const [kat, setKat] = useState<string | null>(null);
  const [lihat, setLihat] = useState<string | null>(null);
  const kotak = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    const onKlik = (e: MouseEvent) => { if (kotak.current && !kotak.current.contains(e.target as Node)) onClose(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onKlik);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onKlik);
    };
  }, [onClose]);

  const hasil = useMemo(() => {
    const kata = cari.toLowerCase().split(/\s+/).filter(Boolean);
    const pilih = KATEGORI.filter((k) => !kat || k.id === kat);
    if (!kata.length) return pilih;
    // Saat mencari: satu daftar urut kecocokan (judul pertanyaan > kata kunci > isi jawaban)
    const skor = (it: Item) => {
      const t = it.tanya.toLowerCase(), k = it.kata.join(" ").toLowerCase(), j = it.jawab.toLowerCase();
      if (!kata.every((w) => t.includes(w) || k.includes(w) || j.includes(w))) return 0;
      return kata.reduce((n, w) => n + (t.includes(w) ? 5 : 0) + (k.includes(w) ? 3 : 0) + (j.includes(w) ? 1 : 0), 0);
    };
    const items = pilih.flatMap((k) => k.items).map((it) => ({ it, n: skor(it) }))
      .filter((x) => x.n > 0).sort((a, b) => b.n - a.n).map((x) => x.it);
    return items.length ? [{ id: "hasil", judul: `Hasil pencarian (${items.length})`, items }] : [];
  }, [cari, kat]);

  const isi = (it: Item) => it.jawab.replaceAll("{nama}", nama);

  return (
    <div className={s.jwBox} ref={kotak} role="dialog" aria-label="Jawab pertanyaan fasil">
      <div className={s.jwHead}>
        <input autoFocus type="search" value={cari} onChange={(e) => setCari(e.target.value)}
          placeholder="Cari: OTP, berita acara, durasi, perencana…" aria-label="Cari jawaban" />
        <button type="button" onClick={onClose} aria-label="Tutup">×</button>
      </div>
      <div className={s.jwKat} role="group" aria-label="Topik">
        <button type="button" aria-pressed={!kat} onClick={() => setKat(null)}>Semua</button>
        {KATEGORI.map((k) => (
          <button key={k.id} type="button" aria-pressed={kat === k.id} onClick={() => setKat(k.id)}>{k.judul}</button>
        ))}
      </div>
      <div className={s.jwList}>
        {hasil.length === 0 && <p className={s.jwKosong}>Tidak ada jawaban yang cocok. Coba kata lain.</p>}
        {hasil.map((k) => (
          <div key={k.id}>
            <h4>{k.judul}</h4>
            <ul>
              {k.items.map((it) => (
                <li key={it.id}>
                  <div className={s.jwItem}>
                    <button type="button" className={s.jwTanya} aria-expanded={lihat === it.id}
                      onClick={() => setLihat(lihat === it.id ? null : it.id)}>
                      {it.tanya}
                    </button>
                    <button type="button" className={s.jwPakai} onClick={() => onPilih(isi(it))}>Pakai</button>
                  </div>
                  {lihat === it.id && <p className={s.jwPratinjau}>{isi(it)}</p>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className={s.jwSumber}>Sumber: panduan Adendum Kepala Sekolah dan PKS Adendum (Okt 2026). Periksa dulu sebelum mengirim.</p>
    </div>
  );
}
