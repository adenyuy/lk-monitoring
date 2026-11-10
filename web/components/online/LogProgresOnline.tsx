"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/ui";
import d from "@/components/dashboard/dashboard.module.css";
import s from "./online.module.css";

// Log Progres nasional (tab Log Progres di LK) dengan batang per cutoff dan angka di tiap batang.

type LogBaris = { kelompok: string; komponen: string; nilai: string[] };
type Data = { cutoff: string[]; baris: LogBaris[] };
type Nilai = { teks: string; persen: number | null; a: number | null; b: number | null; hari: number | null };

const fmt = (n: number) => n.toLocaleString("id-ID");
const pct = (v: number) => `${v.toFixed(1).replace(".", ",")}%`;
const angkaId = (t: string) => Number(t.replace(/\./g, "").replace(",", "."));

/** "11.117 / 18.743 (59,3%)", "32,6%", "4,1 hari", "18.744", "-" */
function bacaNilai(teks: string): Nilai {
  const t = (teks ?? "").trim();
  const out: Nilai = { teks: t, persen: null, a: null, b: null, hari: null };
  const rasio = t.match(/^([\d.]+)\s*\/\s*([\d.]+)(?:\s*\(([\d.,]+)%\))?/);
  if (rasio) {
    out.a = angkaId(rasio[1]); out.b = angkaId(rasio[2]);
    out.persen = rasio[3] ? angkaId(rasio[3]) : out.b ? (out.a / out.b) * 100 : null;
    return out;
  }
  const p = t.match(/^([\d.,]+)\s*%$/);
  if (p) { out.persen = angkaId(p[1]); return out; }
  const h = t.match(/^([\d.,]+)\s*hari/);
  if (h) { out.hari = angkaId(h[1]); return out; }
  if (/^[\d.]+$/.test(t)) out.a = angkaId(t);
  return out;
}

/** "Cutoff 2 (06/11)" -> ["Cutoff 2", "06/11"] */
function pecahLabel(c: string): [string, string] {
  const m = c.match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? [m[1], m[2]] : [c, ""];
}

export function LogProgresOnline() {
  const [data, setData] = useState<Data | null | undefined>(undefined);
  useEffect(() => { api<Data>("/api/dashboard/log-progres").then(setData).catch(() => setData(null)); }, []);
  if (data === undefined) return <section className={d.card}><div className={s.memuat}><Spinner label="Memuat" /> Membaca Log Progres…</div></section>;
  if (!data?.cutoff.length) return null;
  return <LogProgres data={data} />;
}

