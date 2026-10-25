import type { Metadata } from "next";
import { SetupFlow } from "@/components/setup/SetupFlow";

export const metadata: Metadata = { title: "Persiapan – LK Monitoring" };

export default function SetupPage() {
  return <SetupFlow />;
}
