import type { Metadata } from "next";

export const metadata: Metadata = { title: "Tarik Cutoff – LK Monitoring" };

// Dibangun di Fase 8.
export default function CutoffPage() {
  return (
    <div style={{ padding: "48px 0", color: "var(--muted)" }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>Tarik Cutoff</h1>
      Fitur tarik data cutoff ke LK sedang dibangun.
    </div>
  );
}
