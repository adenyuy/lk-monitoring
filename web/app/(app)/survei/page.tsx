import type { Metadata } from "next";
import { SurveiView } from "@/components/survei/SurveiView";

export const metadata: Metadata = { title: "Survei – LK Monitoring" };

export default function SurveiPage() {
  return <SurveiView />;
}
