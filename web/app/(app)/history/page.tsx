import type { Metadata } from "next";

export const metadata: Metadata = { title: "Riwayat – LK Monitoring" };

// Dibangun di Fase 7.
export default function HistoryPage() {
  return (
    <div style={{ padding: "48px 0", color: "var(--muted)" }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>Riwayat</h1>
      Rekap kiriman per hari sedang dibangun.
    </div>
  );
}
