import type { Metadata } from "next";
import { FaqView } from "@/components/faq/FaqView";

export const metadata: Metadata = { title: "Panduan – LK Monitoring" };

export default function PanduanPage() {
  return <FaqView />;
}
