"use client";

import { useMemo, useState } from "react";
import type { Dash } from "@/components/dashboard/DashboardView";
import d from "@/components/dashboard/dashboard.module.css";
import b from "./bimtek.module.css";

/** Warna kategori per kelompok bimtek, urut tetap mengikuti daftar semua kelompok (bukan peringkat),
 *  jadi warna satu kelompok tidak berubah saat filter berganti. Lebih dari 8 kelompok: abu-abu + label. */
const WARNA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const fmt = (n: number) => n.toLocaleString("id-ID");
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${v.toFixed(1).replace(".", ",")}%`);
const pendek = (bt: string) => bt.replace(/^Bimtek\s+/i, "");

export function BimtekPanel({ x, aktif, pilih }: { x: Dash; aktif: string; pilih: (bt: string) => void }) {
  const per = useMemo(() => x.per_bimtek ?? [], [x.per_bimtek]);
  const tren = x.tren_bimtek;
  const urutan = x.pilihan_bimtek ?? per.map((p) => p.bimtek);
  const warna = (bt: string) => { const i = urutan.indexOf(bt); return i >= 0 && i < WARNA.length ? WARNA[i] : "#8a93a6"; };

  // komponen yang sudah due di salah satu kelompok
  const komp = useMemo(() => {
    const ada = new Set(per.flatMap((p) => p.capaian.filter((c) => c.relevan > 0).map((c) => c.kode)));
    return (per[0]?.capaian ?? []).filter((c) => ada.has(c.kode));
  }, [per]);

  if (!per.length) return null;
  const total = per.reduce((n, p) => n + p.sekolah, 0);

  return (
    <section className={d.card} aria-labelledby="h-bimtek">
      <div className={d.cardHead}>
        <h2 id="h-bimtek">Bimtek Pelaporan</h2>
        <span>{fmt(total)} sekolah peserta · klik baris untuk menyaring dashboard</span>
      </div>
      <div className={b.gulir}>
        <table className={b.tabel}>
          <thead>
            <tr>
              <th>Kelompok</th><th className={b.angka}>Sekolah</th><th className={b.angka}>Fasil</th>
              <th className={b.angka}>Tuntas</th><th className={b.angka}>Progres fisik</th>
              {komp.map((k) => <th key={k.kode} className={b.angka}>{k.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {per.map((p) => (
              <tr key={p.bimtek} className={aktif === p.bimtek ? b.aktif : undefined}
                onClick={() => pilih(aktif === p.bimtek ? "" : p.bimtek)} tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") pilih(aktif === p.bimtek ? "" : p.bimtek); }}>
                <td><i className={b.kunci} style={{ background: warna(p.bimtek) }} aria-hidden="true" />{p.bimtek}</td>
                <td className={b.angka}>{fmt(p.sekolah)}</td>
                <td className={b.angka}>{fmt(p.fasil)}</td>
                <td className={b.angka}>{fmt(p.lengkap)} <small>({pct(p.sekolah ? (p.lengkap / p.sekolah) * 100 : null)})</small></td>
                <td className={b.angka}>{pct(p.progres)}</td>
                {komp.map((k) => {
                  const c = p.capaian.find((y) => y.kode === k.kode);
                  return (
                    <td key={k.kode} className={b.angka} title={c ? `${fmt(c.selesai)} dari ${fmt(c.relevan)} sekolah` : ""}>
                      {c?.relevan ? <>{pct(c.persen)}<small>{fmt(c.selesai)}/{fmt(c.relevan)}</small></> : "–"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tren && <Pergerakan tren={tren} warna={warna} aktif={aktif} />}
    </section>
  );
}

type Tren = NonNullable<Dash["tren_bimtek"]>;

function Pergerakan({ tren, warna, aktif }: { tren: Tren; warna: (bt: string) => string; aktif: string }) {
  const pilihan = tren.kolom.filter((k) => tren.kelompok.some((g) => (g.seri[k.kode] ?? []).some((v) => v !== null)));
  const [ukur, setUkur] = useState("");
  const [hover, setHover] = useState<number | null>(null);
  const kode = pilihan.find((k) => k.kode === ukur)?.kode ?? pilihan.find((k) => k.kode === "l50")?.kode ?? pilihan[0]?.kode ?? "";
  const label = tren.kolom.find((k) => k.kode === kode)?.label ?? "";
  const kel = aktif ? tren.kelompok.filter((g) => g.bimtek === aktif) : tren.kelompok;

  if (!tren.cutoff.length || !pilihan.length) {
    return <p className={b.catatan}>Pergerakan per kelompok bimtek mulai tercatat dari cutoff berikutnya (tab Log Progres Bimtek).</p>;
  }

  const n = tren.cutoff.length;
  if (!kel.some((g) => (g.seri[kode] ?? []).some((v) => v !== null))) {
    return <p className={b.catatan}>Belum ada catatan {label} untuk kelompok ini.</p>;
  }
  const W = 760, H = 260, KIRI = 44, KANAN = 96, ATAS = 18, BAWAH = 40;
  const semua = kel.flatMap((g) => g.seri[kode] ?? []).filter((v): v is number => v !== null);
  const lo = Math.max(0, Math.floor((Math.min(...semua) - 5) / 10) * 10);
  const hi = Math.min(100, Math.ceil((Math.max(...semua) + 5) / 10) * 10);
  const xs = (i: number) => KIRI + (n > 1 ? (i / (n - 1)) * (W - KIRI - KANAN) : (W - KIRI - KANAN) / 2);
  const ys = (v: number) => ATAS + (1 - (v - lo) / Math.max(1, hi - lo)) * (H - ATAS - BAWAH);
  const garisY = [lo, (lo + hi) / 2, hi];
  const lebarHit = n > 1 ? (W - KIRI - KANAN) / (n - 1) : W - KIRI - KANAN;
  const pecah = (c: string) => { const m = c.match(/^(.*?)\s*\((.*)\)\s*$/); return m ? [m[1], m[2]] : [c, ""]; };

  // label langsung di ujung garis, didorong supaya tidak bertumpuk
  const ujung = kel.map((g) => {
    const v = g.seri[kode] ?? [];
    let i = v.length - 1;
    while (i >= 0 && v[i] === null) i--;
    return i < 0 ? null : { g, i, v: v[i] as number, y: ys(v[i] as number) };
  }).filter((u): u is NonNullable<typeof u> => !!u).sort((a, c) => a.y - c.y);
  for (let j = 1; j < ujung.length; j++) ujung[j].y = Math.max(ujung[j].y, ujung[j - 1].y + 14);

  return (
    <div className={b.tren}>
      <div className={b.trenHead}>
        <h3>Pergerakan per cutoff</h3>
        <label>
          <span>Ukuran</span>
          <select value={kode} onChange={(e) => setUkur(e.target.value)}>
            {pilihan.map((k) => <option key={k.kode} value={k.kode}>{k.label}</option>)}
          </select>
        </label>
      </div>
      <ul className={b.legenda}>
        {kel.map((g) => <li key={g.bimtek}><i style={{ background: warna(g.bimtek) }} aria-hidden="true" />{g.bimtek}</li>)}
      </ul>
      <div className={b.kanvas} onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
          aria-label={`${label} per kelompok bimtek, ${n} cutoff`}>
          {garisY.map((v) => (
            <g key={v}>
              <line x1={KIRI} x2={W - KANAN} y1={ys(v)} y2={ys(v)} className={b.grid} />
              <text x={KIRI - 8} y={ys(v) + 4} textAnchor="end" className={b.sumbu}>{Math.round(v)}%</text>
            </g>
          ))}
          {tren.cutoff.map((c, i) => (
            <g key={c}>
              <text x={xs(i)} y={H - BAWAH + 16} textAnchor="middle" className={b.sumbu}>{pecah(c)[0].replace("Cutoff", "C")}</text>
              <text x={xs(i)} y={H - BAWAH + 30} textAnchor="middle" className={b.sumbuTgl}>{pecah(c)[1]}</text>
            </g>
          ))}
          {hover !== null && <line x1={xs(hover)} x2={xs(hover)} y1={ATAS} y2={H - BAWAH} className={b.silang} />}
          {kel.map((g) => {
            const v = g.seri[kode] ?? [];
            const titik = v.map((y, i) => (y === null ? null : `${xs(i)},${ys(y)}`)).filter(Boolean).join(" ");
            return (
              <g key={g.bimtek}>
                {n > 1 && <polyline points={titik} fill="none" stroke={warna(g.bimtek)} strokeWidth={2} strokeLinejoin="round" />}
                {v.map((y, i) => (y === null ? null : (
                  <circle key={i} cx={xs(i)} cy={ys(y)} r={hover === i ? 5 : 4} fill={warna(g.bimtek)} className={b.titik} />
                )))}
              </g>
            );
          })}
          {ujung.map((u) => (
            <text key={u.g.bimtek} x={W - KANAN + 10} y={u.y + 4} className={b.labelUjung}>
              {pendek(u.g.bimtek)} {pct(u.v)}
            </text>
          ))}
          {tren.cutoff.map((c, i) => (
            <rect key={c} x={xs(i) - lebarHit / 2} y={ATAS} width={lebarHit} height={H - ATAS - BAWAH} fill="transparent"
              onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0} aria-label={c} />
          ))}
        </svg>
        {hover !== null && (
          <div className={b.tip} style={{ left: `${(xs(hover) / W) * 100}%` }} role="status">
            <b>{tren.cutoff[hover]}</b>
            {kel.map((g) => (
              <span key={g.bimtek}>
                <i style={{ background: warna(g.bimtek) }} aria-hidden="true" />{pendek(g.bimtek)}
                <em>{pct(g.seri[kode]?.[hover] ?? null)}</em>
              </span>
            ))}
          </div>
        )}
      </div>
      <details className={b.detail}>
        <summary>Lihat sebagai tabel</summary>
        <div className={b.gulir}>
          <table className={b.tabel}>
            <thead><tr><th>{label}</th>{tren.cutoff.map((c) => <th key={c} className={b.angka}>{c}</th>)}</tr></thead>
            <tbody>
              {kel.map((g) => (
                <tr key={g.bimtek}>
                  <td>{g.bimtek}</td>
                  {tren.cutoff.map((c, i) => <td key={c} className={b.angka}>{pct(g.seri[kode]?.[i] ?? null)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
