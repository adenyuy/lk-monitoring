// Tipe data LK format baru (WEEK n, Log Komunikasi) dan Blast.

export type KodeKom = "T" | "T1" | "T2" | "TP" | "R" | "C" | "N" | "";
export type Kelompok = "perlu_telepon" | "dibaca" | "terkirim" | "menunggu" | "belum" | "terhubung" | "beres";
export type Tahap = "pendahuluan" | "berkala" | "l50" | "l100" | "selesai";

export type LkInfo = {
  week: number;
  hari: string;
  tanggal_panjang: string;
  blok: 1 | 2;
  blok_label: string;
  log_hari_ini: boolean;
  log_rentang: string[];
  wa_otomatis: boolean;
  cutoff: string;
  kode: { kode: KodeKom; arti: string }[];
};

export type FasilLk = {
  kunci: string;
  nama: string;
  nomor: string;
  ptn: string;
  koor: string;
  punya_nomor: boolean;
  kelompok: Kelompok;
  kode_hari_ini: KodeKom;
  kode_minggu: { tanggal: string; kode: KodeKom }[];
  sekolah: number;
  perlu: number;
  lengkap: number;
  todo: number;
  todo_fasil: number;
  fokus: { judul: string; jumlah: number }[];
  tunggu_maks: number | null;
  tag: string[];
  tanpa_progres: boolean;
  belum_ditelepon: boolean;
  progres_naik: number | null;
  /** {kode kolom papan: jumlah sekolah yang tertahan di sana} */
  posisi: Record<string, number>;
  /** status komunikasi minggu ini (papan kedua) */
  kom?: string;
  balasan?: string;
  waktu_balasan?: string;
};

export type PosisiKolom = { kode: string; label: string; fasil: number; sekolah: number };

export type Indikator = { kode: string; nada: "warn" | "info"; jumlah: number; judul: string; isi: string };

export type LkRingkasan = LkInfo & {
  total: { fasil: number; sekolah: number; perlu: number; lengkap: number; dihubungi: number; todo: number };
  kelompok: { kode: Kelompok; label: string; arti: string; jumlah: number }[];
  tahap: { kode: Tahap; jumlah: number }[];
  fokus: { judul: string; jumlah: number }[];
  indikator: Indikator[];
  posisi: PosisiKolom[];
  kom: { kode: string; label: string; arti: string; jumlah: number }[];
  tag: string[];
  fasil: FasilLk[];
};

export type StatusKomp = "selesai" | "belum" | "due" | "kosong" | "tanpa_data";

export type Komp = {
  kode: string;
  label: string;
  tahap: Tahap;
  pelaku: "sekolah" | "fasil";
  status: StatusKomp;
  tampil: string;
  tunggu: number | null;
  menunggu: string;
};

export type TodoItem = {
  kode: string;
  judul: string;
  pelaku: "sekolah" | "fasil";
  komponen: string[];
  detail: string;
  tunggu: number | null;
  isian: Record<string, { kendala: string; tl: string }>;
};

export type SekolahDetail = {
  npsn: string;
  nama: string;
  angkatan: string;
  kab: string;
  tahap: Tahap;
  komponen: Komp[];
  todo: TodoItem[];
  lengkap: boolean;
  selesai: number;
  relevan: number;
  kepsek: string;
  punya_hp_kepsek: boolean;
  delta: number | null;
};

export type FasilDetail = LkInfo & FasilLk & {
  nomor_tersamar: string;
  nomor_lain: string[];
  hp_koor: boolean;
  nomor_koor: string;
  koor_tersamar: string;
  sekolah_detail: SekolahDetail[];
};

export type OpsiLk = {
  kendala: Record<string, string[]>;
  komponen: { kode: string; label: string; tahap: Tahap; pelaku: string }[];
};

export const KELOMPOK_INFO: Record<Kelompok, { label: string; tone: "bad" | "warn" | "info" | "muted" | "ok" }> = {
  perlu_telepon: { label: "Perlu ditelepon", tone: "bad" },
  dibaca: { label: "Dibaca, belum membalas", tone: "warn" },
  terkirim: { label: "Terkirim, belum dibaca", tone: "info" },
  menunggu: { label: "Menunggu konfirmasi", tone: "info" },
  belum: { label: "Belum dihubungi", tone: "muted" },
  terhubung: { label: "Terhubung", tone: "ok" },
  beres: { label: "Semua hijau", tone: "ok" },
};

