"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace("/dashboard/"); }, [router]);
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><Spinner label="Memuat" /></main>;
}
