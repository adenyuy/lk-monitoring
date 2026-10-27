"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ChatRekap, FasilRekap, Rekap } from "@/lib/types";
import { Chip, Notice, Spinner } from "@/components/ui";
import { FasilDrawer } from "@/components/today/FasilDrawer";
import { TahapBoard } from "./TahapBoard";
import s from "./rekap.module.css";

const PRIO = [
  { k: "p1", label: "Prioritas 1", arti: "belum submit 50%" },
  { k: "p2", label: "Prioritas 2", arti: "progres < 50%" },
  { k: "p3", label: "Prioritas 3", arti: "belum reviu" },
  { k: "selesai", label: "Selesai", arti: "tidak perlu tindak lanjut" },
] as const;

const CHAT: Record<ChatRekap, { label: string; tone: "muted" | "bad" | "info" | "ok" }> = {
  belum: { label: "Belum dikirim", tone: "muted" },
  gagal: { label: "Gagal", tone: "bad" },
  terkirim: { label: "Terkirim", tone: "muted" },
  dibaca: { label: "Dibaca", tone: "info" },
  dibalas: { label: "Membalas", tone: "ok" },
};
const CHAT_URUT: Record<ChatRekap, number> = { belum: 0, gagal: 1, terkirim: 2, dibaca: 3, dibalas: 4 };
const TAHAP_LABEL: Record<FasilRekap["tahap_kini"], string> = {
  belum: "Belum dihubungi", gagal: "Gagal kirim", terkirim: "Dihubungi", dibaca: "Dibaca", dibalas: "Membalas",
  ditanya: "Isian ditanyakan", lk_lengkap: "LK lengkap", selesai: "Selesai",
};
const TAHAP = ["Broadcast terkirim", "Dibaca", "Fasil membalas", "Isian LK ditanyakan", "Isian LK lengkap"];

type Filter = "semua" | "p1_belum" | "membalas" | "isian" | "luar";
const FILTER: { k: Filter; label: string; cocok: (r: FasilRekap) => boolean }[] = [
  { k: "semua", label: "Semua", cocok: () => true },
  { k: "p1_belum", label: "Belum dihubungi", cocok: (r) => r.isian_perlu > 0 && (r.chat === "belum" || r.chat === "gagal") },
  { k: "membalas", label: "Sudah membalas", cocok: (r) => r.chat === "dibalas" },
  { k: "isian", label: "Isian LK belum lengkap", cocok: (r) => r.isian_lengkap < r.isian_perlu },
  { k: "luar", label: "Tidak masuk Broadcast", cocok: (r) => !r.di_broadcast },
];

type Kolom = "nama" | "p1" | "p2" | "p3" | "selesai" | "chat" | "isian";

const PER_HAL = 15;

type AlurKey = "semua" | "p1" | "p2" | "p3";
const ALUR_TAB: { k: AlurKey; label: string; ket: string }[] = [
  { k: "semua", label: "Semua", ket: "Semua fasil yang masih punya sekolah belum selesai:" },
  { k: "p1", label: "P1", ket: "Fasil dengan sekolah Prioritas 1 (belum submit laporan 50%):" },
  { k: "p2", label: "P2", ket: "Fasil dengan sekolah Prioritas 2 (sudah submit, progres di bawah 50%):" },
  { k: "p3", label: "P3", ket: "Fasil dengan sekolah Prioritas 3 (belum direviu):" },
];
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);

