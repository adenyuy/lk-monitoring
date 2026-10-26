"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ChatRekap, FasilRekap, Rekap } from "@/lib/types";
import { Chip, Notice, Spinner } from "@/components/ui";
import { FasilDrawer } from "@/components/today/FasilDrawer";
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
const TAHAP = ["Broadcast terkirim", "Dibaca", "Fasil membalas", "Isian LK ditanyakan", "Isian LK lengkap"];

type Filter = "semua" | "p1_belum" | "membalas" | "isian" | "luar";
const FILTER: { k: Filter; label: string; cocok: (r: FasilRekap) => boolean }[] = [
  { k: "semua", label: "Semua", cocok: () => true },
  { k: "p1_belum", label: "P1 belum dihubungi", cocok: (r) => r.p1 > 0 && (r.chat === "belum" || r.chat === "gagal") },
  { k: "membalas", label: "Sudah membalas", cocok: (r) => r.chat === "dibalas" },
  { k: "isian", label: "Isian LK belum lengkap", cocok: (r) => r.isian_lengkap < r.isian_perlu },
  { k: "luar", label: "Tidak masuk Broadcast", cocok: (r) => !r.di_broadcast },
];

type Kolom = "nama" | "p1" | "p2" | "p3" | "selesai" | "chat" | "isian";

const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);

export function RekapView() {
  const [data, setData] = useState<Rekap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("semua");
  const [cari, setCari] = useState("");
  const [urut, setUrut] = useState<{ k: Kolom; naik: boolean }>({ k: "p1", naik: false });
  const [buka, setBuka] = useState<string | null>(null);

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
  const p1 = data.p1;

  function th(k: Kolom, label: string, num = false) {
    const aktif = urut.k === k;
    return (
      <th className={num ? s.num : undefined} aria-sort={aktif ? (urut.naik ? "ascending" : "descending") : "none"}>
        <button type="button" onClick={() => setUrut({ k, naik: aktif ? !urut.naik : k === "nama" })}>
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

      <div className={s.grid3}>
        <section className={s.card} aria-labelledby="h-p1" data-tour="p1">
          <div className={s.cardHead}><h2 id="h-p1">Prioritas 1</h2><span>{p1.sekolah} sekolah, {p1.fasil} fasil</span></div>
          <Meter label="Fasil P1 sudah dihubungi" a={p1.fasil_dihubungi} b={p1.fasil} />
          <Meter label="Fasil P1 sudah membalas" a={p1.fasil_membalas} b={p1.fasil} />
          <Meter label="Sekolah P1 yang fasilnya sudah dihubungi" a={p1.sekolah_dihubungi} b={p1.sekolah} />
        </section>

        <section className={s.card} aria-labelledby="h-isian" data-tour="isian">
          <div className={s.cardHead}><h2 id="h-isian">Isian LK</h2><span>{data.isian.perlu} sekolah perlu diisi</span></div>
          {data.isian.blok.map((b) => (
            <Meter key={b.no} label={`Sesi ${b.label} (${b.kolom})`} a={b.lengkap} b={data.isian.perlu}
              badge={b.no === data.blok.no ? "hari ini" : undefined} />
          ))}
          <p className={s.note}>Lengkap = status komunikasi dan semua alasan yang relevan sudah terisi.</p>
        </section>

        <section className={s.card} aria-labelledby="h-kom">
          <div className={s.cardHead}><h2 id="h-kom">Status komunikasi</h2><span>per sekolah</span></div>
          <ul className={s.bars}>
            {data.isian.komunikasi.map((k) => (
              <li key={k.label}>
                <span className={s.barLabel}>{k.label.replace(/^\d+\.\s*/, "")}</span>
                <span className={s.barTrack}><span style={{ width: `${pct(k.jumlah, data.isian.perlu)}%` }}
                  className={k.label === "Belum diisi" ? s.barMuted : undefined} /></span>
                <span className={s.barVal}>{k.jumlah}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {data.luar_broadcast.fasil > 0 && (
        <button type="button" className={s.luar} onClick={() => setFilter("luar")}>
          <b>{data.luar_broadcast.fasil} fasil tidak masuk Broadcast</b>
          <span>
            {data.luar_broadcast.p1_sekolah
              ? `${data.luar_broadcast.p1_sekolah} sekolah P1 di antaranya belum submit, padahal progresnya sudah 50% atau lebih.`
              : "Semua sekolahnya sudah selesai atau bukan P1."} Lihat daftarnya
          </span>
        </button>
      )}

      <section className={s.card} aria-labelledby="h-tabel" data-tour="tabel">
        <div className={s.cardHead}>
          <h2 id="h-tabel">Per fasil</h2>
          <input className={s.search} type="search" placeholder="Cari nama fasil" value={cari}
            onChange={(e) => setCari(e.target.value)} aria-label="Cari nama fasil" />
        </div>
        <div className={s.filters} role="group" aria-label="Saring">
          {FILTER.map((f) => (
            <button key={f.k} type="button" aria-pressed={filter === f.k} onClick={() => setFilter(f.k)}>
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
              {baris.map((r) => (
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
      </section>

      {buka && <FasilDrawer nomor={buka} versi={0} onClose={tutup} />}
    </div>
  );
}

function Meter({ label, a, b, badge }: { label: string; a: number; b: number; badge?: string }) {
  return (
    <div className={s.meter}>
      <div className={s.meterTop}>
        <span>{label}{badge && <em className={s.badge}>{badge}</em>}</span>
        <b>{a}<small> / {b}</small></b>
      </div>
      <span className={s.meterTrack} role="img" aria-label={`${a} dari ${b}`}>
        <span style={{ width: `${pct(a, b)}%` }} />
      </span>
    </div>
  );
}
