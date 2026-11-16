"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  KUADRAN, NAMA_SUMBER, PILIHAN_HARI, belumMulai, berlangsung, fmt, hrefKelompok, kuadranDari, labelBimtek, pct, poin,
  rentang, teksTahap, tgl, tglPanjang, warnaDari, type Kuadran,
  type Kelompok, type Rekap,
} from "./BimtekView";
import { DaftarNasional, barisNasional } from "./BimtekDaftar";
import { Tip } from "./Tip";
import b from "./bimtekRekap.module.css";

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
  return { judul: "Bimtek Pelaporan", sub: awal && akhir ? `Rekap nasional · ${tgl(awal.mulai)} – ${tglTahun(akhir.selesai)}` : "Rekap nasional" };
}

export function BimtekNasional({ r }: { r: Rekap }) {
  const kel = r.kelompok;
  const jalan = kel.filter((k) => k.tahap !== "akan datang");
  const total = kel.reduce((n, k) => n + pesertaDari(k), 0);
  const sudah = jalan.reduce((n, k) => n + pesertaDari(k), 0);
  // rata-rata tertimbang (jumlah sekolah wajib 50%) dari bimtek yang sudah selesai diukur
  const terukur = kel.map((k) => ({ k, u: ukur50(k) })).filter(({ u }) => u.naik !== null);
  const bobot = terukur.reduce((n, { u }) => n + u.wajib, 0);
  const rata = (f: (u: ReturnType<typeof ukur50>) => number) =>
    bobot ? terukur.reduce((n, { u }) => n + f(u) * u.wajib, 0) / bobot : null;
  const naikRata = rata((u) => u.naik!);
  const nantiKel = kel.filter((k) => k.tahap === "akan datang");
  const rentangKode = (ks: Kelompok[]) => (ks.length ? `Bimtek ${ks[0].kode.slice(1)}${ks.length > 1 ? `–${ks.at(-1)!.kode.slice(1)}` : ""}` : "");
  const [pilih, setPilih] = useState("");
  const [batas, setBatas] = useState(7);
  const [kuadran, setKuadran] = useState<Kuadran | "">("");
  const kelSF = kel.filter((k) => !belumMulai(k) && (k.sekolah_baris?.length ?? 0) > 0);
  const rows = useMemo(() => barisNasional(r, kelSF.filter((k) => !pilih || k.kode === pilih), batas),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [r, pilih, batas]);

  return (
    <div className={b.halaman}>

      <dl className={`${b.strip} ${b.stripNas}`}>
        <div>
          <dt>Jumlah bimtek</dt>
          <dd>{kel.length}</dd>
          <p className={b.stripKet}>{jalan.length} sudah berjalan · {kel.length - jalan.length} akan datang</p>
        </div>
        <div>
          <dt>Total sekolah bimtek</dt>
          <dd>{fmt(total)}</dd>
          <p className={b.stripKet}>{pct((total / Math.max(1, r.sekolah_total)) * 100)} dari {fmt(r.sekolah_total)} sekolah binaan</p>
        </div>
        <div>
          <dt>Sudah dibimtek</dt>
          <dd>{fmt(sudah)}</dd>
          <p className={b.stripKet}>{jalan.length ? rentangKode(jalan) : "belum ada"}
            {total - sudah > 0 && <> · {fmt(total - sudah)} menunggu {rentangKode(nantiKel)}</>}</p>
        </div>
        <div className={b.stripSorot}>
          <dt><Tip kanan isi={<>Rata-rata kenaikan persen sekolah yang sudah mengirim Laporan 50%, dari sehari sebelum bimtek
            sampai hari terakhir bimtek, ditimbang jumlah sekolah tiap bimtek.</>}>Kenaikan Lap. 50% selama bimtek</Tip></dt>
          <dd>{naikRata === null ? "–" : `${poin(naikRata)} poin`}</dd>
          <p className={b.stripKet}>{naikRata === null ? "menunggu bimtek selesai"
            : `rata-rata ${rentangKode(terukur.map((x) => x.k))}, sebelum → hari terakhir`}</p>
        </div>
      </dl>

      <ol className={b.kartuNas} aria-label="Bimtek">
        {kel.map((k) => <KartuBimtek key={k.kode} r={r} k={k} />)}
      </ol>

      <KurvaNasional r={r} />
      <Jadwal r={r} />
      <MatriksSF r={r} kel={kelSF} pilih={pilih} setPilih={setPilih} batas={batas} setBatas={setBatas}
        kuadran={kuadran} setKuadran={setKuadran} />
      {r.fasil_tunggu && kelSF.length > 0 && <DaftarNasional r={r} rows={rows} kuadran={kuadran} setKuadran={setKuadran} batas={batas} />}
    </div>
  );
}

