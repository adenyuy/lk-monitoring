import type { Metadata } from "next";
import { FaqView } from "@/components/faq/FaqView";

export const metadata: Metadata = { title: "Tanya jawab – LK Monitoring" };

export default function FaqPage() {
  return <FaqView />;
}
