"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
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
