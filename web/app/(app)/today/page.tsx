import type { Metadata } from "next";
import { TodayView } from "@/components/today/TodayView";

export const metadata: Metadata = { title: "Hari ini – LK Monitoring" };

export default function TodayPage() {
  return <TodayView />;
}
