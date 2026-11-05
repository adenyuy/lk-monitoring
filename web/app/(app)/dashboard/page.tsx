import type { Metadata } from "next";
import { DashboardView } from "@/components/dashboard/DashboardView";

export const metadata: Metadata = { title: "Dashboard – LK Monitoring" };

export default function DashboardPage() {
  return <DashboardView />;
}
