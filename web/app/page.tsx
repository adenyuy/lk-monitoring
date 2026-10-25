"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/hooks";
import { Notice, Spinner } from "@/components/ui";

// Pintu masuk: arahkan ke persiapan atau ke layar kerja.
export default function Home() {
  const router = useRouter();
  const { me, error } = useMe();

  useEffect(() => {
    if (!me) return;
    const siap = me.logged_in && !!me.access && me.settings.setup_selesai;
    router.replace(siap ? "/today/" : "/setup/");
  }, [me, router]);

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      {error ? (
        <div style={{ maxWidth: 480 }}>
          <Notice tone="bad" title="Aplikasi belum tersambung">
            {error}. Tutup jendela ini lalu buka lagi lewat shortcut LK Monitoring.
          </Notice>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)" }}>
          <Spinner label="Memuat" /> Memuat LK Monitoring…
        </div>
      )}
    </main>
  );
}
