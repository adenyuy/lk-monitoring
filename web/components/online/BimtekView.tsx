"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import b from "./bimtekRekap.module.css";

/* ---------- bentuk data (backend/app/rekap_bimtek.py) ---------- */
export type Titik = { pct: number | null; pct_banding: number | null; konversi: number | null; konversi_banding: number | null;
  dampak: number | null; n?: number; n_banding?: number } | null;
/** Satu komponen: sebelum bimtek (T0) -> data terbaru, untuk sekolah yang komponennya sudah jatuh tempo di T0. */
export type Komp = { kode: string; label: string; ada: boolean;
  due?: number; awal_pct?: number | null; akhir_pct?: number | null; belum_awal?: number; jadi_selesai?: number;
  konversi?: number | null; due_banding?: number; awal_pct_banding?: number | null; akhir_pct_banding?: number | null;
  belum_awal_banding?: number; konversi_banding?: number | null; dampak?: number | null };
export type Capaian = { awal: number | null; akhir: number | null; awal_banding: number | null; akhir_banding: number | null;
  naik: number | null; naik_banding: number | null; komponen: string[] };
export type Kelompok = {
  kode: string; tag: string; mulai: string; selesai: string; catatan: string; tahap: "selesai" | "berjalan" | "akan datang";
  sekolah: number; t0: string; t1: string; t2: string; t2_tersedia: boolean;
  /** jumlah di daftar peserta (termasuk yang tidak ada di export); `sekolah` = yang ada di export */
  peserta_daftar?: number;
  hotel?: { nama: string; region: string; sekolah: number }[];
  l50: { wajib: number; wajib_banding: number; awal: number | null; awal_banding: number | null; belum_awal: number;
    belum_awal_banding: number; n_awal?: number; t1: Titik; t2: Titik; sekarang: Titik; verif_median: number | null;
    verif_median_banding: number | null };
  awal?: { sumber: string; waktu: string; jenis: "export" | "cutoff" | "lk_lama" };
  /** potret komponen di hari terakhir bimtek (export/cutoff paling lambat 2 hari sesudahnya) */
  akhir1?: { sumber: string; waktu: string; jenis: "export" | "cutoff" };
  komponen?: Komp[];
  capaian?: Capaian;
  progres?: { naik: number; naik_banding: number | null; dampak: number | null; naik5: number | null;
    naik5_banding: number | null; n: number };
  /** baris per sekolah peserta, urut kolom `kolom_sekolah` */
  sekolah_baris?: (string | number | null)[][];
};
export type Rekap = {
  dibuat: string; data_terbaru: { sumber: string; waktu: string }; peserta: Record<string, number>; sekolah_total: number;
  non_peserta: number; wajib50: number; sumber_export: string[]; kelompok: Kelompok[];
  kurva: { tanggal: string[]; seri: { kode: string; sekolah: number; nilai: (number | null)[] }[] };
  kolom_sekolah?: string[];
  komponen_urut?: string[];
  /** hari menunggu reviu Lap. 50% per fasil (semua binaan), urut terlama dulu */
};
export type Resp = { rekap: Rekap | null; bisa_hitung: boolean; folder: string; admin?: boolean; saya?: string;
  status: { jalan?: boolean; mulai?: string; error?: string; selesai?: string } };

/* Warna kategori tetap per kelompok (urutan B1..B8), non-peserta abu-abu. */
export const WARNA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const ABU = "#8a93a6";
export const warnaDari = (kode: string) => (kode === "Non-peserta" ? ABU : WARNA[(Number(kode.replace(/\D/g, "")) || 1) - 1] ?? ABU);

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
export const tgl = (iso: string) => { const d = new Date(iso.slice(0, 10)); return `${d.getDate()} ${BULAN[d.getMonth()]}`; };
export const tglPanjang = (iso: string) => {
  const d = new Date(iso);
  return `${HARI[d.getDay()]}, ${d.getDate()} ${BULAN[d.getMonth()]} ${d.getFullYear()}${iso.length > 10 ? ` pukul ${iso.slice(11, 16).replace(":", ".")}` : ""}`;
};
export const rentang = (a: string, z: string) => `${new Date(a).getDate()}–${tgl(z)}`;
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${v.toFixed(1).replace(".", ",")}%`);
export const poin = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1).replace(".", ",")}`);
export const fmt = (n: number) => n.toLocaleString("id-ID");
export const KOMP_PENDEK: Record<string, string> = { lp: "LP", lp_rev: "Reviu LP", mg: "Mingguan", mg_rev: "Reviu Mg",
  bl: "Bulanan", bl_rev: "Reviu Bl", l50: "Lap. 50%", l50_rev: "Reviu 50%", l100: "Lap. 100%" };
export const KET_KOMP: Record<string, string> = {
  mg: "Selesai = semua Laporan Mingguan yang jatuh tempo sudah terkirim. Bisa turun karena tiap minggu ada laporan baru yang jatuh tempo.",
  mg_rev: "Selesai = semua Laporan Mingguan yang dikirim sudah direviu. Bisa turun bila sekolah mengirim laporan baru yang belum direviu.",
  bl: "Selesai = semua Laporan Bulanan yang jatuh tempo sudah terkirim. Bisa turun karena tiap bulan ada laporan baru yang jatuh tempo.",
  bl_rev: "Selesai = semua Laporan Bulanan yang dikirim sudah direviu. Bisa turun bila sekolah mengirim laporan baru yang belum direviu.",
  l50: "Dari tanggal kirim per sekolah, jadi tersedia untuk semua kelompok.",
};
/** Asal data hari ini: salinan LK setelah cutoff, atau file export aplikasi. */
export const sumberData = (r: Rekap) => (r.data_terbaru.sumber.startsWith("LK") ? "dari LK setelah cutoff" : "dari export aplikasi");