export function RekapView() {
  const [data, setData] = useState<Rekap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("semua");
  const [cari, setCari] = useState("");
  const [urut, setUrut] = useState<{ k: Kolom; naik: boolean }>({ k: "p1", naik: false });
  const [buka, setBuka] = useState<string | null>(null);
  const [hal, setHal] = useState(0);
  const [tabAlur, setTabAlur] = useState<AlurKey>("p1");

  const muat = useCallback(async () => {
    try {
      setData(await api<Rekap>("/api/rekap"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void muat();
  }, [muat]);

  const tutup = useCallback(() => { setBuka(null); void muat(); }, [muat]);

  const baris = useMemo(() => {
    if (!data) return [];
    const f = FILTER.find((x) => x.k === filter)!;
    const q = cari.trim().toLowerCase();
    const nilai = (r: FasilRekap): number | string =>
      urut.k === "nama" ? r.nama.toLowerCase()
        : urut.k === "chat" ? CHAT_URUT[r.chat]
        : urut.k === "isian" ? (r.isian_perlu ? r.isian_lengkap / r.isian_perlu : 2)
        : r[urut.k];
    return data.fasil
      .filter((r) => f.cocok(r) && (!q || r.nama.toLowerCase().includes(q)))
      .sort((a, b) => {
        const x = nilai(a), y = nilai(b);
        const c = x < y ? -1 : x > y ? 1 : a.nama.localeCompare(b.nama);
        return urut.naik ? c : -c;
      });
  }, [data, filter, cari, urut]);

  if (error && !data) return <Notice tone="bad" title="Rekap tidak bisa dimuat">{error}</Notice>;
  if (!data) {
    return <div className={s.loading}><Spinner label="Memuat" /> Membaca LK dan sheet Broadcast…</div>;
  }

  const sk = data.sekolah;
  const al = data.alur[tabAlur];
  const lb = data.luar_broadcast;

  function th(k: Kolom, label: string, num = false) {
    const aktif = urut.k === k;
    return (
      <th className={num ? s.num : undefined} aria-sort={aktif ? (urut.naik ? "ascending" : "descending") : "none"}>
        <button type="button" onClick={() => { setUrut({ k, naik: aktif ? !urut.naik : k === "nama" }); setHal(0); }}>
          {label}<span aria-hidden="true" className={s.sortIcon}>{aktif ? (urut.naik ? "↑" : "↓") : ""}</span>
        </button>
      </th>
    );
  }

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Rekap</h1>
          <p>LK WEEK {data.week}, {data.tanggal_panjang}. {data.fasil_total} fasil, {sk.total} sekolah binaan.</p>
        </div>
      </header>

      <section className={s.card} aria-labelledby="h-prio" data-tour="prio">
        <div className={s.cardHead}>
          <h2 id="h-prio">Sekolah binaan per prioritas</h2>
          <span>{sk.total} sekolah</span>
        </div>
        <div className={s.stack} role="img"
          aria-label={PRIO.map((p) => `${p.label} ${sk[p.k]}`).join(", ")}>
          {PRIO.map((p) => sk[p.k] > 0 && (
            <span key={p.k} className={s[`seg_${p.k}`]} style={{ flexGrow: sk[p.k] }}
              title={`${p.label}: ${sk[p.k]} sekolah (${pct(sk[p.k], sk.total)}%)`} />
          ))}
        </div>
        <dl className={s.prioGrid}>
          {PRIO.map((p) => (
            <div key={p.k}>
              <dt><span className={`${s.key} ${s[`seg_${p.k}`]}`} aria-hidden="true" />{p.label}</dt>
              <dd>{sk[p.k]}<small> {pct(sk[p.k], sk.total)}%</small></dd>
              <span className={s.arti}>{p.arti}</span>
            </div>
          ))}
        </dl>
      </section>

      <section className={s.card} aria-labelledby="h-alur" data-tour="p1">
        <div className={s.cardHead}>
          <h2 id="h-alur">Kemajuan fasil minggu ini</h2>
          <div className={s.tabs} role="tablist" aria-label="Prioritas">
            {ALUR_TAB.map((x) => (
              <button key={x.k} type="button" role="tab" aria-selected={tabAlur === x.k} onClick={() => setTabAlur(x.k)}>
                {x.label} <span>{data.alur[x.k].fasil}</span>
              </button>
            ))}
          </div>
        </div>
        <p className={s.alurKet}>
          {ALUR_TAB.find((x) => x.k === tabAlur)!.ket} {al.fasil} fasil, {al.sekolah} sekolah.
          Dihitung ulang tiap Senin.
        </p>
        <ol className={s.funnel}>
          {[
            { label: "Fasil", n: al.fasil, ket: tabAlur === "semua" ? "punya sekolah belum selesai" : `punya sekolah ${tabAlur.toUpperCase()}` },
            { label: "Dihubungi", n: al.dihubungi, ket: "Broadcast atau chat terkirim" },
            { label: "Membalas", n: al.membalas, ket: "fasil sudah membalas" },
            { label: "LK lengkap", n: al.lk_lengkap, ket: `isian sesi ${data.blok.label}` },
          ].map((x, i) => (
            <li key={x.label}>
              <span className={s.fLabel}>{x.label}</span>
              <b className={s.fNum}>{x.n}{i > 0 && <small> {pct(x.n, al.fasil)}%</small>}</b>
              <span className={s.fTrack} aria-hidden="true">
                <span style={{ width: `${i === 0 ? 100 : pct(x.n, al.fasil)}%` }} />
              </span>
              <span className={s.fKet}>{x.ket}</span>
            </li>
          ))}
        </ol>
      </section>

      <TahapBoard fasil={data.fasil} onBuka={setBuka} />

      {lb.fasil > 0 && (
        <button type="button" className={s.luar} onClick={() => { setFilter("luar"); setHal(0); }}>
          <b>{lb.fasil} fasil tidak masuk Broadcast</b>
          <span>
            Mereka membina {lb.sekolah} sekolah, {lb.perlu} di antaranya belum selesai
            {lb.p1_sekolah ? ` (${lb.p1_sekolah} sekolah P1${lb.p1_progres_50 ? `, ${lb.p1_progres_50} di antaranya progresnya sudah 50% atau lebih tapi belum submit` : ""})` : ""}.
            Mereka tidak dikirimi Broadcast otomatis, jadi perlu dichat manual. Minggu ini {lb.dihubungi} dari {lb.fasil} sudah
            dihubungi. Lihat daftarnya
          </span>
        </button>
      )}

      <section className={s.card} aria-labelledby="h-tabel" data-tour="tabel">
        <div className={s.cardHead}>
          <h2 id="h-tabel">Per fasil</h2>
          <input className={s.search} type="search" placeholder="Cari nama fasil" value={cari}
            onChange={(e) => { setCari(e.target.value); setHal(0); }} aria-label="Cari nama fasil" />
        </div>
        <div className={s.filters} role="group" aria-label="Saring">
          {FILTER.map((f) => (
            <button key={f.k} type="button" aria-pressed={filter === f.k} onClick={() => { setFilter(f.k); setHal(0); }}>
              {f.label} <span>{data.fasil.filter(f.cocok).length}</span>
            </button>
          ))}
        </div>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                {th("nama", "Fasil")}
                {th("p1", "P1", true)}
                {th("p2", "P2", true)}
                {th("p3", "P3", true)}
                {th("selesai", "Selesai", true)}
                {th("chat", "Chat")}
                {th("isian", "Isian LK")}
                <th>Tahap</th>
              </tr>
            </thead>
            <tbody>
              {baris.slice(hal * PER_HAL, (hal + 1) * PER_HAL).map((r) => (
                <tr key={r.nomor || r.nama} onClick={() => r.nomor && setBuka(r.nomor)} className={r.nomor ? s.click : undefined}>
                  <td>
                    <button type="button" className={s.nameBtn} disabled={!r.nomor} onClick={() => setBuka(r.nomor)}>
                      {r.nama}
                    </button>
                    <span className={s.sub}>
                      {r.nomor_tersamar || "Nomor tidak ada"}
                      {!r.di_broadcast && <span className={s.luarTag}>Tidak masuk Broadcast</span>}
                    </span>
                  </td>
                  <td className={s.num}>{r.p1 || <span className={s.zero}>0</span>}</td>
                  <td className={s.num}>{r.p2 || <span className={s.zero}>0</span>}</td>
                  <td className={s.num}>{r.p3 || <span className={s.zero}>0</span>}</td>
                  <td className={s.num}>{r.selesai || <span className={s.zero}>0</span>}</td>
                  <td><Chip tone={CHAT[r.chat].tone}>{CHAT[r.chat].label}</Chip></td>
                  <td>
                    {r.isian_perlu ? (
                      <span className={s.isian}>
                        <span className={s.miniTrack}><span style={{ width: `${pct(r.isian_lengkap, r.isian_perlu)}%` }} /></span>
                        {r.isian_lengkap}/{r.isian_perlu}
                      </span>
                    ) : <span className={s.zero}>Tidak perlu</span>}
                  </td>
                  <td>
                    <span className={s.tahapLbl}>{TAHAP_LABEL[r.tahap_kini]}</span>
                    <span className={s.dots} role="img"
                      aria-label={TAHAP.map((t, i) => `${t}: ${r.tahap[i] ? "ya" : "belum"}`).join(", ")}
                      title={TAHAP.map((t, i) => `${r.tahap[i] ? "✓" : "·"} ${t}`).join("\n")}>
                      {r.tahap.map((ok, i) => <span key={i} className={ok ? s.dotOk : undefined} />)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {baris.length === 0 && <div className={s.empty}>Tidak ada fasil yang cocok dengan saringan ini.</div>}
        </div>
        {baris.length > PER_HAL && (
          <nav className={s.pager} aria-label="Halaman tabel">
            <span>{hal * PER_HAL + 1}–{Math.min(baris.length, (hal + 1) * PER_HAL)} dari {baris.length} fasil</span>
            <div>
              <button type="button" onClick={() => setHal(hal - 1)} disabled={hal === 0} aria-label="Halaman sebelumnya">‹</button>
              {Array.from({ length: Math.ceil(baris.length / PER_HAL) }, (_, i) => (
                <button key={i} type="button" aria-current={i === hal ? "page" : undefined} onClick={() => setHal(i)}>
                  {i + 1}
                </button>
              ))}
              <button type="button" onClick={() => setHal(hal + 1)} disabled={(hal + 1) * PER_HAL >= baris.length}
                aria-label="Halaman berikutnya">›</button>
            </div>
          </nav>
        )}
      </section>

      {buka && <FasilDrawer nomor={buka} versi={0} onClose={tutup} />}
    </div>
  );
}
