"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { post } from "@/lib/api";
import { Button, Notice, Spinner } from "@/components/ui";
import {
  DataPer, KET_KOMP, KOMP_PENDEK, KUADRAN, PILIHAN_HARI, belumMulai, berlangsung, fmt, hariIni, hrefKelompok, kuadranDari,
  labelBimtek, pct, poin, rentang, selisihHari, tgl, tglPanjang, useRekap, warnaDari, type Kelompok, type Kuadran,
  type Rekap,
} from "./BimtekView";
import { BimtekNasional, judulNasional, tglJam } from "./BimtekNasional";
import { Tip } from "./Tip";
import b from "./bimtekRekap.module.css";

/* ---------- baris sekolah ---------- */
type Sekolah = { npsn: string; nama: string; pic: string; fasil: string; prov: string; kab: string; tgl50: string;
  kategori: string; progres_awal: number | null; progres: number | null; verif50: number | null;
  awal_kode: string; akhir_kode: string; hotel?: string; rev50?: string; tunggu50?: number | null; t1_kode?: string };
/** Perubahan satu komponen: naik (belum -> sudah), tetap (masih belum), sudah (sejak sebelum), turun, kosong. */
type Ubah = "naik" | "gerak" | "tetap" | "sudah" | "turun" | "kosong";
const UBAH: Record<Ubah, { simbol: string; label: string }> = {
  naik: { simbol: "↑", label: "Belum → sudah" },
  gerak: { simbol: "↗", label: "Ada kiriman baru, belum lengkap" },
  tetap: { simbol: "✕", label: "Masih belum" },
  sudah: { simbol: "✓", label: "Sudah sejak sebelum bimtek" },
  turun: { simbol: "↓", label: "Sempat sudah, lalu belum lagi (ada laporan baru jatuh tempo)" },
  kosong: { simbol: "·", label: "Belum jatuh tempo" },
};
const ubahDari = (a: string, z: string): Ubah =>
  a === "B" ? (z === "S" ? "naik" : z === "P" ? "gerak" : "tetap") : a === "S" ? (z === "B" ? "turun" : "sudah") : "kosong";

type Hasil = Sekolah & { ubah: Ubah[]; belumAwal: number; naik: number; tetap: number; efektif: number | null };
type Saring = "semua" | "belum_efektif" | "efektif" | "tanpa";
const SARING: { k: Saring; label: string; ket: string }[] = [
  { k: "belum_efektif", label: "Belum efektif", ket: "Ada komponen yang tertunggak sejak sebelum bimtek dan sampai sekarang tidak bergerak sama sekali." },
  { k: "efektif", label: "Efektif", ket: "Semua komponen yang tertunggak sebelum bimtek sudah bergerak (selesai, atau ada kiriman baru)." },
  { k: "tanpa", label: "Tanpa tunggakan", ket: "Sebelum bimtek tidak ada komponen yang tertunggak (sudah selesai atau belum jatuh tempo)." },
];
const PER_HAL = 25;
const HARI_SEBELUM = 14;
const TANPA_HOTEL = "(tanpa hotel)";
const KAT50: Record<string, string> = { sebelum: "Sebelum bimtek", saat: "Saat bimtek", sesudah: "Setelah bimtek", belum: "Belum kirim", belum_due: "Belum jatuh tempo" };
const REV50: Record<string, string> = { setuju: "Disetujui", tolak: "Dikembalikan", menunggu: "Menunggu reviu" };

function olah(r: Rekap, k: Kelompok, kodeAda: string[]): Hasil[] {
  const kol = r.kolom_sekolah ?? [];
  const urut = r.komponen_urut ?? [];
  const pakai = urut.map((x) => kodeAda.includes(x));
  return (k.sekolah_baris ?? []).map((x) => {
    const s = Object.fromEntries(kol.map((c, i) => [c, x[i]])) as unknown as Sekolah;
    const ubah = urut.map((_, i) => (pakai[i] ? ubahDari(s.awal_kode?.[i] ?? "-", s.akhir_kode?.[i] ?? "-") : "kosong"));
    const naik = ubah.filter((u) => u === "naik" || u === "gerak").length, tetap = ubah.filter((u) => u === "tetap").length;
    const belumAwal = naik + tetap;
    return { ...s, ubah, belumAwal, naik, tetap, efektif: belumAwal ? (naik / belumAwal) * 100 : null };
  });
}


/* ---------- tiga titik: sebelum, hari terakhir bimtek, hari ini ---------- */
type Titik3 = { due: number; d0: number; d1: number; d2: number; n0: number | null; n1: number | null; n2: number | null };
const jt = (c: string | undefined) => c === "S" || c === "B";
/**
 * Dari kode per sekolah. Komponen kirim: penyebut tetap = yang jatuh tempo sebelum bimtek. Komponen reviu: penyebut tiap
 * titik = sekolah yang sudah mengirim saat itu (reviu baru berlaku setelah laporan dikirim). n null = tidak ada data.
 */
function tigaTitik(rows: Sekolah[], i: number, adaSesudah: boolean, reviu: boolean): Titik3 {
  const kode = (s: Sekolah, t: 0 | 1 | 2) => (t === 0 ? s.awal_kode : t === 1 ? s.t1_kode : s.akhir_kode)?.[i];
  const due = rows.filter((s) => jt(s.awal_kode?.[i]));
  const dasar = (t: 0 | 1 | 2) => (reviu ? rows.filter((s) => jt(kode(s, t))) : due);
  const ada = (t: 0 | 1 | 2) => (t === 0 || adaSesudah) && rows.some((s) => (kode(s, t) ?? "-") !== "-");
  const n = (t: 0 | 1 | 2) => (ada(t) ? dasar(t).filter((s) => kode(s, t) === "S").length : null);
  const d = [0, 1, 2].map((t) => (ada(t as 0 | 1 | 2) ? dasar(t as 0 | 1 | 2).length : 0));
  return { due: reviu ? Math.max(...d) : due.length, d0: d[0], d1: d[1], d2: d[2], n0: n(0), n1: n(1), n2: n(2) };
}
const persen = (n: number | null, d: number) => (n === null || !d ? null : (n / d) * 100);
const adalahReviu = (kode: string) => kode.endsWith("_rev");
/** Komponen yang punya data di salah satu titik (reviu boleh tanpa data sebelum bimtek). */
function komponenAda(r: Rekap, k: Kelompok, rows: Sekolah[], adaSesudah: boolean) {
  const urut = r.komponen_urut ?? [];
  return (k.komponen ?? []).filter((c) => {
    if (!c.ada) return false;
    if (!adalahReviu(c.kode)) return !!c.due;
    const t = tigaTitik(rows, urut.indexOf(c.kode), adaSesudah, true);
    return t.d0 + t.d1 + t.d2 > 0;
  });
}

