"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { KODE_WARNA, hariPendek } from "@/lib/lk";
import { Notice, Spinner } from "@/components/ui";
import s from "./online.module.css";

type Kendala = { npsn: string; sekolah: string; fasil: string; ptn: string; pic: string; komponen: string; sesi: number;
  kendala: string; tindak_lanjut: string };
type Pic = { nama: string; sekolah: number; fasil: number; terisi: number[]; terakhir: string | null; kendala: number };
type Log = {
  tanggal: string[]; hari_ini: string; week: number; dibuat: string; pic: Pic[];
  kode: { kode: string; arti: string }[];
  kendala_teratas: { kendala: string; jumlah: number }[];
  kendala_terbaru?: Kendala[];
  detail?: { nama: string; fasil: { nama: string; ptn: string; sekolah: number; kode: Record<string, string> }[]; kendala: Kendala[] };
};

const fmt = (n: number) => n.toLocaleString("id-ID");
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);
const tanggalPanjang = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short" }) : "–";

/** Siapa (PIC) mengisi Log Komunikasi fasil yang mana, dan kendala sekolah yang dicatat. Semua dari Sheet LK. */
export function LogOnlineView() {
  const [pic, setPic] = useState("");
  const [d, setD] = useState<Log | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);

  const muat = useCallback(async (p: string) => {
    setMemuat(true);
    try {
      setD(await api<Log>(`/api/log-online${p ? `?pic=${encodeURIComponent(p)}` : ""}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(pic); }, [pic, muat]);

  if (error && !d) return <Notice tone="bad" title="Log tidak bisa dimuat">{error}</Notice>;
  if (!d) return <div className={s.memuat}><Spinner label="Memuat" /> Membaca LK…</div>;

  return (
    <div className={`${s.halaman} ${memuat ? s.redup : ""}`}>
      <header className={s.kepala}>
        <div>
          <p className={s.eyebrow}>WEEK {d.week} · dibaca {d.dibuat}</p>
          <h1>Log pengisian {d.detail ? d.detail.nama : "semua PIC"}</h1>
        </div>
        <label className={s.pilih}>
          <span>Lihat</span>
          <select value={pic} onChange={(e) => setPic(e.target.value)} aria-label="Pilih PIC">
            <option value="">Semua PIC</option>
            {d.pic.map((p) => <option key={p.nama} value={p.nama}>{p.nama}</option>)}
          </select>
        </label>
      </header>

      {d.detail ? <DetailPic d={d} /> : <SemuaPic d={d} pilih={setPic} />}
    </div>
  );
}

function Sel({ a, b }: { a: number; b: number }) {
  const p = pct(a, b);
  const tone = !b ? s.selKosong : p >= 80 ? s.selBaik : p >= 40 ? s.selSedang : p > 0 ? s.selKurang : s.selNol;
  return <td className={`${s.sel} ${tone}`} title={`${a} dari ${b} fasil terisi`}>{b ? `${p}%` : "–"}</td>;
}

function SemuaPic({ d, pilih }: { d: Log; pilih: (p: string) => void }) {
  const total = d.tanggal.map((_, i) => d.pic.reduce((n, p) => n + p.terisi[i], 0));
  const fasil = d.pic.reduce((n, p) => n + p.fasil, 0);
  const maks = Math.max(1, ...d.kendala_teratas.map((x) => x.jumlah));

  return (
    <>
      <section className={s.kartu}>
        <div className={s.kartuKepala}>
          <h2>Pengisian Log Komunikasi per PIC</h2>
          <span>% fasil yang kodenya terisi tiap hari · klik nama untuk detail</span>
        </div>
        <div className={s.gulir}>
          <table className={s.tabel}>
            <thead>
              <tr>
                <th>PIC</th><th className={s.angka}>Fasil</th>
                {d.tanggal.map((t) => <th key={t} className={s.angka}>{hariPendek(t)}</th>)}
                <th>Terakhir diisi</th><th className={s.angka}>Kendala</th>
              </tr>
            </thead>
            <tbody>
              {d.pic.map((p) => (
                <tr key={p.nama} className={s.barisKlik} onClick={() => pilih(p.nama)}>
                  <td><button type="button" className={s.tautan}>{p.nama}</button><small>{fmt(p.sekolah)} sekolah</small></td>
                  <td className={s.angka}>{fmt(p.fasil)}</td>
                  {p.terisi.map((n, i) => <Sel key={d.tanggal[i]} a={n} b={p.fasil} />)}
                  <td className={p.terakhir !== d.hari_ini ? s.redupTeks : undefined}>{tanggalPanjang(p.terakhir)}</td>
                  <td className={s.angka}>{fmt(p.kendala)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Nasional</td><td className={s.angka}>{fmt(fasil)}</td>
                {total.map((n, i) => <Sel key={d.tanggal[i]} a={n} b={fasil} />)}
                <td /><td className={s.angka}>{fmt(d.pic.reduce((n, p) => n + p.kendala, 0))}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <div className={s.dua}>
        <section className={s.kartu}>
          <div className={s.kartuKepala}><h2>Kendala terbanyak</h2><span>seluruh sekolah</span></div>
          {d.kendala_teratas.length === 0 ? <p className={s.kosong}>Belum ada kendala yang dicatat.</p> : (
            <ul className={s.batang}>
              {d.kendala_teratas.map((x) => (
                <li key={x.kendala}>
                  <span title={x.kendala}>{x.kendala}</span>
                  <div><i style={{ width: `${(x.jumlah / maks) * 100}%` }} /></div>
                  <b>{fmt(x.jumlah)}</b>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className={s.kartu}>
          <div className={s.kartuKepala}><h2>Catatan terbaru</h2><span>sesi terakhir lebih dulu</span></div>
          <DaftarKendala data={d.kendala_terbaru ?? []} tampilPic ringkas />
        </section>
      </div>
    </>
  );
}

function DetailPic({ d }: { d: Log }) {
  const det = d.detail!;
  const p = d.pic.find((x) => x.nama === det.nama);
  const ratarata = p && p.fasil ? Math.round(p.terisi.reduce((n, x) => n + pct(x, p.fasil), 0) / Math.max(1, p.terisi.length)) : 0;

  return (
    <>
      <section className={s.kpi}>
        <div><span>Fasilitator</span><b>{fmt(det.fasil.length)}</b><small>{fmt(p?.sekolah ?? 0)} sekolah</small></div>
        <div><span>Rata-rata pengisian</span><b>{ratarata}%</b><small>{d.tanggal.length} hari kerja terakhir</small></div>
        <div><span>Terakhir diisi</span><b>{tanggalPanjang(p?.terakhir ?? null)}</b><small>Log Komunikasi</small></div>
        <div><span>Kendala dicatat</span><b>{fmt(p?.kendala ?? 0)}</b><small>isian petugas, tanpa teks otomatis</small></div>
      </section>

      <section className={s.kartu}>
        <div className={s.kartuKepala}>
          <h2>Log Komunikasi per fasil</h2>
          <span className={s.legenda}>
            {d.kode.filter((k) => KODE_WARNA[k.kode]).map((k) => (
              <i key={k.kode} style={{ background: KODE_WARNA[k.kode].bg, color: KODE_WARNA[k.kode].fg }} title={k.arti}>{k.kode}</i>
            ))}
          </span>
        </div>
        <div className={s.gulir}>
          <table className={s.tabel}>
            <thead>
              <tr><th>Fasil</th><th className={s.angka}>Sekolah</th>{d.tanggal.map((t) => <th key={t} className={s.angka}>{hariPendek(t)}</th>)}</tr>
            </thead>
            <tbody>
              {det.fasil.map((f) => (
                <tr key={f.nama + f.ptn}>
                  <td>{f.nama}<small>{f.ptn}</small></td>
                  <td className={s.angka}>{f.sekolah}</td>
                  {d.tanggal.map((t) => {
                    const k = f.kode[t];
                    const w = k ? KODE_WARNA[k] : undefined;
                    return <td key={t} className={s.kode}>
                      {k ? <i style={w ? { background: w.bg, color: w.fg } : undefined} title={w?.label}>{k}</i> : <em>·</em>}
                    </td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={s.kartu}>
        <div className={s.kartuKepala}><h2>Kendala &amp; tindak lanjut sekolah</h2><span>{fmt(det.kendala.length)} catatan</span></div>
        <DaftarKendala data={det.kendala} />
      </section>
    </>
  );
}

function DaftarKendala({ data, tampilPic = false, ringkas = false }: { data: Kendala[]; tampilPic?: boolean; ringkas?: boolean }) {
  const [cari, setCari] = useState("");
  const [batas, setBatas] = useState(ringkas ? 8 : 30);
  const hasil = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return q ? data.filter((x) => `${x.sekolah} ${x.fasil} ${x.komponen} ${x.kendala} ${x.tindak_lanjut}`.toLowerCase().includes(q)) : data;
  }, [cari, data]);

  if (!data.length) return <p className={s.kosong}>Belum ada kendala yang dicatat.</p>;
  return (
    <>
      {!ringkas && (
        <input className={s.cari} type="search" placeholder="Cari sekolah, fasil, komponen, atau isi kendala…"
          value={cari} onChange={(e) => setCari(e.target.value)} />
      )}
      <ul className={s.catatan}>
        {hasil.slice(0, batas).map((x, i) => (
          <li key={`${x.npsn}-${x.komponen}-${x.sesi}-${i}`}>
            <div className={s.catatanKepala}>
              <b>{x.sekolah}</b>
              <span>{x.komponen} · sesi {x.sesi}</span>
            </div>
            <small>Fasil {x.fasil}{tampilPic ? ` · PIC ${x.pic}` : ""}</small>
            {x.kendala && <p><em>Kendala</em>{x.kendala}</p>}
            {x.tindak_lanjut && <p><em>Tindak lanjut</em>{x.tindak_lanjut}</p>}
          </li>
        ))}
      </ul>
      {hasil.length > batas && (
        <button type="button" className={s.lagi} onClick={() => setBatas((b) => b + 30)}>
          Tampilkan lagi ({fmt(hasil.length - batas)} tersisa)
        </button>
      )}
      {!hasil.length && <p className={s.kosong}>Tidak ada yang cocok.</p>}
    </>
  );
}
