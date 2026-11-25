import type { Metadata } from "next";
import { TimelineView } from "@/components/dashboard/TimelineView";

export const metadata: Metadata = { title: "Timeline – LK Monitoring" };

export default function TimelinePage() {
  return <TimelineView />;
}
