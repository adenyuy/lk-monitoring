"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button, Notice, Spinner } from "@/components/ui";
import { Batang, Capaian, Komunikasi, Kpi, type Dash } from "@/components/dashboard/DashboardView";
import d from "@/components/dashboard/dashboard.module.css";
import { LogProgresOnline } from "./LogProgresOnline";
import s from "./online.module.css";

type Komp = { kode: string; label: string; selesai: number; harus: number; persen: number | null };
type RankPic = { nama: string; peringkat?: number; sekolah: number; fasil: number; selesai: number; harus: number;
  persen: number | null; komponen: Komp[]; log_isi: number; log_slot: number; log_persen: number | null; progres: number | null };
type Rank = { pic: RankPic[]; nasional: RankPic; hari_log: string[]; komponen: { kode: string; label: string }[]; dibuat: string };

const NASIONAL = "__semua__";
const fmt = (n: number) => n.toLocaleString("id-ID");
const persen = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${String(Math.round(v * 10) / 10).replace(".", ",")}%`);

function useDash(pic: string) {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);
  const muat = useCallback(async (paksa = false) => {
    setMemuat(true);
    try {
      const q = new URLSearchParams();
      if (pic && pic !== NASIONAL) q.set("pic", pic);
      if (paksa) q.set("paksa", "true");
      setData(await api<Dash>(`/api/dashboard${q.size ? `?${q}` : ""}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, [pic]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  return { data, error, memuat, muat };
}

