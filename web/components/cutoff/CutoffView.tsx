"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./cutoff2.module.css";

type Status = { jalan: boolean; langkah: string; persen: number; hasil: null | { tab: string; sekolah: number; baru: number;
  keterangan: number; cutoff: string }; error: string };
type Info = {
  weeks: number[]; week_aktif: number | null; senin_baru: string;
  riwayat: { waktu: string; week: string; file: string; sekolah: string; baru: string; oleh: string }[];
  log_progres: { cutoff: string[]; baris: { kelompok: string; komponen: string; nilai: string[] }[] };
  status: Status; kolom_wajib: string[];
};
type Cek = { token: string; file: string; week: number; tab: string; sekolah_file: number; sekolah_lk: number; cocok: number;
  baru: number; tidak_di_file: number; berubah: { kolom: string; jumlah: number }[];
  naik_selesai: { komponen: string; jumlah: number }[]; bku_bpp: boolean };

const fmt = (n: number | string) => Number(n).toLocaleString("id-ID");

export function CutoffView() {
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [cek, setCek] = useState<Cek | null>(null);
  const [busy, setBusy] = useState(false);
  const [aksiError, setAksiError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [seret, setSeret] = useState(false);
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

  async function tulis() {
    if (!cek) return;
    setBusy(true);
    setAksiError(null);
    try {
      setStatus(await post<Status>("/api/cutoff/tulis", { token: cek.token }));
      setCek(null);
      setFile(null);
    } catch (e) {
      setAksiError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && !info) return <Notice tone="bad" title="Tarik Cutoff tidak bisa dimuat">{error}</Notice>;
  if (!info) return <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>;

  return (
    <div className={s.page}>
      <header className={s.head}>
        <h1>Tarik Cutoff</h1>
        <p>Unggah export per sekolah dari aplikasi. Data komponen di WEEK diperbarui, keterangan otomatis Kendala/TL
          ditulis ulang sesuai to-do terbaru, dan Log Progres mendapat kolom cutoff baru.</p>
      </header>

      {status?.jalan && (
        <section className={`${s.card} ${s.jalan}`} aria-live="polite">
          <div className={s.jalanHead}><Spinner /> <b>{status.langkah}…</b><span>{status.persen}%</span></div>
          <div className={s.bar}><span style={{ width: `${status.persen}%` }} /></div>
          <small>Proses ini bisa beberapa menit untuk belasan ribu sekolah. Halaman boleh ditinggal.</small>
        </section>
      )}
      {!status?.jalan && status?.hasil && (
        <Notice tone="ok" title={`${status.hasil.cutoff} tersimpan di ${status.hasil.tab}`}>
          {fmt(status.hasil.sekolah)} sekolah diperbarui{status.hasil.baru ? `, ${fmt(status.hasil.baru)} sekolah baru` : ""},
          {" "}{fmt(status.hasil.keterangan)} keterangan otomatis ditulis ulang.
        </Notice>
      )}
      {!status?.jalan && status?.error && <Notice tone="bad" title="Penulisan cutoff gagal">{status.error}</Notice>}

      <section className={s.card}>
        <div className={s.cardHead}>
          <h2>1. Pilih file dan WEEK tujuan</h2>
          <label className={s.week}>
            <span>WEEK</span>
            <select value={week ?? ""} onChange={(e) => { setWeek(Number(e.target.value)); setCek(null); }}>
              {info.weeks.map((w) => <option key={w} value={w}>WEEK {w}{w === info.week_aktif ? " (terbaru)" : ""}</option>)}
            </select>
          </label>
        </div>
        <div className={`${s.drop} ${seret ? s.dropAktif : ""}`}
          onDragOver={(e) => { e.preventDefault(); setSeret(true); }} onDragLeave={() => setSeret(false)}
          onDrop={(e) => { e.preventDefault(); setSeret(false); const f = e.dataTransfer.files[0]; if (f) void periksa(f); }}>
          <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 15V3" /><path d="m7 8 5-5 5 5" /><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" /></svg>
          <b>{file ? file.name : "Seret file CSV / Excel ke sini"}</b>
          <span>atau</span>
          <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()} disabled={busy || !!status?.jalan}>Pilih file</Button>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void periksa(f); e.target.value = ""; }} />
          <details className={s.wajib}>
            <summary>Kolom yang wajib ada di file</summary>
            <p>{info.kolom_wajib.join(" · ")}</p>
          </details>
        </div>
        {busy && !cek && <p className={s.muted}><Spinner /> Membandingkan file dengan LK…</p>}
        {aksiError && <Notice tone="bad" title="File belum bisa dipakai">{aksiError}</Notice>}
      </section>

      {cek && (
        <section className={s.card}>
          <div className={s.cardHead}><h2>2. Periksa perubahan</h2><span>{cek.file} → {cek.tab}</span></div>
          <div className={s.angka}>
            <div><b>{fmt(cek.cocok)}</b><span>sekolah cocok</span></div>
            <div><b>{fmt(cek.baru)}</b><span>sekolah baru (ditambahkan, PIC dikosongkan)</span></div>
            <div><b>{fmt(cek.tidak_di_file)}</b><span>sekolah LK tidak ada di file (dibiarkan)</span></div>
          </div>
          <div className={s.dua}>
            <div>
              <h3>Komponen yang bertambah selesai</h3>
              {cek.naik_selesai.length ? (
                <ul className={s.daftar}>{cek.naik_selesai.map((x) => <li key={x.komponen}><span>{x.komponen}</span><b>+{fmt(x.jumlah)}</b></li>)}</ul>
              ) : <p className={s.muted}>Belum ada komponen yang bertambah selesai.</p>}
            </div>
            <div>
              <h3>Kolom yang berubah</h3>
              {cek.berubah.length ? (
                <ul className={s.daftar}>{cek.berubah.slice(0, 12).map((x) => <li key={x.kolom}><span>{x.kolom}</span><b>{fmt(x.jumlah)}</b></li>)}</ul>
              ) : <p className={s.muted}>Tidak ada nilai yang berubah.</p>}
            </div>
          </div>
          {!cek.bku_bpp && <Notice tone="info">File ini belum punya kolom BKU/BPP, jadi isi BKU dan BPP di LK tidak diubah.</Notice>}
          <div className={s.aksi}>
            <Button variant="ghost" onClick={() => setCek(null)}>Batal</Button>
            <Button loading={busy} onClick={() => void tulis()}>Tulis ke {cek.tab}</Button>
          </div>
        </section>
      )}

      <WeekBaru info={info} onSelesai={muat} />

      {info.log_progres.cutoff.length > 0 && (
        <section className={s.card}>
          <div className={s.cardHead}><h2>Log Progres nasional</h2><span>dari tab Log Progres</span></div>
          <div className={s.tabelWrap}>
            <table className={s.tabel}>
              <thead><tr><th>Komponen</th>{info.log_progres.cutoff.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {info.log_progres.baris.map((b, i) => (
                  <tr key={i} className={b.kelompok !== info.log_progres.baris[i - 1]?.kelompok ? s.grupAwal : undefined}>
                    <td><small>{b.kelompok !== info.log_progres.baris[i - 1]?.kelompok ? b.kelompok : ""}</small>{b.komponen}</td>
                    {b.nilai.map((v, j) => <td key={j} className={s.num}>{v}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {info.riwayat.length > 0 && (
        <section className={s.card}>
          <div className={s.cardHead}><h2>Riwayat tarikan</h2></div>
          <ul className={s.riwayat}>
            {info.riwayat.map((r, i) => (
              <li key={i}><span>{r.waktu}</span><b>{r.week}</b><span>{r.file}</span><span>{fmt(r.sekolah)} sekolah{Number(r.baru) ? `, ${r.baru} baru` : ""}</span><small>{r.oleh}</small></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function WeekBaru({ info, onSelesai }: { info: Info; onSelesai: () => void }) {
  const [senin, setSenin] = useState(info.senin_baru);
  const [konfirmasi, setKonfirmasi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);
  const berikut = (info.week_aktif ?? 0) + 1;
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
    <section className={s.card}>
      <div className={s.cardHead}><h2>WEEK baru</h2><span>sekali seminggu, sebelum Senin</span></div>
      <p className={s.muted}>
        Menyalin WEEK {info.week_aktif} menjadi WEEK {berikut}: data sekolah dan komponen ikut, isian Kendala/TL petugas
        dikosongkan (keterangan otomatis ditulis ulang), dan Log Komunikasi mendapat 5 kolom tanggal Senin–Jumat.
      </p>
      <div className={s.weekBaris}>
        <label className={s.week}><span>Senin</span><input type="date" value={senin} onChange={(e) => setSenin(e.target.value)} /></label>
        {konfirmasi ? (
          <>
            <span>Buat WEEK {berikut} mulai {senin}?</span>
            <Button variant="ghost" size="sm" onClick={() => setKonfirmasi(false)}>Batal</Button>
            <Button size="sm" loading={busy} onClick={() => void buat()}>Ya, buat</Button>
          </>
        ) : (
          <Button variant="secondary" size="sm" onClick={() => setKonfirmasi(true)}>Buat WEEK {berikut}</Button>
        )}
      </div>
      {hasil && <p className={hasil.tone === "ok" ? s.ok : s.bad}>{hasil.teks}</p>}
    </section>
  );
}
