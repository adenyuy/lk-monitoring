"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button, Notice, Spinner } from "@/components/ui";
import { Batang, Capaian, Komunikasi, Kpi, type Dash } from "@/components/dashboard/DashboardView";
import d from "@/components/dashboard/dashboard.module.css";
import { BimtekPanel } from "./BimtekPanel";
import { LogProgresOnline } from "./LogProgresOnline";
import s from "./online.module.css";

/** belum = sekolah yang komponennya belum selesai; kendala/tl = berapa di antaranya sudah diisi petugas (null = tanpa kolom);
 *  kom = kode Log Komunikasi terakhir FASIL dari sekolah-sekolah itu, jumlah fasil per kode ("-" = belum ada catatan). */
type Komp = { kode: string; label: string; selesai: number; harus: number; persen: number | null;
  belum: number; fasil_belum: number; kendala: number | null; tl: number | null; kom: Record<string, number> };
type RankPic = { nama: string; peringkat?: number; sekolah: number; fasil: number; selesai: number; harus: number;
  persen: number | null; komponen: Komp[]; belum: number; kendala: number; tl: number; kom: Record<string, number>;
  log_isi: number; log_slot: number; log_persen: number | null; log_kode: Record<string, number>;
  log_hari: LogHari[]; rinci: RinciFasil[]; progres: number | null };
/** Per fasil: n nama, s jumlah sekolah, h kode Log Komunikasi per hari (urut hari_log),
 *  k per komponen [belum, selesai, harus, kendala & TL terisi (sesi mana pun), lalu kendala & TL per sesi urut `blok`]. */
type RinciFasil = { n: string; s: number; h: string[]; k: Record<string, number[]> };
/** Log Komunikasi satu hari, per sekolah: isi = sekolah yang sudah diberi kode. */
type LogHari = { tanggal: string; isi: number; slot: number; kode: Record<string, number> };
type Rank = { pic: RankPic[]; nasional: RankPic; hari_log: string[]; komponen: { kode: string; label: string }[];
  kode_kom: { kode: string; arti: string }[]; berkolom: string[];
  blok: { blok: number; label: string }[]; blok_hari: number[]; dibuat: string };

const NASIONAL = "__semua__";
const fmt = (n: number) => n.toLocaleString("id-ID");
const persen = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${String(Math.round(v * 10) / 10).replace(".", ",")}%`);

function useDash(pic: string, bimtek = "") {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);
  const muat = useCallback(async (paksa = false) => {
    setMemuat(true);
    try {
      const q = new URLSearchParams();
      if (pic && pic !== NASIONAL) q.set("pic", pic);
      if (bimtek) q.set("bimtek", bimtek);
      if (paksa) q.set("paksa", "true");
      setData(await api<Dash>(`/api/dashboard${q.size ? `?${q}` : ""}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, [pic, bimtek]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  return { data, error, memuat, muat };
}