export const labelBimtek = (kode: string) => `Bimtek ke-${kode.replace(/\D/g, "")}`;
export const NAMA_SUMBER: Record<string, string> = { export: "export aplikasi", cutoff: "salinan LK saat cutoff", lk_lama: "baseline LK lama" };

/** Rekap dari /api/dashboard/bimtek (dipakai halaman utama dan detail). */
export function useRekap() {
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const muat = useCallback(async () => {
    try { setData(await api<Resp>("/api/dashboard/bimtek")); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  return { data, error, setError, muat };
}

/** Sekolah peserta yang punya komponen tertunggak sebelum bimtek dan tidak bergerak sama sekali sampai data terbaru. */
export function belumEfektif(r: Rekap, k: Kelompok): number {
  const kol = r.kolom_sekolah ?? [], urut = r.komponen_urut ?? [];
  const ia = kol.indexOf("awal_kode"), iz = kol.indexOf("akhir_kode");
  const pakai = urut.map((x) => (k.capaian?.komponen ?? []).includes(x));
  if (ia < 0 || iz < 0) return 0;
  return (k.sekolah_baris ?? []).filter((x) => {
    const a = String(x[ia] ?? ""), z = String(x[iz] ?? "");
    return pakai.some((p, i) => p && a[i] === "B" && z[i] !== "S" && z[i] !== "P");
  }).length;
}

export const hrefKelompok = (kode: string) => `/bimtek/${kode.toLowerCase()}/`;



/* ---------- data per kapan + tombol hitung ---------- */
export function DataPer({ r, data, onHitung }: { r: Rekap | null; data: Resp; onHitung?: () => void }) {
  const jalan = !!data.status.jalan;
  return (
    <div className={b.metaData}>
      <span className={`${b.metaTitik} ${jalan ? b.metaTitikJalan : ""}`} aria-hidden="true" />
      {jalan ? <span>Menghitung ulang rekap…</span> : r ? (
        <span title={`${r.data_terbaru.sumber} · dihitung ${tglPanjang(r.dibuat)}`}>
          Data <b>{tglPanjang(r.data_terbaru.waktu)}</b>
          <span className={b.metaSumber}>{sumberData(r).replace("dari ", "")}</span>
        </span>
      ) : <span>Belum ada rekap</span>}
      {data.bisa_hitung && onHitung && (
        <button type="button" className={b.metaUlang} onClick={onHitung} disabled={jalan}
          aria-label="Hitung ulang rekap" title={`Hitung ulang rekap dari folder ${data.folder}`}>
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            strokeLinejoin="round" className={jalan ? b.putar : undefined} aria-hidden="true">
            <path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" />
          </svg>
        </button>
      )}
    </div>
  );
}

/* ---------- kartu kelompok: sebelum -> sesudah (capaian komponen yang ada datanya) ---------- */
export function teksKomponen(c: Capaian | undefined) {
  if (!c || !c.komponen.length) return "";
  return c.komponen.length === 1 ? KOMP_PENDEK[c.komponen[0]] : `${c.komponen.length} komponen`;
}

/* ---------- status menurut kalender ---------- */
/** Tanggal hari ini (lokal) "YYYY-MM-DD". */
export const hariIni = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
/** Bimtek yang sedang berlangsung menurut kalender (bukan menurut data). */
export const berlangsung = (k: Kelompok) => { const h = hariIni(); return k.mulai <= h && h <= k.selesai; };
/** Bimtek yang belum mulai menurut kalender. */
export const belumMulai = (k: Kelompok) => hariIni() < k.mulai;
/** Selisih hari kalender a -> b (tanggal "YYYY-MM-DD"). */
export const selisihHari = (a: string, b: string) => Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86400000);

/* ---------- status Lap. 50% per sekolah ---------- */
export type Kuadran = "sekolah" | "fasil" | "aman";
export const KUADRAN: { k: Kuadran; label: string; ket: string }[] = [
  { k: "sekolah", label: "Sekolah bermasalah", ket: "Lap. 50% sudah jatuh tempo tapi belum dikirim, jadi fasil belum bisa mereviu." },
  { k: "fasil", label: "Fasil bermasalah", ket: "Sekolah sudah kirim Lap. 50%, tapi laporannya menunggu reviu fasil lebih lama dari batas hari." },
  { k: "aman", label: "Aman", ket: "Lap. 50% sudah dikirim dan tidak tertahan di reviu, atau belum jatuh tempo." },
];
export const PILIHAN_HARI = [1, 3, 7, 14];
/** Status satu sekolah: belum kirim padahal jatuh tempo -> sekolah; laporannya menunggu reviu > batas hari -> fasil. */
export function kuadranDari(kode50: string | undefined, rev50: string | undefined, tunggu50: number | null | undefined, batas: number): Kuadran {
  if (kode50 === "B") return "sekolah";
  return rev50 === "menunggu" && tunggu50 != null && tunggu50 > batas ? "fasil" : "aman";
}

