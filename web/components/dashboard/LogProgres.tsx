"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import d from "./dashboard.module.css";
import s from "./logprogres.module.css";

// Log Progres nasional (tab Log Progres di LK): ringkasan per cutoff. Dulu ada di halaman Tarik Cutoff.

type LogBaris = { kelompok: string; komponen: string; nilai: string[] };
type Data = { cutoff: string[]; baris: LogBaris[] };

const fmt = (n: number) => n.toLocaleString("id-ID");

export function LogProgresNasional() {
  const [data, setData] = useState<Data | null>(null);
  useEffect(() => {
    api<Data>("/api/dashboard/log-progres").then(setData).catch(() => setData(null));
  }, []);
  if (!data?.cutoff.length) return null;
  return <LogProgres data={data} />;
}
type Nilai = { teks: string; persen: number | null; a: number | null; b: number | null; hari: number | null };

function angkaId(t: string) {
  return Number(t.replace(/\./g, "").replace(",", "."));
}

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
  const pct = t.match(/^([\d.,]+)\s*%$/);
  if (pct) { out.persen = angkaId(pct[1]); return out; }
  const hari = t.match(/^([\d.,]+)\s*hari/);
  if (hari) { out.hari = angkaId(hari[1]); return out; }
  if (/^[\d.]+$/.test(t)) out.a = angkaId(t);
  return out;
}

function LogProgres({ data }: { data: Data }) {
  const kelompok = useMemo(() => {
    const out: { nama: string; baris: (LogBaris & { v: Nilai[] })[] }[] = [];
    for (const b of data.baris) {
      const x = { ...b, v: b.nilai.map(bacaNilai) };
      const akhir = out[out.length - 1];
      if (akhir && akhir.nama === b.kelompok) akhir.baris.push(x);
      else out.push({ nama: b.kelompok, baris: [x] });
    }
    return out;
  }, [data]);
  const umum = kelompok.find((k) => k.nama === "Umum");
  const total = umum?.baris[0]?.v.at(-1)?.a ?? null;
  const n = data.cutoff.length;

  return (
    <section className={d.card} aria-labelledby="h-logp">
      <div className={d.cardHead}>
        <div>
          <h2 id="h-logp">Log Progres nasional</h2>
          <p className={s.muted}>{data.cutoff.at(-1)}{total ? ` · ${fmt(total)} sekolah` : ""}{n > 1 ? ` · tren ${n} cutoff` : ""}</p>
        </div>
      </div>
      <div className={s.logGrid}>
        {kelompok.filter((k) => k.nama !== "Umum").map((k) => {
          const utama = k.baris.find((b) => b.v.some((v) => v.persen !== null)) ?? k.baris[0];
          const v = utama.v.at(-1)!;
          const lain = k.baris.filter((b) => b !== utama);
          const seri = utama.v.map((x) => x.persen);
          const sebelum = [...seri].slice(0, -1).reverse().find((x) => x !== null) ?? null;
          const beda = v.persen !== null && sebelum !== null ? v.persen - sebelum : null;
          const kosong = v.persen === null && v.a === null && v.hari === null;
          return (
            <article key={k.nama} className={`${s.logKartu} ${kosong ? s.logKosong : ""}`}>
              <header>
                <h3>{k.nama}</h3>
                {beda !== null && Math.abs(beda) >= 0.05 && (
                  <span className={beda > 0 ? s.naikT : s.turunT}>{beda > 0 ? "▲" : "▼"} {Math.abs(beda).toFixed(1).replace(".", ",")} poin</span>
                )}
              </header>
              <div className={s.logUtama}>
                {v.persen !== null ? <Cincin persen={v.persen} /> : null}
                <div>
                  <b>{v.persen !== null ? `${v.persen.toFixed(1).replace(".", ",")}%` : kosong ? "Belum ada data" : v.teks}</b>
                  <span>{utama.komponen}</span>
                  {v.a !== null && v.b !== null && <small>{fmt(v.a)} dari {fmt(v.b)}</small>}
                </div>
              </div>
              {n > 1 && seri.filter((x) => x !== null).length > 1 && <Spark nilai={seri} label={data.cutoff} />}
              {lain.length > 0 && (
                <ul className={s.logLain}>
                  {lain.map((b) => {
                    const x = b.v.at(-1)!;
                    return (
                      <li key={b.komponen}>
                        <span>{b.komponen}</span>
                        {x.persen !== null ? (
                          <span className={s.miniBar} title={x.teks}><span style={{ width: `${Math.min(100, x.persen)}%` }} /></span>
                        ) : <span />}
                        <b className={x.hari !== null && x.hari > 3 ? s.lamaT : undefined}>
                          {x.persen !== null ? `${x.persen.toFixed(1).replace(".", ",")}%` : x.teks || "–"}
                        </b>
                      </li>
                    );
                  })}
                </ul>
              )}
            </article>
          );
        })}
      </div>
      <details className={s.wajib}>
        <summary>Lihat sebagai tabel</summary>
        <div className={s.tabelWrap}>
          <table className={s.tabel}>
            <thead><tr><th>Komponen</th>{data.cutoff.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {data.baris.map((b, i) => (
                <tr key={i} className={b.kelompok !== data.baris[i - 1]?.kelompok ? s.grupAwal : undefined}>
                  <td><small>{b.kelompok !== data.baris[i - 1]?.kelompok ? b.kelompok : ""}</small>{b.komponen}</td>
                  {b.nilai.map((v, j) => <td key={j} className={s.num}>{v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function Cincin({ persen }: { persen: number }) {
  const r = 22, c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(100, persen));
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true" className={s.cincin}>
      <circle cx="28" cy="28" r={r} className={s.cincinDasar} />
      <circle cx="28" cy="28" r={r} className={s.cincinIsi} strokeDasharray={`${(p / 100) * c} ${c}`} transform="rotate(-90 28 28)" />
    </svg>
  );
}

function Spark({ nilai, label }: { nilai: (number | null)[]; label: string[] }) {
  const W = 220, H = 40;
  const ada = nilai.filter((v): v is number => v !== null);
  const lo = Math.max(0, Math.min(...ada) - 3), hi = Math.min(100, Math.max(...ada) + 3);
  const rentang = Math.max(6, hi - lo);
  const titik = nilai.map((v, i) => (v === null ? null : {
    x: (i / Math.max(1, nilai.length - 1)) * (W - 8) + 4, y: H - 5 - ((v - lo) / rentang) * (H - 10), v, c: label[i] }))
    .filter(Boolean) as { x: number; y: number; v: number; c: string }[];
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" className={s.spark}
      aria-label={titik.map((t) => `${t.c}: ${t.v.toFixed(1)}%`).join(", ")}>
      <polyline points={titik.map((p) => `${p.x},${p.y}`).join(" ")} />
      {titik.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={i === titik.length - 1 ? 3.5 : 2.5}>
          <title>{`${p.c}: ${p.v.toFixed(1).replace(".", ",")}%`}</title>
        </circle>
      ))}
    </svg>
  );
}
