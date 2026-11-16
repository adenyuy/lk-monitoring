import type { Metadata } from "next";
import { BimtekDetail } from "@/components/online/BimtekDetail";

export const metadata: Metadata = { title: "Monitoring Bimtek – LK Monitoring" };

export default function Halaman() {
  return <BimtekDetail />;
}
