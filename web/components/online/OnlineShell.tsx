"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, api, post } from "@/lib/api";
import { Notice, Spinner } from "@/components/ui";
import s from "./online.module.css";

const TAB = [
  { href: "/dashboard/", label: "Ringkasan" },
  { href: "/log/", label: "Log" },
];

/** Kerangka dashboard online: cek login, header, tab. Tanpa menu blast/LK/forum. */
export function OnlineShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname() ?? "";
  const [email, setEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ email: string }>("/api/auth/saya")
      .then((r) => setEmail(r.email))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/masuk/");
        else setError(e instanceof Error ? e.message : String(e));
      });
  }, [router]);

  const keluar = async () => {
    try { await post("/api/auth/keluar"); } finally { router.replace("/masuk/"); }
  };

  if (error) return <main className={s.isi}><Notice tone="bad" title="Tidak bisa terhubung">{error}</Notice></main>;
  if (!email) return <main className={s.memuat}><Spinner label="Memuat" /> Memeriksa akses…</main>;

  return (
    <>
      <header className={s.atas}>
        <div className={s.atasDalam}>
          <span className={s.merek}>LK Monitoring</span>
          <nav className={s.tabs} aria-label="Bagian dashboard">
            {TAB.map((t) => (
              <Link key={t.href} href={t.href} className={s.tab}
                aria-current={path.startsWith(t.href.slice(0, -1)) ? "page" : undefined}>{t.label}</Link>
            ))}
          </nav>
          <div className={s.akun}>
            <span title={email}>{email}</span>
            <button type="button" onClick={() => void keluar()}>Keluar</button>
          </div>
        </div>
      </header>
      <main className={s.isi}>{children}</main>
    </>
  );
}
