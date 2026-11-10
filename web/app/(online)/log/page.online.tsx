import type { Metadata } from "next";
import { LogOnlineView } from "@/components/online/LogOnlineView";

export const metadata: Metadata = { title: "Log – LK Monitoring" };

export default function LogPage() {
  return <LogOnlineView />;
}
