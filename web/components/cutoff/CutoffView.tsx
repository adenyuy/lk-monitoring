"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./cutoff2.module.css";

type Status = { jalan: boolean; langkah: string; persen: number; hasil: null | { tab: string; sekolah: number; baru: number;
  keterangan: number; cutoff: string; log_kom?: LogKomHasil; bimtek?: BimtekHasil | null }; error: string };
type BimtekHasil = { ditulis?: number; kolom_baru?: boolean; error?: string };

function teksBimtek(x?: BimtekHasil | null) {
  if (!x) return "";
  if (x.error) return ` Bimtek Pelaporan belum terisi (${x.error}); isi lagi dari kartu Bimtek Pelaporan.`;
  return x.ditulis ? ` ${x.ditulis.toLocaleString("id-ID")} sekolah baru diberi Bimtek Pelaporan.` : "";
}
type LogKomHasil = { ditambah: number; pic_diubah: number };

function teksLogKom(x?: LogKomHasil) {
  if (!x || (!x.ditambah && !x.pic_diubah)) return " Log Komunikasi sudah sesuai.";
  return ` Log Komunikasi: ${x.ditambah ? `${x.ditambah} sekolah baru ditambahkan` : ""}`
    + `${x.ditambah && x.pic_diubah ? ", " : ""}${x.pic_diubah ? `${x.pic_diubah} PIC disamakan` : ""}.`;
}
type Info = {
  weeks: number[]; week_aktif: number | null; senin_baru: string; cutoff_terakhir: string;
  riwayat: { waktu: string; week: string; file: string; sekolah: string; baru: string; oleh: string }[];
  status: Status; kolom_wajib: string[];
  log_cutoff: LogCutoff[]; minggu: HariCutoff[];
};
type Tarikan = { jam: string; oleh: string; file: string; week: string; sekolah: string; baru: string };
type LogCutoff = { cutoff: string; tanggal: string; sekolah: string; tarikan: Tarikan[] };
type HariCutoff = { tanggal: string; hari: string; label: string; status: "sudah" | "tarik" | "hari_ini" | "lewat" | "nanti";
  cutoff: string; jam: string; oleh: string };

const namaOleh = (email: string) => (email.split("@")[0] || "").replace(/[._\d]+/g, " ").trim();
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
  { sampai: 72, label: "Menyamakan Log Komunikasi" },
  { sampai: 88, label: "Mengisi Log Progres" },
  { sampai: 100, label: "Bimtek Pelaporan & Log Progres Bimtek" },
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

      <StatusMinggu hari={info.minggu} />

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
                  {" "}{fmt(status.hasil.keterangan)} keterangan otomatis ditulis ulang, dan Log Progres mendapat kolom baru.{teksLogKom(status.hasil.log_kom)}{teksBimtek(status.hasil.bimtek)}
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

          <LogCutoffView data={info.log_cutoff} />
        </div>

        <aside className={s.samping}>
          <WeekBaru info={info} onSelesai={muat} />
          <PicBaru />
          <BimtekBaru />
        </aside>
      </div>

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
        <li>Log Komunikasi mendapat kolom Senin–Sabtu dengan judul WEEK-nya</li>
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

// ---------- status cutoff minggu ini ----------

const STATUS_HARI: Record<HariCutoff["status"], string> = {
  sudah: "Sudah cutoff", tarik: "Ditarik, belum masuk Log Progres", hari_ini: "Belum ditarik hari ini",
  lewat: "Tidak ada cutoff", nanti: "Belum",
};

