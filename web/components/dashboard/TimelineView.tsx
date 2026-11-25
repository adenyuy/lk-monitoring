"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Notice, Spinner } from "@/components/ui";
import d from "./dashboard.module.css";
import l from "./logprogres.module.css";
import s from "./timeline.module.css";

type Basis = "pks" | "salur1";
type Seri = (number | null)[];
type Timeline = {
  minggu: { bulan: string; w: string; mulai: string; selesai: string }[];
  basis: Record<Basis, Seri>;
  komponen: ({ kode: string; label: string } & Record<Basis, Seri>)[];
  data_per: string;
  file: string[];
  /** Per kode intervensi: per minggu, kegiatan yang berlangsung minggu itu. */
  intervensi: Record<string, { kode: string; nama: string; mulai: string; selesai: string }[][]>;
};

// Baris tabel intervensi. Data baru ada untuk Bimtek Pelaporan; baris lain menunggu sumber datanya.
const AKSI = [
  { kode: "bimtek", label: "Bimtek Pelaporan" },
  { kode: "survei", label: "Survey Cepat" },
  { kode: "wa_blast", label: "WA Blast" },
  { kode: "dm", label: "Direct Message" },
  { kode: "weekly", label: "Weekly Meeting" },
  { kode: "wa_sekolah", label: "WA Blast Sekolah" },
  { kode: "one_on_one", label: "One on One" },
  { kode: "eskalasi", label: "Eskalasi" },
];
const KUNCI_URUT = "lkm-timeline-urutan";

const BASIS: { kode: Basis; label: string }[] = [
  { kode: "pks", label: "Sudah PKS" },
  { kode: "salur1", label: "Sudah salur tahap 1" },
];

