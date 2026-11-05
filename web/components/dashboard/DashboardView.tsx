"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { KELOMPOK_INFO, KODE_WARNA, TAHAP_LABEL, hariPendek, type Kelompok, type Tahap } from "@/lib/lk";
import { Chip, Notice, Spinner } from "@/components/ui";
import s from "./dashboard.module.css";

type Capaian = { kode: string; label: string; tahap: Tahap; pelaku: string; selesai: number; belum: number; due: number;
  kosong: number; tanpa_data: number; relevan: number; persen: number | null; rasio: [number, number] | null };
type Dash = {
  pic: string; nasional: boolean; week: number; cutoff: string; dibuat: string;
  distribusi: { sekolah: number; fasil: number; koor: number; jml_ptn: number; jml_kab: number; rata_sekolah_per_fasil: number;
    maks_sekolah_per_fasil: number; tanpa_hp_fasil: number;
    angkatan: { nama: string; jumlah: number }[]; provinsi: { nama: string; jumlah: number }[];
    kab: { nama: string; jumlah: number }[]; ptn: { nama: string; jumlah: number }[] };
  capaian: Capaian[];
  tahap: { kode: Tahap; jumlah: number }[];
  fokus: { judul: string; jumlah: number }[];
  todo: { sekolah_perlu: number; sekolah_beres: number; item: number; oleh_sekolah: number; oleh_fasil: number; lengkap: number;
    tunggu_rata: number | null; tunggu_lewat3: number };
  komunikasi: { hari: { tanggal: string; kode: Record<string, number>; tercatat: number; fasil: number }[];
    total: Record<string, number>; kode: { kode: string; arti: string }[] };
  tren: { cutoff: string[]; seri: { kode: string; label: string; nilai: (number | null)[] }[]; rata_pic: Record<string, number | null> };
  fasil: { nama: string; sekolah: number; perlu: number; lengkap: number; todo: number; todo_fasil: number; kelompok: Kelompok;
    terhubung: number; lambat: number; tidak: number; telepon: number; hari_tercatat: number; tunggu_maks: number | null }[];
  pilihan_pic?: string[];
};

const TAHAP_WARNA: Record<Tahap, string> = {
  pendahuluan: "#c9d4ef", berkala: "#8ea3dc", l50: "#5673bf", l100: "#2346a0", selesai: "#2f8f5b",
};
const URUT_KODE = ["T", "TP", "T1", "T2", "R", "C", "N"];
const KODE_BATANG: Record<string, string> = {
  T: "#2f8f5b", TP: "#1f7a6c", T1: "#d9a23a", T2: "#c47a2c", R: "#5673bf", C: "#c8484b", N: "#9b4a7f",
};
const fmt = (n: number) => n.toLocaleString("id-ID");
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);

