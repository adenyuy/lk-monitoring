"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./cutoff2.module.css";

type Status = { jalan: boolean; langkah: string; persen: number; hasil: null | { tab: string; sekolah: number; baru: number;
  keterangan: number; cutoff: string }; error: string };
type LogBaris = { kelompok: string; komponen: string; nilai: string[] };
type Info = {
  weeks: number[]; week_aktif: number | null; senin_baru: string; cutoff_terakhir: string;
  riwayat: { waktu: string; week: string; file: string; sekolah: string; baru: string; oleh: string }[];
  log_progres: { cutoff: string[]; baris: LogBaris[] };
  status: Status; kolom_wajib: string[];
};
type Cek = { token: string; file: string; week: number; tab: string; sekolah_file: number; sekolah_lk: number; cocok: number;
  baru: number; tidak_di_file: number; berubah: { kolom: string; jumlah: number }[];
  naik_selesai: { komponen: string; jumlah: number }[]; bku_bpp: boolean };

const fmt = (n: number | string) => Number(n).toLocaleString("id-ID");

/** Tahap penulisan cutoff, sesuai persen yang dilaporkan server. */
const TAHAP_TULIS: { sampai: number; label: string }[] = [
  { sampai: 10, label: "Memperbarui komponen sekolah" },
  { sampai: 25, label: "Menambah sekolah baru" },
  { sampai: 40, label: "Mengurutkan per PIC" },
  { sampai: 55, label: "Menulis keterangan otomatis" },
  { sampai: 80, label: "Mengisi Log Progres" },
  { sampai: 100, label: "Selesai" },
];

