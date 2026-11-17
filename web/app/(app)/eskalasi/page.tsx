import type { Metadata } from "next";
import { EskalasiView } from "@/components/eskalasi/EskalasiView";

export const metadata: Metadata = { title: "Eskalasi – LK Monitoring" };

export default function EskalasiPage() {
  return <EskalasiView />;
}
