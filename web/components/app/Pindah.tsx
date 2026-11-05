"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Halaman lama (Hari ini, Rekap) dipindah ke LK; tautan lama tetap jalan. */
export function Pindah({ ke }: { ke: string }) {
  const router = useRouter();
  useEffect(() => {
    const q = window.location.search;
    router.replace(`${ke}${q}`);
  }, [ke, router]);
  return null;
}
