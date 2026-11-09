"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import s from "./submenu.module.css";

const TAB = [
  { href: "/dashboard/", label: "Ringkasan" },
  { href: "/paparan/", label: "Paparan" },
  { href: "/log/", label: "Log" },
];

export function SubMenu() {
  const path = usePathname() ?? "";
  const [baru, setBaru] = useState(false);

  // Titik di tab Log bila ada perubahan data yang belum dilihat (sama dengan penanda di menu)
  useEffect(() => {
    let hidup = true;
    const cek = async () => {
      try {
        const r = await api<{ items: { id: number }[] }>("/api/perubahan?batas=1");
        let dilihat = 0;
        try { dilihat = Number(localStorage.getItem("lkm-perubahan-dilihat") ?? 0); } catch { /* abaikan */ }
        if (hidup) setBaru(!!r.items[0] && r.items[0].id > dilihat);
      } catch { /* hanya penanda */ }
    };
    void cek();
    const sudah = () => setBaru(false);
    window.addEventListener("lkm-perubahan-dilihat", sudah);
    return () => { hidup = false; window.removeEventListener("lkm-perubahan-dilihat", sudah); };
  }, []);

  return (
    <nav className={s.tabs} aria-label="Bagian Dashboard">
      {TAB.map((t) => {
        const aktif = path.startsWith(t.href.slice(0, -1));
        return (
          <Link key={t.href} href={t.href} className={s.tab} aria-current={aktif ? "page" : undefined}>
            {t.label}
            {t.href === "/log/" && baru && !aktif && <span className={s.titik} title="Ada perubahan data baru" />}
          </Link>
        );
      })}
    </nav>
  );
}
