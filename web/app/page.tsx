"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Health = { ok: boolean; version: string };

// Halaman sementara (Fase 0): memastikan web & backend tersambung.
// Diganti layar setup / Hari ini di Fase 2–3.
export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Health>("/api/health").then(setHealth).catch((e) => setError(e.message));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 40 }}>
      <h1>LK Monitoring</h1>
      {health && <p>Backend tersambung. Versi {health.version}.</p>}
      {error && <p>Backend belum tersambung: {error}</p>}
      {!health && !error && <p>Menghubungkan ke backend…</p>}
    </main>
  );
}
