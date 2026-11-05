import type { Metadata } from "next";
import { BlastView } from "@/components/blast/BlastView";

export const metadata: Metadata = { title: "Blast – LK Monitoring" };

export default function BlastPage() {
  return <BlastView />;
}
