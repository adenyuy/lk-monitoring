"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useMe, usePolling } from "@/lib/hooks";
import type { WaStatus } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import s from "./app.module.css";

const WA_WARNA: Record<string, string> = { logged_in: "#1e7a4c", qr: "#e0a43a", loading: "#e0a43a" };

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const { me, error } = useMe();
  const [wa, setWa] = useState<WaStatus | null>(null);

  const siap = !!me && me.logged_in && !!me.access && me.settings.setup_selesai;

  // Belum selesai persiapan -> arahkan ke /setup/
  useEffect(() => {
    if (me && !siap) router.replace("/setup/");
  }, [me, siap, router]);

  const cekWa = async () => {
    try {
      setWa(await api<WaStatus>("/api/wa/status"));
    } catch {
      /* status WA hanya informasi di header */
    }
  };
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (siap) void cekWa();
  }, [siap]);
  usePolling(cekWa, 30000, siap);

  if (error && !me) {
    return (
      <div className={s.center}>
        <div style={{ maxWidth: 480 }}>
          <Notice tone="bad" title="Aplikasi belum tersambung">
            {error}. Tutup jendela ini lalu buka lagi lewat shortcut LK Monitoring.
          </Notice>
        </div>
      </div>
    );
  }
  if (!siap) {
    return (
      <div className={s.center}>
        <span style={{ display: "flex", gap: 10, alignItems: "center" }}><Spinner label="Memuat" /> Memuat…</span>
      </div>
    );
  }

  const nav = [
    { href: "/today/", label: "Hari ini" },
    { href: "/history/", label: "Riwayat" },
    ...(me.access?.fitur.includes("cutoff") ? [{ href: "/cutoff/", label: "Tarik Cutoff" }] : []),
  ];
  const waLabel = wa?.state === "logged_in" ? wa.nomor_tersamar || "WhatsApp terhubung"
    : wa?.state === "closed" ? "WhatsApp belum dibuka" : wa ? "WhatsApp menunggu" : "Memeriksa WhatsApp";

  return (
    <>
      <header className={s.header}>
        <div className={s.headerIn}>
          <div className={s.left}>
            <Link href="/today/" className={s.brand}>
              <span className={s.logo}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2"
                  strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" />
                </svg>
              </span>
              LK Monitoring
            </Link>
            <nav className={s.nav} aria-label="Menu utama">
              {nav.map((n) => (
                <Link key={n.href} href={n.href} className={s.navLink}
                  aria-current={path?.startsWith(n.href.slice(0, -1)) ? "page" : undefined}>
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className={s.right}>
            <span className={s.wa} title="Status WhatsApp">
              <span className={s.waDot} style={{ background: WA_WARNA[wa?.state ?? ""] ?? "#98a2b3" }} />
              {waLabel}
            </span>
            <span className={s.who}>{me.settings.nama_petugas}</span>
            <Link href="/setup/" className={s.batas}>Batas harian {me.settings.batas_harian}</Link>
          </div>
        </div>
      </header>
      <main className={s.main}>{children}</main>
      <footer className={s.footer}>
        <span>Tim Monitoring Revitalisasi SD 2026</span>
        <span>Versi {me.version}</span>
      </footer>
    </>
  );
}
