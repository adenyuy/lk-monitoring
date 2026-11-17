"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  KUADRAN, NAMA_SUMBER, PILIHAN_HARI, belumMulai, fmt, hrefKelompok, kuadranDari, labelBimtek, pct, poin,
  rentang, tgl, tglPanjang, warnaDari, type Kuadran,
  type Kelompok, type Rekap,
} from "./BimtekView";
import { DaftarNasional, barisNasional } from "./BimtekDaftar";
import { Tip } from "./Tip";
import b from "./bimtekRekap.module.css";
import s from "./online.module.css";

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
/** "5 Nov 2026, 22.31" */
export const tglJam = (iso: string) => {
  const d = new Date(iso);
  return `${d.getDate()} ${BULAN[d.getMonth()]} ${d.getFullYear()}${iso.length > 10 ? `, ${iso.slice(11, 16).replace(":", ".")}` : ""}`;
};
const tglTahun = (iso: string) => `${tgl(iso)} ${iso.slice(0, 4)}`;

/** Kapan data "sebelum" dan "sesudah" semua komponen diambil (halaman detail). */
export function periodeData(r: Rekap, k: Kelompok) {
  const nanti = k.tahap === "akan datang";
  const sebelum = k.awal
    ? { tanggal: tglJam(k.awal.waktu), ket: NAMA_SUMBER[k.awal.jenis] ?? k.awal.jenis }
    : !nanti
      ? { tanggal: tglTahun(k.t0), ket: "dihitung dari tanggal kirim Lap. 50%" }
      : { tanggal: "Belum tersimpan", ket: `ambil sebelum ${tgl(k.mulai)}`, kosong: true };
  const sesudah = nanti
    ? { tanggal: "Belum ada", ket: `setelah ${tgl(k.selesai)}`, kosong: true }
    : { tanggal: tglJam(r.data_terbaru.waktu), ket: "export aplikasi" };
  return { sebelum, sesudah };
}

/**
 * Lap. 50% terkirim: H-1 sebelum bimtek -> hari terakhir bimtek, peserta dan pembanding (sekolah yang belum dibimtek saat
 * itu) di tanggal yang sama. Efek = kenaikan peserta - kenaikan pembanding.
 */
export function ukur50(k: Kelompok) {
  const l = k.l50, t1 = l.t1;
  const naik = t1 && t1.pct !== null && l.awal !== null ? t1.pct - l.awal : null;
  const naikLain = t1 && t1.pct_banding !== null && l.awal_banding !== null ? t1.pct_banding - l.awal_banding : null;
  // jumlah sekolah riil (rekap lama tanpa n: dihitung balik dari persen)
  const dariPct = (v: number | null) => (v === null ? null : Math.round((v / 100) * l.wajib));
  const nAwal = l.n_awal ?? dariPct(l.awal), nAkhir = t1 ? (t1.n ?? dariPct(t1.pct)) : null;
  return {
    awal: l.awal, akhir: t1?.pct ?? null, naik, naikLain,
    efek: naik !== null && naikLain !== null ? naik - naikLain : null, wajib: l.wajib,
    nAwal, nAkhir, nNaik: nAwal !== null && nAkhir !== null ? nAkhir - nAwal : null,
  };
}

const pesertaDari = (k: Kelompok) => k.peserta_daftar ?? k.sekolah;

/** Halaman awal Bimtek: rekap nasional seluruh bimtek. */
/** Judul & subjudul halaman nasional (dipakai kerangka halaman). */
export function judulNasional(r: Rekap) {
  const awal = r.kelompok[0], akhir = r.kelompok.at(-1);
  return { judul: "Bimtek Pelaporan", chip: awal && akhir ? ["Rekap nasional", `${tgl(awal.mulai)} – ${tglTahun(akhir.selesai)}`] : ["Rekap nasional"] };
}

