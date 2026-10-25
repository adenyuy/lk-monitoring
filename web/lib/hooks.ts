"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "./api";
import type { Me } from "./types";

/** Status pengguna dari /api/me. `reload()` untuk mengambil ulang. */
export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const data = await api<Me>("/api/me");
      setMe(data);
      setError(null);
      return data;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  useEffect(() => {
    // Ambil sekali saat halaman dibuka.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
  }, [reload]);

  return { me, error, reload };
}

/** Dengarkan /api/events (SSE). `onEvent(type, data)` dipanggil untuk tiap peristiwa. */
export function useEvents(onEvent: (type: string, data: unknown) => void) {
  const ref = useRef(onEvent);
  useEffect(() => {
    ref.current = onEvent;
  });
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`);
    const types = ["halo", "kirim_mulai", "kirim_proses", "kirim_hasil", "kirim_jeda", "kirim_selesai",
      "kirim_stop_diminta", "chat_diperbarui"];
    const handlers = types.map((t) => {
      const h = (e: MessageEvent) => ref.current(t, e.data ? JSON.parse(e.data) : null);
      es.addEventListener(t, h as EventListener);
      return [t, h] as const;
    });
    return () => {
      handlers.forEach(([t, h]) => es.removeEventListener(t, h as EventListener));
      es.close();
    };
  }, []);
}

/** Detik tersisa menuju `epochSeconds` (diperbarui tiap detik). */
export function useCountdown(epochSeconds: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!epochSeconds) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [epochSeconds]);
  return epochSeconds ? Math.max(0, Math.round(epochSeconds - now / 1000)) : null;
}

/** Jalankan `fn` tiap `ms` milidetik selama `active` true. */
export function usePolling(fn: () => void | Promise<unknown>, ms: number, active: boolean) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  });
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => void ref.current(), ms);
    return () => window.clearInterval(id);
  }, [ms, active]);
}