function StatusMinggu({ hari }: { hari: HariCutoff[] }) {
  if (!hari?.length) return null;
  const ini = hari.find((h) => h.tanggal === new Date().toLocaleDateString("sv-SE"));
  const sudah = hari.filter((h) => h.status === "sudah").length;
  return (
    <section className={s.minggu} aria-label="Status cutoff minggu ini">
      <div className={s.mingguHead}>
        <h2>Cutoff minggu ini</h2>
        <span>{sudah} dari {hari.length} hari{ini ? ` · hari ini ${ini.status === "sudah" ? `sudah ditarik pukul ${ini.jam || "–"}` : "belum ditarik"}` : ""}</span>
      </div>
      <ol className={s.mingguHari}>
        {hari.map((h) => (
          <li key={h.tanggal} className={s[`h_${h.status}`]} aria-label={`${h.label}: ${STATUS_HARI[h.status]}`}>
            <span className={s.hariNama}>{h.label}</span>
            <span className={s.hariIkon} aria-hidden="true">{h.status === "sudah" ? "✓" : h.status === "hari_ini" ? "!" : h.status === "tarik" ? "…" : ""}</span>
            <b>{h.cutoff ? h.cutoff.replace(/\s*\(.*\)$/, "") : STATUS_HARI[h.status]}</b>
            <small>{h.jam ? `${h.jam}${h.oleh ? ` · ${namaOleh(h.oleh)}` : ""}` : h.status === "sudah" ? "tercatat di Log Progres" : " "}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}

function LogCutoffView({ data }: { data: LogCutoff[] }) {
  const [semua, setSemua] = useState(false);
  if (!data?.length) return null;
  const tampil = semua ? data : data.slice(0, 5);
  return (
    <section className={s.card}>
      <div className={s.cardHead}><h2>Log cutoff</h2><span>{data.filter((x) => x.cutoff).length} cutoff tercatat</span></div>
      <ol className={s.logCut}>
        {tampil.map((x) => (
          <li key={x.tanggal}>
            <div className={s.logCutHead}>
              <b>{x.cutoff || "Tarikan tanpa kolom Log Progres"}</b>
              <span>{new Date(`${x.tanggal}T00:00:00`).toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long" })}
                {x.sekolah ? ` · ${x.sekolah} sekolah` : ""}</span>
            </div>
            {x.tarikan.length ? (
              <ul>
                {x.tarikan.map((r, i) => (
                  <li key={i}>
                    <span className={s.logJam}>{r.jam}</span>
                    <span>{namaOleh(r.oleh) || r.oleh}{Number(r.baru) ? ` · ${r.baru} sekolah baru` : ""}</span>
                    <small title={r.file}>{r.file}</small>
                  </li>
                ))}
              </ul>
            ) : <p className={s.muted}>Catatan tarikannya tidak ada (hanya tercatat di Log Progres).</p>}
          </li>
        ))}
      </ol>
      {data.length > 5 && (
        <button type="button" className={s.linkBtnCut} onClick={() => setSemua(!semua)}>
          {semua ? "Tampilkan 5 terakhir" : `Tampilkan semua (${data.length})`}
        </button>
      )}
    </section>
  );
}

// ---------- PIC sekolah baru dari sheet pembagian ----------

type PicCek = {
  file: string; tab: string; lk_tab: string; sheet_sekolah: number; kosong: number; akan_ditulis: number;
  jml_isi: number; jml_beda: number; asing: string[];
  isi: { npsn: string; nama: string; pic: string }[];
  beda: { npsn: string; nama: string; pic: string; pic_lama: string }[];
  tanpa: { npsn: string; nama: string; fasil: string }[];
  per_pic: { pic: string; jumlah: number }[];
};

function PicBaru() {
  const [info, setInfo] = useState<{ kosong: number; link: string } | null>(null);
  const [link, setLink] = useState("");
  const [ganti, setGanti] = useState(false);
  const [cek, setCek] = useState<PicCek | null>(null);
  const [busy, setBusy] = useState<"" | "cek" | "isi">("");
  const [pesan, setPesan] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  const muat = useCallback(async () => {
    try {
      const r = await api<{ kosong: number; link: string }>("/api/cutoff/pic");
      setInfo(r);
      setLink((l) => l || r.link);
    } catch { /* kartu tetap bisa dipakai tanpa ringkasan */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  async function periksa(g = ganti) {
    setBusy("cek"); setPesan(null);
    try {
      setCek(await post<PicCek>("/api/cutoff/pic/cek", { link, ganti_beda: g }));
    } catch (e) {
      setCek(null);
      setPesan({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(""); }
  }
  async function isi() {
    setBusy("isi"); setPesan(null);
    try {
      const r = await post<{ ditulis: number; diisi: number; diganti: number; tanpa: unknown[]; lk_tab: string;
        log_kom: LogKomHasil }>(
        "/api/cutoff/pic/isi", { link, ganti_beda: ganti });
      setPesan({ tone: "ok", teks: `${r.ditulis} PIC ditulis di ${r.lk_tab}`
        + (r.diganti ? ` (${r.diisi} diisi, ${r.diganti} diganti)` : "")
        + (r.tanpa.length ? `. ${r.tanpa.length} sekolah masih tanpa PIC karena tidak ada di sheet.` : ".")
        + teksLogKom(r.log_kom) });
      setCek(null);
      void muat();
    } catch (e) {
      setPesan({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(""); }
  }

  return (
    <section className={`${s.card} ${s.weekCard}`}>
      <div className={s.cardHead}>
        <h2>PIC sekolah baru</h2>
        {info && <span>{info.kosong ? `${info.kosong} sekolah tanpa PIC` : "Semua sekolah sudah ber-PIC"}</span>}
      </div>
      <p className={s.catatanTulis}>
        Tempel link sheet pembagian terbaru. Aplikasi mencari tab berkolom NPSN dan Nama Anggota, lalu hanya mengisi
        kolom PIC di LK, lalu menyamakan PIC dan sekolah baru di Log Komunikasi.
      </p>
      <input className={s.linkInput} type="url" placeholder="https://docs.google.com/spreadsheets/d/…" value={link}
        onChange={(e) => { setLink(e.target.value); setCek(null); }} aria-label="Link sheet pembagian" />
      <label className={s.centang}>
        <input type="checkbox" checked={ganti} onChange={(e) => { setGanti(e.target.checked); if (cek) void periksa(e.target.checked); }} />
        Ganti juga PIC yang berbeda dengan sheet
      </label>
      {!cek && (
        <Button variant="secondary" size="sm" loading={busy === "cek"} disabled={!link.trim()} onClick={() => void periksa()}>
          Cek
        </Button>
      )}
      {cek && (
        <div className={s.picHasil}>
          <p>Dari <b>{cek.file}</b>, tab <b>{cek.tab}</b> ({cek.sheet_sekolah.toLocaleString("id-ID")} sekolah):</p>
          <ul className={s.cekList}>
            <li>{cek.jml_isi} sekolah tanpa PIC akan diisi</li>
            <li>{cek.jml_beda} sekolah punya PIC berbeda{cek.jml_beda ? (ganti ? ", akan diganti" : ", dibiarkan") : ""}</li>
            {cek.tanpa.length > 0 && <li>{cek.tanpa.length} sekolah tanpa PIC tidak ada di sheet</li>}
            {cek.asing.length > 0 && <li>Nama tidak dikenal (dilewati): {cek.asing.join(", ")}</li>}
          </ul>
          {cek.per_pic.length > 0 && (
            <p className={s.catatanTulis}>{cek.per_pic.map((x) => `${x.pic} ${x.jumlah}`).join(", ")}</p>
          )}
          {cek.tanpa.length > 0 && (
            <details className={s.picDetail}>
              <summary>Lihat sekolah yang tidak ada di sheet</summary>
              <ul>{cek.tanpa.map((x) => <li key={x.npsn}>{x.npsn} {x.nama}</li>)}</ul>
            </details>
          )}
          {ganti && cek.beda.length > 0 && (
            <details className={s.picDetail}>
              <summary>Lihat PIC yang akan diganti</summary>
              <ul>{cek.beda.map((x) => <li key={x.npsn}>{x.nama}: {x.pic_lama} → {x.pic}</li>)}</ul>
            </details>
          )}
          <div className={s.picAksi}>
            <Button variant="ghost" size="sm" onClick={() => setCek(null)}>Batal</Button>
            <Button size="sm" loading={busy === "isi"} disabled={!cek.akan_ditulis} onClick={() => void isi()}>
              {cek.akan_ditulis ? `Isi ${cek.akan_ditulis} PIC` : "Tidak ada yang perlu diisi"}
            </Button>
          </div>
        </div>
      )}
      {pesan && <p className={pesan.tone === "ok" ? s.ok : s.bad}>{pesan.teks}</p>}
    </section>
  );
}

type BimtekCek = {
  file: string; tab: string; lk_tab: string; sheet_sekolah: number; ada_kolom: boolean; akan_ditulis: number;
  jml_isi: number; jml_beda: number; jml_tanpa: number;
  beda: { npsn: string; nama: string; bimtek: string; bimtek_lama: string }[];
  tanpa: { npsn: string; bimtek: string }[];
  per_bimtek: { bimtek: string; jumlah: number }[];
};
type BimtekInfo = { ada_kolom: boolean; terisi: number; sekolah: number; link: string; sumber: "" | "link" | "file";
  file: string; per_bimtek: { bimtek: string; jumlah: number }[] };

/** Kolom Bimtek Pelaporan di LK, diisi dari sheet daftar bimtek (kolom NPSN + Tag). Mirip PIC sekolah baru. */
function BimtekBaru() {
  const [info, setInfo] = useState<BimtekInfo | null>(null);
  const [mode, setMode] = useState<"link" | "file">("link");
  const [link, setLink] = useState("");
  const [berkas, setBerkas] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [ganti, setGanti] = useState(false);
  const [cek, setCek] = useState<BimtekCek | null>(null);
  const [busy, setBusy] = useState<"" | "cek" | "isi">("");
  const [pesan, setPesan] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  const muat = useCallback(async () => {
    try {
      const r = await api<BimtekInfo>("/api/cutoff/bimtek");
      setInfo(r);
      setLink((l) => l || r.link);
      if (r.sumber === "file") setMode((m) => (m === "link" && !r.link ? "file" : m));
    } catch { /* kartu tetap bisa dipakai tanpa ringkasan */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  /** Link: JSON; file: multipart berisi file + ganti_beda. */
  function kirim<T>(aksi: "cek" | "isi", g: boolean, f: File | null = berkas): Promise<T> {
    if (mode === "link") return post<T>(`/api/cutoff/bimtek/${aksi}`, { link, ganti_beda: g });
    const form = new FormData();
    form.append("file", f!);
    form.append("ganti_beda", String(g));
    return api<T>(`/api/cutoff/bimtek/${aksi}-file`, { method: "POST", body: form });
  }

  async function periksa(g = ganti, f: File | null = berkas) {
    setBusy("cek"); setPesan(null);
    try {
      setCek(await kirim<BimtekCek>("cek", g, f));
    } catch (e) {
      setCek(null);
      setPesan({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(""); }
  }
  async function isi() {
    setBusy("isi"); setPesan(null);
    try {
      const r = await kirim<{ ditulis: number; diisi: number; diganti: number; tanpa: number; lk_tab: string;
        kolom_baru: boolean }>("isi", ganti);
      setPesan({ tone: "ok", teks: (r.kolom_baru ? `Kolom Bimtek Pelaporan ditambahkan di ${r.lk_tab}. ` : "")
        + `${r.ditulis.toLocaleString("id-ID")} sekolah diisi di ${r.lk_tab}`
        + (r.diganti ? ` (${r.diisi} diisi, ${r.diganti} diganti)` : "")
        + (r.tanpa ? `. ${r.tanpa} sekolah di sheet belum ada di LK; terisi otomatis saat cutoff memasukkannya.` : ".") });
      setCek(null);
      void muat();
    } catch (e) {
      setPesan({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(""); }
  }

  return (
    <section className={`${s.card} ${s.weekCard}`}>
      <div className={s.cardHead}>
        <h2>Bimtek Pelaporan</h2>
        {info && <span>{info.ada_kolom ? `${info.terisi.toLocaleString("id-ID")} sekolah peserta` : "Kolom belum ada"}</span>}
      </div>
      <p className={s.catatanTulis}>
        Tempel link sheet atau unggah file daftar bimtek (CSV/Excel) berkolom NPSN dan Tag. Aplikasi mengisi kolom
        Bimtek Pelaporan di bagian Informasi Sekolah (kolom ditambahkan setelah Angkatan bila belum ada). Setiap cutoff,
        sekolah baru ikut diisi dari sumber terakhir.
      </p>
      {info && info.per_bimtek.length > 0 && (
        <p className={s.catatanTulis}>{info.per_bimtek.map((x) => `${x.bimtek} ${x.jumlah.toLocaleString("id-ID")}`).join(" · ")}</p>
      )}
      {info?.sumber && (
        <p className={s.catatanTulis}>
          Sumber terakhir: {info.sumber === "file" ? <>file <b>{info.file || "(tersimpan)"}</b></> : "link sheet"}
        </p>
      )}
      <div className={s.sumberPilih} role="radiogroup" aria-label="Sumber daftar bimtek">
        {(["link", "file"] as const).map((m) => (
          <button key={m} type="button" role="radio" aria-checked={mode === m}
            onClick={() => { setMode(m); setCek(null); setPesan(null); }}>
            {m === "link" ? "Link sheet" : "Upload file"}
          </button>
        ))}
      </div>
      {mode === "link" ? (
        <input className={s.linkInput} type="url" placeholder="https://docs.google.com/spreadsheets/d/…" value={link}
          onChange={(e) => { setLink(e.target.value); setCek(null); }} aria-label="Link sheet daftar bimtek" />
      ) : (
        <div className={s.berkasPilih}>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xlsm,.tsv,.txt" hidden
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              e.target.value = "";
              setBerkas(f); setCek(null);
              if (f) void periksa(ganti, f);
            }} />
          <Button variant="secondary" size="sm" loading={busy === "cek"} onClick={() => inputRef.current?.click()}>
            {berkas ? "Ganti file" : "Pilih file CSV/Excel"}
          </Button>
          {berkas && <span title={berkas.name}>{berkas.name}</span>}
        </div>
      )}
      <label className={s.centang}>
        <input type="checkbox" checked={ganti} onChange={(e) => { setGanti(e.target.checked); if (cek) void periksa(e.target.checked); }} />
        Ganti juga isian yang berbeda dengan {mode === "link" ? "sheet" : "file"}
      </label>
      {!cek && mode === "link" && (
        <Button variant="secondary" size="sm" loading={busy === "cek"} disabled={!link.trim()} onClick={() => void periksa()}>
          Cek
        </Button>
      )}
      {cek && (
        <div className={s.picHasil}>
          <p>Dari <b>{cek.file}</b>{cek.tab !== "CSV" && <>, {mode === "link" ? "tab" : "sheet"} <b>{cek.tab}</b></>}
            {" "}({cek.sheet_sekolah.toLocaleString("id-ID")} sekolah):</p>
          <ul className={s.cekList}>
            {!cek.ada_kolom && <li>Kolom Bimtek Pelaporan akan ditambahkan di {cek.lk_tab} (setelah Angkatan)</li>}
            <li>{cek.jml_isi.toLocaleString("id-ID")} sekolah akan diisi</li>
            <li>{cek.jml_beda} sekolah isiannya berbeda{cek.jml_beda ? (ganti ? ", akan diganti" : ", dibiarkan") : ""}</li>
            {cek.jml_tanpa > 0 && <li>{cek.jml_tanpa} sekolah di sheet belum ada di LK</li>}
          </ul>
          {cek.per_bimtek.length > 0 && (
            <p className={s.catatanTulis}>{cek.per_bimtek.map((x) => `${x.bimtek} ${x.jumlah.toLocaleString("id-ID")}`).join(", ")}</p>
          )}
          {cek.tanpa.length > 0 && (
            <details className={s.picDetail}>
              <summary>Lihat NPSN yang belum ada di LK</summary>
              <ul>{cek.tanpa.map((x) => <li key={x.npsn}>{x.npsn} · {x.bimtek}</li>)}</ul>
            </details>
          )}
          {ganti && cek.beda.length > 0 && (
            <details className={s.picDetail}>
              <summary>Lihat isian yang akan diganti</summary>
              <ul>{cek.beda.map((x) => <li key={x.npsn}>{x.nama}: {x.bimtek_lama} → {x.bimtek}</li>)}</ul>
            </details>
          )}
          <div className={s.picAksi}>
            <Button variant="ghost" size="sm" onClick={() => setCek(null)}>Batal</Button>
            <Button size="sm" loading={busy === "isi"} disabled={!cek.akan_ditulis && cek.ada_kolom} onClick={() => void isi()}>
              {cek.akan_ditulis ? `Isi ${cek.akan_ditulis.toLocaleString("id-ID")} sekolah` : cek.ada_kolom ? "Tidak ada yang perlu diisi" : "Tambah kolom"}
            </Button>
          </div>
        </div>
      )}
      {pesan && <p className={pesan.tone === "ok" ? s.ok : s.bad}>{pesan.teks}</p>}
    </section>
  );
}
