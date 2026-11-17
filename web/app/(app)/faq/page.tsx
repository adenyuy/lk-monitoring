import type { Metadata } from "next";
import { FaqEskalasi } from "@/components/eskalasi/FaqEskalasi";

export const metadata: Metadata = { title: "FAQ – LK Monitoring" };

export default function FaqPage() {
  return <FaqEskalasi />;
}
