import type { Komp, Tahap } from "@/lib/lk";
import s from "./lk.module.css";

const PENDEK: Record<string, string> = {
  lp: "Kirim", lp_rev: "Reviu", progres: "Fisik", mg: "Mingguan", mg_rev: "R. Mgg", bl: "Bulanan", bl_rev: "R. Bln",
  bku: "BKU", bpp: "BPP", l50: "Unggah", l50_rev: "Reviu", l100: "Unggah", l100_rev: "Reviu",
};

const KELOMPOK: { tahap: Tahap; label: string }[] = [
  { tahap: "pendahuluan", label: "Pendahuluan" },
  { tahap: "berkala", label: "Berkala" },
  { tahap: "l50", label: "50%" },
  { tahap: "l100", label: "100%" },
];

function kelas(k: Komp, todo: boolean) {
  if (k.status === "selesai") return s.seg_selesai;
  if (todo) return s.seg_todo;
  if (k.menunggu) return s.seg_menunggu;
  if (k.status === "belum") return s.seg_belum;
  return s.seg_due;
}

function arti(k: Komp, todo: boolean) {
  if (k.status === "selesai") return "selesai";
  if (todo) return "to-do";
  if (k.menunggu) return k.menunggu.toLowerCase();
  if (k.status === "due") return "belum due";
  if (k.status === "kosong") return "belum ada laporan";
  if (k.status === "tanpa_data") return "belum ada data";
  return "berjalan";
}

/** Lintasan 13 komponen dari kiri ke kanan: tujuannya semua hijau. */
export function Track({ komponen, todo }: { komponen: Komp[]; todo: Set<string> }) {
  return (
    <div className={s.track} role="list" aria-label="Status komponen dari kiri ke kanan">
      {KELOMPOK.map((g) => {
        const isi = komponen.filter((k) => k.tahap === g.tahap);
        return (
          <div key={g.tahap} className={s.trackGrup} style={{ flexGrow: isi.length }}>
            <span className={s.trackLabel}>{g.label}</span>
            <div className={s.trackSeg}>
              {isi.map((k) => {
                const t = todo.has(k.kode);
                const tampil = k.status === "tanpa_data" ? "" : `: ${k.tampil}`;
                return (
                  <span key={k.kode} role="listitem" className={`${s.seg} ${kelas(k, t)}`}
                    title={`${k.label}${tampil} (${arti(k, t)})`} aria-label={`${k.label}, ${arti(k, t)}`}>
                    <i>{PENDEK[k.kode] ?? k.label}</i>
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
