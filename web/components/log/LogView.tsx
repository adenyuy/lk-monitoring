"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Aktivitas, FasilTercatat, KalenderLog, LogHari, Perubahan } from "@/lib/types";
import { Notice } from "@/components/ui";
import { FasilDrawer } from "@/components/today/FasilDrawer";
import s from "./log.module.css";

export const KUNCI_DILIHAT = "lkm-perubahan-dilihat"; // dibaca juga oleh AppShell

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];
const HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const KOLOM = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dariIso = (x: string) => {
  const [y, m, d] = x.split("-").map(Number);
  return new Date(y, m - 1, d || 1);
};
const jamMenit = (w: string) => w.slice(11, 16).replace(":", ".");
const tglPanjang = (x: string) => {
  const d = dariIso(x);
  return `${HARI[d.getDay()]}, ${d.getDate()} ${BULAN[d.getMonth()]}`;
};

function tingkat(n: number) {
  if (!n) return "";
  if (n <= 3) return s.calL1;
  if (n <= 10) return s.calL2;
  return s.calL3;
}

type Baris =
  | { tipe: "data"; waktu: string; sesi: number; sesi_label: string; x: Perubahan }
  | { tipe: "fasil"; waktu: string; sesi: number; sesi_label: string; x: Aktivitas };

type Saring = "semua" | "data" | "fasil";

/** Halaman Log: perubahan data Broadcast/LK dan riwayat chat & isian per fasil. */
export function LogView() {
  const [tab, setTab] = useState<"hari" | "fasil">("hari");
  const [nomorFasil, setNomorFasil] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<string | null>(null);

  // Tandai log perubahan sudah dilihat (titik merah di menu hilang)
  useEffect(() => {
    api<{ items: Perubahan[] }>("/api/perubahan?batas=1")
      .then((r) => {
        try {
          if (r.items[0]) localStorage.setItem(KUNCI_DILIHAT, String(r.items[0].id));
          window.dispatchEvent(new Event("lkm-perubahan-dilihat"));
        } catch {
          /* penanda "sudah dilihat" hanya kenyamanan */
        }
      })
      .catch(() => {});
  }, []);

  const bukaFasil = useCallback((nomor: string) => {
    setNomorFasil(nomor);
    setTab("fasil");
    window.scrollTo({ top: 0 });
  }, []);

  return (
    <div className={s.page}>
      <header className={s.head}>
        <h1>Log</h1>
        <p>Perubahan data di Broadcast dan LK, serta riwayat chat dan isian LK per fasil. Disimpan 90 hari.</p>
      </header>

      <div className={s.tabs} role="tablist" aria-label="Jenis log" data-tour="logtab">
        <button type="button" role="tab" aria-selected={tab === "hari"} onClick={() => setTab("hari")}>Per hari</button>
        <button type="button" role="tab" aria-selected={tab === "fasil"} onClick={() => setTab("fasil")}>
          Riwayat per fasil
        </button>
      </div>

      {tab === "hari" ? <PerHari onFasil={bukaFasil} /> : (
        <PerFasil nomor={nomorFasil} onPilih={setNomorFasil} onBuka={setDrawer} />
      )}
      {drawer && <FasilDrawer nomor={drawer} versi={0} onClose={() => setDrawer(null)} />}
    </div>
  );
}

