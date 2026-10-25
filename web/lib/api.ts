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
    // Backend selalu mengirim {"detail": "<pesan untuk pengguna>"}
    throw new ApiError(res.status, body?.detail ?? `Permintaan gagal (${res.status})`);
  }
  return body as T;
}
