// Bentuk respons backend (lihat backend/app/routers).

export type Me = {
  version: string;
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

// Batas harian (sama dengan backend/app/config.py)
export const BATAS = { min: 10, max: 70, langkah: 5, kuning: 40, merah: 50 } as const;