const angka = (n: number) => n.toLocaleString("id-ID");
const persen = (p: number) => `${p.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
const tgl = (t: string) => new Date(t).toLocaleDateString("id-ID", { day: "numeric", month: "short" });

/** Timeline mingguan (Senin–Minggu) Sep–Nov: persen sekolah yang sudah kirim/direviu tiap komponen LK. */
export function TimelineView() {
  const [data, setData] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [basis, setBasis] = useState<Basis>("pks");
  const [hover, setHover] = useState<{ kode: string; i: number } | null>(null);
  const [urut, setUrut] = useState(AKSI.map((a) => a.kode));
  const [seret, setSeret] = useState<string | null>(null);

  // Urutan baris intervensi diingat per browser
  useEffect(() => {
    try {
      const simpan = JSON.parse(localStorage.getItem(KUNCI_URUT) ?? "[]") as string[];
      const ada = simpan.filter((k) => AKSI.some((a) => a.kode === k));
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (ada.length) setUrut([...ada, ...AKSI.map((a) => a.kode).filter((k) => !ada.includes(k))]);
    } catch { /* abaikan */ }
  }, []);
  const pindah = (kode: string, ke: number) => {
    setUrut((u) => {
      const baru = u.filter((k) => k !== kode);
      baru.splice(Math.max(0, Math.min(baru.length, ke)), 0, kode);
      try { localStorage.setItem(KUNCI_URUT, JSON.stringify(baru)); } catch { /* abaikan */ }
      return baru;
    });
  };

  useEffect(() => {
    api<Timeline>("/api/dashboard/timeline").then(setData).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <Notice tone="bad" title="Timeline tidak bisa dimuat">{error}</Notice>;
  if (!data) return <div className={d.loading}><Spinner label="Memuat" /> Menghitung timeline dari file export…</div>;

  const pembagi = data.basis[basis];
  const bulan = data.minggu.filter((_, i) => i % 4 === 0).map((m) => m.bulan);

  return (
    <div className={d.page}>
      <div className={d.head}>
        <div>
          <h1>Timeline</h1>
          <p className={s.sub}>Kumulatif sampai hari Minggu tiap pekan · data per {new Date(data.data_per).toLocaleString("id-ID",
            { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</p>
        </div>
        <div className={s.pilih} role="group" aria-label="Pembagi persen">
          <span>Persen dari sekolah</span>
          {BASIS.map((b) => (
            <button key={b.kode} type="button" aria-pressed={basis === b.kode} onClick={() => setBasis(b.kode)}>{b.label}</button>
          ))}
        </div>
      </div>

      <section className={d.card}>
        <div className={d.cardHead}>
          <h2>Timeline per komponen LK</h2>
          <span>Pembagi: {BASIS.find((b) => b.kode === basis)!.label} · arahkan kursor ke grafik untuk detail</span>
        </div>
        <div className={s.kartu}>
        <div className={s.grid}>
          <div className={s.sudut}><b>Bulan</b><small>2026</small></div>
          {bulan.map((b) => <div key={b} className={s.bulan}>{b}</div>)}
          <div className={s.sudut}><b>Minggu</b><small>Senin–Minggu · tgl Senin</small></div>
          {data.minggu.map((m) => (
            <div key={m.mulai} className={s.minggu} title={`${tgl(m.mulai)} – ${tgl(m.selesai)}`}>
              {m.w}<small>{tgl(m.mulai)}</small>
            </div>
          ))}

          {data.komponen.map((k) => {
            const p = k[basis].map((v, i) => (v == null || !pembagi[i] ? null : (v / pembagi[i]!) * 100));
            const titik = p.map((v, i) => (v == null ? null : { x: ((i + 0.5) / 12) * 100, y: 100 - v, v, i })).filter((t) => t !== null);
            const akhir = titik[titik.length - 1];
            const h = hover?.kode === k.kode ? hover.i : null;
            return (
              <div key={k.kode} className={s.baris}>
                <div className={s.label}>
                  <b>{k.label}</b>
                  {akhir && <span>{persen(akhir.v)} · {angka(k[basis][akhir.i]!)} sekolah</span>}
                </div>
                <div className={s.plot} onMouseLeave={() => setHover(null)}>
                  {h !== null && <span className={s.sorot} style={{ left: `${(h / 12) * 100}%` }} />}
                  <span className={s.y100}>100%</span><span className={s.y0}>0</span>
                  <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                    <line x1="0" x2="100" y1="50" y2="50" className={s.bantu} />
                    <polyline points={titik.map((t) => `${t.x},${t.y}`).join(" ")} className={s.garis} />
                  </svg>
                  {titik.map((t) => (
                    <span key={t.i} className={`${s.titik} ${h === t.i ? s.aktif : ""}`}
                      style={{ left: `${t.x}%`, top: `calc(18px + (100% - 32px) * ${t.y / 100})` }}>
                      <em>{persen(t.v)}</em>
                    </span>
                  ))}
                  {titik.map((t) => (
                    <span key={t.i} className={s.zona} style={{ left: `${(t.i / 12) * 100}%` }} tabIndex={0}
                      aria-label={`${data.minggu[t.i].bulan} ${data.minggu[t.i].w}: ${persen(t.v)}`}
                      onMouseEnter={() => setHover({ kode: k.kode, i: t.i })} onFocus={() => setHover({ kode: k.kode, i: t.i })}
                      onBlur={() => setHover(null)} />
                  ))}
                  {h !== null && p[h] != null && (() => {
                    const m = data.minggu[h];
                    const v = k[basis][h]!, lalu = h > 0 ? k[basis][h - 1] : null;
                    const poin = h > 0 && p[h - 1] != null ? p[h]! - p[h - 1]! : null;
                    const kanan = h < 6;
                    return (
                      <div className={s.tip} role="tooltip"
                        style={kanan ? { left: `calc(${((h + 1) / 12) * 100}% + 6px)` } : { right: `calc(${((12 - h) / 12) * 100}% + 6px)` }}>
                        <header>{m.bulan} {m.w} · {tgl(m.mulai)} – {tgl(m.selesai)}</header>
                        <div className={s.tipUtama}>
                          <b>{persen(p[h]!)}</b>
                          {poin !== null && Math.abs(poin) >= 0.05 && (
                            <span className={poin > 0 ? l.naikT : l.turunT}>{poin > 0 ? "▲" : "▼"} {Math.abs(poin).toFixed(1).replace(".", ",")} poin</span>
                          )}
                        </div>
                        <dl>
                          <dt>{k.label}</dt><dd>{angka(v)} sekolah</dd>
                          <dt>Pembagi ({BASIS.find((b) => b.kode === basis)!.label.toLowerCase().replace("pks", "PKS")})</dt><dd>{angka(pembagi[h]!)}</dd>
                          <dt>Belum</dt><dd>{angka(pembagi[h]! - v)}</dd>
                          {lalu != null && <><dt>Tambah minggu ini</dt><dd>+{angka(v - lalu)}</dd></>}
                        </dl>
                        {poin !== null && poin < 0 && pembagi[h - 1] != null && pembagi[h]! > pembagi[h - 1]! && (
                          <p>Persen turun karena pembagi naik {angka(pembagi[h]! - pembagi[h - 1]!)} sekolah.</p>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </div>
            );
          })}

          <div className={s.label}><b>Pembagi</b><span>{BASIS.find((b) => b.kode === basis)!.label}</span></div>
          {pembagi.map((v, i) => <div key={i} className={s.pembagi}>{v == null ? "–" : angka(v)}</div>)}

          <div className={`${s.sudut} ${s.intHead}`}><b>Intervensi</b><small>seret baris untuk menukar</small></div>
          <div className={s.intJudul}>Kegiatan yang berjalan tiap minggu</div>
          {urut.map((kode, idx) => {
            const a = AKSI.find((x) => x.kode === kode)!;
            const per = data.intervensi?.[kode];
            return (
              <div key={kode} className={`${s.baris} ${seret === kode ? s.diseret : ""}`}
                onDragOver={(e) => { if (seret) e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); if (seret && seret !== kode) pindah(seret, idx); setSeret(null); }}>
                <div className={s.intLabel} draggable onDragStart={(e) => { setSeret(kode); e.dataTransfer.effectAllowed = "move"; }}
                  onDragEnd={() => setSeret(null)}>
                  <span className={s.pegangan} aria-hidden="true">⋮⋮</span>
                  <span className={s.intNama}>{a.label}{!per && <small>Belum ada data</small>}</span>
                  <span className={s.geser}>
                    <button type="button" disabled={idx === 0} onClick={() => pindah(kode, idx - 1)} aria-label={`Naikkan ${a.label}`}>▲</button>
                    <button type="button" disabled={idx === urut.length - 1} onClick={() => pindah(kode, idx + 1)} aria-label={`Turunkan ${a.label}`}>▼</button>
                  </span>
                </div>
                {data.minggu.map((m, i) => {
                  const isi = per?.[i] ?? [];
                  return (
                    <div key={m.mulai} className={`${s.intSel} ${per ? "" : s.intKosong}`}>
                      {isi.length > 0 && (
                        <span className={s.cek} tabIndex={0}
                          title={isi.map((x) => `${x.nama} · ${tgl(x.mulai)} – ${tgl(x.selesai)}`).join("\n")}>
                          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>
                          <small>{isi.map((x) => x.kode).join(", ")}</small>
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        </div>
        <details className={l.wajib}>
          <summary>Lihat sebagai tabel</summary>
          <div className={l.tabelWrap}>
            <table className={l.tabel}>
              <thead><tr><th>Komponen</th>{data.minggu.map((m) => <th key={m.mulai}>{m.bulan} {m.w}</th>)}</tr></thead>
              <tbody>
                {data.komponen.map((k) => (
                  <tr key={k.kode}>
                    <td>{k.label}</td>
                    {k[basis].map((v, i) => (
                      <td key={i} className={l.num}>
                        {v == null || !pembagi[i] ? "–" : `${angka(v)} / ${angka(pembagi[i]!)} (${persen((v / pembagi[i]!) * 100)})`}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <p className={s.catatan}>
        Satu pekan = Senin–Minggu; W1 = Senin pertama tiap bulan. Tanggal per sekolah diambil yang paling awal dari semua file
        export ({data.file.length} file), jadi kirim ulang setelah revisi tidak menggeser minggunya. Laporan Mingguan,
        Bulanan, BKU, BPP, dan progres fisik tidak punya riwayat tanggal di export, jadi tidak ditampilkan.
      </p>
    </div>
  );
}
