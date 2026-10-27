import type { Metadata } from "next";
import { SetupFlow } from "@/components/setup/SetupFlow";
import { Pembaruan } from "@/components/app/Pembaruan";

export const metadata: Metadata = { title: "Persiapan – LK Monitoring" };

export default function SetupPage() {
  return (
    <>
      <Pembaruan />
      <SetupFlow />
    </>
  );
}