export function BimtekNasional({ r }: { r: Rekap }) {
  const kel = r.kelompok;
  const jalan = kel.filter((k) => k.tahap !== "akan datang");
  const total = kel.reduce((n, k) => n + pesertaDari(k), 0);
  const sudah = jalan.reduce((n, k) => n + pesertaDari(k), 0);
  const [pilih, setPilih] = useState("");
  const [batas, setBatas] = useState(7);
  const [kuadran, setKuadran] = useState<Kuadran | "">("");
  const kelSF = kel.filter((k) => !belumMulai(k) && (k.sekolah_baris?.length ?? 0) > 0);
  const rows = useMemo(() => barisNasional(r, kelSF.filter((k) => !pilih || k.kode === pilih), batas),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [r, pilih, batas]);

  return (
    <div className={b.halaman}>

      <section className={s.kpi} aria-label="Ringkasan bimtek">
        <div><span>Semesta</span><b>{fmt(r.sekolah_total)}</b><small>sekolah binaan</small></div>
        <div><span>Jumlah bimtek</span><b>{kel.length}</b></div>
        <div><span>Akan dibimtek</span><b>{fmt(total)}</b><small>sekolah</small></div>
        <div><span>Sudah dibimtek</span><b>{fmt(sudah)}</b><small>sekolah</small></div>
      </section>

      <Jadwal r={r} />
      <KurvaNasional r={r} />
      <MatriksSF r={r} kel={kelSF} pilih={pilih} setPilih={setPilih} batas={batas} setBatas={setBatas}
        kuadran={kuadran} setKuadran={setKuadran} />
      {kelSF.length > 0 && <DaftarNasional r={r} rows={rows} kuadran={kuadran} setKuadran={setKuadran} batas={batas} />}
    </div>
  );
}