export const TAHAP_LABEL: Record<Tahap, string> = {
  pendahuluan: "Pendahuluan", berkala: "Laporan berkala", l50: "Laporan 50%", l100: "Laporan 100%",
  selesai: "Semua hijau",
};

/** Warna kode Log Komunikasi (semantik: hijau terhubung, kuning lambat, merah tidak sampai). */
export const KODE_WARNA: Record<string, { bg: string; fg: string; label: string }> = {
  T: { bg: "#e3f3ea", fg: "#1e5e3c", label: "Respon baik" },
  TP: { bg: "#d8efe9", fg: "#155e52", label: "Ditelepon" },
  T1: { bg: "#fff4de", fg: "#7a4900", label: "Menunggu konfirmasi" },
  T2: { bg: "#fde9d2", fg: "#8a4a0c", label: "Respon lambat" },
  R: { bg: "#e8edf9", fg: "#2346a0", label: "Hanya dibaca" },
  C: { bg: "#fcecec", fg: "#a6282b", label: "Centang satu" },
  N: { bg: "#f2e6ee", fg: "#8a2d63", label: "Tidak ada WA" },
};

export const HARI_PENDEK = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"];

export function hariPendek(iso: string) {
  const d = new Date(`${iso}T00:00:00`);
  return `${HARI_PENDEK[d.getDay()]} ${d.getDate()}`;
}

export function inisial(nama: string) {
  const bersih = nama.replace(/^(dr|ir|prof|drs|hj|h)\.?\s+/gi, "").replace(/[.,]/g, " ");
  const kata = bersih.split(/\s+/).filter((k) => /^[A-Za-z]/.test(k) && k.length > 1);
  return ((kata[0]?.[0] ?? "?") + (kata[1]?.[0] ?? "")).toUpperCase();
}

// ---------- Blast ----------

export type JenisPenerima = "fasil" | "koor" | "sekolah";

export type TodoRingkas = { judul: string; detail: string; pelaku: "sekolah" | "fasil"; posisi?: string };

export type Penerima = {
  kunci: string;
  nama: string;
  tersamar: string;
  punya_nomor: boolean;
  kelompok: string;
  tag: string[];
  ptn: string;
  koor?: string;
  angkatan: string[];
  kab: string[];
  jumlah_sekolah: number;
  perlu: number;
  terakhir_blast: string;
  /** Jam chat keluar terakhir hari ini (aplikasi atau terdeteksi di WhatsApp), '' bila belum. */
  chat_hari_ini?: string;
  /** Status chat minggu ini. */
  chat?: "" | "terkirim" | "dibaca" | "dibalas";
  /** Komponen papan LK -> jumlah sekolah yang tertahan di situ. */
  posisi?: Record<string, number>;
  // fasil
  sekolah?: { nama: string; tahap: Tahap; todo: TodoRingkas[] }[];
  // koor
  fasil?: { nama: string; kelompok: Kelompok; sekolah: number; perlu: number; todo: number; todo_fasil: number;
    belum_ditelepon: boolean; tanpa_progres: boolean; sulit: boolean; posisi?: Record<string, number> }[];
  // sekolah
  kepsek?: string;
  todo?: TodoRingkas[];
  tahap?: Tahap;
};

export type BlastState = {
  running: boolean;
  paused: boolean;
  coba: boolean;
  judul: string;
  total: number;
  diproses: number;
  terkirim: number;
  gagal: number;
  sekarang: string;
  berikutnya: string;
  berikutnya_pada: number | null;
  istirahat_sampai: number | null;
  stop_diminta: boolean;
  berhenti_karena: string;
  mulai: number | null;
  selesai: number | null;
  aturan: Aturan | Record<string, never>;
  hasil: { nama: string; jenis: string; status: string; keterangan: string; waktu: string }[];
  sisa: { nama: string; jenis: string }[];
};

export type Aturan = { jeda_min: number; jeda_max: number; istirahat_setiap: number; istirahat_menit: number };

export type TemplateSaya = { id: string; judul: string; jenis: JenisPenerima; teks: string };
