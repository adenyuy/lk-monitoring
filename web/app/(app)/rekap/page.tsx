import type { Metadata } from "next";
import { RekapView } from "@/components/rekap/RekapView";

export const metadata: Metadata = { title: "Rekap – LK Monitoring" };

export default function RekapPage() {
  return <RekapView />;
}
