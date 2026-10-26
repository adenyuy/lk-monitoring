"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import s from "./app.module.css";

export type Langkah = { target: string; judul: string; isi: string };

const UMUM: Langkah[] = [
  { target: "nav", judul: "Menu", isi: "Pindah halaman di sini: Rekap, Hari ini, dan Tarik Cutoff. Di laptop, arahkan kursor ke menu untuk melihat namanya." },
  { target: "dock", judul: "Tombol bulat", isi: "Lingkarannya hitung mundur sesi; arahkan kursor untuk melihat menit dan detiknya. Ketuk untuk pindah halaman, membuka log perubahan, panduan, atau tanya jawab. Seret untuk memindahkannya ke mana saja." },
];

/** Langkah panduan per halaman. `target` = nilai atribut data-tour di elemen. */
export const PANDUAN: Record<string, Langkah[]> = {
  "/today/": [
    ...UMUM,
    { target: "pengingat", judul: "Pengingat", isi: "Muncul bila ada sesi yang terlewat, antrean lanjutan dari kemarin, atau fasil yang perlu dichat lagi. Klik nama fasil untuk langsung membuka chat dan LK-nya." },
    { target: "now", judul: "Mulai kirim di sini", isi: "Tekan Kirim untuk mengirim pesan Broadcast sesi ini satu per satu. Nyalakan Mode coba bila ingin melihat prosesnya tanpa benar-benar mengirim." },
    { target: "sesi", judul: "Lima sesi hari ini", isi: "Pilih sesi untuk melihat fasil yang sudah dan akan dikirimi di sesi itu." },
    { target: "fasil", judul: "Daftar fasil", isi: "Batang warna menunjukkan prioritas sekolah binaannya. Klik satu fasil untuk membuka LK dan chat WhatsApp-nya berdampingan." },
    { target: "wa", judul: "Status WhatsApp", isi: "Harus terhubung sebelum mengirim. Bila belum, tekan Buka WhatsApp di pengingat merah." },
  ],
  "/rekap/": [
    ...UMUM,
    { target: "prio", judul: "Sekolah per prioritas", isi: "P1 belum submit laporan 50%, P2 sudah submit tapi progres di bawah 50%, P3 belum direviu." },
    { target: "p1", judul: "Kemajuan P1", isi: "Berapa fasil P1 yang sudah dihubungi dan membalas." },
    { target: "isian", judul: "Isian LK", isi: "Berapa sekolah yang status komunikasi dan alasannya sudah lengkap, per sesi LK." },
    { target: "tabel", judul: "Per fasil", isi: "Urutkan dengan klik judul kolom, saring dengan tombol di atas tabel, lalu klik fasil untuk membuka LK dan chat-nya." },
  ],
  "/faq/": [...UMUM],
  "/cutoff/": [
    ...UMUM,
    { target: "kalender", judul: "Riwayat tarik", isi: "Kotak besar = tarik mingguan per WEEK, kotak kecil = tarik harian per hari. Hijau berarti sudah ditarik." },
    { target: "mode", judul: "Jenis tarikan", isi: "Harian mengisi M–O dan menghitung ulang Prioritas. Mingguan mengisi baseline J–L." },
    { target: "file", judul: "File cutoff", isi: "Pilih atau seret file CSV/Excel dari aplikasi, lalu tekan Cek file. Belum ada yang ditulis sampai Anda menekan Tulis." },
  ],
};

function terlihat(target: string): HTMLElement | null {
  return [...document.querySelectorAll<HTMLElement>(`[data-tour="${target}"]`)]
    .find((e) => e.getBoundingClientRect().width > 0) ?? null;
}

type Kotak ={ top: number; left: number; width: number; height: number };
const JARAK = 8;

/** Panduan bertahap yang menyorot bagian layar satu per satu. */
export function Tour({ langkah, onClose }: { langkah: Langkah[]; onClose: () => void }) {
  const ada = langkah.filter((l) => typeof document !== "undefined" && terlihat(l.target));
  const [i, setI] = useState(0);
  const [kotak, setKotak] = useState<Kotak | null>(null);
  const l = ada[i];

  const ukur = useCallback(() => {
    if (!l) return;
    // Elemen yang sama bisa ada di menu samping (laptop) dan bar bawah (HP): pakai yang terlihat
    const el = terlihat(l.target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    setKotak({ top: r.top - JARAK, left: r.left - JARAK, width: r.width + JARAK * 2, height: r.height + JARAK * 2 });
  }, [l]);

  useLayoutEffect(() => {
    if (!l) return;
    const el = terlihat(l.target);
    el?.scrollIntoView({ block: "center", behavior: "instant" as ScrollBehavior });
    // Posisi sorotan harus diukur dari DOM setelah digulir
    // eslint-disable-next-line react-hooks/set-state-in-effect
    ukur();
  }, [l, ukur]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setI((x) => Math.min(x + 1, ada.length - 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(x - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", ukur);
    window.addEventListener("scroll", ukur, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", ukur);
      window.removeEventListener("scroll", ukur, true);
    };
  }, [ada.length, onClose, ukur]);

  if (!l || !kotak) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const lebar = Math.min(320, vw - 32);
  const bawah = kotak.top + kotak.height + 12;
  const muatBawah = bawah + 180 < vh;
  const kanan = kotak.left + kotak.width + 12;
  const sampingKanan = kotak.height > vh * 0.5 && kanan + lebar < vw;
  const pos = sampingKanan
    ? { top: Math.max(16, Math.min(kotak.top, vh - 220)), left: kanan }
    : { top: muatBawah ? bawah : Math.max(16, kotak.top - 12 - 180),
        left: Math.max(16, Math.min(kotak.left, vw - lebar - 16)) };
  const akhir = i === ada.length - 1;

  return (
    <div className={s.tour} role="dialog" aria-modal="true" aria-labelledby="tour-judul">
      <div className={s.tourSpot} style={kotak} />
      <div className={s.tourPop} style={{ ...pos, width: lebar }}>
        <span className={s.tourStep}>{i + 1} dari {ada.length}</span>
        <h3 id="tour-judul">{l.judul}</h3>
        <p>{l.isi}</p>
        <div className={s.tourActions}>
          <button type="button" className={s.tourSkip} onClick={onClose}>Tutup panduan</button>
          <span>
            {i > 0 && <button type="button" className={s.tourBack} onClick={() => setI(i - 1)}>Kembali</button>}
            <button type="button" className={s.tourNext} autoFocus onClick={() => (akhir ? onClose() : setI(i + 1))}>
              {akhir ? "Selesai" : "Lanjut"}
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}
