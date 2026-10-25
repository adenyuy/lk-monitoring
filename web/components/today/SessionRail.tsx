"use client";

import type { SesiRingkas } from "@/lib/types";
import s from "./today.module.css";

const TICKS = ["10.00", "12.00", "14.00", "16.00", "18.00", "20.00", "22.00"];

export function SessionRail({
  sesi,
  dipilih,
  posisi,
  jam,
  onPilih,
}: {
  sesi: SesiRingkas[];
  dipilih: number;
  posisi: number;
  jam: string;
  onPilih: (no: number) => void;
}) {
  // Lebar blok sebanding durasi sesi, tapi tidak lebih sempit dari 120 px agar teks tidak patah.
  const kolom = sesi.map((x) => `minmax(120px, ${x.durasi_menit}fr)`).join(" ");
  const tampilNow = posisi > 0 && posisi < 100;

  return (
    <section className={s.railCard} aria-label="Sesi hari ini">
      <div className={s.railScroll}>
        <div className={s.railInner}>
          <div className={s.blocks} style={{ gridTemplateColumns: kolom }}>
            {sesi.map((x) => {
              const aktif = x.status === "Berjalan";
              const redup = x.status === "Libur";
              const cls = [s.block, aktif ? s.blockActive : "", redup ? s.blockMuted : "",
                x.no === dipilih ? s.blockSelected : ""].join(" ");
              const persen = Math.min(100, Math.round((x.terkirim / x.kuota) * 100));
              return (
                <button key={x.no} type="button" className={cls} aria-pressed={x.no === dipilih}
                  onClick={() => onPilih(x.no)}
                  aria-label={`Sesi ${x.no}, ${x.mulai} sampai ${x.sampai}, ${x.status}, ${x.terkirim} dari ${x.kuota} terkirim`}>
                  <span className={s.blockTop}><span>Sesi {x.no}</span><span>{x.status}</span></span>
                  <span className={s.blockTime}>{x.mulai}</span>
                  <span className={s.blockSub}>{x.terkirim} dari {x.kuota} pesan</span>
                  <span className={s.track}><span className={s.fill} style={{ width: `${persen}%` }} /></span>
                </button>
              );
            })}
          </div>
          {tampilNow && (
            <div className={s.now} style={{ left: `calc(${posisi}% - 1px)` }} aria-hidden="true">
              <span className={s.nowLabel}>{jam}</span>
            </div>
          )}
        </div>
        <div className={s.ticks} aria-hidden="true">
          {TICKS.map((t) => <span key={t}>{t}</span>)}
        </div>
      </div>
    </section>
  );
}
