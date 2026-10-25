import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Hari ini – LK Monitoring" };

// Sementara: layar Hari ini dibangun di Fase 6.
export default function TodayPage() {
  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: "80px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 style={{ fontSize: 26, fontWeight: 600 }}>Persiapan selesai</h1>
      <p style={{ color: "var(--muted)" }}>
        Layar kirim (Hari ini) sedang dibangun. Untuk mengubah nama, WhatsApp, atau batas harian, buka lagi persiapan.
      </p>
      <p><Link href="/setup/">Buka persiapan</Link></p>
    </main>
  );
}