export function DashboardOnline() {
  const [pic, setPic] = useState(NASIONAL);
  const [banding, setBanding] = useState<string | null>(null);
  const [rank, setRank] = useState<Rank | null>(null);
  const utama = useDash(pic);

  useEffect(() => { api<Rank>("/api/ranking").then(setRank).catch(() => setRank(null)); }, []);

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
          <h1>{banding !== null ? "Perbandingan PIC" : x.nasional ? "Dashboard nasional" : `Dashboard ${x.pic}`}</h1>
        </div>
        <div className={s.kontrol}>
          <label className={s.pilih}>
            <span>{banding !== null ? "Kiri" : "Lihat"}</span>
            <PilihPic nilai={pic} ubah={setPic} pilihan={pilihan} />
          </label>
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
              <Button variant="secondary" size="sm"
                onClick={() => setBanding(pic === NASIONAL ? (pilihan[0] ?? NASIONAL) : NASIONAL)}>Bandingkan</Button>
              <Button variant="secondary" size="sm" loading={utama.memuat} onClick={() => void utama.muat(true)}>Hitung ulang</Button>
            </>
          )}
        </div>
      </header>

      {banding !== null ? (
        <Banding a={pic} b={banding} rank={rank} dataA={x} />
      ) : (
        <>
          <Ringkasan x={x} />
          <LogProgresOnline />
          <Ranking rank={rank} aktif={pic} lihat={lihat} bandingkan={bandingkan} />
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

type Urut = "persen" | "log" | "progres" | "nama";

function Ranking({ rank, aktif, lihat, bandingkan }: { rank: Rank | null; aktif: string; lihat: (p: string) => void;
  bandingkan: (a: string, b: string) => void }) {
  const [komp, setKomp] = useState("");
  const [urut, setUrut] = useState<Urut>("persen");
  const [pilih, setPilih] = useState<string[]>([]);

  const baris = useMemo(() => {
    if (!rank) return [];
    const nilai = (p: RankPic) => {
      if (urut === "log") return p.log_persen ?? -1;
      if (urut === "progres") return p.progres ?? -1;
      if (komp) return p.komponen.find((k) => k.kode === komp)?.persen ?? -1;
      return p.persen ?? -1;
    };
    const out = [...rank.pic];
    if (urut === "nama") out.sort((a, b) => a.nama.localeCompare(b.nama));
    else out.sort((a, b) => nilai(b) - nilai(a) || a.nama.localeCompare(b.nama));
    return out;
  }, [rank, komp, urut]);

  if (!rank) return <section className={d.card}><div className={s.memuat}><Spinner label="Memuat" /> Menyusun ranking PIC…</div></section>;

  const nas = rank.nasional;
  const nasKomp = komp ? nas.komponen.find((k) => k.kode === komp) : null;
  const acuan = komp ? nasKomp?.persen ?? null : nas.persen;
  const label = komp ? rank.komponen.find((k) => k.kode === komp)?.label : "Semua komponen";
  const centang = (n: string) => setPilih((p) => p.includes(n) ? p.filter((x) => x !== n) : [...p.slice(-1), n]);

  return (
    <section className={d.card}>
      <div className={d.cardHead}>
        <h2>Ranking PIC</h2>
        <span>sudah diisi ÷ yang seharusnya (komponen yang sudah due) · dihitung {rank.dibuat}</span>
      </div>
      <div className={s.rankAlat}>
        <label className={s.pilih}>
          <span>Komponen</span>
          <select value={komp} onChange={(e) => { setKomp(e.target.value); setUrut("persen"); }}>
            <option value="">Semua komponen</option>
            {rank.komponen.map((k) => <option key={k.kode} value={k.kode}>{k.label}</option>)}
          </select>
        </label>
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
              <th><button type="button" className={s.thTombol} onClick={() => setUrut("nama")}>PIC{urut === "nama" ? " ↑" : ""}</button></th>
              <th className={s.angka}>Sekolah</th>
              <th><button type="button" className={s.thTombol} onClick={() => setUrut("persen")}>{label}{urut === "persen" ? " ↓" : ""}</button></th>
              <th className={s.angka}><button type="button" className={s.thTombol} onClick={() => setUrut("log")}>
                Log Komunikasi{urut === "log" ? " ↓" : ""}</button></th>
              <th className={s.angka}><button type="button" className={s.thTombol} onClick={() => setUrut("progres")}>
                Progres fisik{urut === "progres" ? " ↓" : ""}</button></th>
            </tr>
          </thead>
          <tbody>
            {baris.map((p, i) => {
              const k = komp ? p.komponen.find((x) => x.kode === komp) : null;
              const a = k ? k.selesai : p.selesai, b = k ? k.harus : p.harus, v = k ? k.persen : p.persen;
              return (
                <tr key={p.nama} className={p.nama === aktif ? s.barisAktif : undefined}>
                  <td><input type="checkbox" checked={pilih.includes(p.nama)} onChange={() => centang(p.nama)} aria-label={`Pilih ${p.nama}`} /></td>
                  <td className={s.angka}>{i + 1}</td>
                  <td><button type="button" className={s.tautan} onClick={() => lihat(p.nama)}>{p.nama}</button>
                    <small>{fmt(p.fasil)} fasil</small></td>
                  <td className={s.angka}>{fmt(p.sekolah)}</td>
                  <td><Rasio a={a} b={b} v={v} acuan={acuan} /></td>
                  <td className={s.angka}><span className={nada(p.log_persen, nas.log_persen)}>{persen(p.log_persen)}</span>
                    <small>{fmt(p.log_isi)}/{fmt(p.log_slot)}</small></td>
                  <td className={s.angka}>{persen(p.progres)}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td /><td /><td>Nasional</td><td className={s.angka}>{fmt(nas.sekolah)}</td>
              <td><Rasio a={nasKomp ? nasKomp.selesai : nas.selesai} b={nasKomp ? nasKomp.harus : nas.harus} v={acuan} acuan={null} /></td>
              <td className={s.angka}>{persen(nas.log_persen)}<small>{rank.hari_log.length} hari kerja</small></td>
              <td className={s.angka}>{persen(nas.progres)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
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

function Banding({ a, b, rank, dataA }: { a: string; b: string; rank: Rank | null; dataA: Dash }) {
  const kanan = useDash(b);
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
