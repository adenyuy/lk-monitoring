import type { Metadata } from "next";
import { Suspense } from "react";
import { MasukView } from "@/components/online/MasukView";

export const metadata: Metadata = { title: "Masuk – LK Monitoring" };

export default function MasukPage() {
  return <Suspense><MasukView /></Suspense>;
}