export function DashboardOnline() {
  const [pic, setPic] = useState(NASIONAL);
  const [banding, setBanding] = useState<string | null>(null);
  const [rank, setRank] = useState<Rank | null>(null);
  const [bimtek, setBimtek] = useState("");
  const utama = useDash(pic, bimtek);
  const admin = !!utama.data?.admin;

  useEffect(() => {
    if (!admin) return; // ranking tidak dipakai (komponennya disembunyikan)
    const q = bimtek ? `?bimtek=${encodeURIComponent(bimtek)}` : "";
    api<Rank>(`/api/dashboard/ranking${q}`).then(setRank).catch(() => setRank(null));
  }, [admin, bimtek]);

  const pilihan = utama.data?.pilihan_pic ?? rank?.pic.map((x) => x.nama) ?? [];
  const lihat = (p: string) => { setPic(p); setBanding(null); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const bandingkan = (a: string, b: string) => { setPic(a); setBanding(b); window.scrollTo({ top: 0, behavior: "smooth" }); };

  if (utama.error && !utama.data) return <Notice tone="bad" title="Dashboard tidak bisa dimuat">{utama.error}</Notice>;
  if (!utama.data) return <div className={s.memuat}><Spinner label="Memuat" /> Menghitung dashboard…</div>;
  const x = utama.data;

  return (
    <div className={`${s.halaman} ${utama.memuat ? s.redup : ""}`}>
      <header className={s.kepala}>
        <div>
          <p className={s.eyebrow}>WEEK {x.week}{x.cutoff ? ` · ${x.cutoff}` : ""} · dihitung {x.dibuat}</p>
          <h1>{banding !== null ? "Perbandingan PIC" : x.nasional ? "Dashboard nasional" : `Dashboard ${x.pic}`}
            {x.bimtek ? <small className={s.subJudul}> · {x.bimtek === "-" ? "bukan peserta bimtek" : x.bimtek}</small> : null}</h1>
        </div>
        <div className={s.kontrol}>
          <label className={s.pilih}>
            <span>{banding !== null ? "Kiri" : "Lihat"}</span>
            <PilihPic nilai={pic} ubah={setPic} pilihan={pilihan} />
          </label>
          {(x.pilihan_bimtek?.length ?? 0) > 0 && (
            <label className={s.pilih}>
              <span>Bimtek</span>
              <select value={bimtek} onChange={(e) => setBimtek(e.target.value)} aria-label="Saring Bimtek Pelaporan">
                <option value="">Semua sekolah</option>
                {x.pilihan_bimtek!.map((b) => <option key={b} value={b}>{b}</option>)}
                <option value="-">Bukan peserta bimtek</option>
              </select>
            </label>
          )}
          {banding !== null ? (
            <>
              <label className={s.pilih}>
                <span>Kanan</span>
                <PilihPic nilai={banding} ubah={setBanding} pilihan={pilihan} />
              </label>
              <Button variant="secondary" size="sm" onClick={() => setBanding(null)}>Selesai banding</Button>
            </>
          ) : (
            <>
              {admin && (
                <Button variant="secondary" size="sm"
                  onClick={() => setBanding(pic === NASIONAL ? (pilihan[0] ?? NASIONAL) : NASIONAL)}>Bandingkan</Button>
              )}
              <Button variant="secondary" size="sm" loading={utama.memuat} onClick={() => void utama.muat(true)}>Hitung ulang</Button>
            </>
          )}
        </div>
      </header>

      {banding !== null ? (
        <Banding a={pic} b={banding} rank={rank} dataA={x} bimtek={bimtek} />
      ) : (
        <>
          <Ringkasan x={x} />
          <BimtekPanel x={x} aktif={bimtek} pilih={setBimtek} />
          <LogProgresOnline />
          {admin && <Ranking rank={rank} aktif={pic} lihat={lihat} bandingkan={bandingkan} />}
        </>
      )}
    </div>
  );
}

function PilihPic({ nilai, ubah, pilihan }: { nilai: string; ubah: (v: string) => void; pilihan: string[] }) {
  return (
    <select value={nilai} onChange={(e) => ubah(e.target.value)} aria-label="Pilih PIC">
      <option value={NASIONAL}>Nasional (semua PIC)</option>
      {pilihan.map((p) => <option key={p} value={p}>{p}</option>)}
    </select>
  );
}

/** Urutan: kartu ringkas → sebaran → capaian → progres & komunikasi. */
function Ringkasan({ x }: { x: Dash }) {
  const di = x.distribusi;
  return (
    <>
      <section className={s.kpi5}>
        <Kpi label="Sekolah binaan" nilai={fmt(di.sekolah)} ket={`${fmt(x.lengkap)} sekolah tuntas`} aksen />
        <Kpi label="PTN" nilai={fmt(di.jml_ptn)} ket="perguruan tinggi pendamping" />
        <Kpi label="Koordinator" nilai={fmt(di.koor)} ket="koordinator fasil" />
        <Kpi label="Fasilitator" nilai={fmt(di.fasil)}
          ket={`rata-rata ${String(di.rata_sekolah_per_fasil).replace(".", ",")} sekolah per fasil`} />
        <Kpi label="Kabupaten/kota" nilai={fmt(di.jml_kab)} ket={`${fmt(di.provinsi.length)}+ provinsi`} />
      </section>

      <div className={s.tiga}>
        <section className={d.card}><div className={d.cardHead}><h2>Angkatan</h2><span>jumlah sekolah</span></div><Batang data={di.angkatan} /></section>
        <section className={d.card}><div className={d.cardHead}><h2>Sebaran provinsi</h2><span>8 teratas</span></div><Batang data={di.provinsi} /></section>
        <section className={d.card}><div className={d.cardHead}><h2>Sebaran PTN</h2><span>8 teratas</span></div><Batang data={di.ptn} /></section>
      </div>

      <section className={d.card}>
        <div className={d.cardHead}><h2>Capaian per komponen</h2><span>% sekolah selesai dari yang seharusnya (sudah due)</span></div>
        <Capaian data={x.capaian} rata={{}} />
      </section>

      <div className={s.duaSeimbang}>
        <section className={d.card}>
          <div className={d.cardHead}><h2>Sebaran progres fisik</h2>
            <span>rata-rata {persen(x.progres.rata)} · {fmt(x.progres.ada)} sekolah melapor</span></div>
          <Batang data={x.progres.sebaran} />
        </section>
        <section className={d.card}>
          <div className={d.cardHead}><h2>Frekuensi komunikasi</h2><span>fasil per kode Log Komunikasi, per hari</span></div>
          <Komunikasi data={x.komunikasi} />
        </section>
      </div>
    </>
  );
}

/* ---------- ranking ---------- */

/** Urutan kode komunikasi dari yang paling baik; "-" = belum ada catatan di Log Komunikasi. */
const URUT_KODE = ["T", "TP", "T1", "T2", "R", "C2", "C", "N", "-"];
const KELAS_KODE: Record<string, string> = {
  T: s.kT, TP: s.kTP, T1: s.kT1, T2: s.kT1, R: s.kR, C2: s.kC, C: s.kC, N: s.kN, "-": s.kKosong,
};
const kelasKode = (k: string) => KELAS_KODE[k] ?? s.kC;
const HARI_PENDEK = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"];
const tglPendek = (iso: string) => { const t = new Date(`${iso}T00:00:00`); return `${HARI_PENDEK[t.getDay()]} ${iso.slice(8, 10)}/${iso.slice(5, 7)}`; };
const bagi = (a: number | null, b: number) => (a === null || !b ? null : a / b * 100);
const tambah = (c: Record<string, number>, k: string, n = 1) => { c[k] = (c[k] ?? 0) + n; };

/** hari = indeks hari_log; sesi = indeks `blok` yang memuat hari-hari itu (isian Kendala/TL per sesi). */
type Filter = { komp: string[]; kode: string[]; hari: number[]; sesi: number[]; nSesi: number };

/** Posisi kendala & TL di array komponen fasil untuk sesi terpilih (semua sesi = gabungan, dihitung per sekolah). */
const posIsian = (f: Filter) => (f.sesi.length === 1 && f.nSesi > 1 ? 5 + 2 * f.sesi[0] : 3);

/** Hasil satu PIC (atau gabungan) untuk kombinasi filter. */
type Hasil = {
  selesai: number; harus: number; fasilBelum: number; cocok: number; belum: number; kendala: number | null; tl: number | null;
  kom: Record<string, number>; logIsi: number; logSlot: number; logKode: Record<string, number>; fasil: FasilCocok[];
};
type FasilCocok = { f: RinciFasil; belum: number; kendala: number; tl: number; kode: string[] };

function hitungFilter(rinci: RinciFasil[], f: Filter, semuaKomp: string[], berkolom: Set<string>, simpanFasil: boolean): Hasil {
  const komps = f.komp.length ? f.komp : semuaKomp;
  const adaKolom = komps.some((k) => berkolom.has(k));
  const pos = posIsian(f);
  const h: Hasil = { selesai: 0, harus: 0, fasilBelum: 0, cocok: 0, belum: 0, kendala: adaKolom ? 0 : null, tl: adaKolom ? 0 : null,
    kom: {}, logIsi: 0, logSlot: 0, logKode: {}, fasil: [] };
  for (const x of rinci) {
    const kode = f.hari.map((i) => x.h[i] || "-");
    const kodeCocok = !f.kode.length || kode.some((k) => f.kode.includes(k));
    // Log Komunikasi: semua fasil, hari terpilih
    for (const k of kode) {
      h.logSlot += 1;
      if (k !== "-") { h.logIsi += 1; tambah(h.logKode, k); }
    }
    if (!kodeCocok) continue;
    let belum = 0, kendala = 0, tl = 0;
    for (const kp of komps) {
      const v = x.k[kp];
      if (!v) continue;
      belum += v[0]; h.selesai += v[1]; h.harus += v[2];
      if (berkolom.has(kp)) { kendala += v[pos] ?? 0; tl += v[pos + 1] ?? 0; }
    }
    if (!belum) continue;
    h.cocok += 1;
    h.belum += belum;
    if (h.kendala !== null) h.kendala += kendala;
    if (h.tl !== null) h.tl += tl;
    for (const k of kode) tambah(h.kom, k);
    if (simpanFasil) h.fasil.push({ f: x, belum, kendala, tl, kode });
  }
  // fasil yang punya sekolah belum (tanpa filter komunikasi), pembanding kolom "Fasil cocok"
  h.fasilBelum = rinci.filter((x) => komps.some((kp) => (x.k[kp]?.[0] ?? 0) > 0)).length;
  return h;
}

type Urut = "persen" | "cocok" | "kendala" | "tl" | "log" | "progres" | "nama";

function Ranking({ rank, aktif, lihat, bandingkan }: { rank: Rank | null; aktif: string; lihat: (p: string) => void;
  bandingkan: (a: string, b: string) => void }) {
  const [komp, setKomp] = useState<string[]>([]);
  const [kode, setKode] = useState<string[]>([]);
  const [hariPilih, setHariPilih] = useState<number[] | null>(null); // null = hari terakhir
  const [urut, setUrut] = useState<Urut>("persen");
  const [pilih, setPilih] = useState<string[]>([]);
  const [buka, setBuka] = useState<string | null>(null);

  const nHari = rank?.hari_log.length ?? 0;
  const hari = useMemo(() => hariPilih ?? (nHari ? [nHari - 1] : []), [hariPilih, nHari]);
  const filter = useMemo<Filter>(() => {
    const blokIdx = (rank?.blok ?? []).map((b) => b.blok);
    const sesi = [...new Set(hari.map((i) => blokIdx.indexOf(rank?.blok_hari[i] ?? -1)).filter((j) => j >= 0))].sort();
    return { komp, kode, hari, sesi, nSesi: blokIdx.length };
  }, [komp, kode, hari, rank]);
  const semuaKomp = useMemo(() => rank?.komponen.map((k) => k.kode) ?? [], [rank]);
  const berkolom = useMemo(() => new Set(rank?.berkolom ?? []), [rank]);

  const hasil = useMemo(() => {
    const m = new Map<string, Hasil>();
    for (const p of rank?.pic ?? []) m.set(p.nama, hitungFilter(p.rinci, filter, semuaKomp, berkolom, true));
    return m;
  }, [rank, filter, semuaKomp, berkolom]);
  const nas = useMemo(() => hitungFilter((rank?.pic ?? []).flatMap((p) => p.rinci), filter, semuaKomp, berkolom, false),
    [rank, filter, semuaKomp, berkolom]);

  const baris = useMemo(() => {
    if (!rank) return [];
    const nilai = (p: RankPic) => {
      const h = hasil.get(p.nama)!;
      if (urut === "cocok") return h.cocok;
      if (urut === "kendala") return bagi(h.kendala, h.belum) ?? -1;
      if (urut === "tl") return bagi(h.tl, h.belum) ?? -1;
      if (urut === "log") return bagi(h.logIsi, h.logSlot) ?? -1;
      if (urut === "progres") return p.progres ?? -1;
      return bagi(h.selesai, h.harus) ?? -1;
    };
    const out = [...rank.pic];
    if (urut === "nama") out.sort((a, b) => a.nama.localeCompare(b.nama));
    else out.sort((a, b) => nilai(b) - nilai(a) || a.nama.localeCompare(b.nama));
    return out;
  }, [rank, urut, hasil]);

  if (!rank) return <section className={d.card}><div className={s.memuat}><Spinner label="Memuat" /> Menyusun ranking PIC…</div></section>;

  const arti = Object.fromEntries(rank.kode_kom.map((k) => [k.kode, k.arti])) as Record<string, string>;
  arti["-"] = "Belum ada catatan di Log Komunikasi";
  const labelKomp = Object.fromEntries(rank.komponen.map((k) => [k.kode, k.label])) as Record<string, string>;
  const ubah = <T,>(daftar: T[], v: T) => (daftar.includes(v) ? daftar.filter((x) => x !== v) : [...daftar, v]);
  const ubahHari = (i: number) => {
    const baru = ubah(hari, i).sort((a, b) => a - b);
    setHariPilih(baru.length ? baru : null);
  };
  const adaFilter = komp.length > 0 || kode.length > 0 || hariPilih !== null;
  const centang = (n: string) => setPilih((p) => p.includes(n) ? p.filter((x) => x !== n) : [...p.slice(-1), n]);
  const th = (u: Urut, teks: string, panah = "↓") => (
    <button type="button" className={s.thTombol} onClick={() => setUrut(u)}>{teks}{urut === u ? ` ${panah}` : ""}</button>
  );
  const teksKomp = komp.length ? komp.map((k) => labelKomp[k]).join(", ") : "semua komponen";
  const teksHari = hari.map((i) => tglPendek(rank.hari_log[i])).join(", ");
  const teksKode = kode.length ? kode.map((k) => (k === "-" ? "belum ada" : k)).join(", ") : "";
  const nasCapai = bagi(nas.selesai, nas.harus);

  return (
    <section className={d.card}>
      <div className={d.cardHead}>
        <h2>Ranking PIC</h2>
        <span>dihitung {rank.dibuat} · klik judul kolom untuk mengurutkan</span>
      </div>

      <div className={s.filter}>
        <div className={s.filterBaris} role="group" aria-label="Filter komponen">
          <span className={s.filterLabel}>Komponen</span>
          <button type="button" aria-pressed={!komp.length} onClick={() => setKomp([])}>Semua</button>
          {rank.komponen.map((k) => (
            <button key={k.kode} type="button" aria-pressed={komp.includes(k.kode)} onClick={() => setKomp(ubah(komp, k.kode))}>{k.label}</button>
          ))}
        </div>
        <div className={s.filterBaris} role="group" aria-label="Filter komunikasi">
          <span className={s.filterLabel}>Komunikasi</span>
          <button type="button" aria-pressed={!kode.length} onClick={() => setKode([])}>Semua</button>
          {URUT_KODE.map((k) => (
            <button key={k} type="button" aria-pressed={kode.includes(k)} title={arti[k]} onClick={() => setKode(ubah(kode, k))}>
              <i className={kelasKode(k)} />{k === "-" ? "Belum ada" : k}
            </button>
          ))}
        </div>
        <div className={s.filterBaris} role="group" aria-label="Filter hari">
          <span className={s.filterLabel}>Hari</span>
          <button type="button" aria-pressed={hari.length === nHari} onClick={() => setHariPilih(rank.hari_log.map((_, i) => i))}>Semua</button>
          {rank.hari_log.map((t, i) => (
            <button key={t} type="button" aria-pressed={hari.includes(i)} onClick={() => ubahHari(i)}>{tglPendek(t)}</button>
          ))}
        </div>
        <p className={s.filterRingkas}>
          Menampilkan <b>{teksKomp}</b>{teksKode ? <> · fasil berkode <b>{teksKode}</b></> : null} · hari <b>{teksHari}</b>
          {" "}· isian Kendala/TL <b>{filter.sesi.length === 1 && filter.nSesi > 1 ? `sesi ${rank.blok[filter.sesi[0]].label}` : "semua sesi WEEK ini"}</b>
          {adaFilter && <> · <button type="button" className={s.tautanKecil}
            onClick={() => { setKomp([]); setKode([]); setHariPilih(null); }}>Reset filter</button></>}
        </p>
      </div>

      <div className={s.rankAlat}>
        <span className={s.legendaRank}>
          <i className={s.tBaik} /> di atas nasional <i className={s.tSedang} /> sekitar nasional <i className={s.tKurang} /> di bawah nasional
        </span>
        {pilih.length === 2 ? (
          <Button size="sm" onClick={() => { bandingkan(pilih[0], pilih[1]); setPilih([]); }}>Bandingkan {pilih.length} PIC</Button>
        ) : <span className={s.ketKecil}>Centang 2 PIC untuk membandingkan</span>}
      </div>

      <div className={s.gulir}>
        <table className={s.tabel}>
          <thead>
            <tr>
              <th aria-label="Pilih" />
              <th className={s.angka}>#</th>
              <th>{th("nama", "PIC", "↑")}</th>
              <th className={s.angka}>Sekolah</th>
              <th>{th("persen", "Capaian")}</th>
              <th className={s.angka} title="Fasil yang punya sekolah belum selesai (dan cocok dengan filter komunikasi)">{th("cocok", "Fasil")}</th>
              <th className={s.angka} title="Dari sekolah yang belum selesai pada fasil tersebut">{th("kendala", "Kendala terisi")}</th>
              <th className={s.angka}>{th("tl", "TL terisi")}</th>
              <th>Komunikasi fasil</th>
              <th className={s.angka}>{th("log", "Log Komunikasi")}</th>
              <th className={s.angka}>{th("progres", "Progres fisik")}</th>
            </tr>
          </thead>
          <tbody>
            {baris.map((p, i) => {
              const h = hasil.get(p.nama)!;
              const terbuka = buka === p.nama;
              const tutupBuka = () => setBuka(terbuka ? null : p.nama);
              return (
                <Fragment key={p.nama}>
                  <tr className={p.nama === aktif ? s.barisAktif : undefined}>
                    <td><input type="checkbox" checked={pilih.includes(p.nama)} onChange={() => centang(p.nama)} aria-label={`Pilih ${p.nama}`} /></td>
                    <td className={s.angka}>{i + 1}</td>
                    <td><button type="button" className={s.tautan} onClick={() => lihat(p.nama)}>{p.nama}</button>
                      <small>{fmt(p.fasil)} fasil · <button type="button" className={s.tautanKecil} aria-expanded={terbuka}
                        onClick={tutupBuka}>{terbuka ? "Tutup detail ▴" : "Detail ▾"}</button></small></td>
                    <td className={s.angka}>{fmt(p.sekolah)}</td>
                    <td><Rasio a={h.selesai} b={h.harus} v={bagi(h.selesai, h.harus)} acuan={nasCapai} /></td>
                    <td className={s.angka}><button type="button" className={s.selTombol} onClick={tutupBuka} title="Lihat daftar fasil">
                      <b>{fmt(h.cocok)}</b><small>{kode.length ? `dari ${fmt(h.fasilBelum)} fasil` : "fasil punya sekolah belum"}</small></button></td>
                    <td className={s.angka}><Terisi a={h.kendala} b={h.belum} acuan={bagi(nas.kendala, nas.belum)} /></td>
                    <td className={s.angka}><Terisi a={h.tl} b={h.belum} acuan={bagi(nas.tl, nas.belum)} /></td>
                    <td><BatangKode kom={h.kom} arti={arti} sorot={kode} satuan={hari.length > 1 ? "fasil-hari" : "fasil"} /></td>
                    <td className={s.angka}><button type="button" className={s.selTombol} onClick={tutupBuka} title="Lihat rincian per hari">
                      <span className={nada(bagi(h.logIsi, h.logSlot), bagi(nas.logIsi, nas.logSlot))}>{persen(bagi(h.logIsi, h.logSlot))}</span>
                      <small>{fmt(h.logIsi)}/{fmt(h.logSlot)} {hari.length > 1 ? "fasil-hari" : "fasil"}{h.logKode.TP ? ` · ${fmt(h.logKode.TP)} ditelepon` : ""}</small>
                    </button></td>
                    <td className={s.angka}>{persen(p.progres)}</td>
                  </tr>
                  {terbuka && (
                    <tr className={s.barisDetail}>
                      <td colSpan={11}><DetailPic p={p} h={h} filter={filter} rank={rank} arti={arti} berkolom={berkolom} /></td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td /><td /><td>Semua PIC</td><td className={s.angka}>{fmt(rank.pic.reduce((a, p) => a + p.sekolah, 0))}</td>
              <td><Rasio a={nas.selesai} b={nas.harus} v={nasCapai} acuan={null} /></td>
              <td className={s.angka}><b>{fmt(nas.cocok)}</b>{kode.length ? <small>dari {fmt(nas.fasilBelum)} fasil</small> : null}</td>
              <td className={s.angka}><Terisi a={nas.kendala} b={nas.belum} acuan={null} /></td>
              <td className={s.angka}><Terisi a={nas.tl} b={nas.belum} acuan={null} /></td>
              <td><BatangKode kom={nas.kom} arti={arti} sorot={kode} satuan={hari.length > 1 ? "fasil-hari" : "fasil"} /></td>
              <td className={s.angka}>{persen(bagi(nas.logIsi, nas.logSlot))}<small>{fmt(nas.logIsi)}/{fmt(nas.logSlot)}</small></td>
              <td className={s.angka}>{persen(rank.nasional.progres)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function Terisi({ a, b, acuan }: { a: number | null; b: number; acuan: number | null }) {
  if (a === null) return <span className={s.ketKecil}>tanpa kolom</span>;
  if (!b) return <span className={s.ketKecil}>–</span>;
  const v = a / b * 100;
  return <><span className={nada(v, acuan)}>{persen(v)}</span><small>{fmt(a)}/{fmt(b)} sekolah</small></>;
}

/** Batang bertumpuk kode komunikasi, plus angka per kode (kode yang difilter ditebalkan). */
function BatangKode({ kom, arti, sorot, satuan }: { kom: Record<string, number>; arti: Record<string, string>; sorot: string[]; satuan: string }) {
  const total = Object.values(kom).reduce((a, b) => a + b, 0);
  if (!total) return <span className={s.ketKecil}>–</span>;
  const ada = URUT_KODE.filter((k) => kom[k]).concat(Object.keys(kom).filter((k) => !URUT_KODE.includes(k)));
  return (
    <div className={s.kom}>
      <span className={s.komBar}>
        {ada.map((k) => <span key={k} className={kelasKode(k)} style={{ width: `${kom[k] / total * 100}%` }}
          title={`${k}: ${fmt(kom[k])} ${satuan} · ${arti[k] ?? ""}`} />)}
      </span>
      <span className={s.komAngka}>
        {ada.map((k) => <span key={k} className={sorot.includes(k) ? s.komSorot : undefined} title={arti[k]}>
          <i className={kelasKode(k)} />{k === "-" ? "–" : k} {fmt(kom[k])}</span>)}
      </span>
    </div>
  );
}

/** Rincian satu PIC mengikuti filter: per komponen, daftar fasil yang cocok, dan Log Komunikasi per hari. */
function DetailPic({ p, h, filter, rank, arti, berkolom }: { p: RankPic; h: Hasil; filter: Filter; rank: Rank;
  arti: Record<string, string>; berkolom: Set<string> }) {
  const satuan = filter.hari.length > 1 ? "fasil-hari" : "fasil";
  const komps = (filter.komp.length ? rank.komponen.filter((k) => filter.komp.includes(k.kode)) : rank.komponen);
  const perKomp = komps.map((k) => ({ k, h: hitungFilter(p.rinci, { ...filter, komp: [k.kode] }, [], berkolom, false) }))
    .filter((x) => x.h.harus);
  const kodeLog = URUT_KODE.filter((k) => p.log_hari.some((x) => x.kode[k]));
  const [semua, setSemua] = useState(false);
  const daftar = semua ? h.fasil : h.fasil.slice(0, 15);
  return (
    <div className={s.detail}>
      <div className={s.detailKiri}>
        <h3>Per komponen</h3>
        <table className={s.tabelDetail}>
          <thead><tr><th>Komponen</th><th className={s.angka}>Belum</th><th className={s.angka}>Kendala terisi</th>
            <th className={s.angka}>TL terisi</th><th>Komunikasi fasil</th></tr></thead>
          <tbody>
            {perKomp.map(({ k, h: x }) => (
              <tr key={k.kode}>
                <td>{k.label}<small>{persen(bagi(x.selesai, x.harus))} selesai</small></td>
                <td className={s.angka}>{fmt(x.belum)}<small>{fmt(x.cocok)} fasil</small></td>
                <td className={s.angka}><Terisi a={x.kendala} b={x.belum} acuan={null} /></td>
                <td className={s.angka}><Terisi a={x.tl} b={x.belum} acuan={null} /></td>
                <td><BatangKode kom={x.kom} arti={arti} sorot={filter.kode} satuan={satuan} /></td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Fasil ({fmt(h.fasil.length)})</h3>
        {h.fasil.length ? (
          <>
            <table className={s.tabelDetail}>
              <thead><tr><th>Fasil</th><th className={s.angka}>Sekolah belum</th><th className={s.angka}>Kendala</th>
                <th className={s.angka}>TL</th><th>Kode {filter.hari.map((i) => tglPendek(rank.hari_log[i])).join(" · ")}</th></tr></thead>
              <tbody>
                {daftar.map((x) => (
                  <tr key={x.f.n}>
                    <td>{x.f.n}<small>{fmt(x.f.s)} sekolah binaan</small></td>
                    <td className={s.angka}>{fmt(x.belum)}</td>
                    <td className={s.angka}>{fmt(x.kendala)}/{fmt(x.belum)}</td>
                    <td className={s.angka}>{fmt(x.tl)}/{fmt(x.belum)}</td>
                    <td><span className={s.kodeHari}>{x.kode.map((k, i) => (
                      <span key={i} className={filter.kode.includes(k) ? s.komSorot : undefined} title={arti[k]}>
                        <i className={kelasKode(k)} />{k === "-" ? "–" : k}</span>))}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {h.fasil.length > 15 && (
              <button type="button" className={s.tautanKecil} onClick={() => setSemua(!semua)}>
                {semua ? "Tampilkan 15 saja" : `Tampilkan semua ${fmt(h.fasil.length)} fasil`}</button>
            )}
          </>
        ) : <p className={s.ketKecil}>Tidak ada fasil yang cocok dengan filter.</p>}
      </div>
      <div>
        <h3>Log Komunikasi per hari</h3>
        <p className={s.ketKecil}>Per fasil ({fmt(p.fasil)} fasil). Kode fasil = kode terbanyak di antara sekolah binaannya hari itu.
          Hari terpilih disorot.</p>
        <div className={s.gulir}>
          <table className={s.tabelDetail}>
            <thead><tr><th>Hari</th><th className={s.angka}>Terisi</th>
              {kodeLog.map((k) => <th key={k} className={s.angka} title={arti[k]}><i className={`${s.titikKode} ${kelasKode(k)}`} />{k}</th>)}</tr></thead>
            <tbody>
              {p.log_hari.map((x, i) => ({ x, i })).reverse().map(({ x, i }) => (
                <tr key={x.tanggal} className={filter.hari.includes(i) ? s.barisAktif : undefined}>
                  <td>{tglPendek(x.tanggal)}</td>
                  <td className={s.angka}>{persen(bagi(x.isi, x.slot))}<small>{fmt(x.isi)}/{fmt(x.slot)}</small></td>
                  {kodeLog.map((k) => <td key={k} className={s.angka}>{x.kode[k] ? fmt(x.kode[k]) : <span className={s.ketKecil}>–</span>}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function nada(v: number | null, acuan: number | null) {
  if (v === null || acuan === null) return undefined;
  return v >= acuan + 3 ? s.tBaikT : v <= acuan - 3 ? s.tKurangT : s.tSedangT;
}

function Rasio({ a, b, v, acuan }: { a: number; b: number; v: number | null; acuan: number | null }) {
  if (!b) return <span className={s.ketKecil}>belum due</span>;
  const kelas = acuan === null ? s.tNetral : v !== null && v >= acuan + 3 ? s.tBaik : v !== null && v <= acuan - 3 ? s.tKurang : s.tSedang;
  return (
    <div className={s.rasio} title={`${fmt(a)} dari ${fmt(b)} yang seharusnya`}>
      <span className={s.rasioBar}>
        <span className={kelas} style={{ width: `${Math.min(100, v ?? 0)}%` }} />
        {acuan !== null && <em style={{ left: `${Math.min(100, acuan)}%` }} title={`Nasional ${persen(acuan)}`} />}
      </span>
      <b>{persen(v)}</b>
      <small>{fmt(a)}/{fmt(b)}</small>
    </div>
  );
}

/* ---------- banding kiri-kanan ---------- */

function Banding({ a, b, rank, dataA, bimtek }: { a: string; b: string; rank: Rank | null; dataA: Dash; bimtek: string }) {
  const kanan = useDash(b, bimtek);
  const cari = (p: string) => (p === NASIONAL ? rank?.nasional : rank?.pic.find((x) => x.nama === p)) ?? null;
  const ra = cari(a), rb = cari(b);
  const namaA = a === NASIONAL ? "Nasional" : a, namaB = b === NASIONAL ? "Nasional" : b;

  return (
    <>
      {ra && rb && (
        <section className={d.card}>
          <div className={d.cardHead}><h2>Selisih</h2><span>sudah diisi ÷ yang seharusnya · ▲▼ = kiri dibanding kanan</span></div>
          <div className={s.gulir}>
            <table className={s.tabel}>
              <thead><tr><th>Ukuran</th><th>{namaA}</th><th>{namaB}</th><th className={s.angka}>Selisih</th></tr></thead>
              <tbody>
                <BarisBanding label="Semua komponen" a={ra.persen} b={rb.persen} ka={`${fmt(ra.selesai)}/${fmt(ra.harus)}`} kb={`${fmt(rb.selesai)}/${fmt(rb.harus)}`} tebal />
                {ra.komponen.map((k, i) => {
                  const kb = rb.komponen[i];
                  if (!k.harus && !kb?.harus) return null;
                  return <BarisBanding key={k.kode} label={k.label} a={k.persen} b={kb?.persen ?? null}
                    ka={`${fmt(k.selesai)}/${fmt(k.harus)}`} kb={kb ? `${fmt(kb.selesai)}/${fmt(kb.harus)}` : ""} />;
                })}
                <BarisBanding label="Pengisian Log Komunikasi" a={ra.log_persen} b={rb.log_persen}
                  ka={`${fmt(ra.log_isi)}/${fmt(ra.log_slot)}`} kb={`${fmt(rb.log_isi)}/${fmt(rb.log_slot)}`} tebal />
                <BarisBanding label="Progres fisik rata-rata" a={ra.progres} b={rb.progres} ka="" kb="" />
              </tbody>
            </table>
          </div>
        </section>
      )}
      <div className={s.banding}>
        <Kolom judul={namaA} x={dataA} />
        {kanan.data ? <Kolom judul={namaB} x={kanan.data} />
          : kanan.error ? <Notice tone="bad">{kanan.error}</Notice>
          : <div className={s.memuat}><Spinner label="Memuat" /> Menghitung {namaB}…</div>}
      </div>
    </>
  );
}

function BarisBanding({ label, a, b, ka, kb, tebal }: { label: string; a: number | null; b: number | null; ka: string; kb: string; tebal?: boolean }) {
  const beda = a !== null && b !== null ? a - b : null;
  return (
    <tr className={tebal ? s.barisTebal : undefined}>
      <td>{label}</td>
      <td><b>{persen(a)}</b> <small className={s.inline}>{ka}</small></td>
      <td><b>{persen(b)}</b> <small className={s.inline}>{kb}</small></td>
      <td className={s.angka}>{beda === null ? "–" : (
        <span className={beda >= 0.05 ? s.tBaikT : beda <= -0.05 ? s.tKurangT : undefined}>
          {beda >= 0.05 ? "▲ " : beda <= -0.05 ? "▼ " : ""}{String(Math.abs(Math.round(beda * 10) / 10)).replace(".", ",")} poin
        </span>)}</td>
    </tr>
  );
}

function Kolom({ judul, x }: { judul: string; x: Dash }) {
  const di = x.distribusi;
  return (
    <div className={s.kolomBanding}>
      <h2 className={s.judulKolom}>{judul}</h2>
      <section className={s.kpi2}>
        <Kpi label="Sekolah" nilai={fmt(di.sekolah)} ket={`${fmt(x.lengkap)} tuntas`} aksen />
        <Kpi label="Fasilitator" nilai={fmt(di.fasil)} ket={`${fmt(di.koor)} koordinator · ${fmt(di.jml_ptn)} PTN`} />
      </section>
      <section className={d.card}><div className={d.cardHead}><h2>Capaian per komponen</h2></div><Capaian data={x.capaian} rata={{}} /></section>
      <section className={d.card}><div className={d.cardHead}><h2>Sebaran progres fisik</h2><span>rata-rata {persen(x.progres.rata)}</span></div>
        <Batang data={x.progres.sebaran} /></section>
      <section className={d.card}><div className={d.cardHead}><h2>Frekuensi komunikasi</h2></div><Komunikasi data={x.komunikasi} /></section>
      <section className={d.card}><div className={d.cardHead}><h2>Sebaran PTN</h2></div><Batang data={di.ptn} /></section>
    </div>
  );
}
