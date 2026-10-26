import type { Metadata } from "next";
import { CutoffView } from "@/components/cutoff/CutoffView";

export const metadata: Metadata = { title: "Tarik Cutoff – LK Monitoring" };

export default function CutoffPage() {
  return <CutoffView />;
}
