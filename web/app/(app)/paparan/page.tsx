import type { Metadata } from "next";
import { PaparanView } from "@/components/paparan/PaparanView";

export const metadata: Metadata = { title: "Paparan – LK Monitoring" };

export default function PaparanPage() {
  return <PaparanView />;
}
