"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/hooks";
import type { Me, Petugas } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import { StepLogin } from "./StepLogin";
import { StepPetugas } from "./StepPetugas";
import { StepWhatsApp } from "./StepWhatsApp";
import { StepBatas } from "./StepBatas";
import s from "./setup.module.css";

const STEPS = [
  { label: "Masuk Google", hint: "Akun yang terdaftar di tim" },
  { label: "Pilih nama", hint: "Sesuai sheet Broadcast" },
  { label: "Hubungkan WhatsApp", hint: "Scan QR sekali saja" },
  { label: "Batas harian", hint: "Pesan maksimal per hari" },
];

/** Langkah pertama yang belum beres. */
function firstIncomplete(me: Me): number {
  if (me.needs_credentials || !me.logged_in || !me.access) return 0;
  if (!me.settings.nama_petugas) return 1;
  if (!me.settings.wa_terhubung) return 2;
  return 3;
}

function Logo() {
  return (
    <span className={s.logo}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" />
      </svg>
    </span>
  );
}

export function SetupFlow() {
  const router = useRouter();
  const { me, error, reload } = useMe();
  const [step, setStep] = useState<number | null>(null);
  const [petugas, setPetugas] = useState<Petugas | null>(null);

  // Tentukan langkah awal sekali, saat data pertama kali datang.
  if (me && step === null) setStep(firstIncomplete(me));
  const current = step ?? 0;
  const go = (n: number) => setStep(Math.max(0, Math.min(STEPS.length - 1, n)));

  return (
    <div className={s.page}>
        <aside className={s.side}>
          <div className={s.brand}>
            <Logo />
            LK Monitoring
          </div>
          <h2 className={s.headline}>Siapkan sekali, kirim per sesi.</h2>
          <p className={s.lead}>
            Empat langkah ini cukup dilakukan sekali di laptop ini. Setelah itu kamu tinggal membuka aplikasi dan menekan
            kirim saat sesi berjalan.
          </p>
          <ol className={s.rail} aria-label="Langkah persiapan">
            {STEPS.map((st, i) => {
              const cls = i < current ? s.done : i === current ? s.current : "";
              return (
                <li key={st.label} className={`${s.railItem} ${cls}`} aria-current={i === current ? "step" : undefined}>
                  <span className={s.dot} aria-hidden="true">
                    {i < current ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                        strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                    ) : i + 1}
                  </span>
                  <span className={s.railLabel}>
                    {st.label}
                    <span className={s.railHint}>{st.hint}</span>
                  </span>
                </li>
              );
            })}
          </ol>
          <div className={s.sideFoot}>
            <span>Tim Monitoring Revitalisasi SD 2026</span>
            <span>Versi {me?.version ?? "–"}</span>
          </div>
        </aside>

        <main className={s.main}>
        <section className={s.card} aria-live="polite">
          {error && !me && (
            <Notice tone="bad" title="Aplikasi belum tersambung">
              {error}. Tutup jendela ini lalu buka lagi lewat shortcut LK Monitoring.
            </Notice>
          )}
          {!me && !error && (
            <div className={s.waiting}>
              <Spinner label="Memuat" />
              <span>Memuat…</span>
            </div>
          )}

          {me && (
            <>
              <div className={s.stepNo}>Langkah {current + 1} dari {STEPS.length}</div>
              {current === 0 && <StepLogin me={me} reload={reload} onNext={() => go(1)} />}
              {current === 1 && (
                <StepPetugas me={me} onBack={() => go(0)}
                  onNext={(p) => { setPetugas(p); void reload(); go(2); }} />
              )}
              {current === 2 && <StepWhatsApp onBack={() => go(1)} onNext={() => { void reload(); go(3); }} />}
              {current === 3 && (
                <StepBatas awal={me.settings.batas_harian} namaPetugas={petugas?.nama ?? me.settings.nama_petugas}
                  jumlahFasilAwal={petugas?.jumlah_fasil ?? null}
                  onBack={() => go(2)} onDone={() => router.replace("/today/")} />
              )}
            </>
          )}
        </section>
        </main>
    </div>
  );
}
