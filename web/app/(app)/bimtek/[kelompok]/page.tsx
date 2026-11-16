import type { Metadata } from "next";
import { BimtekDetail } from "@/components/online/BimtekDetail";

// Ekspor statis: satu halaman per kelompok (b1..b8). Kelompok tanpa data menampilkan pesan.
export const dynamicParams = false;
export function generateStaticParams() {
  return Array.from({ length: 8 }, (_, i) => ({ kelompok: `b${i + 1}` }));
}

export async function generateMetadata({ params }: { params: Promise<{ kelompok: string }> }): Promise<Metadata> {
  const { kelompok } = await params;
  return { title: `Bimtek ${kelompok.toUpperCase()} – LK Monitoring` };
}

export default async function Halaman({ params }: { params: Promise<{ kelompok: string }> }) {
  const { kelompok } = await params;
  return <BimtekDetail kode={kelompok} />;
}
