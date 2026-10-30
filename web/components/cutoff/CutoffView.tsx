"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, post } from "@/lib/api";
import type { CutoffCek, CutoffInfo, CutoffKolom, CutoffMode, CutoffRun } from "@/lib/types";
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
      <StatusTarik info={info} />
      <div className={s.layout}>
        <Kalender info={info} onUbah={setInfo} />
        <FormTarik info={info} onSelesai={muat} />
      </div>
    </div>
  );
}

const oleh = (r: CutoffRun) => (r.oleh ? ` oleh ${r.oleh}` : "");

/** Sudah/belum ditarik untuk hari ini dan WEEK aktif, dari admin mana pun. */
function StatusTarik({ info }: { info: CutoffInfo }) {
  const terakhir = (f: (r: CutoffRun) => boolean) => info.riwayat.filter(f).at(-1);
  const hariIni = (r?: CutoffRun) => !!r && r.waktu.startsWith(info.hari_ini);
  const kapan = (r: CutoffRun) => `${r.waktu.startsWith(info.hari_ini) ? "hari ini" : tgl(r.waktu.slice(0, 10))}, ${jam(r.waktu)}${oleh(r)}`;
  const harian = terakhir((r) => r.mode === "harian");
  const mingguan = terakhir((r) => r.mode === "mingguan" && r.week === info.week_aktif);
  const tunggu = terakhir((r) => r.mode === "waktu_tunggu");
  const item: [string, boolean, string][] = [
    ["Harian", hariIni(harian), harian ? (hariIni(harian) ? `Sudah ${kapan(harian)}` : `Belum hari ini. Terakhir ${kapan(harian)}`) : "Belum pernah"],
    [`Mingguan WEEK ${info.week_aktif}`, !!mingguan, mingguan ? `Sudah ${kapan(mingguan)}` : "Belum ditarik minggu ini"],
    ["Waktu tunggu", hariIni(tunggu), tunggu ? (hariIni(tunggu) ? `Sudah ${kapan(tunggu)}` : `Belum hari ini. Terakhir ${kapan(tunggu)}`) : "Belum pernah"],
  ];
  return (
    <section className={s.status} aria-label="Status tarik data">
      {item.map(([judul, ok, teks]) => (
        <div key={judul} className={`${s.statusItem} ${ok ? s.statusOk : ""}`}>
          <i aria-hidden="true">{ok ? "✓" : ""}</i>
          <div><b>{judul}</b><span>{teks}</span></div>
        </div>
      ))}
    </section>
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
    <section className={s.card} aria-labelledby="h-kal" data-tour="kalender">
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
                onMouseEnter={() => setDetail({ judul: `WEEK ${w}, tarik mingguan (baseline)`, runs: mingguan })}
                onFocus={() => setDetail({ judul: `WEEK ${w}, tarik mingguan (baseline)`, runs: mingguan })} />
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
              <span key={i}>
                Pukul {jam(r.waktu)}{oleh(r)}{r.sekolah ? `, ${angka(r.sekolah)} sekolah` : ""}{r.file ? `, file ${r.file}` : ""}
              </span>
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
        <small>Riwayat dari semua admin, dicatat di LK (tab tersembunyi Log Tarik Data).</small>
      </div>
    </section>
  );
}

const rentang = (k?: CutoffKolom) => (k ? `${k.mulai}–${k.akhir}` : "progres/submit/reviu");