function LogProgres({ data }: { data: Data }) {
  // Setiap baris (komponen) jadi kartu tren sendiri; baris tanpa angka % / hari (mis. jumlah sekolah) dilewati.
  const kartu = useMemo(() => data.baris.map((b) => ({ ...b, v: b.nilai.map(bacaNilai) }))
    .filter((b) => b.v.some((x) => x.persen !== null || x.hari !== null)), [data]);
  const total = data.baris.find((b) => b.kelompok === "Umum") ? bacaNilai(data.baris.find((b) => b.kelompok === "Umum")!.nilai.at(-1) ?? "").a : null;

  return (
    <section className={d.card} aria-labelledby="h-logp-online">
      <div className={d.cardHead}>
        <h2 id="h-logp-online">Log Progres nasional</h2>
        <span>{data.cutoff.length} cutoff{total ? ` · ${fmt(total)} sekolah` : ""} · angka di tiap titik = nilai saat cutoff itu</span>
      </div>
      <div className={s.lpGrid}>
        {kartu.map((b, i) => (
          <article key={`${b.kelompok}-${b.komponen}-${i}`} className={s.lpKartu}>
            <header>
              <span>{b.kelompok}</span>
              <h3>{b.komponen}</h3>
            </header>
            <Tren cutoff={data.cutoff} nilai={b.v} />
          </article>
        ))}
      </div>
      <details className={s.lpTabel}>
        <summary>Lihat sebagai tabel</summary>
        <div className={s.gulir}>
          <table className={s.tabel}>
            <thead><tr><th>Komponen</th>{data.cutoff.map((c) => <th key={c} className={s.angka}>{c}</th>)}</tr></thead>
            <tbody>
              {data.baris.map((b, i) => (
                <tr key={i}>
                  <td>{b.kelompok !== data.baris[i - 1]?.kelompok && <small>{b.kelompok}</small>}{b.komponen}</td>
                  {b.nilai.map((v, j) => <td key={j} className={s.angka}>{v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

/** Garis tren per cutoff; tiap titik diberi label nilai (dan jumlah bila ada). Satuan % atau hari. */
function Tren({ cutoff, nilai }: { cutoff: string[]; nilai: Nilai[] }) {
  const hari = nilai.every((x) => x.persen === null);
  const angka = nilai.map((x) => (hari ? x.hari : x.persen));
  const ada = angka.filter((v): v is number => v !== null);
  if (!ada.length) return <p className={s.kosong}>Belum ada data.</p>;
  const W = 320, H = 170, KIRI = 22, KANAN = 22, ATAS = 44, BAWAH = 34;
  const lo = Math.min(...ada), hi = Math.max(...ada);
  const pad = Math.max((hi - lo) * 0.25, hari ? 0.5 : 2);
  const min = Math.max(0, lo - pad), maks = hi + pad;
  const x = (i: number) => KIRI + (cutoff.length > 1 ? (i / (cutoff.length - 1)) * (W - KIRI - KANAN) : (W - KIRI - KANAN) / 2);
  const y = (v: number) => ATAS + (1 - (v - min) / Math.max(0.001, maks - min)) * (H - ATAS - BAWAH);
  const teks = (v: number) => (hari ? `${v.toFixed(1).replace(".", ",")} hr` : pct(v));
  const titik = angka.map((v, i) => (v === null ? null : { i, v, x: x(i), y: y(v) })).filter(Boolean) as { i: number; v: number; x: number; y: number }[];
  const akhir = titik.at(-1)!;
  const awal = titik[0];
  const naik = titik.length > 1 ? akhir.v - awal.v : null;
  const baik = naik === null ? null : hari ? naik <= 0 : naik >= 0;

  return (
    <div className={s.lpTren}>
      <div className={s.lpAngka}>
        <b>{teks(akhir.v)}</b>
        {naik !== null && Math.abs(naik) >= 0.05 && (
          <span className={baik ? s.tBaikT : s.tKurangT}>{naik > 0 ? "▲" : "▼"} {Math.abs(naik).toFixed(1).replace(".", ",")} {hari ? "hari" : "poin"} sejak {pecahLabel(cutoff[awal.i])[0]}</span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" className={s.lpSvg}
        aria-label={titik.map((p) => `${cutoff[p.i]}: ${teks(p.v)}`).join(", ")}>
        <line x1={KIRI - 8} x2={W - KANAN + 8} y1={H - BAWAH} y2={H - BAWAH} className={s.lpDasar} />
        <polyline points={titik.map((p) => `${p.x},${p.y}`).join(" ")} className={s.lpGaris} />
        {titik.map((p) => {
          const n = nilai[p.i];
          const terakhir = p === akhir;
          return (
            <g key={p.i}>
              <circle cx={p.x} cy={p.y} r={terakhir ? 4.5 : 3.5} className={terakhir ? s.lpTitikAkhir : s.lpTitik} />
              <text x={p.x} y={p.y - (n.a !== null && n.b !== null ? 20 : 10)} textAnchor="middle" className={s.lpNilai}>{teks(p.v)}</text>
              {n.a !== null && n.b !== null && (
                <text x={p.x} y={p.y - 9} textAnchor="middle" className={s.lpJumlah}>{fmt(n.a)}/{fmt(n.b)}</text>
              )}
              <text x={p.x} y={H - BAWAH + 15} textAnchor="middle" className={s.lpSumbu}>{pecahLabel(cutoff[p.i])[0].replace("Cutoff", "C")}</text>
              <text x={p.x} y={H - BAWAH + 28} textAnchor="middle" className={s.lpSumbuTgl}>{pecahLabel(cutoff[p.i])[1]}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
