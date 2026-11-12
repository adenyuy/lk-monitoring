// Saat build produksi, web & API satu origin (localhost:8787) → base kosong.
// Saat `next dev` (port 3000), API dipanggil langsung ke backend lewat env ini.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // Backend mengirim {"detail": "<pesan untuk pengguna>"}; isian yang ditolak validasi (422) berupa daftar objek
    throw new ApiError(res.status, pesanError(body?.detail, res.status));
  }
  return body as T;
}

type GalatValidasi = { type?: string; msg?: string; ctx?: { max_length?: number; min_length?: number } };

function pesanError(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    const e = detail[0] as GalatValidasi;
    if (e?.type === "string_too_long") return `Teks terlalu panjang (maks ${e.ctx?.max_length ?? "?"} karakter). Persingkat lalu kirim lagi.`;
    if (e?.type === "string_too_short") return "Teks masih kosong.";
    if (e?.msg) return `Isian ditolak: ${e.msg}`;
  }
  return `Permintaan gagal (${status})`;
}

export function post<T>(path: string, data?: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
}

export function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return api<T>(path, { method: "POST", body: form });
}