/** Kolom LK yang terbaca dari judul baris 2. Bila admin menyisipkan/memindah kolom, aplikasi ikut menyesuaikan. */
function KolomLk({ kolom }: { kolom: CutoffInfo["kolom"] }) {
  if (kolom.error) {
    return <Notice tone="bad" title="Kolom LK tidak dikenali">{kolom.error}</Notice>;
  }
  if (!kolom.harian || !kolom.mingguan) return null;
  const baris = [
    ["NPSN", kolom.harian.npsn],
    ["Prioritas", kolom.harian.prioritas],
    ["Baseline (progres, submit, reviu)", rentang(kolom.mingguan)],
    ["Harian (progres, submit, reviu)", rentang(kolom.harian)],
    ["Isian sesi Senin–Rabu", kolom.blok?.["1"] ?? "–"],
    ["Isian sesi Rabu–Jumat", kolom.blok?.["2"] ?? "–"],
  ];
  return (
    <details className={s.kolomLk}>
      <summary>Kolom LK terbaca otomatis dari judul baris 2</summary>
      <dl>
        {baris.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
      <p>Kalau admin menyisipkan atau memindah kolom, aplikasi menyesuaikan sendiri selama judul kolomnya tetap sama.</p>
    </details>
  );
}

function FormTarik({ info, onSelesai }: { info: CutoffInfo; onSelesai: () => void }) {
  const [mode, setMode] = useState<CutoffMode>("harian");
  const tunggu = mode === "waktu_tunggu";
  const [week, setWeek] = useState(info.weeks.includes(info.week_aktif) ? info.week_aktif : info.weeks.at(-1) ?? "1");
  const [file, setFile] = useState<File | null>(null);
  const [cek, setCek] = useState<CutoffCek | null>(null);
  const [busy, setBusy] = useState<"cek" | "tulis" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasil, setHasil] = useState<string | null>(null);
  const [seret, setSeret] = useState(false);
  const [yakin, setYakin] = useState(false);
  // File yang mencakup kurang dari separuh sekolah di sheet hampir pasti salah pilih
  const curiga = !!cek && (cek.mode === "waktu_tunggu"
    ? cek.menunggu_ada < cek.menunggu_lk * 0.5
    : cek.sekolah_mingguan < cek.sekolah_sheet * 0.5);

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

      <fieldset className={s.field} data-tour="mode">
        <legend>Jenis tarikan</legend>
        <div className={s.modes}>
          {([
            ["harian", "Harian", `Progres, submit, dan reviu terbaru ke kolom ${rentang(info.kolom.harian)}, lalu hitung ulang Prioritas${info.kolom.harian ? ` (${info.kolom.harian.prioritas})` : ""}.`],
            ["mingguan", "Mingguan (baseline)", `Data awal pekan ke kolom ${rentang(info.kolom.mingguan)}. Biasanya tiap Senin.`],
            ["waktu_tunggu", "Waktu tunggu", "Hari sejak laporan 50% dikirim, untuk sekolah yang sudah submit tapi belum direviu. Ditulis ke kolom Waktu Tunggu. Tarik tiap hari."],
          ] as const).map(([k, judul, isi]) => (
            <label key={k} className={`${s.mode} ${mode === k ? s.modeOn : ""}`}>
              <input type="radio" name="mode" value={k} checked={mode === k} onChange={() => { setMode(k); reset(); }} />
              <b>{judul}</b>
              <span>{isi}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <KolomLk kolom={info.kolom} />

      <label className={s.field}>
        <span className={s.legend}>Sheet tujuan</span>
        <select value={week} onChange={(e) => { setWeek(e.target.value); reset(); }}>
          {(info.weeks.length ? info.weeks : ["1"]).map((w) => <option key={w} value={w}>WEEK {w}</option>)}
        </select>
      </label>

      <div className={s.field} data-tour="file">
        <span className={s.legend}>{tunggu ? "File tanggal kirim laporan 50%" : "File cutoff"}</span>
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
            <><b>Pilih atau seret file CSV/Excel ke sini</b><span>{tunggu
              ? "Berisi kolom NPSN dan Tanggal Kirim (seperti tab Raw Reviu 50%)."
              : "File cutoff dari aplikasi, kolom A–G: NPSN sampai Sudah Review."}</span></>
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
          {cek.mode === "waktu_tunggu" ? (
            <dl className={s.stats}>
              <div><dt>Baris di file</dt><dd>{angka(cek.baris_file)}</dd></div>
              <div><dt>Sekolah di file</dt><dd>{angka(cek.sekolah_file)}</dd></div>
              <div><dt>Tanpa tanggal kirim (dilewati)</dt><dd>{angka(cek.tanpa_tanggal)}</dd></div>
              <div><dt>Sekolah di {cek.tab}</dt><dd>{angka(cek.sekolah_sheet)}</dd></div>
              <div><dt>Ada di file dan di {cek.tab}</dt><dd>{angka(cek.sekolah_cocok)}</dd></div>
              <div className={s.statKey}>
                <dt>Menunggu reviu yang dapat angka waktu tunggu</dt>
                <dd>{angka(cek.menunggu_ada)} / {angka(cek.menunggu_lk)}</dd>
              </div>
            </dl>
          ) : (
          <dl className={s.stats}>
            <div><dt>Baris di file</dt><dd>{angka(cek.baris_file)}</dd></div>
            <div><dt>Sekolah punya laporan mingguan/bulanan/bulanan</dt><dd>{angka(cek.sekolah_mingguan)}</dd></div>
            <div><dt>Sekolah punya laporan 50%</dt><dd>{angka(cek.sekolah_lap50)}</dd></div>
            <div><dt>Sekolah di {cek.tab}</dt><dd>{angka(cek.sekolah_sheet)}</dd></div>
            <div><dt>Tanpa laporan mingguan/bulanan</dt><dd>{angka(cek.tanpa_mingguan)}</dd></div>
            <div className={s.statKey}><dt>Baris yang berubah</dt><dd>{angka(cek.berubah)}</dd></div>
          </dl>
          )}
          {cek.prioritas?.length > 0 && (
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
                {cek.mode === "waktu_tunggu" ? (
                  <>Hanya {angka(cek.menunggu_ada)} dari {angka(cek.menunggu_lk)} sekolah yang menunggu reviu punya tanggal kirim
                    di file ini. Bila ditulis, waktu tunggu sekolah lainnya jadi kosong.</>
                ) : (
                  <>Hanya {angka(cek.sekolah_mingguan)} dari {angka(cek.sekolah_sheet)} sekolah di {cek.tab} punya laporan mingguan/bulanan
                    di file ini. Bila ditulis, sekolah lain akan kehilangan progresnya dan banyak yang berubah jadi Prioritas 1.</>
                )}
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
            <span className={s.hint}>{cek.mode === "waktu_tunggu"
              ? `Kolom ${cek.kolom} (Waktu Tunggu) di ${cek.tab} akan ditimpa untuk ${angka(cek.sekolah_sheet)} sekolah, dihitung per hari ini.`
              : `Kolom ${cek.kolom} di ${cek.tab} akan ditimpa untuk ${angka(cek.sekolah_sheet)} sekolah.`}</span>
          </div>
        </div>
      )}
    </section>
  );
}