export function DashboardView() {
  const [pic, setPic] = useState("");
  const [d, setD] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);

  const muat = useCallback(async (p: string) => {
    setMemuat(true);
    try {
      setD(await api<Dash>(`/api/dashboard${p ? `?pic=${encodeURIComponent(p)}` : ""}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(pic); }, [pic, muat]);

  if (error && !d) return <Notice tone="bad" title="Dashboard tidak bisa dimuat">{error}</Notice>;
  if (!d) return <div className={s.loading}><Spinner label="Memuat" /> Menghitung…</div>;

  const di = d.distribusi;
  const beresPct = pct(d.todo.sekolah_beres, di.sekolah);

  return (
    <div className={`${s.page} ${memuat ? s.memuat : ""}`}>
      <header className={s.head}>
        <div>
          <p className={s.eyebrow}>WEEK {d.week}{d.cutoff ? ` · ${d.cutoff}` : ""} · dihitung {d.dibuat}</p>
          <h1>Dashboard {d.nasional ? "nasional" : d.pic}</h1>
        </div>
        {d.pilihan_pic && (
          <label className={s.pilihPic}>
            <span>Lihat</span>
            <select value={pic} onChange={(e) => setPic(e.target.value)} aria-label="Pilih PIC">
              <option value="">Saya sendiri</option>
              <option value="__semua__">Nasional (semua PIC)</option>
              {d.pilihan_pic.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            {memuat && <Spinner label="Memuat" />}
          </label>
        )}
      </header>

      <section className={s.kpi} aria-label="Ringkasan">
        <Kpi label="Sekolah binaan" nilai={fmt(di.sekolah)} ket={`${di.jml_kab} kab/kota · ${di.jml_ptn} PTN`} />
        <Kpi label="Fasilitator" nilai={fmt(di.fasil)} ket={`rata-rata ${String(di.rata_sekolah_per_fasil).replace(".", ",")} sekolah, paling banyak ${di.maks_sekolah_per_fasil}`} />
        <Kpi label="Koordinator" nilai={fmt(di.koor)} ket={di.tanpa_hp_fasil ? `${di.tanpa_hp_fasil} sekolah tanpa nomor fasil` : "semua fasil punya nomor"} />
        <Kpi label="Sekolah semua hijau" nilai={`${beresPct}%`} ket={`${fmt(d.todo.sekolah_beres)} dari ${fmt(di.sekolah)} sekolah tanpa to-do`} aksen />
        <Kpi label="To-do terbuka" nilai={fmt(d.todo.item)} ket={`${fmt(d.todo.oleh_sekolah)} tugas sekolah · ${fmt(d.todo.oleh_fasil)} reviu fasil`} />
      </section>

      <div className={s.grid2}>
        <section className={s.card}>
          <div className={s.cardHead}>
            <h2>Capaian per komponen</h2>
            <span>% sekolah selesai dari yang sudah due{!d.nasional && d.tren.cutoff.length ? " · garis = rata-rata semua PIC" : ""}</span>
          </div>
          <Capaian data={d.capaian} rata={d.nasional ? {} : d.tren.rata_pic} />
        </section>

        <div className={s.kolom}>
          <section className={s.card}>
            <div className={s.cardHead}><h2>Posisi sekolah</h2><span>tahap to-do saat ini</span></div>
            <TahapBar data={d.tahap} total={di.sekolah} />
          </section>
          <section className={s.card}>
            <div className={s.cardHead}><h2>Fokus to-do terbanyak</h2><span>jumlah sekolah</span></div>
            <Batang data={d.fokus.map((f) => ({ nama: f.judul, jumlah: f.jumlah }))} />
          </section>
          <section className={s.card}>
            <div className={s.cardHead}><h2>Reviu fasil</h2></div>
            <div className={s.duo}>
              <div><b>{d.todo.tunggu_rata !== null ? `${String(d.todo.tunggu_rata).replace(".", ",")} hari` : "–"}</b><span>rata-rata waktu tunggu reviu</span></div>
              <div><b className={d.todo.tunggu_lewat3 ? s.merah : undefined}>{fmt(d.todo.tunggu_lewat3)}</b><span>laporan menunggu lebih dari 3 hari</span></div>
            </div>
          </section>
        </div>
      </div>

      <section className={s.card}>
        <div className={s.cardHead}>
          <h2>Frekuensi komunikasi</h2>
          <span>{d.nasional ? "jumlah fasil per kode Log Komunikasi, per hari" : "fasil binaan per kode Log Komunikasi, per hari"}</span>
        </div>
        <Komunikasi data={d.komunikasi} />
      </section>

      <section className={s.card}>
        <div className={s.cardHead}>
          <h2>Tren per cutoff</h2>
          <span>{d.tren.cutoff.length ? `${d.tren.cutoff.length} cutoff tercatat di Log Progres PIC` : "belum ada riwayat"}</span>
        </div>
        <Tren tren={d.tren} />
      </section>

      <div className={s.grid3}>
        <section className={s.card}><div className={s.cardHead}><h2>Angkatan</h2></div><Batang data={di.angkatan} /></section>
        <section className={s.card}><div className={s.cardHead}><h2>Provinsi teratas</h2></div><Batang data={di.provinsi} /></section>
        <section className={s.card}><div className={s.cardHead}><h2>PTN teratas</h2></div><Batang data={di.ptn} /></section>
      </div>

      {d.fasil.length > 0 && (
        <section className={s.card}>
          <div className={s.cardHead}><h2>Per fasil</h2><span>komunikasi dihitung dari semua hari yang tercatat</span></div>
          <TabelFasil data={d.fasil} />
        </section>
      )}
    </div>
  );
}

function Kpi({ label, nilai, ket, aksen }: { label: string; nilai: string; ket: string; aksen?: boolean }) {
  return (
    <div className={`${s.kpiItem} ${aksen ? s.kpiAksen : ""}`}>
      <span>{label}</span>
      <b>{nilai}</b>
      <small>{ket}</small>
    </div>
  );
}

function Capaian({ data, rata }: { data: Capaian[]; rata: Record<string, number | null> }) {
  const grup: { tahap: Tahap; label: string }[] = [
    { tahap: "pendahuluan", label: "Pendahuluan" }, { tahap: "berkala", label: "Berkala" },
    { tahap: "l50", label: "Laporan 50%" }, { tahap: "l100", label: "Laporan 100%" },
  ];
  return (
    <div className={s.capaian}>
      {grup.map((g) => (
        <div key={g.tahap} className={s.capGrup}>
          <h3>{g.label}</h3>
          {data.filter((x) => x.tahap === g.tahap).map((x) => {
            const r = rata[x.kode];
            const ket = x.relevan ? `${fmt(x.selesai)} dari ${fmt(x.relevan)} sekolah` : x.tanpa_data ? "belum ada data" : "belum due";
            return (
              <div key={x.kode} className={s.capBaris} title={`${x.label}: ${ket}${x.due ? `, ${fmt(x.due)} belum due` : ""}`}>
                <span className={s.capLabel}>{x.label}{x.pelaku === "fasil" && <i>fasil</i>}</span>
                <span className={s.capBar}>
                  {x.persen !== null && <span style={{ width: `${x.persen}%` }} />}
                  {r !== undefined && r !== null && <em style={{ left: `${Math.min(100, r)}%` }} title={`Rata-rata PIC ${r}%`} />}
                </span>
                <b>{x.persen !== null ? `${Math.round(x.persen)}%` : "–"}</b>
                <small>{ket}</small>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TahapBar({ data, total }: { data: { kode: Tahap; jumlah: number }[]; total: number }) {
  return (
    <>
      <div className={s.stack} role="img" aria-label={data.map((x) => `${TAHAP_LABEL[x.kode]} ${x.jumlah}`).join(", ")}>
        {data.filter((x) => x.jumlah).map((x) => (
          <span key={x.kode} style={{ flexGrow: x.jumlah, background: TAHAP_WARNA[x.kode] }}
            title={`${TAHAP_LABEL[x.kode]}: ${fmt(x.jumlah)} sekolah (${pct(x.jumlah, total)}%)`} />
        ))}
      </div>
      <ul className={s.legend}>
        {data.map((x) => (
          <li key={x.kode}>
            <i style={{ background: TAHAP_WARNA[x.kode] }} />
            <span>{TAHAP_LABEL[x.kode]}</span>
            <b>{fmt(x.jumlah)}</b>
            <small>{pct(x.jumlah, total)}%</small>
          </li>
        ))}
      </ul>
    </>
  );
}

function Batang({ data }: { data: { nama: string; jumlah: number }[] }) {
  const maks = Math.max(1, ...data.map((x) => x.jumlah));
  if (!data.length) return <p className={s.kosong}>Belum ada data.</p>;
  return (
    <ul className={s.batang}>
      {data.map((x) => (
        <li key={x.nama} title={`${x.nama}: ${fmt(x.jumlah)}`}>
          <span className={s.batangNama}>{x.nama}</span>
          <span className={s.batangBar}><span style={{ width: `${(x.jumlah / maks) * 100}%` }} /></span>
          <b>{fmt(x.jumlah)}</b>
        </li>
      ))}
    </ul>
  );
}

function Komunikasi({ data }: { data: Dash["komunikasi"] }) {
  const [sorot, setSorot] = useState<string | null>(null);
  if (!data.hari.length) return <p className={s.kosong}>Log Komunikasi belum punya kolom tanggal.</p>;
  const maks = Math.max(1, ...data.hari.map((h) => h.fasil));
  const ada = data.hari.some((h) => h.tercatat);
  return (
    <div className={s.kom}>
      <div className={s.komChart} role="img" aria-label="Jumlah fasil per kode komunikasi per hari">
        {data.hari.map((h) => (
          <div key={h.tanggal} className={s.komKolom}
            title={`${hariPendek(h.tanggal)}: ${h.tercatat}/${h.fasil} fasil tercatat\n${URUT_KODE.filter((k) => h.kode[k]).map((k) => `${k} ${h.kode[k]}`).join(", ")}`}>
            <div className={s.komBatang} style={{ height: 160 }}>
              {URUT_KODE.filter((k) => h.kode[k]).map((k) => (
                <span key={k} style={{ height: `${(h.kode[k] / maks) * 100}%`, background: KODE_BATANG[k],
                  opacity: sorot && sorot !== k ? 0.25 : 1 }} />
              ))}
            </div>
            <small>{hariPendek(h.tanggal)}</small>
            <b>{h.tercatat}<i>/{h.fasil}</i></b>
          </div>
        ))}
      </div>
      <ul className={s.komLegend} onMouseLeave={() => setSorot(null)}>
        {URUT_KODE.map((k) => (
          <li key={k} onMouseEnter={() => setSorot(k)}>
            <i style={{ background: KODE_BATANG[k] }} />
            <b>{k}</b><span>{KODE_WARNA[k].label}</span><em>{fmt(data.total[k] ?? 0)}</em>
          </li>
        ))}
      </ul>
      {!ada && <p className={s.kosong}>Belum ada kode yang tercatat di rentang ini.</p>}
    </div>
  );
}

function Tren({ tren }: { tren: Dash["tren"] }) {
  if (!tren.cutoff.length) {
    return <p className={s.kosong}>Tren muncul setelah Tarik Cutoff berikutnya (Log Progres PIC terisi tiap cutoff).</p>;
  }
  return (
    <div className={s.tren}>
      {tren.seri.map((x) => {
        const v = x.nilai;
        const akhir = [...v].reverse().find((n) => n !== null) ?? null;
        const awal = v.find((n) => n !== null) ?? null;
        const naik = akhir !== null && awal !== null ? akhir - awal : null;
        return (
          <div key={x.kode} className={s.trenItem}>
            <span className={s.trenLabel}>{x.label}</span>
            <Spark nilai={v} />
            <b>{akhir !== null ? `${String(akhir).replace(".", ",")}%` : "–"}</b>
            {naik !== null && v.filter((n) => n !== null).length > 1 && (
              <small className={naik > 0 ? s.naik : naik < 0 ? s.turun : undefined}>
                {naik > 0 ? "+" : ""}{String(Math.round(naik * 10) / 10).replace(".", ",")} poin
              </small>
            )}
          </div>
        );
      })}
      <p className={s.trenKet}>{tren.cutoff.join(" → ")}</p>
    </div>
  );
}

function Spark({ nilai }: { nilai: (number | null)[] }) {
  const W = 120, H = 32;
  const titik = nilai.map((v, i) => (v === null ? null : { x: nilai.length > 1 ? (i / (nilai.length - 1)) * (W - 6) + 3 : W / 2, y: H - 3 - (v / 100) * (H - 6) }));
  const ada = titik.filter(Boolean) as { x: number; y: number }[];
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" className={s.spark}>
      <line x1="0" x2={W} y1={H - 3} y2={H - 3} className={s.sparkDasar} />
      {ada.length > 1 && <polyline points={ada.map((p) => `${p.x},${p.y}`).join(" ")} className={s.sparkGaris} />}
      {ada.length > 0 && <circle cx={ada[ada.length - 1].x} cy={ada[ada.length - 1].y} r="3.5" className={s.sparkTitik} />}
    </svg>
  );
}

type KolomFasil = "nama" | "sekolah" | "perlu" | "todo" | "isian" | "terhubung" | "tidak" | "telepon";

function TabelFasil({ data }: { data: Dash["fasil"] }) {
  const [urut, setUrut] = useState<{ k: KolomFasil; naik: boolean }>({ k: "todo", naik: false });
  const [cari, setCari] = useState("");
  const [semua, setSemua] = useState(false);
  const baris = useMemo(() => {
    const q = cari.toLowerCase();
    const nilai = (r: Dash["fasil"][number]) => urut.k === "nama" ? r.nama.toLowerCase()
      : urut.k === "isian" ? (r.perlu ? r.lengkap / r.perlu : 2) : r[urut.k];
    return data.filter((r) => !q || r.nama.toLowerCase().includes(q)).sort((a, b) => {
      const x = nilai(a), y = nilai(b);
      const c = x < y ? -1 : x > y ? 1 : 0;
      return urut.naik ? c : -c;
    });
  }, [data, urut, cari]);
  const th = (k: KolomFasil, label: string, num = true) => {
    const aktif = urut.k === k;
    return (
      <th className={num ? s.num : undefined} aria-sort={aktif ? (urut.naik ? "ascending" : "descending") : "none"}>
        <button type="button" onClick={() => setUrut({ k, naik: aktif ? !urut.naik : k === "nama" })}>
          {label}{aktif ? (urut.naik ? " ↑" : " ↓") : ""}
        </button>
      </th>
    );
  };
  return (
    <>
      <input type="search" className={s.cari} placeholder="Cari fasil" value={cari} onChange={(e) => setCari(e.target.value)} aria-label="Cari fasil" />
      <div className={s.tabelWrap}>
        <table className={s.tabel}>
          <thead>
            <tr>
              {th("nama", "Fasil", false)}{th("sekolah", "Sekolah")}{th("perlu", "Punya to-do")}{th("todo", "To-do")}
              {th("isian", "Isian sesi")}{th("terhubung", "Terhubung")}{th("tidak", "Tidak sampai / dibaca")}{th("telepon", "Ditelepon")}
              <th>Hari ini</th>
            </tr>
          </thead>
          <tbody>
            {(semua || cari ? baris : baris.slice(0, 20)).map((r) => (
              <tr key={r.nama}>
                <td>{r.nama}{r.todo_fasil > 0 && <small>{r.todo_fasil} reviu menunggu{r.tunggu_maks ? `, terlama ${Math.round(r.tunggu_maks)} hari` : ""}</small>}</td>
                <td className={s.num}>{r.sekolah}</td>
                <td className={s.num}>{r.perlu}</td>
                <td className={s.num}>{r.todo}</td>
                <td className={s.num}>{r.perlu ? `${r.lengkap}/${r.perlu}` : "–"}</td>
                <td className={s.num}>{r.terhubung}{r.lambat ? <small>+{r.lambat} lambat</small> : null}</td>
                <td className={`${s.num} ${r.tidak >= 2 && !r.telepon ? s.merah : ""}`}>{r.tidak}</td>
                <td className={s.num}>{r.telepon}</td>
                <td><Chip tone={KELOMPOK_INFO[r.kelompok].tone}>{KELOMPOK_INFO[r.kelompok].label}</Chip></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!semua && !cari && baris.length > 20 && (
        <button type="button" className={s.lebih} onClick={() => setSemua(true)}>Tampilkan semua {baris.length} fasil</button>
      )}
    </>
  );
}
