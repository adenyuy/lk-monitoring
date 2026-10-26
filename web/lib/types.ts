// Bentuk respons backend (lihat backend/app/routers).

export type Me = {
  version: string;
  api_rev?: number;
  needs_credentials: boolean;
  login: { status: "idle" | "running" | "done" | "error"; error: string };
  logged_in: boolean;
  email: string | null;
  access: { nama_petugas: string; fitur: string[] } | null;
  access_error: string | null;
  settings: {
    nama_petugas: string | null;
    batas_harian: number;
    kirim_akhir_pekan: boolean;
    week: string;
    wa_terhubung: boolean;
    setup_selesai: boolean;
  };
};

export type Petugas = { nama: string; jumlah_fasil: number };

export type WaStatus = {
  state: "closed" | "loading" | "qr" | "logged_in" | "error";
  nomor_tersamar: string;
  error?: string;
};

export type Kondisi = {
  kode: string;
  judul: string;
  bisa_kirim: boolean;
  sesi: number | null;
  kuota: number;
  sesi_berikutnya: number | null;
  mulai_berikutnya: string | null;
};

export type Pengiriman = {
  running: boolean;
  coba: boolean;
  sesi: number | null;
  target: number;
  dicoba: number;
  terkirim: number;
  gagal: number;
  sekarang: string;
  berikutnya: string;
  berikutnya_pada: number | null;
  stop_diminta: boolean;
  berhenti_karena: string;
  mulai: number | null;
  selesai: number | null;
  hasil: { nama: string; status: string; keterangan: string; waktu: string }[];
};

export type SesiRingkas = {
  no: number;
  mulai: string;
  sampai: string;
  kuota: number;
  terkirim: number;
  perkiraan: number;
  durasi_menit: number;
  status: "Selesai" | "Berjalan" | "Kuota habis" | "Berikutnya" | "Belum" | "Libur";
};

export type Today = {
  tanggal: string;
  tanggal_panjang: string;
  jam_sekarang: string;
  posisi_sekarang: number;
  kondisi: Kondisi;
  sesi_aktif: number | null;
  sisa_menit_sesi: number | null;
  menit_ke_berikutnya: number | null;
  batas_harian: number;
  terkirim_hari_ini: number;
  dibalas_hari_ini: number;
  belum_dikirim: number;
  total_fasil: number;
  sesi: SesiRingkas[];
  pengiriman: Pengiriman;
};

export type LkRingkas = { jumlah: number; p1: number; p2: number; p3: number; selesai: number };

export type BarisSesi = {
  jam: string;
  nama_fasil: string;
  nomor: string;
  lk: LkRingkas;
  status: string;
  keterangan: string;
};

export type SesiDetail = {
  no: number;
  mulai: string;
  sampai: string;
  kuota: number;
  terkirim: number;
  aktif: boolean;
  kondisi: Kondisi;
  sudah: BarisSesi[];
  akan: BarisSesi[];
};

export type Fasil = {
  nama_fasil: string;
  nomor_tersamar: string;
  status: string;
  pesan: string;
  waktu_kirim: string;
  status_kirim: string;
  balasan: string;
  waktu_balasan: string;
  sekolah: SekolahLk[];
};

export type IsianKey = "a1" | "a2" | "b1" | "b2" | "c1" | "c2";
export type Isian = Record<IsianKey, string>;

export type SekolahLk = {
  npsn: string;
  nama: string;
  progres: number | null;
  prioritas: string;
  submit: string;
  reviu: string;
  komunikasi: string;
  isian: Record<string, Isian>; // per blok: "1" Senin–Rabu, "2" Rabu–Jumat
};

export type LkOpsi = {
  opsi: { komunikasi: string[]; alasan_progres: string[]; alasan_submit: string[]; alasan_reviu: string[] };
  blok_default: number;
  blok: { no: number; label: string }[];
};

// Harus sama dengan backend/app/config.py API_REV
export const API_REV = 4;

// Batas harian (sama dengan backend/app/config.py)
export const BATAS = { min: 10, max: 70, langkah: 5, kuning: 40, merah: 50 } as const;

export type Percakapan = {
  status: "belum_ada" | "terkirim" | "dibaca" | "dibalas";
  dibaca_pada: string;
  pesan: { keluar: boolean; teks: string; waktu: string; status: string }[];
};
