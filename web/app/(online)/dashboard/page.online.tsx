import type { Metadata } from "next";
import { DashboardOnline } from "@/components/online/DashboardOnline";

export const metadata: Metadata = { title: "Dashboard – LK Monitoring" };

export default function DashboardPage() {
  return <DashboardOnline />;
}