function PerHari({ onFasil }: { onFasil: (nomor: string) => void }) {
  const [kal, setKal] = useState<KalenderLog | null>(null);
  const [pilih, setPilih] = useState<string | null>(null);
  const [hari, setHari] = useState<LogHari | null>(null);
  const [saring, setSaring] = useState<Saring>("semua");
  const [error, setError] = useState<string | null>(null);

  const muatBulan = useCallback(async (b?: string) => {
    try {
      const k = await api<KalenderLog>(`/api/log/kalender${b ? `?bulan=${b}` : ""}`);
      setKal(k);
      return k;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const k = await muatBulan();
      if (k) setPilih(k.hari_ini);
    })();
  }, [muatBulan]);

  useEffect(() => {
    if (!pilih) return;
    let batal = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHari(null);
    api<LogHari>(`/api/log/hari?tanggal=${pilih}`)
      .then((r) => { if (!batal) setHari(r); })
      .catch((e) => { if (!batal) setError(e.message); });
    return () => { batal = true; };
  }, [pilih]);

  const jumlah = useMemo(
    () => new Map((kal?.hari ?? []).map((h) => [h.tanggal, h.broadcast + h.lk + h.fasil])), [kal]);

  const sel = useMemo(() => {
    if (!kal) return [];
    const awal = dariIso(kal.bulan);
    const geser = (awal.getDay() + 6) % 7; // Senin = 0
    const nHari = new Date(awal.getFullYear(), awal.getMonth() + 1, 0).getDate();
    const out: (string | null)[] = Array(geser).fill(null);
    for (let d = 1; d <= nHari; d++) out.push(iso(new Date(awal.getFullYear(), awal.getMonth(), d)));
    while (out.length % 7) out.push(null);
    return out;
  }, [kal]);

  const grup = useMemo(() => {
    if (!hari) return [];
    const semua: Baris[] = [
      ...(saring !== "fasil" ? hari.perubahan.map((x) => ({ tipe: "data" as const, waktu: x.waktu, sesi: x.sesi, sesi_label: x.sesi_label, x })) : []),
      ...(saring !== "data" ? hari.aktivitas.map((x) => ({ tipe: "fasil" as const, waktu: x.waktu, sesi: x.sesi, sesi_label: x.sesi_label, x })) : []),
    ].sort((a, b) => a.waktu.localeCompare(b.waktu));
    const g = new Map<number, { label: string; items: Baris[] }>();
    for (const b of semua) {
      const e = g.get(b.sesi) ?? { label: b.sesi_label, items: [] };
      e.items.push(b);
      g.set(b.sesi, e);
    }
    return [...g.entries()].sort((a, b) => a[0] - b[0]).map(([no, v]) => ({ no, ...v }));
  }, [hari, saring]);

  if (!kal) {
    return error ? <Notice tone="bad" title="Log tidak bisa dimuat">{error}</Notice> : <p className={s.note}>Memuat log…</p>;
  }

  const bln = dariIso(kal.bulan);
  const bisaMundur = !!kal.paling_awal && kal.paling_awal.slice(0, 7) < kal.bulan;
  const bisaMaju = kal.bulan < kal.hari_ini.slice(0, 7);
  const pindah = (n: number) => void muatBulan(iso(new Date(bln.getFullYear(), bln.getMonth() + n, 1)).slice(0, 7));
  const nData = hari?.perubahan.length ?? 0;
  const nFasil = hari?.aktivitas.length ?? 0;

  return (
    <section className={s.card} aria-label="Log per hari">
      <div className={s.grid}>
        <div className={s.cal} data-tour="kalender">
          <div className={s.calHead}>
            <button type="button" onClick={() => pindah(-1)} disabled={!bisaMundur} aria-label="Bulan sebelumnya">‹</button>
            <b>{BULAN[bln.getMonth()]} {bln.getFullYear()}</b>
            <button type="button" onClick={() => pindah(1)} disabled={!bisaMaju} aria-label="Bulan berikutnya">›</button>
          </div>
          <div className={s.calGrid}>
            {KOLOM.map((k) => <span key={k} className={s.calDow} aria-hidden="true">{k}</span>)}
            {sel.map((t, i) => {
              if (!t) return <span key={`k${i}`} />;
              const n = jumlah.get(t) ?? 0;
              return (
                <button key={t} type="button" disabled={t > kal.hari_ini}
                  className={`${s.calDay} ${tingkat(n)} ${t === kal.hari_ini ? s.calToday : ""} ${t === pilih ? s.calSel : ""}`}
                  aria-pressed={t === pilih} onClick={() => setPilih(t)}
                  aria-label={`${Number(t.slice(8))} ${BULAN[bln.getMonth()]}, ${n ? `${n} catatan` : "tidak ada catatan"}`}>
                  <span>{Number(t.slice(8))}</span>
                  {n > 0 && <small>{n}</small>}
                </button>
              );
            })}
          </div>
          <p className={s.note}>Angka di kotak = jumlah catatan hari itu. Makin gelap, makin banyak.</p>
        </div>

        <div className={s.day}>
          {pilih && (
            <div className={s.dayHead}>
              <b>{tglPanjang(pilih)}</b>
              <div className={s.chips} role="group" aria-label="Saring log">
                <button type="button" aria-pressed={saring === "semua"} onClick={() => setSaring("semua")}>
                  Semua <span>{nData + nFasil}</span>
                </button>
                <button type="button" aria-pressed={saring === "data"} onClick={() => setSaring("data")}>
                  Perubahan data <span>{nData}</span>
                </button>
                <button type="button" aria-pressed={saring === "fasil"} onClick={() => setSaring("fasil")}>
                  Aktivitas fasil <span>{nFasil}</span>
                </button>
              </div>
            </div>
          )}
          {!hari && <p className={s.note}>Memuat…</p>}
          {hari && grup.length === 0 && (
            <p className={s.empty}>
              {saring === "data" ? "Tidak ada perubahan Broadcast atau LK di hari ini."
                : saring === "fasil" ? "Tidak ada chat atau isian LK di hari ini."
                : "Belum ada catatan di hari ini."}
            </p>
          )}
          {grup.map((g) => (
            <div key={g.no} className={s.sesiGrup}>
              <h3>{g.label}<span>{g.items.length}</span></h3>
              <ul className={s.rows}>
                {g.items.map((b) => b.tipe === "data"
                  ? <BarisData key={`d${b.x.id}`} x={b.x} />
                  : <BarisFasil key={b.x.id} x={b.x} onFasil={onFasil} />)}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BarisData({ x }: { x: Perubahan }) {
  const [buka, setBuka] = useState(false);
  return (
    <li>
      <button type="button" className={s.row} aria-expanded={buka} onClick={() => setBuka(!buka)}>
        <span className={s.time}>{jamMenit(x.waktu)}</span>
        <span className={`${s.src} ${x.sumber === "lk" ? s.srcLk : s.srcBc}`}>{x.judul}</span>
        <span className={s.sum}>{x.ringkasan}</span>
        <span className={s.more}>{buka ? "Tutup" : `${x.rincian.length} rincian`}</span>
      </button>
      {buka && (
        <ul className={s.detail}>
          {x.rincian.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </li>
  );
}

function BarisFasil({ x, onFasil }: { x: Aktivitas; onFasil?: (nomor: string) => void }) {
  return (
    <li className={s.row}>
      <span className={s.time}>{jamMenit(x.waktu)}</span>
      <span className={s.act}><i className={s[`j_${x.jenis}`]} aria-hidden="true" />{x.label}</span>
      <span className={s.sum}>
        {onFasil ? (
          <button type="button" className={s.nama} onClick={() => onFasil(x.nomor)}>{x.nama}</button>
        ) : null}
        {onFasil ? " " : ""}{x.ringkasan}
      </span>
    </li>
  );
}

function PerFasil({ nomor, onPilih, onBuka }: {
  nomor: string | null; onPilih: (n: string) => void; onBuka: (n: string) => void;
}) {
  const [daftar, setDaftar] = useState<FasilTercatat[] | null>(null);
  const [cari, setCari] = useState("");
  const [riwayat, setRiwayat] = useState<Aktivitas[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ fasil: FasilTercatat[] }>("/api/log/fasil")
      .then((r) => {
        setDaftar(r.fasil);
        if (!nomor && r.fasil.length) {
          const terbaru = [...r.fasil].sort((a, b) => b.terakhir.localeCompare(a.terakhir))[0];
          onPilih(terbaru.nomor);
        }
      })
      .catch((e) => setError(e.message));
    // Hanya saat tab dibuka
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!nomor) return;
    let batal = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRiwayat(null);
    api<{ aktivitas: Aktivitas[] }>(`/api/log/fasil/${nomor}`)
      .then((r) => { if (!batal) setRiwayat(r.aktivitas); })
      .catch((e) => { if (!batal) setError(e.message); });
    return () => { batal = true; };
  }, [nomor]);

  const tampil = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return (daftar ?? []).filter((f) => !q || f.nama.toLowerCase().includes(q));
  }, [daftar, cari]);

  const perTanggal = useMemo(() => {
    const g = new Map<string, Aktivitas[]>();
    for (const x of riwayat ?? []) {
      const t = x.waktu.slice(0, 10);
      g.set(t, [...(g.get(t) ?? []), x]);
    }
    return [...g.entries()];
  }, [riwayat]);

  const dipilih = daftar?.find((f) => f.nomor === nomor);

  if (error && !daftar) return <Notice tone="bad" title="Riwayat tidak bisa dimuat">{error}</Notice>;
  if (!daftar) return <p className={s.note}>Memuat…</p>;
  if (!daftar.length) {
    return (
      <section className={s.card}>
        <p className={s.empty}>Belum ada riwayat. Riwayat muncul setelah Broadcast terkirim, chat dibalas, atau LK diisi.</p>
      </section>
    );
  }

  return (
    <section className={s.card} aria-label="Riwayat per fasil">
      <div className={s.grid}>
        <div className={s.fasilList}>
          <input type="search" className={s.search} placeholder="Cari nama fasil" value={cari}
            onChange={(e) => setCari(e.target.value)} aria-label="Cari nama fasil" />
          <ul>
            {tampil.map((f) => (
              <li key={f.nomor}>
                <button type="button" aria-pressed={f.nomor === nomor} onClick={() => onPilih(f.nomor)}>
                  <b>{f.nama}</b>
                  <small>Terakhir {tglPanjang(f.terakhir.slice(0, 10))}, {jamMenit(f.terakhir)}</small>
                </button>
              </li>
            ))}
            {!tampil.length && <li className={s.note}>Tidak ada yang cocok.</li>}
          </ul>
        </div>

        <div className={s.day}>
          {dipilih && (
            <div className={s.dayHead}>
              <b>{dipilih.nama}</b>
              <button type="button" className={s.openBtn} onClick={() => onBuka(dipilih.nomor)}>Buka chat & LK</button>
            </div>
          )}
          {!riwayat && <p className={s.note}>Memuat…</p>}
          {perTanggal.map(([t, items]) => (
            <div key={t} className={s.sesiGrup}>
              <h3>{tglPanjang(t)}<span>{items.length}</span></h3>
              <ul className={s.rows}>
                {items.map((x) => <BarisFasil key={x.id} x={x} />)}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
