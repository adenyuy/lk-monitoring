import type { Metadata } from "next";
import { DashboardOnline } from "@/components/online/DashboardOnline";

export const metadata: Metadata = { title: "Dashboard – LK Monitoring" };

// Sama dengan dashboard online (data dari LK yang sama); Ranking PIC hanya tampil untuk admin.
export default function DashboardPage() {
  return <DashboardOnline />;
}