/** Halaman Bimtek: menu (Nasional + per bimtek) di atas. Tanpa kode = rekap nasional, dengan kode = detail bimtek itu. */
export function BimtekDetail({ kode }: { kode?: string }) {
  const { data, error, setError, muat } = useRekap();
  // selama hitung ulang berjalan di laptop admin: cek tiap 10 detik
  useEffect(() => {
    if (!data?.status.jalan) return;
    const t = setInterval(() => void muat(), 10000);
    return () => clearInterval(t);
  }, [data?.status.jalan, muat]);
  const hitung = async () => {
    try { await post("/api/dashboard/bimtek/hitung"); void muat(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  if (error && !data) return <Notice tone="bad" title="Rekap Bimtek tidak bisa dimuat">{error}</Notice>;
  if (!data) return <div className={b.memuat}><Spinner label="Memuat" /> Membaca rekap Bimtek…</div>;
  const r = data.rekap;
  const pilih = (kode ?? "").toUpperCase();
  const k = r?.kelompok.find((x) => x.kode.toUpperCase() === pilih);
  const onHitung = data.bisa_hitung ? () => void hitung() : undefined;
  const kepala = !r ? { judul: "Bimtek Pelaporan", chip: [] } : !pilih ? judulNasional(r)
    : { judul: labelBimtek(pilih), chip: k ? [`${rentang(k.mulai, k.selesai)} ${k.selesai.slice(0, 4)}`] : [] };
  const status = k && !belumMulai(k) ? (berlangsung(k) ? "berjalan" : k.tahap) : k ? "akan datang" : "";
  return (
    <div className={b.halaman}>
      <header className={b.kepalaBimtek}>
        <div className={b.judulBimtek}>
          {(kepala.chip.length > 0 || status) && (
            <p className="chips">
              {kepala.chip.map((c) => <span key={c} className="chip">{c}</span>)}
              {k && (status === "berjalan" || status === "akan datang") && <span className={`${b.status} ${b[`status_${status.replace(" ", "_")}`]}`}>
                {status === "berjalan" ? `Hari ke-${selisihHari(k.mulai, hariIni()) + 1} dari ${selisihHari(k.mulai, k.selesai) + 1}`
                  : `${selisihHari(hariIni(), k.mulai)} hari lagi`}</span>}
            </p>
          )}
          <h1>{kepala.judul}</h1>
        </div>
        <DataPer r={r} data={data} onHitung={onHitung} />
      </header>
      {r && <MenuBimtek r={r} pilih={pilih} />}
      {error && <Notice tone="bad">{error}</Notice>}
      {data.status.error && <Notice tone="bad" title="Hitung ulang gagal">{data.status.error}</Notice>}
      {!r ? (
        <section className={b.kosong}>
          <h2>Rekap belum dihitung</h2>
          <p>{data.bisa_hitung ? "Tekan tombol hitung ulang di kanan atas." : "Admin perlu menghitung rekap dari laptop yang menyimpan folder data bimtek."}</p>
        </section>
      ) : !pilih ? (
        <BimtekNasional r={r} />
      ) : !k ? (
        <Notice tone="info" title={`${labelBimtek(pilih)} belum ada di rekap`}>
          Periksa jadwal dan daftar peserta di folder data bimtek, lalu hitung ulang rekap.
        </Notice>
      ) : <Isi r={r} k={k} admin={data.admin ?? false} saya={data.saya ?? ""} />}
    </div>
  );
}

/* ---------- menu per bimtek ---------- */
function MenuBimtek({ r, pilih }: { r: Rekap; pilih: string }) {
  const nav = useRef<HTMLElement>(null);
  // di layar sempit menu bisa digulir: pastikan bimtek terpilih kelihatan
  useEffect(() => {
    const el = nav.current, a = el?.querySelector<HTMLElement>('[aria-current="page"]');
    if (el && a) el.scrollLeft = a.offsetLeft - (el.clientWidth - a.offsetWidth) / 2;
  }, [pilih]);
  return (
    <nav ref={nav} className={b.tabBimtek} aria-label="Pilih bimtek">
      <Link href="/bimtek/" className={b.tabItem} aria-current={pilih ? undefined : "page"}>Nasional</Link>
      {r.kelompok.map((k) => (
        <Link key={k.kode} href={hrefKelompok(k.kode)} className={b.tabItem}
          aria-current={k.kode.toUpperCase() === pilih ? "page" : undefined}>
          {labelBimtek(k.kode).replace(" ke-", " ")}
          {berlangsung(k) && <span className={b.tandaLangsung} title="Sedang berlangsung"><i /><span className="sr-only">Sedang berlangsung</span></span>}
        </Link>
      ))}
    </nav>
  );
}

function Isi({ r, k, admin, saya }: { r: Rekap; k: Kelompok; admin: boolean; saya: string }) {
  const kodeAda = useMemo(() => k.capaian?.komponen ?? [], [k]);
  const sekolah = useMemo(() => olah(r, k, kodeAda), [r, k, kodeAda]);
  const [pic, setPic] = useState("");
  const [hotel, setHotel] = useState("");
  const [saring, setSaring] = useState<Saring>("semua");
  const adaSesudah = k.tahap !== "akan datang" && !!k.sekolah;
  const langsung = berlangsung(k);
  if (belumMulai(k)) {
    return (
      <div className={b.halaman}>
        <section className={`${b.kosong} ${b.segera}`}>
          <h2>Coming soon</h2>
          <p>Bimtek ini mulai {tglPanjang(k.mulai)}. Data tampil setelah ada cutoff selama bimtek.</p>
        </section>
      </div>
    );
  }
  const pilihHotel = (h: string) => {
    setHotel(h);
    requestAnimationFrame(() => document.getElementById("h-rincian")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  return (
    <div className={b.halaman} style={{ ["--w" as string]: warnaDari(k.kode) }}>
      <KartuDetail r={r} k={k} />
      <Komponen r={r} k={k} rows={sekolah} adaSesudah={adaSesudah} />
      <PerHotel r={r} k={k} rows={sekolah} adaSesudah={adaSesudah} onPilih={adaSesudah ? pilihHotel : undefined} />
      <KurvaSatu r={r} k={k} />
      {adaSesudah ? (
        <Rincian r={r} k={k} sekolah={sekolah} pic={pic} setPic={setPic} hotel={hotel} setHotel={setHotel}
          saring={saring} setSaring={setSaring} />
      ) : (
        <section className={b.kosong}>
          <h2>Rincian per sekolah muncul setelah cutoff pertama selama bimtek</h2>
          <p>Data terakhir {tglJam(r.data_terbaru.waktu)}, sebelum bimtek mulai. Setiap cutoff otomatis memperbarui halaman ini.</p>
        </section>
      )}
      {langsung && <PantauPic r={r} k={k} rows={sekolah} admin={admin} saya={saya} />}
    </div>
  );
}

/* ---------- 1. kartu: sekolah, hotel, kapan data diambil ---------- */
function KartuDetail({ r, k }: { r: Rekap; k: Kelompok }) {
  const sudahT1 = new Date(r.data_terbaru.waktu) >= new Date(k.t1);
  return (
    <dl className={`${b.strip} ${b.stripDetail}`}>
      <div><dt>Sekolah</dt><dd>{fmt(k.peserta_daftar ?? k.sekolah)}</dd></div>
      <div><dt>Hotel</dt><dd>{k.hotel?.length || "–"}</dd></div>
      <div>
        <dt><Tip isi={<>Akhir hari sebelum bimtek mulai. Lap. 50% dihitung dari tanggal kirim di export aplikasi; komponen lain
          dari data tersimpan terakhir sebelum bimtek.</>}>Data sebelum</Tip></dt>
        <dd className={b.ddTanggal}>{tgl(k.t0)} {k.t0.slice(0, 4)}</dd>
      </div>
      <div>
        <dt><Tip isi={<>Akhir hari terakhir bimtek. Lap. 50% dari tanggal kirim; komponen lain dari export paling lambat 2 hari
          setelah bimtek selesai.</>}>Data hari terakhir bimtek</Tip></dt>
        <dd className={`${b.ddTanggal} ${sudahT1 ? "" : b.redupDd}`}>{sudahT1 ? `${tgl(k.selesai)} ${k.selesai.slice(0, 4)}` : "Belum"}</dd>
      </div>
      <div><dt>Data hari ini</dt><dd className={b.ddTanggal}>{tglJam(r.data_terbaru.waktu)}</dd></div>
    </dl>
  );
}

/* ---------- 2. per hotel ---------- */
function PerHotel({ r, k, rows, adaSesudah, onPilih }: { r: Rekap; k: Kelompok; rows: Hasil[]; adaSesudah: boolean;
  onPilih?: (h: string) => void }) {
  const urut = r.komponen_urut ?? [];
  const pilihan = komponenAda(r, k, rows, adaSesudah).map((c) => c.kode);
  const [komp, setKomp] = useState("l50");
  const kodeAktif = pilihan.includes(komp) ? komp : pilihan[0] ?? "l50";
  const i = urut.indexOf(kodeAktif), l50 = kodeAktif === "l50", reviu = adalahReviu(kodeAktif), jalan = berlangsung(k);
  const baris = useMemo(() => {
    const grup = new Map<string, Hasil[]>();
    for (const s of rows) {
      const h = s.hotel || TANPA_HOTEL;
      grup.set(h, [...(grup.get(h) ?? []), s]);
    }
    const hitung = (nama: string, xs: Hasil[]) => {
      const t = tigaTitik(xs, i, adaSesudah, reviu);
      const terkirim = xs.filter((s) => s.akhir_kode?.[i] === "S");
      const rev = (v: string) => terkirim.filter((s) => s.rev50 === v).length;
      const p0 = persen(t.n0, t.d0), p1 = persen(t.n1, t.d1), p2 = persen(t.n2, t.d2);
      const ujung = p1 ?? (jalan ? p2 : null);   // selama bimtek: sampai data hari ini
      return { nama, region: k.hotel?.find((h) => h.nama === nama)?.region ?? "", sekolah: xs.length, ...t, p0, p1,
        p2, delta: p0 !== null && ujung !== null ? ujung - p0 : null,
        setuju: rev("setuju"), tolak: rev("tolak"), menunggu: rev("menunggu"), terkirim: terkirim.length };
    };
    const isi = [...grup.entries()].map(([h, xs]) => hitung(h, xs))
      .sort((a, z) => (a.nama === TANPA_HOTEL ? 1 : z.nama === TANPA_HOTEL ? -1 : (z.delta ?? -999) - (a.delta ?? -999) || z.sekolah - a.sekolah));
    return { isi, total: hitung("Total", rows) };
  }, [rows, i, adaSesudah, reviu, jalan, k.hotel]);
  const sel = (p: number | null, n: number | null) => (p === null ? <span className={b.redup}>–</span>
    : <span className={b.tanggalSel}><b>{pct(p)}</b><small>{fmt(n ?? 0)} sekolah</small></span>);
  const baru = (x: typeof baris.total, tot = false) => (
    <tr key={x.nama} className={tot ? b.barisTotal : onPilih ? b.barisKlik : undefined}
      onClick={!tot && onPilih ? () => onPilih(x.nama) : undefined} title={!tot && onPilih ? "Lihat sekolahnya di rincian" : undefined}>
      <td>{tot ? <b>Total</b> : <span className={b.tanggalSel}><b>{x.nama}</b><small>{x.region}</small></span>}</td>
      <td className={b.angka}>{fmt(x.sekolah)}<small>{fmt(x.due)} {reviu ? "sudah kirim" : "jatuh tempo"}</small></td>
      <td className={b.angka}>{sel(x.p0, x.n0)}</td>
      {adaSesudah && <td className={b.angka}>{sel(x.p1, x.n1)}</td>}
      {adaSesudah && <td className={`${b.angka} ${b.kolomDelta}`}>{x.delta === null ? "–"
        : <b className={x.delta >= 0 ? b.naik : b.turun}>{poin(x.delta)}%</b>}</td>}
      {adaSesudah && <td className={b.angka}>{sel(x.p2, x.n2)}</td>}
      {l50 && adaSesudah && <>
        <td className={b.angka}>{fmt(x.setuju)}<small>{pct(persen(x.setuju, x.terkirim))}</small></td>
        <td className={b.angka}>{fmt(x.tolak)}<small>{pct(persen(x.tolak, x.terkirim))}</small></td>
        <td className={b.angka}><b className={x.menunggu ? b.turun : undefined}>{fmt(x.menunggu)}</b><small>{pct(persen(x.menunggu, x.terkirim))}</small></td>
      </>}
    </tr>
  );
  return (
    <section className={b.panel} aria-labelledby="h-hotel">
      <div className={b.panelHead}>
        <h2 id="h-hotel" className={b.h2}>
          <Tip isi={<>Persen sekolah yang komponennya selesai, dari sekolah yang komponen itu sudah jatuh tempo sebelum bimtek.
            Untuk reviu: dari sekolah yang sudah mengirim pada tanggal itu. Δ = hari terakhir bimtek dikurangi sebelum.
            Disetujui, dikembalikan, dan menunggu reviu dihitung dari sekolah yang sudah mengirim Lap. 50% (data hari ini).
            Klik hotel untuk melihat sekolahnya di rincian.</>}>Per hotel</Tip>
        </h2>
        {pilihan.length > 1 && (
          <div className={b.saringBaris}>
            <select value={kodeAktif} onChange={(e) => setKomp(e.target.value)} aria-label="Pilih komponen">
              {pilihan.map((x) => <option key={x} value={x}>{(k.komponen ?? []).find((c) => c.kode === x)?.label ?? KOMP_PENDEK[x]}</option>)}
            </select>
          </div>
        )}
      </div>
      {!k.hotel?.length && <p className={b.ket}>Pemetaan hotel bimtek ini belum ada di master.</p>}
      <div className={b.gulir}>
        <table className={`${b.tabel} ${b.tabelHotel}`}>
          <thead>
            <tr>
              <th>Hotel</th><th className={b.angka}>Sekolah</th>
              <th className={b.angka}>{adaSesudah ? "Sebelum" : "Kondisi awal"}<small>{tgl(k.t0)}</small></th>
              {adaSesudah && <th className={b.angka}>Hari terakhir<small>{tgl(k.selesai)}</small></th>}
              {adaSesudah && <th className={`${b.angka} ${b.kolomDelta}`}>{jalan
                ? <Tip isi="Kenaikan sejak sebelum bimtek sampai data hari ini. Ikut berubah tiap cutoff selama bimtek.">Δ s.d. hari ini</Tip> : "Δ"}</th>}
              {adaSesudah && <th className={b.angka}>Hari ini<small>{tgl(r.data_terbaru.waktu)}</small></th>}
              {l50 && adaSesudah && <><th className={b.angka}>Disetujui</th><th className={b.angka}>Dikembalikan</th>
                <th className={b.angka}>Menunggu reviu</th></>}
            </tr>
          </thead>
          <tbody>{baris.isi.map((x) => baru(x))}</tbody>
          <tfoot>{baru(baris.total, true)}</tfoot>
        </table>
      </div>
    </section>
  );
}

/* ---------- 4. pergerakan per komponen: tabel (kiri), batang bertumpuk (kanan) ---------- */
const WARNA_KOMP = { sebelum: "#0f6aa6", selama: "#5aaee3", belum: "#e4e9ef" };
const RUMUS_PERSEN = <>Persen = sekolah yang selesai ÷ sekolah yang komponennya jatuh tempo sebelum bimtek. Untuk reviu: sekolah
  yang semua laporannya sudah direviu ÷ sekolah yang sudah mengirim pada tanggal itu. Angka kecil = jumlah sekolah selesai.</>;
function Komponen({ r, k, rows, adaSesudah }: { r: Rekap; k: Kelompok; rows: Hasil[]; adaSesudah: boolean }) {
  const urut = r.komponen_urut ?? [];
  const [sorot, setSorot] = useState<string | null>(null);
  const jalan = berlangsung(k);
  const isi = komponenAda(r, k, rows, adaSesudah).map((c) => {
    const t = tigaTitik(rows, urut.indexOf(c.kode), adaSesudah, adalahReviu(c.kode));
    const p = [persen(t.n0, t.d0), persen(t.n1, t.d1), persen(t.n2, t.d2)];
    // selama bimtek berjalan, "sesudah" = data hari ini
    const nAkhir = t.n1 ?? (jalan ? t.n2 : null), pAkhir = p[1] ?? (jalan ? p[2] : null);
    return { c, t, p, nAkhir, pAkhir };
  });
  const sel = (v: number | null, n: number | null) => (v === null ? <span className={b.redup}>–</span>
    : <span className={b.tanggalSel}><b>{pct(v)}</b><small>{fmt(n ?? 0)}</small></span>);
  return (
    <div className={`${b.duaKartu} ${b.duaKartuLebar}`}>
      <section className={b.panel} aria-labelledby="h-komp">
        <div className={b.panelHead}>
          <h2 id="h-komp" className={b.h2}>
            <Tip isi={<>Persen sekolah yang komponennya selesai, dari sekolah yang komponen itu sudah jatuh tempo sebelum bimtek.
              Untuk reviu: dari sekolah yang sudah mengirim laporannya pada tanggal itu, jadi persennya bisa turun bila banyak
              kiriman baru masuk; karena itu Δ dihitung dari jumlah sekolah.</>}>Pergerakan per komponen</Tip>
          </h2>
        </div>
        <div className={b.gulir}>
          <table className={`${b.tabel} ${b.tabelJadwal}`}>
            <thead>
              <tr>
                <th>Komponen</th><th className={b.angka}>Jatuh tempo</th>
                <th className={b.angka}><Tip isi={RUMUS_PERSEN}>Sebelum</Tip></th>
                {adaSesudah && <th className={b.angka}><Tip isi={RUMUS_PERSEN}>Hari terakhir</Tip></th>}
                {adaSesudah && <th className={`${b.angka} ${b.kolomDelta}`}><Tip kanan isi={<>
                  <b>Δ = jumlah sekolah selesai {jalan ? "hari ini" : "di hari terakhir"} − jumlah sebelum bimtek.</b> Angka kecil = selisih
                  persennya. Untuk reviu, sekolah dihitung selesai bila semua laporannya sudah direviu. Kalau sekolah mengirim
                  laporan baru (mingguan/bulanan berulang), statusnya kembali menunggu reviu, jadi jumlahnya bisa turun.
                  Negatif = antrean reviu bertambah (laporan baru masuk lebih cepat dari yang direviu fasil).</>}>Δ</Tip></th>}
                {adaSesudah && <th className={b.angka}><Tip kanan isi={RUMUS_PERSEN}>Hari ini</Tip></th>}
              </tr>
            </thead>
            <tbody>
              {isi.map(({ c, t, p, nAkhir, pAkhir }) => {
                const dn = t.n0 !== null && nAkhir !== null ? nAkhir - t.n0 : null;
                return (
                  <tr key={c.kode}>
                    <td>{KET_KOMP[c.kode] ? <Tip isi={KET_KOMP[c.kode]}>{c.label}</Tip> : c.label}</td>
                    <td className={b.angka}>{fmt(t.due)}{adalahReviu(c.kode) && <small>sudah kirim</small>}</td>
                    <td className={b.angka}>{sel(p[0], t.n0)}</td>
                    {adaSesudah && <td className={b.angka}>{sel(p[1], t.n1)}</td>}
                    {adaSesudah && (
                      <td className={`${b.angka} ${b.kolomDelta}`}>{dn === null || p[0] === null || pAkhir === null ? <span className={b.redup}>–</span>
                        : <span className={b.tanggalSel}><b className={dn >= 0 ? b.naik : b.turun}>{dn >= 0 ? "+" : "−"}{fmt(Math.abs(dn))}</b>
                          <small>{poin(pAkhir - p[0])}%</small></span>}</td>
                    )}
                    {adaSesudah && <td className={b.angka}>{sel(p[2], t.n2)}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <section className={b.panel} aria-labelledby="h-komp-batang">
        <div className={b.panelHead}>
          <h2 id="h-komp-batang" className={b.h2}>
            <Tip isi={<>Panjang batang = sekolah yang komponennya jatuh tempo (untuk reviu: yang sudah mengirim). Biru tua =
              sekolah yang sudah selesai sebelum bimtek; biru muda = tambahannya sampai data hari ini. Angka hijau/merah =
              naik atau turunnya.</>}>Sebelum bimtek & hari ini</Tip>
          </h2>
        </div>
        <ul className={`${b.legendaKotak} ${b.legendaBaris}`}>
          <li><i style={{ background: WARNA_KOMP.sebelum }} />Sebelum bimtek</li>
          <li><i style={{ background: WARNA_KOMP.selama }} />Naik s.d. hari ini</li>
          <li><i style={{ background: WARNA_KOMP.belum }} />Belum</li>
        </ul>
        <ul className={`${b.batangList} ${b.batangRapat}`}>
          {isi.map(({ c, t, p }) => {
            const n0 = t.n0 ?? 0, n2 = t.n2 ?? n0, due = Math.max(1, t.due), d = n2 - n0;
            const lebar = (n: number) => `${(Math.max(0, n) / due) * 100}%`;
            // reviu bisa turun (ada kiriman baru): bagian gelap = yang lebih kecil dari keduanya
            const gelap = Math.min(n0, n2), tambah = Math.max(0, d);
            const naik = d === 0 ? null : <em className={d > 0 ? b.naik : b.turun}>{d > 0 ? "+" : "−"}{fmt(Math.abs(d))}</em>;
            // angka sebelum di ujung bagian gelap, naik/turun di ujung batang; digabung bila keduanya terlalu berdekatan
            const pisah = Math.abs(d) / due >= 0.12;
            const ujung = (n: number) => (n / due < 0.25 ? { left: 0 } : { left: lebar(n), transform: "translateX(-100%)" });
            return (
              <li key={c.kode} onMouseEnter={() => setSorot(c.kode)} onMouseLeave={() => setSorot(null)}>
                <span className={b.batangNama}>{KOMP_PENDEK[c.kode] ?? c.label}</span>
                <span className={b.batangWadah}>
                  {pisah ? <>
                    <span className={b.batangAngka} style={ujung(n0)}>{fmt(n0)}</span>
                    <span className={b.batangAngka} style={{ left: lebar(Math.max(n0, n2)), transform: "translateX(-100%)" }}>{naik}</span>
                  </> : <span className={b.batangAngka} style={ujung(Math.max(n0, n2))}>{fmt(n0)}{naik && <> {naik}</>}</span>}
                  <span className={b.batangJalur} aria-hidden="true">
                    <span style={{ width: lebar(gelap), background: WARNA_KOMP.sebelum }} />
                    <span style={{ width: lebar(tambah), background: WARNA_KOMP.selama }} />
                    <span style={{ width: lebar(t.due - gelap - tambah), background: WARNA_KOMP.belum }} />
                  </span>
                </span>
                <span className={b.batangTeks}><span><b>{pct(p[2] ?? p[0])}</b> dari {fmt(t.due)} sekolah</span></span>
                {sorot === c.kode && (
                  <div className={b.batangTip} role="status">
                    <b>{c.label}</b>
                    <span><i style={{ background: WARNA_KOMP.sebelum }} />Sebelum ({tgl(k.t0)} {k.t0.slice(0, 4)})<em>{fmt(n0)} sekolah</em></span>
                    <span><i style={{ background: WARNA_KOMP.selama }} />Hari ini ({tglJam(r.data_terbaru.waktu)})<em>{fmt(n2)} sekolah</em></span>
                    <span><i />{d >= 0 ? "Naik" : "Turun"}<em>{d >= 0 ? "+" : "−"}{fmt(Math.abs(d))} sekolah · {poin((p[2] ?? 0) - (p[0] ?? 0))}%</em></span>
                    <span><i style={{ background: WARNA_KOMP.belum }} />Belum<em>{fmt(Math.max(0, t.due - n2))} sekolah</em></span>
                    <span><i />{adalahReviu(c.kode) ? "Sudah kirim" : "Jatuh tempo"}<em>{fmt(t.due)} sekolah</em></span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

/* ---------- 6. pantau sekolah binaan PIC selama bimtek berlangsung ---------- */
function PantauPic({ r, k, rows, admin, saya }: { r: Rekap; k: Kelompok; rows: Hasil[]; admin: boolean; saya: string }) {
  const urut = r.komponen_urut ?? [];
  const daftarPic = useMemo(() => [...new Set(rows.map((s) => s.pic).filter(Boolean))].sort(), [rows]);
  const [pic, setPic] = useState(saya && daftarPic.includes(saya) ? saya : "");
  const [fasil, setFasil] = useState("");
  const [batasBaris, setBatasBaris] = useState(25);
  const picAktif = admin ? pic : saya;
  const milik = rows.filter((s) => (picAktif ? s.pic === picAktif : admin));
  const daftarFasil = [...new Set(milik.map((s) => s.fasil).filter(Boolean))].sort();
  const tampil = milik.filter((s) => !fasil || s.fasil === fasil)
    .map((s) => ({ s, belum: [...(s.akhir_kode ?? "")].filter((c) => c === "B").length }))
    .sort((a, z) => z.belum - a.belum || a.s.nama.localeCompare(z.s.nama));
  const kolom = urut.map((kode, i) => ({ kode, i })).filter(({ i }) => milik.some((s) => (s.akhir_kode?.[i] ?? "-") !== "-"));
  const i50 = urut.indexOf("l50");
  const belum50 = milik.filter((s) => s.akhir_kode?.[i50] === "B").length;
  const tunggu = milik.filter((s) => s.rev50 === "menunggu").length;
  const unduhPantau = () => {
    const sel = (v: unknown) => { const t = String(v ?? ""); return /[;"\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
    const teks: Record<string, string> = { S: "Sudah", B: "Belum", P: "Ada kiriman baru", D: "Belum jatuh tempo", "-": "" };
    const judul = ["NPSN", "Nama Sekolah", "PIC", "Fasilitator", "Kab/Kota", "Hotel", ...kolom.map((x) => KOMP_PENDEK[x.kode]),
      "Reviu Lap. 50%", "Menunggu reviu (hari)", "Data per"];
    const isi = tampil.map(({ s }) => [s.npsn, s.nama, s.pic, s.fasil, s.kab, s.hotel ?? "",
      ...kolom.map((x) => teks[s.akhir_kode?.[x.i] ?? "-"] ?? ""), REV50[s.rev50 ?? ""] ?? "",
      s.rev50 === "menunggu" ? s.tunggu50 ?? "" : "", r.data_terbaru.waktu.replace("T", " ")]);
    const csv = "\ufeff" + [judul, ...isi].map((x) => x.map(sel).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${k.kode}_pantau${picAktif ? `_${picAktif.replace(/\W+/g, "-")}` : ""}${fasil ? `_${fasil.replace(/\W+/g, "-")}` : ""}_${r.data_terbaru.waktu.slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const SIMBOL: Record<string, [string, string]> = { S: ["✓", "sudah2"], B: ["✕", "tetap"], P: ["↗", "gerak"], D: ["·", "kosong"], "-": ["·", "kosong"] };
  return (
    <section className={`${b.panel} ${b.panelSorot}`} aria-labelledby="h-pantau">
      <div className={b.panelHead}>
        <div>
          <h2 id="h-pantau" className={b.h2}>
            <Tip isi={<>Sekolah binaan yang sedang ikut bimtek ini, dengan status tiap komponen per data terakhir
              ({tglJam(r.data_terbaru.waktu)}). Urut dari yang paling banyak komponen belum selesai.</>}>
              {picAktif ? (picAktif === saya ? "Sekolah binaan saya" : `Sekolah binaan ${picAktif}`) : "Sekolah binaan per PIC"}</Tip>
          </h2>
          <p className={b.ket}>Bimtek sedang berlangsung sampai {tgl(k.selesai)}. Dorong sekolah yang masih ✕.</p>
        </div>
        <div className={b.saringBaris}>
          {admin && (
            <select value={pic} onChange={(e) => { setPic(e.target.value); setFasil(""); }} aria-label="Pilih PIC">
              <option value="">Semua PIC</option>
              {daftarPic.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          )}
          <select value={fasil} onChange={(e) => setFasil(e.target.value)} aria-label="Pilih fasil">
            <option value="">Semua fasil ({daftarFasil.length})</option>
            {daftarFasil.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <Button size="sm" variant="secondary" onClick={unduhPantau} disabled={!tampil.length}>Unduh CSV ({fmt(tampil.length)})</Button>
        </div>
      </div>
      {!admin && !saya ? (
        <p className={b.ket}>Akun ini belum terhubung ke nama PIC di LK.</p>
      ) : (
        <>
          <dl className={b.pantauAngka}>
            <div><dt>Sekolah</dt><dd>{fmt(milik.length)}</dd></div>
            <div><dt>Hotel</dt><dd>{new Set(milik.map((s) => s.hotel).filter(Boolean)).size}</dd></div>
            <div><dt>Lap. 50% belum kirim</dt><dd className={belum50 ? b.turun : undefined}>{fmt(belum50)}</dd></div>
            <div><dt>Menunggu reviu fasil</dt><dd className={tunggu ? b.turun : undefined}>{fmt(tunggu)}</dd></div>
          </dl>
          <div className={b.gulir}>
            <table className={`${b.tabel} ${b.rincian}`}>
              <thead>
                <tr>
                  <th>Sekolah</th><th>Fasil</th><th>Hotel</th>
                  {kolom.map((x) => <th key={x.kode} className={b.kolomKomp}>{KOMP_PENDEK[x.kode]}</th>)}
                  <th>Reviu Lap. 50%</th>
                </tr>
              </thead>
              <tbody>
                {tampil.slice(0, batasBaris).map(({ s }) => (
                  <tr key={s.npsn}>
                    <td className={b.kolomSekolah}><b>{s.nama}</b><small>NPSN {s.npsn} · {s.kab}</small></td>
                    <td className={b.kolomPic}>{s.fasil || "–"}{!picAktif && <small>{s.pic}</small>}</td>
                    <td>{s.hotel || "–"}</td>
                    {kolom.map((x) => {
                      const [simbol, kelas] = SIMBOL[s.akhir_kode?.[x.i] ?? "-"] ?? SIMBOL["-"];
                      return <td key={x.kode} className={b.kolomKomp}><span className={`${b.ubah} ${b[`ubah_${kelas}`]}`}>{simbol}</span></td>;
                    })}
                    <td><Reviu s={s} /></td>
                  </tr>
                ))}
                {!tampil.length && <tr><td colSpan={kolom.length + 4} className={b.kosongBaris}>Tidak ada sekolah binaan di bimtek ini.</td></tr>}
              </tbody>
            </table>
          </div>
          {tampil.length > batasBaris && (
            <button type="button" className={b.lihatSemua} onClick={() => setBatasBaris(batasBaris + 50)}>
              Tampilkan lebih banyak ({fmt(batasBaris)} dari {fmt(tampil.length)} sekolah)
            </button>
          )}
        </>
      )}
    </section>
  );
}

function Reviu({ s }: { s: Sekolah }) {
  if (!s.rev50) return <span className={b.redup}>–</span>;
  return (
    <span className={`${b.rev} ${b[`rev_${s.rev50}`]}`}>
      {REV50[s.rev50]}{s.rev50 === "menunggu" && s.tunggu50 != null && <small> {s.tunggu50} hari</small>}
    </span>
  );
}

function Meter({ v }: { v: number | null }) {
  if (v === null) return <span className={b.belumAda}>–</span>;
  return (
    <span className={b.meter}>
      <span className={b.meterJalur}><span style={{ width: `${v}%` }} /></span>
      <b>{pct(v)}</b>
    </span>
  );
}

/* ---------- 5. rincian per sekolah per komponen + CSV ---------- */
function Rincian({ r, k, sekolah, pic, setPic, hotel, setHotel, saring, setSaring }: {
  r: Rekap; k: Kelompok; sekolah: Hasil[]; pic: string; setPic: (p: string) => void; hotel: string; setHotel: (h: string) => void;
  saring: Saring; setSaring: (s: Saring) => void;
}) {
  const [cari, setCari] = useState("");
  const [hal, setHal] = useState(0);
  const [kuadran, setKuadran] = useState<Kuadran | "">("");
  const [batas, setBatas] = useState(7);
  const i50 = (r.komponen_urut ?? []).indexOf("l50");
  const kuadranS = (s: Hasil) => kuadranDari(s.akhir_kode?.[i50], s.rev50, s.tunggu50, batas);
  const urut = r.komponen_urut ?? [];
  const kodeAda = k.capaian?.komponen ?? [];
  const kolom = urut.map((kode, i) => ({ kode, i })).filter((x) => kodeAda.includes(x.kode));
  const daftarPic = useMemo(() => [...new Set(sekolah.map((s) => s.pic || "(tanpa PIC)"))].sort(), [sekolah]);
  const daftarHotel = useMemo(() => [...new Set(sekolah.map((s) => s.hotel || TANPA_HOTEL))].sort(), [sekolah]);
  const cocokSaring = (s: Hasil, x: Saring) =>
    x === "semua" || (x === "belum_efektif" ? s.tetap > 0 : x === "efektif" ? s.belumAwal > 0 && !s.tetap : !s.belumAwal);
  const dasar = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return sekolah.filter((s) => (!pic || (s.pic || "(tanpa PIC)") === pic) && (!hotel || (s.hotel || TANPA_HOTEL) === hotel)
      && (!q || s.nama.toLowerCase().includes(q) || s.npsn.includes(q) || s.fasil.toLowerCase().includes(q) || s.kab.toLowerCase().includes(q)));
  }, [sekolah, pic, hotel, cari]);
  const dasarK = dasar.filter((s) => cocokSaring(s, saring));
  const baris = dasarK.filter((s) => !kuadran || kuadranS(s) === kuadran)
    .sort((a, z) => (a.efektif ?? 101) - (z.efektif ?? 101) || z.tetap - a.tetap || a.nama.localeCompare(z.nama));
  const halMaks = Math.max(0, Math.ceil(baris.length / PER_HAL) - 1);
  const halIni = Math.min(hal, halMaks);
  const tampil = baris.slice(halIni * PER_HAL, (halIni + 1) * PER_HAL);

  const unduh = () => {
    const sel = (v: unknown) => { const t = String(v ?? ""); return /[;"\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
    const teksUbah = (u: Ubah) => (u === "naik" ? "Belum → Sudah" : u === "gerak" ? "Ada kiriman baru" : u === "tetap" ? "Belum → Belum"
      : u === "sudah" ? "Sudah" : u === "turun" ? "Sudah → Belum" : "-");
    const judul = ["NPSN", "Nama Sekolah", "PIC", "Fasilitator", "Kab/Kota", "Provinsi", "Hotel", "Bimtek", "Tanggal Bimtek",
      ...kolom.map((x) => `${KOMP_PENDEK[x.kode]} (sebelum → sesudah)`), "Komponen masih belum", "Efektivitas (%)",
      "Tgl Kirim 50%", "Kirim 50%", "Reviu 50%", "Waktu tunggu reviu (hari)", `Status (batas reviu ${batas} hari)`,
      "Progres sebelum (%)", "Progres sekarang (%)", "Data per"];
    const isi = baris.map((s) => [s.npsn, s.nama, s.pic, s.fasil, s.kab, s.prov, s.hotel ?? "", labelBimtek(k.kode), rentang(k.mulai, k.selesai),
      ...kolom.map((x) => teksUbah(s.ubah[x.i])),
      kolom.filter((x) => s.ubah[x.i] === "tetap").map((x) => KOMP_PENDEK[x.kode]).join(", "),
      s.efektif === null ? "" : s.efektif.toFixed(0), s.tgl50.replace("T", " "), KAT50[s.kategori] ?? "", REV50[s.rev50 ?? ""] ?? "",
      s.rev50 === "menunggu" ? s.tunggu50 ?? "" : "", KUADRAN.find((q) => q.k === kuadranS(s))?.label ?? "",
      s.progres_awal ?? "", s.progres ?? "", r.data_terbaru.waktu.replace("T", " ")]);
    const csv = "﻿" + [judul, ...isi].map((x) => x.map(sel).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${k.kode}${kuadran ? `_${kuadran}-${batas}hari` : ""}${saring !== "semua" ? `_${saring.replace("_", "-")}` : ""}${pic ? `_${pic.replace(/\W+/g, "-")}` : ""}${hotel ? `_${hotel.replace(/\W+/g, "-")}` : ""}_${r.data_terbaru.waktu.slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className={b.panel} aria-labelledby="h-rincian">
      <div className={b.panelHead}>
        <h2 id="h-rincian" className={b.h2}>
          <Tip isi={<>Tiap komponen: ↑ belum → sudah, ↗ ada kiriman baru tapi belum lengkap (laporan berulang), ✕ tidak bergerak,
            ✓ sudah sejak sebelum bimtek, ↓ sempat sudah lalu ada laporan baru jatuh tempo, · belum jatuh tempo. Efektivitas =
            komponen yang bergerak (↑ atau ↗) ÷ komponen yang tertunggak sebelum bimtek.</>}>Rincian per sekolah</Tip>
        </h2>
        <Button size="sm" variant="secondary" onClick={unduh} disabled={!baris.length}>Unduh CSV ({fmt(baris.length)} sekolah)</Button>
      </div>
      <div className={b.saring}>
        <div className={b.saringKuadran}>
          <div className={b.chip} role="group" aria-label="Sekolah x fasil">
            <button type="button" aria-pressed={!kuadran} onClick={() => { setKuadran(""); setHal(0); }}>
              Semua <small>{fmt(dasarK.length)}</small>
            </button>
            {KUADRAN.map((q) => (
              <button key={q.k} type="button" aria-pressed={kuadran === q.k} title={q.ket} className={b[`kq_${q.k}`]}
                onClick={() => { setKuadran(q.k); setHal(0); }}>
                {q.label} <small>{fmt(dasarK.filter((s) => kuadranS(s) === q.k).length)}</small>
              </button>
            ))}
          </div>
          <label className={b.pilihBatas}>
            <Tip kanan isi={<>Lap. 50% sekolah disebut telat direviu (fasil bermasalah) kalau menunggu reviu lebih lama dari
              batas ini.</>}>Telat direviu bila lebih dari</Tip>
            <select value={batas} onChange={(e) => { setBatas(Number(e.target.value)); setHal(0); }} aria-label="Batas hari reviu">
              {PILIHAN_HARI.map((h) => <option key={h} value={h}>{h} hari</option>)}
            </select>
          </label>
        </div>
        <div className={b.saringBaris}>
          <select value={saring} onChange={(e) => { setSaring(e.target.value as Saring); setHal(0); }} aria-label="Saring efektivitas">
            <option value="semua">Efektivitas: semua</option>
            {SARING.map((x) => <option key={x.k} value={x.k}>{x.label} ({fmt(dasar.filter((s) => cocokSaring(s, x.k)).length)})</option>)}
          </select>
          <select value={pic} onChange={(e) => { setPic(e.target.value); setHal(0); }} aria-label="Saring PIC">
            <option value="">Semua PIC</option>
            {daftarPic.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select value={hotel} onChange={(e) => { setHotel(e.target.value); setHal(0); }} aria-label="Saring hotel">
            <option value="">Semua hotel</option>
            {daftarHotel.map((h) => <option key={h} value={h}>{h}</option>)}
          </select>
          <input type="search" placeholder="Cari sekolah, NPSN, fasil, atau kabupaten" value={cari}
            onChange={(e) => { setCari(e.target.value); setHal(0); }} aria-label="Cari sekolah" />
        </div>
      </div>
      <div className={b.gulir}>
        <table className={`${b.tabel} ${b.rincian}`}>
          <thead>
            <tr>
              <th>Sekolah</th><th>PIC / fasil</th><th>Hotel</th>
              <th><Tip isi={<>Sekolah bermasalah: Lap. 50% jatuh tempo tapi belum dikirim. Fasil bermasalah: sudah dikirim tapi
                menunggu reviu lebih lama dari batas hari.</>}>Status</Tip></th><th>Kirim Lap. 50%</th><th>Reviu Lap. 50%</th>
              <th className={b.angka}><Tip isi={<>Berapa hari Lap. 50% sekolah ini sudah menunggu reviu fasil.</>}>Waktu tunggu reviu</Tip></th>
              <th className={b.angka}>Progres fisik</th>
              <th className={b.angka}>Efektivitas</th>
              {kolom.map((x) => (
                <th key={x.kode} className={b.kolomKomp}>
                  {KET_KOMP[x.kode] ? <Tip isi={KET_KOMP[x.kode]}>{KOMP_PENDEK[x.kode]}</Tip> : KOMP_PENDEK[x.kode]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tampil.map((s) => (
              <tr key={s.npsn}>
                <td className={b.kolomSekolah}><b>{s.nama}</b><small>NPSN {s.npsn} · {s.kab}</small></td>
                <td className={b.kolomPic}>{s.pic || "–"}<small>{s.fasil}</small></td>
                <td className={b.kolomHotel}>{s.hotel || "–"}</td>
                <td><span className={`${b.kq} ${b[`kq_${kuadranS(s)}`]}`}>{KUADRAN.find((q) => q.k === kuadranS(s))?.label}</span></td>
                <td className={b.kolomKirim}>
                  {s.tgl50 ? <>{tgl(s.tgl50)}<small>{KAT50[s.kategori]}</small></> : <span className={s.kategori === "belum" ? b.turun : b.redup}>{KAT50[s.kategori] ?? "–"}</span>}
                </td>
                <td><Reviu s={s} /></td>
                <td className={b.angka}>{(() => { const t = s.rev50 === "menunggu" ? s.tunggu50 ?? null : null; return t === null ? <span className={b.redup}>–</span>
                  : <b className={t > batas ? b.turun : undefined}>{t} hari</b>; })()}</td>
                <td className={b.angka}>{s.progres === null ? "–" : <>{pct(s.progres)}<small>{s.progres_awal === null ? "" : `dari ${pct(s.progres_awal)}`}</small></>}</td>
                <td className={b.angka}><Meter v={s.efektif} /></td>
                {kolom.map((x) => {
                  const u = s.ubah[x.i];
                  return (
                    <td key={x.kode} className={b.kolomKomp}>
                      <span className={`${b.ubah} ${b[`ubah_${u}`]}`} title={`${KOMP_PENDEK[x.kode]}: ${UBAH[u].label}`}>{UBAH[u].simbol}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
            {!tampil.length && <tr><td colSpan={kolom.length + 9} className={b.kosongBaris}>Tidak ada sekolah yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className={b.legendaUbah}>
        {(["naik", "gerak", "tetap", "sudah", "turun", "kosong"] as Ubah[]).map((u) => (
          <span key={u}><span className={`${b.ubah} ${b[`ubah_${u}`]}`}>{UBAH[u].simbol}</span>{UBAH[u].label}</span>
        ))}
      </p>
      {baris.length > PER_HAL && (
        <div className={b.halaman2}>
          <span>{fmt(halIni * PER_HAL + 1)}–{fmt(Math.min(baris.length, (halIni + 1) * PER_HAL))} dari {fmt(baris.length)} sekolah</span>
          <button type="button" disabled={halIni === 0} onClick={() => setHal(halIni - 1)}>‹ Sebelumnya</button>
          <button type="button" disabled={halIni >= halMaks} onClick={() => setHal(halIni + 1)}>Berikutnya ›</button>
        </div>
      )}
    </section>
  );
}

/* ---------- 3. Laporan 50% per hari: satu garis kelompok (pudar sebelum bimtek) ---------- */
function KurvaSatu({ r, k }: { r: Rekap; k: Kelompok }) {
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
  const grup = r.kurva.seri.find((s) => s.kode === k.kode);
  if (!grup) return null;
  const sempit = lebarWadah < 600;
  const W = Math.max(320, lebarWadah), H = sempit ? 260 : 300, KIRI = 40, KANAN = sempit ? 56 : 80, ATAS = 30, BAWAH = 40;
  const lebar = W - KIRI - KANAN, tinggi = H - ATAS - BAWAH;
  const idx = (iso: string) => t.indexOf(iso.slice(0, 10));
  const akhir = t.length - 1;
  const iMulai = idx(k.mulai) >= 0 ? idx(k.mulai) : akhir, iSelesai = idx(k.selesai) >= 0 ? idx(k.selesai) : -1;
  const s0 = Math.max(0, iMulai - HARI_SEBELUM);
  const rentangI = Math.max(1, akhir - s0);
  const x = (i: number) => KIRI + ((i - s0) / rentangI) * lebar;
  const y = (v: number) => ATAS + (1 - v / 100) * tinggi;
  const garis = (v: (number | null)[], dari: number, sampai: number) =>
    v.map((n, i) => (n === null || i < Math.max(dari, s0) || i > sampai ? null : `${x(i)},${y(n)}`)).filter(Boolean).join(" ");
  const titik = [{ i: iMulai - 1, label: "Sebelum" }, { i: iSelesai, label: "Hari terakhir" }, { i: akhir, label: "Hari ini" }]
    .filter((p, j, a) => p.i >= s0 && p.i <= akhir && grup.nilai[p.i] !== null && a.findIndex((q) => q.i === p.i) === j);
  const minggu = t.map((d, i) => ({ d, i })).filter(({ d, i }) => i >= s0 && new Date(d).getDay() === 1);
  const sumbu = sempit && minggu.length > 4 ? minggu.filter((_, j) => j % 2 === 0) : minggu;
  const warna = warnaDari(k.kode);
  const bandAkhir = iSelesai >= 0 ? iSelesai : akhir;
  const gerak = (e: React.PointerEvent<SVGSVGElement>) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const i = s0 + Math.round(((((e.clientX - box.left) / box.width) * W - KIRI) / lebar) * rentangI);
    setHover(i >= s0 && i < t.length ? i : null);
  };
  return (
    <section className={b.panel} aria-labelledby="h-kurva1">
      <h2 id="h-kurva1" className={b.h2}>
        <Tip isi={<>Persen sekolah yang Laporan 50%-nya jatuh tempo dan sudah dikirim, per hari, mulai 2 minggu sebelum bimtek.
          Titik = sebelum bimtek, hari terakhir bimtek, dan hari ini.</>}>Laporan 50% per hari</Tip>
      </h2>
      <div className={b.kanvas} ref={wadah}>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" className={b.svg}
          aria-label={`${labelBimtek(k.kode)}: ${pct(grup.nilai[akhir])} sudah mengirim Laporan 50%`}
          onPointerMove={gerak} onPointerLeave={() => setHover(null)}>
          {iMulai <= akhir && idx(k.mulai) >= 0 && (
            <>
              <rect x={x(iMulai) - 4} y={ATAS} width={Math.max(8, x(bandAkhir) - x(iMulai) + 8)} height={tinggi} fill={warna} opacity={0.12} />
              <text x={x(iMulai) - 2} y={ATAS - 10} className={b.bandLabel}>Bimtek {rentang(k.mulai, k.selesai)}</text>
            </>
          )}
          {[0, 50, 100].map((v) => (
            <g key={v}>
              <line x1={KIRI} x2={KIRI + lebar} y1={y(v)} y2={y(v)} className={v === 0 ? b.sumbuDasar : b.grid} />
              <text x={KIRI - 8} y={y(v) + 4} textAnchor="end" className={b.sumbu}>{v}%</text>
            </g>
          ))}
          {sumbu.map(({ d, i }) => <text key={d} x={x(i)} y={H - BAWAH + 18} textAnchor="middle" className={b.sumbu}>{tgl(d)}</text>)}
          <polyline points={garis(grup.nilai, 0, iMulai)} fill="none" stroke={warna} strokeWidth={2} opacity={0.35} />
          <polyline points={garis(grup.nilai, iMulai, akhir)} fill="none" stroke={warna} strokeWidth={3} strokeLinejoin="round" />
          {titik.map((p) => (
            <g key={p.label}>
              <circle cx={x(p.i)} cy={y(grup.nilai[p.i] as number)} r={5} fill={warna} className={b.titik} />
              <text x={x(p.i)} y={y(grup.nilai[p.i] as number) - 12} textAnchor="middle" className={b.labelTitik}>{pct(grup.nilai[p.i])}</text>
            </g>
          ))}
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={ATAS} y2={ATAS + tinggi} className={b.silang} />}
        </svg>
        {hover !== null && (
          <div className={`${b.tip} ${x(hover) > W * 0.55 ? b.tipKiri : b.tipKanan}`} style={{ left: `${(x(hover) / W) * 100}%` }} role="status">
            <b>{tglPanjang(t[hover])}</b>
            <span><i style={{ background: warna }} />{labelBimtek(k.kode)}<em>{pct(grup.nilai[hover])}</em></span>
          </div>
        )}
      </div>
    </section>
  );
}
