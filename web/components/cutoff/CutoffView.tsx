"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, post } from "@/lib/api";
import type { CutoffCek, CutoffInfo, CutoffRun } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import { NoAccess } from "@/components/app/NoAccess";
import s from "./cutoff.module.css";

const HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function tambahHari(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const tgl = (iso: string) => `${Number(iso.slice(8, 10))} ${BULAN[Number(iso.slice(5, 7)) - 1]}`;
const jam = (waktu: string) => waktu.slice(11, 16).replace(":", ".");
const angka = (n: number) => n.toLocaleString("id-ID");

type Detail = { judul: string; runs: CutoffRun[] };

export function CutoffView() {
  const router = useRouter();
  const [info, setInfo] = useState<CutoffInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [terkunci, setTerkunci] = useState(false);

  const muat = useCallback(async () => {
    try {
      setInfo(await api<CutoffInfo>("/api/cutoff"));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setTerkunci(true);
      else setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    // Ambil data sekali saat halaman dibuka
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muat();
  }, [muat]);

  if (terkunci) {
    return <NoAccess onClose={() => router.replace("/today/")} />;
  }
  if (error && !info) return <Notice tone="bad" title="Tarik Cutoff tidak bisa dimuat">{error}</Notice>;
  if (!info) return <div className={s.loading}><Spinner label="Memuat" /> Membaca daftar WEEK di LK…</div>;

  return (
    <div className={s.page}>
      <header className={s.head}>
        <h1>Tarik Cutoff</h1>
        <p>Unggah file cutoff dari aplikasi, cek hasilnya, lalu tulis ke sheet WEEK di LK.</p>
      </header>
      <div className={s.layout}>
        <Kalender info={info} onUbah={setInfo} />
        <FormTarik info={info} onSelesai={muat} />
      </div>
    </div>
  );
}

/** Kotak hijau: kiri = tarik mingguan (baseline) per WEEK, kanan = tarik harian per hari. */
function Kalender({ info, onUbah }: { info: CutoffInfo; onUbah: (i: CutoffInfo) => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [ubah, setUbah] = useState(false);
  const weeks = info.weeks.length ? info.weeks : ["1"];

  async function simpanMulai(tanggal: string) {
    if (!tanggal) return;
    onUbah(await post<CutoffInfo>("/api/cutoff/week1", { tanggal }));
    setUbah(false);
  }

  const total = info.riwayat.length;
  return (
    <section className={s.card} aria-labelledby="h-kal">
      <div className={s.cardHead}>
        <h2 id="h-kal">Riwayat tarik</h2>
        <span>{total ? `${total} kali ditarik` : "Belum pernah"}</span>
      </div>

      <div className={s.cal} onMouseLeave={() => setDetail(null)}>
        <div className={s.calHead} aria-hidden="true">
          <span className={s.calWeekLabel} />
          <span className={s.calBigHead}>Mingguan</span>
          <span className={s.calDays}>{HARI.map((h) => <span key={h}>{h[0]}</span>)}</span>
        </div>
        {weeks.map((w) => {
          const senin = tambahHari(info.week1_senin, (Number(w) - 1) * 7);
          const mingguan = info.riwayat.filter((r) => r.mode === "mingguan" && r.week === w);
          return (
            <div key={w} className={s.calRow}>
              <span className={s.calWeekLabel}>
                <b>WEEK {w}</b>
                <small>{tgl(senin)}–{tgl(tambahHari(senin, 6))}</small>
              </span>
              <button type="button" className={`${s.big} ${mingguan.length ? s.on : ""}`}
                aria-label={`WEEK ${w} mingguan: ${mingguan.length ? "sudah ditarik" : "belum ditarik"}`}
                onMouseEnter={() => setDetail({ judul: `WEEK ${w}, tarik mingguan (baseline J–L)`, runs: mingguan })}
                onFocus={() => setDetail({ judul: `WEEK ${w}, tarik mingguan (baseline J–L)`, runs: mingguan })} />
              <span className={s.calDays}>
                {HARI.map((h, i) => {
                  const d = tambahHari(senin, i);
                  const runs = info.riwayat.filter((r) => r.mode === "harian" && r.week === w && r.waktu.startsWith(d));
                  const judul = `${h}, ${tgl(d)}: tarik harian WEEK ${w}`;
                  return (
                    <button key={d} type="button"
                      className={`${s.day} ${runs.length ? s.on : ""} ${i >= 5 ? s.weekend : ""} ${d === info.hari_ini ? s.today : ""}`}
                      aria-label={`${judul}: ${runs.length ? "sudah ditarik" : "belum"}`}
                      onMouseEnter={() => setDetail({ judul, runs })} onFocus={() => setDetail({ judul, runs })} />
                  );
                })}
              </span>
            </div>
          );
        })}
      </div>

      <div className={s.detail} aria-live="polite">
        {detail ? (
          <>
            <b>{detail.judul}</b>
            {detail.runs.length === 0 ? <span>Belum ditarik.</span> : detail.runs.map((r, i) => (
              <span key={i}>Pukul {jam(r.waktu)}, {angka(r.sekolah)} sekolah, file {r.file}</span>
            ))}
          </>
        ) : (
          <span>Arahkan kursor ke kotak untuk melihat kapan data ditarik.</span>
        )}
      </div>

      <div className={s.legend}>
        <span><i className={`${s.swatch} ${s.on}`} /> Sudah ditarik</span>
        <span><i className={s.swatch} /> Belum</span>
        <span><i className={`${s.swatch} ${s.today}`} /> Hari ini</span>
      </div>

      <div className={s.mulai}>
        {ubah ? (
          <label>
            WEEK 1 mulai
            <input type="date" defaultValue={info.week1_senin} onChange={(e) => void simpanMulai(e.target.value)} />
          </label>
        ) : (
          <span>
            WEEK 1 dimulai Senin, {tgl(info.week1_senin)}.{" "}
            <button type="button" className={s.linkBtn} onClick={() => setUbah(true)}>Ubah</button>
          </span>
        )}
        <small>Riwayat dicatat di laptop ini, jadi tarikan dari laptop admin lain tidak ikut tampil.</small>
      </div>
    </section>
  );
}

function FormTarik({ info, onSelesai }: { info: CutoffInfo; onSelesai: () => void }) {
  const [mode, setMode] = useState<"harian" | "mingguan">("harian");
  const [week, setWeek] = useState(info.weeks.includes(info.week_aktif) ? info.week_aktif : info.weeks.at(-1) ?? "1");
  const [file, setFile] = useState<File | null>(null);
  const [cek, setCek] = useState<CutoffCek | null>(null);
  const [busy, setBusy] = useState<"cek" | "tulis" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasil, setHasil] = useState<string | null>(null);
  const [seret, setSeret] = useState(false);
  const [yakin, setYakin] = useState(false);
  // File yang mencakup kurang dari separuh sekolah di sheet hampir pasti salah pilih
  const curiga = !!cek && cek.sekolah_mingguan < cek.sekolah_sheet * 0.5;

  function reset() {
    setYakin(false);
    setCek(null);
    setHasil(null);
    setError(null);
  }

  async function periksa() {
    if (!file) return;
    setBusy("cek");
    reset();
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("mode", mode);
      form.append("week", week);
      setCek(await api<CutoffCek>("/api/cutoff/cek", { method: "POST", body: form }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function tulis() {
    if (!cek) return;
    setBusy("tulis");
    setError(null);
    try {
      const r = await post<{ sekolah: number; tab: string; kolom: string; waktu: string }>("/api/cutoff/tulis", { token: cek.token });
      setHasil(`${angka(r.sekolah)} sekolah ditulis ke ${r.tab} kolom ${r.kolom}, pukul ${r.waktu}.`);
      setCek(null);
      setFile(null);
      onSelesai();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={s.card} aria-labelledby="h-form">
      <div className={s.cardHead}><h2 id="h-form">Tarik data</h2></div>

      <fieldset className={s.field}>
        <legend>Jenis tarikan</legend>
        <div className={s.modes}>
          {([
            ["harian", "Harian", "Progres, submit, dan reviu terbaru ke kolom M–O, lalu hitung ulang Prioritas (H)."],
            ["mingguan", "Mingguan (baseline)", "Data awal pekan ke kolom J–L. Biasanya tiap Senin."],
          ] as const).map(([k, judul, isi]) => (
            <label key={k} className={`${s.mode} ${mode === k ? s.modeOn : ""}`}>
              <input type="radio" name="mode" value={k} checked={mode === k} onChange={() => { setMode(k); reset(); }} />
              <b>{judul}</b>
              <span>{isi}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className={s.field}>
        <span className={s.legend}>Sheet tujuan</span>
        <select value={week} onChange={(e) => { setWeek(e.target.value); reset(); }}>
          {(info.weeks.length ? info.weeks : ["1"]).map((w) => <option key={w} value={w}>WEEK {w}</option>)}
        </select>
      </label>

      <div className={s.field}>
        <span className={s.legend}>File cutoff</span>
        <label className={`${s.drop} ${seret ? s.dropOn : ""} ${file ? s.dropFile : ""}`}
          onDragOver={(e) => { e.preventDefault(); setSeret(true); }}
          onDragLeave={() => setSeret(false)}
          onDrop={(e) => {
            e.preventDefault();
            setSeret(false);
            const f = e.dataTransfer.files[0];
            if (f) { setFile(f); reset(); }
          }}>
          <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => { setFile(e.target.files?.[0] ?? null); reset(); }} />
          {file ? (
            <><b>{file.name}</b><span>{(file.size / 1024 / 1024).toFixed(1).replace(".", ",")} MB. Klik untuk ganti file.</span></>
          ) : (
            <><b>Pilih atau seret file CSV/Excel ke sini</b><span>File cutoff dari aplikasi, kolom A–G: NPSN sampai Sudah Review.</span></>
          )}
        </label>
      </div>

      <div className={s.actions}>
        <Button variant={cek ? "secondary" : "primary"} loading={busy === "cek"} disabled={!file || busy !== null} onClick={periksa}>
          {busy === "cek" ? "Membaca file…" : "Cek file"}
        </Button>
        <span className={s.hint}>Belum ada yang ditulis ke LK sampai Anda menekan Tulis.</span>
      </div>

      {error && <Notice tone="bad" title="Belum bisa">{error}</Notice>}
      {hasil && <Notice tone="ok" title="Selesai">{hasil}</Notice>}

      {cek && (
        <div className={s.preview}>
          <h3>Hasil cek, belum ditulis</h3>
          {cek.peringatan && <Notice tone="warn" title="Periksa urutan kolom">{cek.peringatan}</Notice>}
          <dl className={s.stats}>
            <div><dt>Baris di file</dt><dd>{angka(cek.baris_file)}</dd></div>
            <div><dt>Sekolah punya laporan mingguan</dt><dd>{angka(cek.sekolah_mingguan)}</dd></div>
            <div><dt>Sekolah punya laporan 50%</dt><dd>{angka(cek.sekolah_lap50)}</dd></div>
            <div><dt>Sekolah di {cek.tab}</dt><dd>{angka(cek.sekolah_sheet)}</dd></div>
            <div><dt>Tanpa laporan mingguan</dt><dd>{angka(cek.tanpa_mingguan)}</dd></div>
            <div className={s.statKey}><dt>Baris yang berubah</dt><dd>{angka(cek.berubah)}</dd></div>
          </dl>
          {cek.prioritas.length > 0 && (
            <table className={s.prio}>
              <thead><tr><th>Prioritas</th><th>Sekarang</th><th>Setelah ditulis</th><th>Selisih</th></tr></thead>
              <tbody>
                {cek.prioritas.map((p) => {
                  const d = p.sesudah - p.sebelum;
                  return (
                    <tr key={p.label}>
                      <td>{p.label}</td>
                      <td>{angka(p.sebelum)}</td>
                      <td><b>{angka(p.sesudah)}</b></td>
                      <td className={d > 0 ? s.naik : d < 0 ? s.turun : s.sama}>{d > 0 ? `+${angka(d)}` : d < 0 ? `−${angka(-d)}` : "0"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {curiga && (
            <div className={s.guard}>
              <Notice tone="bad" title="File ini kemungkinan salah atau terpotong">
                Hanya {angka(cek.sekolah_mingguan)} dari {angka(cek.sekolah_sheet)} sekolah di {cek.tab} punya laporan mingguan
                di file ini. Bila ditulis, sekolah lain akan kehilangan progresnya dan banyak yang berubah jadi Prioritas 1.
              </Notice>
              <label className={s.yakin}>
                <input type="checkbox" checked={yakin} onChange={(e) => setYakin(e.target.checked)} />
                Saya sudah memeriksa file ini dan tetap ingin menulisnya
              </label>
            </div>
          )}
          <div className={s.actions}>
            <Button loading={busy === "tulis"} disabled={busy !== null || (curiga && !yakin)} onClick={tulis}>
              {busy === "tulis" ? "Menulis…" : `Tulis ke ${cek.tab}`}
            </Button>
            <span className={s.hint}>Kolom {cek.kolom} di {cek.tab} akan ditimpa untuk {angka(cek.sekolah_sheet)} sekolah.</span>
          </div>
        </div>
      )}
    </section>
  );
}