/* ---------- grafik semua bimtek ---------- */
function KurvaNasional({ r }: { r: Rekap }) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const wadah = useRef<HTMLDivElement>(null);
  const [lebarWadah, setLebarWadah] = useState(960);
  useEffect(() => {
    const el = wadah.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setLebarWadah(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const t = r.kurva.tanggal;
  const seri = r.kelompok.map((k) => ({ k, s: r.kurva.seri.find((x) => x.kode === k.kode) })).filter((x) => x.s);
  if (!t.length || !seri.length) return null;
  const sempit = lebarWadah < 600;
  const W = Math.max(320, lebarWadah), H = sempit ? 260 : 320, KIRI = 40, KANAN = sempit ? 44 : 64, ATAS = 30, BAWAH = 40;
  const lebar = W - KIRI - KANAN, tinggi = H - ATAS - BAWAH, akhir = t.length - 1;
  const idx = (iso: string) => t.indexOf(iso.slice(0, 10));
  // garis tiap bimtek baru digambar sejak sehari sebelum bimtek itu mulai (sebelumnya sekolahnya belum dibimtek)
  const dariHari = (k: Kelompok) => { const a = idx(k.mulai); return a < 0 ? (k.mulai < t[0] ? 0 : null) : Math.max(0, a - 1); };
  const x = (i: number) => KIRI + (i / Math.max(1, akhir)) * lebar;
  const y = (v: number) => ATAS + (1 - v / 100) * tinggi;
  const garis = (v: (number | null)[], dari: number, sampai: number) =>
    v.map((n, i) => (n === null || i < dari || i > sampai ? null : `${x(i)},${y(n)}`)).filter(Boolean).join(" ");
  const minggu = t.map((d, i) => ({ d, i })).filter(({ d }) => new Date(d).getDay() === 1);
  const sumbu = sempit && minggu.length > 4 ? minggu.filter((_, j) => j % 2 === 0) : minggu;
  const gerak = (e: React.PointerEvent<SVGSVGElement>) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const i = Math.round(((((e.clientX - box.left) / box.width) * W - KIRI) / lebar) * akhir);
    setHover(i >= 0 && i <= akhir ? i : null);
  };
  return (
    <section className={b.panel} aria-labelledby="h-kurva-nas">
      <div className={b.panelHead}>
        <h2 id="h-kurva-nas" className={b.h2}>
          <Tip isi={<>Persen sekolah yang Laporan 50%-nya jatuh tempo dan sudah dikirim, per hari. Area berwarna = minggu bimtek;
            garis tebal = selama bimtek. Dihitung dari tanggal kirim di export aplikasi, jadi bisa sedikit lebih rendah dari
            aslinya karena kirim ulang tercatat dengan tanggal terbaru.</>}>Laporan 50% per hari</Tip>
        </h2>
        <ul className={b.legenda}>
          {seri.map(({ k }) => (
            <li key={k.kode}><span className={b.legendaStatis} style={{ ["--w" as string]: warnaDari(k.kode) }}><i />{labelBimtek(k.kode)}</span></li>
          ))}
        </ul>
      </div>
      <div className={b.kanvas} ref={wadah}>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" className={b.svg}
          aria-label="Persen sekolah yang sudah mengirim Laporan 50% per hari, per bimtek"
          onPointerMove={gerak} onPointerLeave={() => setHover(null)}>
          {seri.map(({ k }) => {
            const a = idx(k.mulai), z = idx(k.selesai);
            if (a < 0) return null;
            const zz = z >= 0 ? z : akhir;
            return (
              <g key={`band-${k.kode}`}>
                <rect x={x(a) - 3} y={ATAS} width={Math.max(6, x(zz) - x(a) + 6)} height={tinggi} fill={warnaDari(k.kode)} opacity={0.1} />
                <text x={(x(a) + x(zz)) / 2} y={ATAS - 10} textAnchor="middle" className={b.bandLabel}>{sempit ? k.kode : labelBimtek(k.kode)}</text>
              </g>
            );
          })}
          {[0, 50, 100].map((v) => (
            <g key={v}>
              <line x1={KIRI} x2={KIRI + lebar} y1={y(v)} y2={y(v)} className={v === 0 ? b.sumbuDasar : b.grid} />
              <text x={KIRI - 8} y={y(v) + 4} textAnchor="end" className={b.sumbu}>{v}%</text>
            </g>
          ))}
          {sumbu.map(({ d, i }) => <text key={d} x={x(i)} y={H - BAWAH + 18} textAnchor="middle" className={b.sumbu}>{tgl(d)}</text>)}
          {seri.map(({ k, s }) => {
            const a = idx(k.mulai), z = idx(k.selesai), w = warnaDari(k.kode);
            const sebelum = a > 0 ? a - 1 : -1, dari = dariHari(k);
            if (dari === null) return null;
            return (
              <g key={k.kode}>
                <polyline points={garis(s!.nilai, dari, akhir)} fill="none" stroke={w} strokeWidth={1.5} opacity={0.3} />
                {a >= 0 && (
                  <polyline points={garis(s!.nilai, Math.max(0, sebelum), z >= 0 ? z : akhir)} fill="none" stroke={w} strokeWidth={3.5}
                    strokeLinejoin="round" strokeLinecap="round" />
                )}
                {[sebelum, z].filter((i) => i >= 0 && s!.nilai[i] !== null).map((i) => (
                  <circle key={i} cx={x(i)} cy={y(s!.nilai[i] as number)} r={4.5} fill={w} className={b.titik} />
                ))}
                {(() => {
                  const naik = ukur50(k).naik;
                  if (naik === null || z < 0 || s!.nilai[z] === null) return null;
                  return <text x={x(z) - 8} y={y(s!.nilai[z] as number) - 12} textAnchor="end" fill={w} className={b.labelNaik}>{poin(naik)}%</text>;
                })()}
              </g>
            );
          })}
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={ATAS} y2={ATAS + tinggi} className={b.silang} />}
        </svg>
        {hover !== null && (
          <div className={`${b.tip} ${x(hover) > W * 0.55 ? b.tipKiri : b.tipKanan}`} style={{ left: `${(x(hover) / W) * 100}%` }} role="status">
            <b>{tglPanjang(t[hover])}</b>
            {seri.filter(({ k }) => { const d = dariHari(k); return d !== null && hover >= d; }).map(({ k, s }) => (
              <span key={k.kode}><i style={{ background: warnaDari(k.kode) }} />{labelBimtek(k.kode)}<em>{pct(s!.nilai[hover])}</em></span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/* ---------- data per bimtek: tabel (kiri), batang sebelum / sesudah (kanan), angkatan ---------- */
const WARNA_ANGKATAN = ["#cfe3f6", "#9cc6ec", "#5fa1dc", "#2f7cc4", "#1d5a96", "#123e6b"];

const WARNA_50 = { sebelum: "#0f6aa6", selama: "#5aaee3", belum: "#cfe3f6", bebas: "#eef1f5" };

function Jadwal({ r }: { r: Rekap }) {
  const router = useRouter();
  const [sorot, setSorot] = useState<string | null>(null);
  const baris = r.kelompok.map((k) => {
    const u = ukur50(k), sekolah = pesertaDari(k);
    return { k, u, sekolah, nanti: belumMulai(k), sebelum: u.nAwal ?? 0, sesudah: u.nAkhir };
  });
  const maks = Math.max(1, ...baris.map((x) => Math.max(x.sekolah, x.u.wajib)));
  const buka = (k: Kelompok) => (belumMulai(k) ? undefined : () => router.push(hrefKelompok(k.kode)));
  const belumAda = <span className={b.tagKosong}>Belum ada data</span>;
  return (
    <>
      <div className={b.duaKartu}>
        <section className={b.panel} aria-labelledby="h-jadwal">
          <div className={b.panelHead}><h2 id="h-jadwal" className={b.h2}>Data per bimtek</h2></div>
          <table className={`${b.tabel} ${b.tabelJadwal}`}>
            <thead><tr><th>Bimtek</th><th className={b.kanan}>Sekolah</th>
              <th className={b.kanan}><Tip kanan isi={<>Peserta yang Laporan 50%-nya sudah jatuh tempo.</>}>Jatuh tempo</Tip></th></tr></thead>
            <tbody>
              {baris.map(({ k, u, sekolah, nanti }) => (
                <tr key={k.kode} className={nanti ? undefined : b.barisKlik} onClick={buka(k)}>
                  <td><span className={b.selBimtek}><span><b>{labelBimtek(k.kode)}</b><small>{rentang(k.mulai, k.selesai)}</small></span></span></td>
                  <td className={b.kanan}><b className={b.angkaTabel}>{fmt(sekolah)}</b></td>
                  <td className={b.kanan}>{nanti ? belumAda : <span className={b.angkaTabel}>{fmt(u.wajib)}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className={b.panel} aria-labelledby="h-batang">
          <div className={b.panelHead}>
            <h2 id="h-batang" className={b.h2}>
              <Tip isi={<>Panjang batang = jumlah sekolah peserta. Sebelum = akhir hari sebelum bimtek mulai. Sesudah = akhir hari
                terakhir bimtek. Jatuh tempo = Laporan 50%-nya sudah harus dikirim. Dihitung dari tanggal kirim di export aplikasi.</>}>
                Lap. 50% sebelum & sesudah</Tip>
            </h2>
          </div>
          <ul className={`${b.legendaKotak} ${b.legendaBaris}`}>
            <li><i style={{ background: WARNA_50.sebelum }} />Terkirim sebelum</li>
            <li><i style={{ background: WARNA_50.selama }} />Selama bimtek</li>
            <li><i style={{ background: WARNA_50.belum }} />Jatuh tempo, belum kirim</li>
            <li><i style={{ background: WARNA_50.bebas }} />Belum jatuh tempo</li>
          </ul>
          <ul className={`${b.batangList} ${b.batangRapat}`}>
            {baris.map(({ k, u, sekolah, nanti, sebelum, sesudah }) => {
              const nama = labelBimtek(k.kode).replace(" ke-", " ");
              if (nanti) return <li key={k.kode}><span className={b.batangNama}>{nama}</span><span className={b.batangKosong}>{belumAda}</span></li>;
              const akhir = sesudah ?? sebelum, wajib = u.wajib;
              const lebar = (n: number) => `${(Math.max(0, n) / maks) * 100}%`;
              const persen = (n: number) => pct(wajib ? (n / wajib) * 100 : null);
              return (
                <li key={k.kode} onMouseEnter={() => setSorot(k.kode)} onMouseLeave={() => setSorot(null)}>
                  <span className={b.batangNama}>{nama}</span>
                  <span className={b.batangWadah}>
                    {/* angka sebelum di ujung bagian "sebelum" (di awal batang bila bagiannya terlalu pendek), sesudah di ujung bagian "selama" */}
                    <span className={b.batangAngka} style={sebelum / maks < 0.06 ? { left: 0 } : { left: lebar(sebelum), transform: "translateX(-100%)" }}>{fmt(sebelum)}</span>
                    {sesudah !== null && (sesudah - sebelum) / maks > 0.06 && (
                      <span className={b.batangAngka} style={{ left: lebar(sesudah), transform: "translateX(-100%)" }}>{fmt(sesudah)}</span>
                    )}
                    {(wajib - akhir) / maks > 0.08 && (
                      <span className={`${b.batangAngka} ${b.batangAngkaRedup}`} style={{ left: lebar(wajib), transform: "translateX(-100%)" }}>{fmt(wajib - akhir)}</span>
                    )}
                    <span className={b.batangJalur} aria-hidden="true">
                      <span style={{ width: lebar(sebelum), background: WARNA_50.sebelum }} />
                      <span style={{ width: lebar(akhir - sebelum), background: WARNA_50.selama }} />
                      <span style={{ width: lebar(wajib - akhir), background: WARNA_50.belum }} />
                      <span style={{ width: lebar(sekolah - wajib), background: WARNA_50.bebas }} />
                    </span>
                  </span>
                  <span className={b.batangTeks}>
                    <span><b>{sesudah === null ? persen(sebelum) : persen(sesudah)}</b> dari {fmt(wajib)} sekolah</span>
                  </span>
                  {sorot === k.kode && (
                    <div className={b.batangTip} role="status">
                      <b>{labelBimtek(k.kode)}</b>
                      <span><i style={{ background: WARNA_50.sebelum }} />Sebelum ({tglTahun(k.t0)})<em>{fmt(sebelum)} sekolah</em></span>
                      <span><i style={{ background: WARNA_50.selama }} />Sesudah ({tglTahun(k.selesai)})
                        <em>{sesudah === null ? "menunggu bimtek selesai" : `${fmt(sesudah)} sekolah`}</em></span>
                      {sesudah !== null && <span><i />Kenaikan<em>+{fmt(sesudah - sebelum)} sekolah · {poin(u.naik)}%</em></span>}
                      <span><i style={{ background: WARNA_50.belum }} />Jatuh tempo, belum kirim<em>{fmt(wajib - akhir)} sekolah</em></span>
                      <span><i style={{ background: WARNA_50.bebas }} />Belum jatuh tempo<em>{fmt(Math.max(0, sekolah - wajib))} sekolah</em></span>
                      <span><i />Jatuh tempo / peserta<em>{fmt(wajib)} / {fmt(sekolah)} sekolah</em></span>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      </div>
      <AngkatanBimtek r={r} />
    </>
  );
}

/** Sebaran angkatan sekolah peserta per bimtek (batang 100%). */
function AngkatanBimtek({ r }: { r: Rekap }) {
  const [sorot, setSorot] = useState<string | null>(null);
  const iA = (r.kolom_sekolah ?? []).indexOf("angkatan");
  const per = r.kelompok.map((k) => {
    const j = new Map<string, number>();
    for (const x of k.sekolah_baris ?? []) { const a = String(x[iA] ?? "") || "?"; j.set(a, (j.get(a) ?? 0) + 1); }
    return { k, j, n: (k.sekolah_baris ?? []).length };
  });
  const semua = [...new Set(per.flatMap(({ j }) => [...j.keys()]))].sort((a, z) => a.localeCompare(z, "id", { numeric: true }));
  const warna = (a: string) => (a === "?" ? "#e4e9ef" : WARNA_ANGKATAN[semua.indexOf(a) % WARNA_ANGKATAN.length]);
  const nama = (a: string) => (a === "?" ? "Tanpa angkatan" : /^\d+$/.test(a) ? `Angkatan ${a}` : a);
  return (
    <section className={b.panel} aria-labelledby="h-angkatan">
      <div className={b.panelHead}>
        <h2 id="h-angkatan" className={b.h2}>Angkatan per bimtek</h2>
        {iA >= 0 && <ul className={b.legendaKotak}>{semua.map((a) => <li key={a}><i style={{ background: warna(a) }} />{nama(a)}</li>)}</ul>}
      </div>
      {iA < 0 ? <p className={b.ket}>Angkatan muncul setelah rekap bimtek dihitung ulang.</p> : (
        <ul className={b.batangList}>
          {per.filter(({ n }) => n > 0).map(({ k, j, n }) => (
            <li key={k.kode} onMouseEnter={() => setSorot(k.kode)} onMouseLeave={() => setSorot(null)}>
              <span className={b.batangNama}>{labelBimtek(k.kode).replace(" ke-", " ")}</span>
              <span className={b.batangJalur}>
                {semua.filter((a) => j.has(a)).map((a) => (
                  <span key={a} style={{ width: `${(j.get(a)! / n) * 100}%`, background: warna(a) }} />
                ))}
              </span>
              <span className={b.batangTeks}>{fmt(n)} sekolah</span>
              {sorot === k.kode && (
                <div className={b.batangTip} role="status">
                  <b>{labelBimtek(k.kode)}</b>
                  {semua.filter((a) => j.has(a)).map((a) => (
                    <span key={a}><i style={{ background: warna(a) }} />{nama(a)}<em>{fmt(j.get(a)!)} · {pct((j.get(a)! / n) * 100)}</em></span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/* ---------- daftar hotel satu bimtek (halaman detail) ---------- */
export function KartuHotel({ k }: { k: Kelompok }) {
  const hotel = k.hotel ?? [], maks = Math.max(1, ...hotel.map((h) => h.sekolah));
  return (
    <article className={b.hotelKartu} style={{ ["--w" as string]: warnaDari(k.kode) }}>
      {hotel.length ? (
        <ul>
          {hotel.map((h) => (
            <li key={h.nama}>
              <span className={b.hotelNama}>{h.nama}<small>{h.region}</small></span>
              <span className={b.hotelJalur} aria-hidden="true"><span style={{ width: `${(h.sekolah / maks) * 100}%` }} /></span>
              <b>{fmt(h.sekolah)}</b>
            </li>
          ))}
        </ul>
      ) : <p className={b.hotelKosong}>Pemetaan hotel belum ada di master.</p>}
    </article>
  );
}

/* ---------- matriks sekolah x fasil ---------- */
function MatriksSF({ r, kel, pilih, setPilih, batas, setBatas, kuadran, setKuadran }: {
  r: Rekap; kel: Kelompok[]; pilih: string; setPilih: (k: string) => void; batas: number; setBatas: (n: number) => void;
  kuadran: Kuadran | ""; setKuadran: (q: Kuadran | "") => void;
}) {
  const kol = r.kolom_sekolah ?? [], iZ = kol.indexOf("akhir_kode"), iR = kol.indexOf("rev50"), iT = kol.indexOf("tunggu50");
  const i50 = (r.komponen_urut ?? []).indexOf("l50");
  if (iZ < 0 || !kel.length) return null;
  const hitungK = (k: Kelompok) => {
    const j: Record<Kuadran, number> = { sekolah: 0, fasil: 0, aman: 0 };
    for (const x of k.sekolah_baris ?? []) {
      const t = iT >= 0 ? x[iT] : null;
      j[kuadranDari(String(x[iZ] ?? "")[i50], iR >= 0 ? String(x[iR] ?? "") : "", typeof t === "number" ? t : null, batas)] += 1;
    }
    return j;
  };
  const perBimtek = kel.map((k) => ({ k, j: hitungK(k) }));
  const jumlah: Record<Kuadran, number> = { sekolah: 0, fasil: 0, aman: 0 };
  for (const { k, j } of perBimtek) {
    if (pilih && k.kode !== pilih) continue;
    for (const q of Object.keys(j) as Kuadran[]) jumlah[q] += j[q];
  }
  const total = Object.values(jumlah).reduce((a, z) => a + z, 0);
  const sel = (q: Kuadran) => {
    const info = KUADRAN.find((x) => x.k === q)!;
    return (
      <div className={`${b.mSel} ${b[`kq_${q}`]} ${kuadran === q ? b.mSelAktif : ""}`} role="button" tabIndex={0}
        aria-pressed={kuadran === q} onClick={() => setKuadran(kuadran === q ? "" : q)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setKuadran(kuadran === q ? "" : q); } }}>
        <span><Tip isi={info.ket}>{info.label}</Tip></span>
        <b>{fmt(jumlah[q])}</b>
        <small>sekolah · {pct(total ? (jumlah[q] / total) * 100 : null)}</small>
      </div>
    );
  };
  return (
    <section className={b.panel} aria-labelledby="h-msf">
      <div className={b.panelHead}>
        <h2 id="h-msf" className={b.h2}>
          <Tip isi={<>Semesta = semua peserta {pilih ? labelBimtek(pilih) : `bimtek yang sudah mulai (${kel.map((k) => labelBimtek(k.kode).replace(" ke-", " ")).join(", ")})`},
            bukan hanya yang jatuh tempo; total {fmt(total)} sekolah. Tiap sekolah masuk satu kelompok menurut Lap. 50%-nya
            sendiri: belum dikirim padahal jatuh tempo (sekolah bermasalah), sudah dikirim tapi menunggu reviu lebih lama dari
            batas hari (fasil bermasalah), atau aman.</>}>Status Lap. 50% per sekolah</Tip>
        </h2>
        <div className={b.saringBaris}>
          <select value={pilih} onChange={(e) => setPilih(e.target.value)} aria-label="Pilih bimtek">
            <option value="">Semua bimtek ({kel.map((k) => k.kode.slice(1)).join(", ")})</option>
            {kel.map((k) => <option key={k.kode} value={k.kode}>{labelBimtek(k.kode)}</option>)}
          </select>
          <select value={batas} onChange={(e) => setBatas(Number(e.target.value))} aria-label="Batas hari reviu">
            {PILIHAN_HARI.map((h) => <option key={h} value={h}>Reviu lewat {h} hari</option>)}
          </select>
        </div>
      </div>
      <div className={b.tigaStatus}>
        {sel("sekolah")}
        {sel("fasil")}
        {sel("aman")}
      </div>
      <div className={b.gulir}>
        <table className={`${b.tabel} ${b.tabelKuadran}`}>
          <thead>
            <tr>
              <th>Bimtek</th>
              {(["sekolah", "fasil", "aman"] as Kuadran[]).map((q) => (
                <th key={q} className={b.angka}><span className={`${b.kq} ${b[`kq_${q}`]}`}>{KUADRAN.find((x) => x.k === q)!.label}</span></th>
              ))}
              <th className={b.angka}>Sekolah</th>
            </tr>
          </thead>
          <tbody>
            {perBimtek.map(({ k, j }) => {
              const n = j.sekolah + j.fasil + j.aman;
              return (
                <tr key={k.kode} className={pilih === k.kode ? b.barisPilih : undefined}>
                  <td><Link href={hrefKelompok(k.kode)} className={b.tautanBiasa}>{labelBimtek(k.kode)}</Link></td>
                  {(["sekolah", "fasil", "aman"] as Kuadran[]).map((q) => (
                    <td key={q} className={b.angka}>{fmt(j[q])}<small>{pct(n ? (j[q] / n) * 100 : null)}</small></td>
                  ))}
                  <td className={b.angka}>{fmt(n)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

