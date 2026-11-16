import type { Metadata } from "next";
import { RankingPage } from "@/components/online/DashboardOnline";

export const metadata: Metadata = { title: "Ranking PIC – LK Monitoring" };

export default function Halaman() {
  return <RankingPage />;
}
