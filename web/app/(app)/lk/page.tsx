import type { Metadata } from "next";
import { Suspense } from "react";
import { LkView } from "@/components/lk/LkView";

export const metadata: Metadata = { title: "LK – LK Monitoring" };

export default function LkPage() {
  return (
    <Suspense>
      <LkView />
    </Suspense>
  );
}