export function CutoffView() {
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [cek, setCek] = useState<Cek | null>(null);
  const [tokenTerakhir, setTokenTerakhir] = useState("");
  const [busy, setBusy] = useState(false);
  const [aksiError, setAksiError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [seret, setSeret] = useState(false);
  const [abaikan, setAbaikan] = useState(true); // hasil cutoff sebelumnya tidak ditampilkan sampai ada tulisan baru
  const inputRef = useRef<HTMLInputElement>(null);

  const muat = useCallback(async () => {
    try {
      const r = await api<Info>("/api/cutoff");
      setInfo(r);
      setStatus(r.status);
      setWeek((w) => w ?? r.week_aktif);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  const pantau = useCallback(async () => {
    const r = await api<Status>("/api/cutoff/status");
    setStatus(r);
    if (!r.jalan) void muat();
  }, [muat]);
  usePolling(pantau, 2000, !!status?.jalan);

  async function periksa(f: File) {
    if (!week) return;
    setFile(f);
    setCek(null);
    setAksiError(null);
    setBusy(true);
    const form = new FormData();
    form.append("file", f);
    form.append("week", String(week));
    try {
      setCek(await api<Cek>("/api/cutoff/cek", { method: "POST", body: form }));
    } catch (e) {
      setAksiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function tulis(token = cek?.token) {
    if (!token) return;
    setBusy(true);
    setAksiError(null);
    setTokenTerakhir(token);
    try {
      setStatus(await post<Status>("/api/cutoff/tulis", { token }));
      setAbaikan(false);
      setCek(null);
      setFile(null);
    } catch (e) {
      setAksiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function ulang() {
    setCek(null); setFile(null); setAksiError(null); setAbaikan(true);
  }

  if (error && !info) return <Notice tone="bad" title="Tarik Cutoff tidak bisa dimuat">{error}</Notice>;
  if (!info) return <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>;

  const jalan = !!status?.jalan;
  const tahap: 1 | 2 | 3 = jalan || (!abaikan && (status?.hasil || status?.error)) ? 3 : cek ? 2 : 1;

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Tarik Cutoff</h1>
          <p>Perbarui LK dari export per sekolah. Setiap cutoff otomatis mengisi kolom baru di Log Progres.</p>
        </div>
        <dl className={s.statusLk}>
          <div><dt>WEEK aktif</dt><dd>{info.week_aktif ? `WEEK ${info.week_aktif}` : "–"}</dd></div>
          <div><dt>Cutoff terakhir</dt><dd>{info.cutoff_terakhir || "belum ada"}</dd></div>
        </dl>
      </header>

      <div className={s.layout}>
        <div className={s.utama}>
          <ol className={s.stepper} aria-label="Langkah tarik cutoff">
            {["Unggah file", "Periksa perubahan", "Tulis ke LK"].map((l, i) => {
              const n = i + 1;
              return (
                <li key={l} className={`${s.step} ${tahap === n ? s.stepAktif : ""} ${tahap > n ? s.stepLewat : ""}`}
                  aria-current={tahap === n ? "step" : undefined}>
                  <span className={s.stepNo}>{tahap > n ? "✓" : n}</span>{l}
                </li>
              );
            })}
          </ol>

          {tahap === 1 && (
            <section className={s.card}>
              <div className={s.cardHead}>
                <h2>Unggah export per sekolah</h2>
                <label className={s.week}>
                  <span>Tulis ke</span>
                  <select value={week ?? ""} onChange={(e) => { setWeek(Number(e.target.value)); setCek(null); }}>
                    {info.weeks.map((w) => <option key={w} value={w}>WEEK {w}{w === info.week_aktif ? " (aktif)" : ""}</option>)}
                  </select>
                </label>
              </div>
              <div className={`${s.drop} ${seret ? s.dropAktif : ""} ${busy ? s.dropSibuk : ""}`}
                onDragOver={(e) => { e.preventDefault(); setSeret(true); }} onDragLeave={() => setSeret(false)}
                onDrop={(e) => { e.preventDefault(); setSeret(false); const f = e.dataTransfer.files[0]; if (f && !busy) void periksa(f); }}>
                {busy ? (
                  <>
                    <Spinner label="Memeriksa" />
                    <b>Membandingkan {file?.name} dengan LK…</b>
                    <span>Biasanya kurang dari setengah menit.</span>
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" width="34" height="34" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /><path d="M12 18v-6" /><path d="m9 15 3-3 3 3" /></svg>
                    <b>Seret file CSV atau Excel ke sini</b>
                    <span>Belum ada yang ditulis ke LK sebelum Anda memeriksa perubahannya.</span>
                    <Button size="sm" onClick={() => inputRef.current?.click()} disabled={jalan}>Pilih file</Button>
                  </>
                )}
                <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" hidden
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) void periksa(f); e.target.value = ""; }} />
              </div>
              {aksiError && <Notice tone="bad" title="File belum bisa dipakai">{aksiError}</Notice>}
              <details className={s.wajib}>
                <summary>Kolom yang wajib ada di file ({info.kolom_wajib.length})</summary>
                <ul>{info.kolom_wajib.map((k) => <li key={k}>{k}</li>)}</ul>
              </details>
            </section>
          )}

          {tahap === 2 && cek && (
            <section className={s.card}>
              <div className={s.cardHead}>
                <h2>Periksa sebelum ditulis</h2>
                <span className={s.fileTag}>{cek.file} → {cek.tab}</span>
              </div>
              <div className={s.angka}>
                <div className={s.angkaOk}><b>{fmt(cek.cocok)}</b><span>sekolah cocok & diperbarui</span></div>
                <div><b>{fmt(cek.baru)}</b><span>sekolah baru ditambahkan (PIC kosong)</span></div>
                <div><b>{fmt(cek.tidak_di_file)}</b><span>sekolah LK tidak ada di file (dibiarkan)</span></div>
              </div>
              <div className={s.dua}>
                <div>
                  <h3>Bertambah selesai sejak cutoff lalu</h3>
                  <BatangNaik data={cek.naik_selesai} />
                </div>
                <div>
                  <h3>Kolom yang berubah</h3>
                  {cek.berubah.length ? (
                    <ul className={s.daftar}>{cek.berubah.slice(0, 12).map((x) => <li key={x.kolom}><span>{x.kolom}</span><b>{fmt(x.jumlah)}</b></li>)}</ul>
                  ) : <p className={s.muted}>Tidak ada nilai yang berubah.</p>}
                </div>
              </div>
              <p className={s.catatanTulis}>
                Yang ditulis hanya kolom komponen dan waktu tunggu reviu. PIC, fasil, koordinator, dan identitas sekolah
                mengikuti sheet Penugasan, jadi tidak diubah cutoff. Sekolah baru ditulis lengkap.
              </p>
              {!cek.bku_bpp && <Notice tone="info">File ini belum punya kolom BKU/BPP, jadi isi BKU dan BPP di LK tidak diubah.</Notice>}
              {aksiError && <Notice tone="bad" title="Belum bisa ditulis">{aksiError}</Notice>}
              <div className={s.aksi}>
                <Button variant="ghost" onClick={ulang}>Ganti file</Button>
                <Button loading={busy} onClick={() => void tulis()}>Tulis ke {cek.tab}</Button>
              </div>
            </section>
          )}

          {tahap === 3 && status && (
            <section className={`${s.card} ${jalan ? s.jalan : ""}`} aria-live="polite">
              <div className={s.cardHead}>
                <h2>{jalan ? "Menulis ke LK…" : status.error ? "Penulisan gagal" : `${status.hasil?.cutoff} tersimpan`}</h2>
                {jalan && <span className={s.persen}>{status.persen}%</span>}
              </div>
              <div className={s.bar}><span style={{ width: `${jalan ? status.persen : status.error ? status.persen : 100}%` }} /></div>
              <ol className={s.tahapTulis}>
                {TAHAP_TULIS.map((t, i) => {
                  const mulai = i ? TAHAP_TULIS[i - 1].sampai : 0;
                  const p = status.hasil && !jalan ? 100 : status.persen;
                  const st = p >= t.sampai && (t.sampai < 100 || !jalan) ? "beres" : p >= mulai ? "jalan" : "nanti";
                  return (
                    <li key={t.label} className={s[`t_${status.error && st === "jalan" ? "gagal" : st}`]}>
                      <i aria-hidden="true">{st === "beres" ? "✓" : st === "jalan" && jalan ? <Spinner /> : ""}</i>{t.label}
                    </li>
                  );
                })}
              </ol>
              {jalan && <small className={s.muted}>Untuk belasan ribu sekolah butuh beberapa menit. Halaman ini boleh ditinggal.</small>}
              {!jalan && status.hasil && (
                <Notice tone="ok" title={`${status.hasil.cutoff} tersimpan di ${status.hasil.tab}`}>
                  {fmt(status.hasil.sekolah)} sekolah diperbarui{status.hasil.baru ? `, ${fmt(status.hasil.baru)} sekolah baru` : ""},
                  {" "}{fmt(status.hasil.keterangan)} keterangan otomatis ditulis ulang, dan Log Progres mendapat kolom baru.
                </Notice>
              )}
              {!jalan && status.error && <Notice tone="bad" title="Penulisan cutoff gagal">{status.error}</Notice>}
              {!jalan && status.error && aksiError && <Notice tone="bad">{aksiError}</Notice>}
              {!jalan && (
                <div className={s.aksi}>
                  {status.error && tokenTerakhir && (
                    <Button onClick={() => void tulis(tokenTerakhir)} loading={busy}>Coba tulis lagi</Button>
                  )}
                  <Button variant="secondary" onClick={ulang}>Tarik cutoff lain</Button>
                </div>
              )}
            </section>
          )}
        </div>

        <aside className={s.samping}>
          <WeekBaru info={info} onSelesai={muat} />
          {info.riwayat.length > 0 && (
            <section className={s.card}>
              <div className={s.cardHead}><h2>Riwayat tarikan</h2></div>
              <ul className={s.riwayat}>
                {info.riwayat.slice(0, 8).map((r, i) => (
                  <li key={i}>
                    <b>{r.week} · {fmt(r.sekolah)} sekolah{Number(r.baru) ? `, ${r.baru} baru` : ""}</b>
                    <span>{r.waktu} · {r.oleh}</span>
                    <small title={r.file}>{r.file}</small>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>

      {info.log_progres.cutoff.length > 0 && <LogProgres data={info.log_progres} />}
    </div>
  );
}

function BatangNaik({ data }: { data: { komponen: string; jumlah: number }[] }) {
  if (!data.length) return <p className={s.muted}>Belum ada komponen yang bertambah selesai.</p>;
  const maks = Math.max(...data.map((x) => x.jumlah));
  return (
    <ul className={s.naik}>
      {data.map((x) => (
        <li key={x.komponen}>
          <span>{x.komponen}</span>
          <span className={s.naikBar}><span style={{ width: `${(x.jumlah / maks) * 100}%` }} /></span>
          <b>+{fmt(x.jumlah)}</b>
        </li>
      ))}
    </ul>
  );
}

function WeekBaru({ info, onSelesai }: { info: Info; onSelesai: () => void }) {
  const [senin, setSenin] = useState(info.senin_baru);
  const [konfirmasi, setKonfirmasi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);
  const berikut = (info.week_aktif ?? 0) + 1;
  const jumat = useMemo(() => {
    const d = new Date(`${senin}T00:00:00`);
    if (Number.isNaN(d.getTime())) return "";
    d.setDate(d.getDate() + 4);
    return d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
  }, [senin]);
  const seninTeks = new Date(`${senin}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short" });
  async function buat() {
    setBusy(true);
    try {
      const r = await post<{ tab: string; tanggal: string[] }>("/api/cutoff/week-baru", { senin });
      setHasil({ tone: "ok", teks: `${r.tab} dibuat. Log Komunikasi mendapat kolom ${r.tanggal[0]} s.d. ${r.tanggal[4]}.` });
      setKonfirmasi(false);
      onSelesai();
    } catch (e) {
      setHasil({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={`${s.card} ${s.weekCard}`}>
      <div className={s.cardHead}><h2>Buat WEEK {berikut}</h2><span>sekali seminggu, sebelum Senin</span></div>
      <ul className={s.cekList}>
        <li>Salin WEEK {info.week_aktif} beserta data sekolah dan komponen</li>
        <li>Isian Kendala & TL dikosongkan, keterangan otomatis ditulis ulang</li>
        <li>Log Komunikasi mendapat kolom Senin–Jumat</li>
      </ul>
      <label className={s.week}><span>Mulai Senin</span><input type="date" value={senin} onChange={(e) => setSenin(e.target.value)} /></label>
      {konfirmasi ? (
        <div className={s.konfirmasi}>
          <span>Buat WEEK {berikut} ({seninTeks}–{jumat})?</span>
          <div>
            <Button variant="ghost" size="sm" onClick={() => setKonfirmasi(false)}>Batal</Button>
            <Button size="sm" loading={busy} onClick={() => void buat()}>Ya, buat</Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" size="sm" onClick={() => setKonfirmasi(true)}>Buat WEEK {berikut}</Button>
      )}
      {hasil && <p className={hasil.tone === "ok" ? s.ok : s.bad}>{hasil.teks}</p>}
    </section>
  );
}

// ---------- Log Progres nasional ----------

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

function LogProgres({ data }: { data: Info["log_progres"] }) {
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
    <section className={s.card} aria-labelledby="h-logp">
      <div className={s.cardHead}>
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