/* ---------- kartu per bimtek ---------- */
function KartuBimtek({ r, k }: { r: Rekap; k: Kelompok }) {
  const u = ukur50(k);
  const nanti = k.tahap === "akan datang" || u.akhir === null;
  const langsung = berlangsung(k);
  if (belumMulai(k)) {
    return (
      <li className={`${b.kNas} ${b.kNasNanti} ${b.kNasSegera}`} style={{ ["--w" as string]: warnaDari(k.kode) }}>
        <div className={b.kNasJudul}>
          <b>{labelBimtek(k.kode)}</b>
          <span>{rentang(k.mulai, k.selesai)}</span>
        </div>
        <p className={b.kNasSekolah}>{fmt(pesertaDari(k))} sekolah</p>
        <p className={b.comingSoon}>Coming soon</p>
      </li>
    );
  }
  return (
    <li className={`${b.kNas} ${nanti ? b.kNasNanti : ""}`} style={{ ["--w" as string]: warnaDari(k.kode) }}>
      <Link href={hrefKelompok(k.kode)} className={b.kartuTautan} aria-label={`Detail ${labelBimtek(k.kode)}`} />
      <div className={b.kNasJudul}>
        <b>{labelBimtek(k.kode)}</b>
        <span>{rentang(k.mulai, k.selesai)}{langsung ? "" : ` · ${teksTahap(k.tahap)}`}</span>
        {langsung && <em className={b.chipSegera}>Berlangsung</em>}
      </div>
      <p className={b.kNasSekolah}>{fmt(pesertaDari(k))} sekolah</p>
      <div className={b.kNasUkur}>
        <span>Lap. 50% terkirim</span>
        {nanti ? (
          <b className={b.kNasAngka}>{pct(u.awal)}<small> per {tgl(r.data_terbaru.waktu)}</small></b>
        ) : (
          <b className={b.kNasAngka}>{pct(u.awal)} <i>→</i> {pct(u.akhir)}</b>
        )}
        <span className={b.kNasRiil}>
          {nanti ? <>{fmt(u.nAwal ?? 0)} dari {fmt(u.wajib)} sekolah</>
            : <>{fmt(u.nAwal ?? 0)} → <b>{fmt(u.nAkhir ?? 0)}</b> dari {fmt(u.wajib)} sekolah</>}
        </span>
        <span className={b.batangSS} aria-hidden="true">
          {!nanti && <span className={b.batangSesudah} style={{ width: `${u.akhir ?? 0}%` }} />}
          <span className={nanti ? b.batangSaatIni : b.batangSebelum} style={{ width: `${u.awal ?? 0}%` }} />
        </span>
      </div>
      {nanti ? (
        <p className={b.kNasBawah}>{langsung ? "Kondisi awal; terbarui tiap cutoff" : `Kenaikan muncul setelah ${tgl(k.selesai)}`}</p>
      ) : (
        <p className={b.kNasBawah}>
          <span><b className={(u.naik ?? 0) >= 0 ? b.naik : b.turun}>{poin(u.naik)} poin</b> selama bimtek</span>
          <small>belum dibimtek {poin(u.naikLain)} · efek <b>{poin(u.efek)}</b></small>
        </p>
      )}
    </li>
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
            const sebelum = a > 0 ? a - 1 : -1;
            return (
              <g key={k.kode}>
                <polyline points={garis(s!.nilai, 0, akhir)} fill="none" stroke={w} strokeWidth={1.5} opacity={0.3} />
                {a >= 0 && (
                  <polyline points={garis(s!.nilai, Math.max(0, sebelum), z >= 0 ? z : akhir)} fill="none" stroke={w} strokeWidth={3.5}
                    strokeLinejoin="round" strokeLinecap="round" />
                )}
                {[sebelum, z].filter((i) => i >= 0 && s!.nilai[i] !== null).map((i) => (
                  <circle key={i} cx={x(i)} cy={y(s!.nilai[i] as number)} r={4.5} fill={w} className={b.titik} />
                ))}
              </g>
            );
          })}
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={ATAS} y2={ATAS + tinggi} className={b.silang} />}
        </svg>
        {hover !== null && (
          <div className={`${b.tip} ${x(hover) > W * 0.55 ? b.tipKiri : b.tipKanan}`} style={{ left: `${(x(hover) / W) * 100}%` }} role="status">
            <b>{tglPanjang(t[hover])}</b>
            {seri.map(({ k, s }) => (
              <span key={k.kode}><i style={{ background: warnaDari(k.kode) }} />{labelBimtek(k.kode)}<em>{pct(s!.nilai[hover])}</em></span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/* ---------- tabel: tanggal & angka sebelum / sesudah ---------- */
function Jadwal({ r }: { r: Rekap }) {
  const router = useRouter();
  const dataAkhir = new Date(r.data_terbaru.waktu);
  return (
    <section className={b.panel} aria-labelledby="h-jadwal">
      <div className={b.panelHead}>
        <h2 id="h-jadwal" className={b.h2}>
          <Tip isi={<>Sebelum = akhir hari sebelum bimtek mulai. Sesudah = akhir hari terakhir bimtek. Angka = persen sekolah yang
            sudah mengirim Laporan 50% (dari yang sudah jatuh tempo), dihitung dari tanggal kirim di export aplikasi. Belum dibimtek =
            sekolah yang belum ikut bimtek saat itu (peserta bimtek berikutnya dan sekolah di luar daftar), diukur di tanggal
            yang sama. Efek bimtek = kenaikan peserta dikurangi kenaikan yang belum dibimtek.</>}>Data per bimtek</Tip>
        </h2>
      </div>
      <div className={b.gulir}>
        <table className={`${b.tabel} ${b.tabelJadwal}`}>
          <thead>
            <tr>
              <th>Bimtek</th><th>Status</th><th className={b.kanan}><Tip isi={<>Peserta di daftar. Persen Laporan 50% dihitung dari
                peserta yang laporannya sudah jatuh tempo (angka “dari … sekolah” di kartu).</>}>Sekolah</Tip></th>
              <th>Sebelum</th><th>Sesudah</th><th className={b.kanan}>Kenaikan</th>
              <th className={b.kanan}>Belum dibimtek</th><th className={b.kanan}>Efek bimtek</th>
            </tr>
          </thead>
          <tbody>
            {r.kelompok.map((k) => {
              const u = ukur50(k), adaSebelum = new Date(k.t0) <= dataAkhir, adaSesudah = u.akhir !== null;
              return (
                <tr key={k.kode} className={b.barisKlik} style={{ ["--w" as string]: warnaDari(k.kode) }}
                  onClick={() => router.push(hrefKelompok(k.kode))}>
                  <td>
                    <Link href={hrefKelompok(k.kode)} className={b.selBimtek} onClick={(e) => e.stopPropagation()}>
                      <span className={b.garisWarna} aria-hidden="true" />
                      <span><b>{labelBimtek(k.kode)}</b><small>{rentang(k.mulai, k.selesai)} {k.selesai.slice(0, 4)}</small></span>
                    </Link>
                  </td>
                  <td><span className={`${b.tahap} ${b[`tahap_${(berlangsung(k) ? "berjalan" : k.tahap).replace(" ", "_")}`]}`}>
                    {berlangsung(k) ? "Berlangsung" : teksTahap(k.tahap)}</span></td>
                  <td className={b.kanan}><b className={b.angkaTabel}>{fmt(pesertaDari(k))}</b></td>
                  <td>
                    <span className={`${b.tanggalSel} ${adaSebelum ? "" : b.tanggalKosong}`}>
                      <b>{pct(u.awal)} <span className={b.riil}>{fmt(u.nAwal ?? 0)} sekolah</span></b>
                      <small>{adaSebelum ? tglTahun(k.t0) : `per ${tgl(r.data_terbaru.waktu)} (sementara)`}</small>
                    </span>
                  </td>
                  <td>
                    <span className={`${b.tanggalSel} ${adaSesudah ? "" : b.tanggalKosong}`}>
                      <b>{adaSesudah ? <>{pct(u.akhir)} <span className={b.riil}>{fmt(u.nAkhir ?? 0)} sekolah</span></> : "–"}</b><small>{adaSesudah ? tglTahun(k.selesai) : `diukur ${tglTahun(k.selesai)}`}</small>
                    </span>
                  </td>
                  <td className={b.kanan}>{u.naik === null ? <span className={b.redup}>–</span>
                    : <span className={b.tanggalSel}><b className={`${b.angkaTabel} ${u.naik >= 0 ? b.naik : b.turun}`}>{poin(u.naik)} poin</b>
                      {u.nNaik !== null && <small>{u.nNaik >= 0 ? "+" : "−"}{fmt(Math.abs(u.nNaik))} sekolah</small>}</span>}</td>
                  <td className={b.kanan}>{u.naikLain === null ? <span className={b.redup}>–</span>
                    : <span className={b.angkaTabel}>{poin(u.naikLain)}</span>}</td>
                  <td className={b.kanan}>{u.efek === null ? <span className={b.redup}>–</span>
                    : <b className={`${b.angkaTabel} ${b.efek}`}>{poin(u.efek)} poin</b>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
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
  const kol = r.kolom_sekolah ?? [], iF = kol.indexOf("fasil"), iZ = kol.indexOf("akhir_kode");
  const i50 = (r.komponen_urut ?? []).indexOf("l50");
  if (!r.fasil_tunggu || iF < 0 || iZ < 0 || !kel.length) return null;
  const hitungK = (k: Kelompok) => {
    const j: Record<Kuadran, number> = { keduanya: 0, sekolah: 0, fasil: 0, aman: 0 };
    for (const x of k.sekolah_baris ?? []) j[kuadranDari(r, String(x[iF] ?? ""), String(x[iZ] ?? "")[i50], batas)] += 1;
    return j;
  };
  const perBimtek = kel.map((k) => ({ k, j: hitungK(k) }));
  const jumlah: Record<Kuadran, number> = { keduanya: 0, sekolah: 0, fasil: 0, aman: 0 };
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
        <small>{pct(total ? (jumlah[q] / total) * 100 : null)} sekolah</small>
      </div>
    );
  };
  return (
    <section className={b.panel} aria-labelledby="h-msf">
      <div className={b.panelHead}>
        <h2 id="h-msf" className={b.h2}>
          <Tip isi={<>Sekolah bermasalah = belum kirim Lap. 50% padahal sudah wajib. Fasil bermasalah = ada Lap. 50% sekolah
            binaannya yang menunggu reviu lebih lama dari batas hari. Daftar sekolahnya ada di halaman tiap bimtek.</>}>
            Sekolah × fasil</Tip>
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
      <div className={b.matriksSF}>
        <span />
        <span className={b.mKepala}>Fasil aman</span>
        <span className={b.mKepala}>Fasil bermasalah</span>
        <span className={b.mSamping}>Sekolah aman</span>
        {sel("aman")}
        {sel("fasil")}
        <span className={b.mSamping}>Sekolah bermasalah</span>
        {sel("sekolah")}
        {sel("keduanya")}
      </div>
      <div className={b.gulir}>
        <table className={`${b.tabel} ${b.tabelKuadran}`}>
          <thead>
            <tr>
              <th>Bimtek</th>
              {(["keduanya", "sekolah", "fasil", "aman"] as Kuadran[]).map((q) => (
                <th key={q} className={b.angka}><span className={`${b.kq} ${b[`kq_${q}`]}`}><i />{KUADRAN.find((x) => x.k === q)!.label}</span></th>
              ))}
              <th className={b.angka}>Sekolah</th>
            </tr>
          </thead>
          <tbody>
            {perBimtek.map(({ k, j }) => {
              const n = j.keduanya + j.sekolah + j.fasil + j.aman;
              return (
                <tr key={k.kode} className={pilih === k.kode ? b.barisPilih : undefined}>
                  <td><Link href={hrefKelompok(k.kode)} className={b.tautanBiasa}>{labelBimtek(k.kode)}</Link></td>
                  {(["keduanya", "sekolah", "fasil", "aman"] as Kuadran[]).map((q) => (
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

