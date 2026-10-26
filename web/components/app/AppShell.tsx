"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useMe, usePolling } from "@/lib/hooks";
import { API_REV, type WaStatus } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import { WaBanner } from "./WaBanner";
import { LockIcon, NoAccess } from "./NoAccess";
import { Countdown } from "./Countdown";
import { PANDUAN, Tour } from "./Tour";
import { IconCutoff, IconHariIni, IconLogo, IconPanduan, IconRekap } from "./Icons";
import s from "./app.module.css";

const WA_WARNA: Record<string, string> = { logged_in: "#1e7a4c", qr: "#e0a43a", loading: "#e0a43a" };

function inisial(nama: string) {
  const k = nama.trim().split(/\s+/);
  return ((k[0]?.[0] ?? "") + (k[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname() ?? "";
  const { me, error } = useMe();
  const [wa, setWa] = useState<WaStatus | null>(null);
  const [terkunci, setTerkunci] = useState(false);
  const [panduan, setPanduan] = useState(false);

  const siap = !!me && me.logged_in && !!me.access && me.settings.setup_selesai;

  // Belum selesai persiapan -> arahkan ke /setup/
  useEffect(() => {
    if (me && !siap) router.replace("/setup/");
  }, [me, siap, router]);

  const cekWa = async () => {
    try {
      setWa(await api<WaStatus>("/api/wa/status"));
    } catch {
      /* status WA hanya informasi */
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

  const bolehCutoff = !!me.access?.fitur.includes("cutoff");
  const aktif = (href: string) => (path.startsWith(href.slice(0, -1)) ? "page" : undefined);
  const waLabel = wa?.state === "logged_in" ? `WhatsApp ${wa.nomor_tersamar || "terhubung"}`
    : wa?.state === "closed" ? "WhatsApp belum dibuka" : wa ? "WhatsApp menunggu" : "Memeriksa WhatsApp";
  const waDot = WA_WARNA[wa?.state ?? ""] ?? "#98a2b3";
  const langkah = PANDUAN[path] ?? PANDUAN["/today/"];

  const menu = (
    <>
      <Link href="/rekap/" className={s.item} aria-current={aktif("/rekap/")}>
        <span className={s.ico}><IconRekap /></span><span className={s.lbl}>Rekap</span>
      </Link>
      <Link href="/today/" className={s.item} aria-current={aktif("/today/")}>
        <span className={s.ico}><IconHariIni /></span><span className={s.lbl}>Hari ini</span>
      </Link>
      {bolehCutoff ? (
        <Link href="/cutoff/" className={s.item} aria-current={aktif("/cutoff/")}>
          <span className={s.ico}><IconCutoff /></span><span className={s.lbl}>Tarik Cutoff</span>
        </Link>
      ) : (
        <button type="button" className={`${s.item} ${s.itemLocked}`} onClick={() => setTerkunci(true)}
          aria-label="Tarik Cutoff, terkunci">
          <span className={s.ico}><IconCutoff /><span className={s.lockBadge}><LockIcon size={10} /></span></span>
          <span className={s.lbl}>Tarik Cutoff</span>
        </button>
      )}
    </>
  );

  return (
    <div className={s.shell}>
      {/* Laptop: menu samping, hanya ikon; melebar saat kursor diarahkan */}
      <aside className={s.side} aria-label="Menu">
        <Link href="/today/" className={s.brand}>
          <span className={s.logo}><IconLogo /></span>
          <span className={s.lbl}>LK Monitoring</span>
        </Link>
        <nav className={s.menu} aria-label="Menu utama" data-tour="nav">{menu}</nav>

        <div className={s.sideBottom}>
          <Countdown />
          <hr className={s.rule} />
          <button type="button" className={s.item} onClick={() => setPanduan(true)}>
            <span className={s.ico}><IconPanduan /></span><span className={s.lbl}>Panduan</span>
          </button>
          <div className={s.user} data-tour="wa">
            <span className={s.avatar} aria-hidden="true">
              {inisial(me.settings.nama_petugas ?? "")}
              <i style={{ background: waDot }} />
            </span>
            <span className={s.lbl}>
              <b>{me.settings.nama_petugas}</b>
              <small>{waLabel}</small>
              <Link href="/setup/" className={s.batas}>Batas harian {me.settings.batas_harian}</Link>
            </span>
          </div>
        </div>
      </aside>

      {/* HP: bar atas ringkas + menu bawah */}
      <header className={s.mTop}>
        <Link href="/today/" className={s.brand}><span className={s.logo}><IconLogo /></span>LK Monitoring</Link>
        <span className={s.mTopRight}>
          <Countdown compact />
          <span className={s.mWa} data-tour="wa" title={waLabel}><i style={{ background: waDot }} /></span>
          <button type="button" className={s.mHelp} onClick={() => setPanduan(true)} aria-label="Panduan"><IconPanduan /></button>
        </span>
      </header>
      <nav className={s.mTab} aria-label="Menu utama" data-tour="nav">{menu}</nav>

      <div className={s.content}>
        {me.api_rev !== API_REV && (
          <div className={s.bannerWrap}>
            <div className={`${s.banner} ${s.bannerWarn}`} role="alert">
              <div className={s.bannerText}>
                <b>Server aplikasi perlu dijalankan ulang</b>
                <span>Tampilan sudah versi baru, tapi server masih versi lama, jadi sebagian fitur belum jalan.
                  Tutup jendela server (Ctrl+C), lalu jalankan lagi.</span>
              </div>
            </div>
          </div>
        )}
        <WaBanner wa={wa} onChange={setWa} />
        <main className={s.main}>{children}</main>
        <footer className={s.footer}>
          <span>Tim Monitoring Revitalisasi SD 2026</span>
          <span>Versi {me.version}</span>
        </footer>
      </div>

      {terkunci && <NoAccess onClose={() => setTerkunci(false)} />}
      {panduan && <Tour key={path} langkah={langkah} onClose={() => setPanduan(false)} />}
    </div>
  );
}
