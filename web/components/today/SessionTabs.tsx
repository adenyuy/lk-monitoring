"use client";

import type { SesiRingkas } from "@/lib/types";
import s from "./today.module.css";

function meta(x: SesiRingkas) {
  switch (x.status) {
    case "Selesai":
      return x.terkirim ? `${x.terkirim} terkirim` : "Lewat";
    case "Kuota habis":
      return `${x.terkirim}/${x.kuota}, penuh`;
    case "Berjalan":
      return `${x.terkirim}/${x.kuota} berjalan`;
    case "Libur":
      return "Libur";
    default:
      return x.perkiraan ? `${x.perkiraan} fasil` : "Tidak ada antrean";
  }
}

/** Lima sesi hari ini sebagai tab. */
export function SessionTabs({ sesi, dipilih, onPilih }: {
  sesi: SesiRingkas[];
  dipilih: number;
  onPilih: (no: number) => void;
}) {
  return (
    <div className={s.tabs} role="tablist" aria-label="Sesi hari ini">
      {sesi.map((x) => {
        const lewat = x.status === "Selesai" || x.status === "Kuota habis";
        return (
          <button key={x.no} type="button" role="tab" aria-selected={x.no === dipilih}
            className={`${s.tabBtn} ${lewat ? s.tabDone : ""} ${x.status === "Berjalan" ? s.tabLive : ""}`}
            onClick={() => onPilih(x.no)}>
            <span className={s.tabTop}>
              {x.status === "Berjalan" && <span className={s.liveDot} aria-hidden="true" />}
              {lewat && x.terkirim > 0 && (
                <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true" className={s.tick}>
                  <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              Sesi {x.no}
            </span>
            <span className={s.tabTime}>{x.mulai}–{x.sampai}</span>
            <span className={s.tabMeta}>{meta(x)}</span>
          </button>
        );
      })}
    </div>
  );
}
