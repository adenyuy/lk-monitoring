"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { KELOMPOK_INFO, hariPendek, type FasilLk, type Kelompok, type LkRingkasan } from "@/lib/lk";
import { Button, Notice, Spinner } from "@/components/ui";
import { FasilPanel } from "./FasilPanel";
import { KodePicker } from "./KodePicker";
import s from "./lk.module.css";

/** Halaman LK: fasil binaan dikelompokkan menurut keadaan komunikasi hari ini, lalu to-do sekolahnya. */
export function LkView() {
  const router = useRouter();
  const params = useSearchParams();
  const [data, setData] = useState<LkRingkasan | null>(null);
  const [error, setError] = useState<{ status?: number; pesan: string } | null>(null);
  const [buka, setBuka] = useState<string | null>(params?.get("fasil") ?? null);
  const [muatUlang, setMuatUlang] = useState(false);

  const muat = useCallback(async (paksa = false) => {
    try {
      if (paksa) setMuatUlang(true);
      setData(await api<LkRingkasan>(`/api/lk2${paksa ? "?refresh=true" : ""}`));
      setError(null);
    } catch (e) {
      const st = (e as { status?: number }).status;
      setError({ status: st, pesan: e instanceof Error ? e.message : String(e) });
    } finally {
      setMuatUlang(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  usePolling(() => muat(), 120000, !buka);

  useEffect(() => {
    const h = (e: Event) => setBuka((e as CustomEvent<string>).detail);
    window.addEventListener("lkm-buka-fasil", h);
    return () => window.removeEventListener("lkm-buka-fasil", h);
  }, []);

  const tutup = useCallback(() => {
    setBuka(null);
    if (params?.get("fasil")) router.replace("/lk/");
    void muat();
  }, [muat, params, router]);

  async function setKode(f: FasilLk, kode: string) {
    setData((d) => d && { ...d, fasil: d.fasil.map((x) => (x.kunci === f.kunci ? { ...x, kode_hari_ini: kode as FasilLk["kode_hari_ini"] } : x)) });
    try {
      await post("/api/lk2/komunikasi", { kunci: f.kunci, kode });
      void muat();
    } catch (e) {
      setError({ pesan: e instanceof Error ? e.message : String(e) });
      void muat();
    }
  }

  async function setWa(aktif: boolean) {
    setData((d) => d && { ...d, wa_otomatis: aktif });
    try {
      await post("/api/lk2/wa-otomatis", { aktif });
      window.dispatchEvent(new CustomEvent("lkm-wa-otomatis", { detail: aktif }));
    } catch {
      void muat();
    }
  }

  if (error && !data) {
    return (
      <div className={s.page}>
        <Notice tone={error.status === 428 ? "info" : "bad"} title={error.status === 428 ? "LK belum terpasang" : "LK tidak bisa dimuat"}>
          {error.pesan} {error.status === 428 && <a href="/admin/">Buka halaman Admin</a>}
        </Notice>
      </div>
    );
  }
  if (!data) return <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>;

  const t = data.total;
  const pctIsi = t.perlu ? Math.round((t.lengkap / t.perlu) * 100) : 100;
  const pctHub = t.fasil ? Math.round((t.dihubungi / t.fasil) * 100) : 0;
  const mulaiLog = data.log_rentang[0];

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <p className={s.eyebrow}>WEEK {data.week} · {data.tanggal_panjang}</p>
          <h1>Lembar kerja</h1>
          <p className={s.sub}>
            Isi sesi <b>{data.blok_label}</b>. {data.cutoff ? <>Data {data.cutoff.replace(/^Cutoff \d+ /, "cutoff ")}.</> : null}
          </p>
        </div>
        <div className={s.headAksi}>
          <label className={s.saklar} title="Matikan bila Anda memakai WhatsApp di HP sendiri dan hanya mengisi LK">
            <input type="checkbox" role="switch" checked={data.wa_otomatis} onChange={(e) => void setWa(e.target.checked)} />
            <span className={s.saklarTrack} aria-hidden="true"><span /></span>
            <span><b>WhatsApp otomatis</b><small>{data.wa_otomatis ? "Chat dibaca & kode komunikasi terisi sendiri" : "Mati: catat kode komunikasi manual"}</small></span>
          </label>
          <Button variant="secondary" size="sm" loading={muatUlang} onClick={() => void muat(true)}>Muat ulang</Button>
        </div>
      </header>

      {!data.log_hari_ini && mulaiLog && (
        <Notice tone="info" title={mulaiLog > data.hari ? `Log Komunikasi WEEK ${data.week} mulai ${hariPendek(mulaiLog)} ${bulan(mulaiLog)}` : "Hari ini belum ada kolom di Log Komunikasi"}>
          {mulaiLog > data.hari
            ? "Kode komunikasi harian baru bisa dicatat mulai tanggal itu. Isian Kendala dan Tindak Lanjut sudah bisa diisi sekarang."
            : "Admin perlu membuat WEEK baru di halaman Tarik Cutoff supaya kolom tanggalnya tersedia."}
        </Notice>
      )}

      <section className={s.ringkas} aria-label="Ringkasan hari ini">
        <Meter judul={`Isian sesi ${data.blok_label}`} nilai={t.lengkap} dari={t.perlu} satuan="sekolah" pct={pctIsi}
          ket={t.perlu ? `${t.perlu - t.lengkap} sekolah belum lengkap Kendala & Tindak Lanjut-nya` : "Tidak ada yang perlu diisi"} />
        <Meter judul="Dihubungi hari ini" nilai={t.dihubungi} dari={t.fasil} satuan="fasil" pct={pctHub}
          ket={data.log_hari_ini ? "Tercatat di Log Komunikasi" : "Log Komunikasi belum dibuka untuk hari ini"} />
        <div className={s.angka}>
          <span>To-do terbuka</span>
          <b>{t.todo.toLocaleString("id-ID")}</b>
          <small>di {t.perlu} dari {t.sekolah} sekolah binaan</small>
        </div>
      </section>

      {data.indikator.length > 0 && <Insight daftar={data.indikator} onBuka={setBuka} />}

      <Papan data={data} onBuka={setBuka} onKode={(f, k) => void setKode(f, k)} />
      <PapanKom data={data} onBuka={setBuka} onKode={(f, k) => void setKode(f, k)} />

      {buka && <FasilPanel kunci={buka} onClose={tutup} kodeLabel={data.kode} />}
    </div>
  );
}

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const bulan = (iso: string) => BULAN[Number(iso.slice(5, 7)) - 1];

function Meter({ judul, nilai, dari, satuan, pct, ket }: {
  judul: string; nilai: number; dari: number; satuan: string; pct: number; ket: string;
}) {
  return (
    <div className={s.meter}>
      <div className={s.meterTop}>
        <span>{judul}</span>
        <b>{nilai}<small>/{dari} {satuan}</small></b>
      </div>
      <div className={s.meterBar} role="meter" aria-valuemin={0} aria-valuemax={dari} aria-valuenow={nilai}
        aria-label={judul}>
        <span style={{ width: `${pct}%` }} />
      </div>
      <small>{ket}</small>
    </div>
  );
}

type Kolom = { kode: string; label: string; ket: string };

const KET_POSISI: Record<string, string> = {
  lp: "Sekolah belum mengirim; komponen lain menunggu",
  lp_rev: "Sudah dikirim, menunggu reviu fasil",
  mg: "Unggah atau reviu Lap. Mingguan",
  bulanan: "Bulanan, BKU, BPP diunggah bersama",
  progres: "Progres fisik belum cukup untuk laporan",
  l50: "Unggah atau reviu Lap. 50%",
  l100: "Unggah atau reviu Lap. 100%",
};

/** Papan kartu: tiap kolom satu komponen; fasil muncul di kolom tempat sekolah binaannya masih tertahan. */
function Insight({ daftar, onBuka }: { daftar: LkRingkasan["indikator"]; onBuka: (kunci: string) => void }) {
  const [buka, setBuka] = useState<string | null>(null);
  return (
    <section className={s.insight} aria-label="Perlu perhatian">
      {daftar.map((x) => {
        const terbuka = buka === x.kode;
        const fasil = x.fasil ?? [];
        return (
          <div key={x.kode} className={`${s.insightItem} ${x.nada === "warn" ? s.insightWarn : ""}`}>
            <button type="button" className={s.insightKepala} aria-expanded={terbuka} disabled={!fasil.length}
              onClick={() => setBuka(terbuka ? null : x.kode)}>
              <b>{x.judul}</b>
              <span>{x.isi}</span>
              {fasil.length > 0 && <small className={s.insightLihat}>{terbuka ? "Sembunyikan fasil ▴" : `Lihat ${fasil.length} fasil ▾`}</small>}
            </button>
            {terbuka && (
              <ul className={s.insightDaftar}>
                {fasil.map((f) => (
                  <li key={f.kunci}>
                    <button type="button" onClick={() => onBuka(f.kunci)} title={`Buka ${f.nama}`}>
                      <b>{f.nama}</b>
                      <small>{[f.ptn, f.ket].filter(Boolean).join(" · ")}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}

function Papan({ data, onBuka, onKode }: {
  data: LkRingkasan; onBuka: (kunci: string) => void; onKode: (f: FasilLk, kode: string) => void;
}) {
  const [fokus, setFokus] = useState<string>("semua");
  const [kel, setKel] = useState<Kelompok | "">("");
  const [tag, setTag] = useState("");
  const [cari, setCari] = useState("");

  const kolom: Kolom[] = useMemo(() => [
    ...data.posisi.map((p) => ({ kode: p.kode, label: p.label, ket: KET_POSISI[p.kode] ?? "" })),
    { kode: "hijau", label: "Semua hijau", ket: "Tidak ada to-do, cukup dipantau" },
  ], [data.posisi]);

  const saring = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return data.fasil.filter((f) => (!kel || f.kelompok === kel) && (!tag || f.tag.includes(tag))
      && (!q || f.nama.toLowerCase().includes(q) || f.ptn.toLowerCase().includes(q)));
  }, [data.fasil, kel, tag, cari]);

  const isi = useMemo(() => {
    const out: Record<string, FasilLk[]> = {};
    for (const k of kolom) {
      out[k.kode] = (k.kode === "hijau" ? saring.filter((f) => !f.perlu) : saring.filter((f) => f.posisi[k.kode]))
        .slice().sort((a, b) => (b.posisi[k.kode] ?? 0) - (a.posisi[k.kode] ?? 0) || a.nama.localeCompare(b.nama));
    }
    return out;
  }, [kolom, saring]);

  const satu = fokus !== "semua";
  const tampilKolom = satu ? kolom.filter((k) => k.kode === fokus) : kolom.filter((k) => isi[k.kode].length);
  const jmlSekolah = (k: string) => isi[k].reduce((n, f) => n + (f.posisi[k] ?? 0), 0);

  return (
    <section className={s.card} aria-labelledby="h-papan">
      <div className={s.papanHead}>
        <div>
          <h2 id="h-papan">Posisi fasil per komponen</h2>
          <p>Fasil muncul di setiap komponen tempat sekolah binaannya masih tertahan. Klik kartu untuk membuka LK fasil.</p>
        </div>
        <input type="search" placeholder="Cari nama fasil atau PTN" value={cari} aria-label="Cari fasil"
          onChange={(e) => setCari(e.target.value)} />
      </div>

      <div className={s.komponenBar} role="tablist" aria-label="Saring komponen">
        <button type="button" role="tab" aria-selected={!satu} onClick={() => setFokus("semua")}>
          <span>Semua komponen</span><b>{saring.length}</b>
        </button>
        {kolom.map((k) => (
          <button key={k.kode} type="button" role="tab" aria-selected={fokus === k.kode} disabled={!isi[k.kode].length}
            onClick={() => setFokus(fokus === k.kode ? "semua" : k.kode)}
            title={k.kode === "hijau" ? k.ket : `${isi[k.kode].length} fasil, ${jmlSekolah(k.kode)} sekolah`}>
            <span>{k.label}</span><b>{isi[k.kode].length}</b>
          </button>
        ))}
      </div>

      <div className={s.alat}>
        <label className={s.pilihKecil}>
          <span>Komunikasi hari ini</span>
          <select value={kel} onChange={(e) => setKel(e.target.value as Kelompok | "")}>
            <option value="">Semua ({data.total.fasil})</option>
            {data.kelompok.filter((k) => k.jumlah).map((k) => <option key={k.kode} value={k.kode}>{k.label} ({k.jumlah})</option>)}
          </select>
        </label>
        {data.tag.length > 0 && (
          <div className={s.tagFilter} aria-label="Saring tag">
            {data.tag.map((x) => (
              <button key={x} type="button" aria-pressed={tag === x} onClick={() => setTag(tag === x ? "" : x)}>#{x}</button>
            ))}
          </div>
        )}
        {kel && <span className={s.artiKelompok}>{data.kelompok.find((k) => k.kode === kel)?.arti}</span>}
      </div>

      <div className={`${s.board} ${satu ? s.boardSatu : ""}`}>
        {tampilKolom.map((k) => (
          <div key={k.kode} className={s.col}>
            <div className={s.colHead}>
              <b>{k.label}</b>
              <span className={s.colN} title="Jumlah fasil">{isi[k.kode].length}</span>
              <small>{k.kode === "hijau" ? k.ket : `${jmlSekolah(k.kode)} sekolah · ${k.ket}`}</small>
            </div>
            <ul className={s.colList}>
              {isi[k.kode].map((f) => (
                <li key={f.kunci}>
                  <KartuFasil f={f} kolom={k.kode} logAda={data.log_hari_ini} kode={data.kode}
                    onBuka={() => onBuka(f.kunci)} onKode={(x) => onKode(f, x)} />
                </li>
              ))}
              {!isi[k.kode].length && <li className={s.colEmpty}>Kosong</li>}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

const TONE_KOM: Record<string, string> = {
  perlu_balas: "ok", telepon: "bad", dibaca: "warn", terkirim: "info", menunggu: "info", terhubung: "ok", belum: "muted",
};

function jam(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"][d.getDay()]} ${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Papan kedua: tiap fasil di satu kolom menurut status komunikasinya minggu ini (sudah membalas atau belum). */
function PapanKom({ data, onBuka, onKode }: {
  data: LkRingkasan; onBuka: (kunci: string) => void; onKode: (f: FasilLk, kode: string) => void;
}) {
  const [cari, setCari] = useState("");
  const [hanyaTodo, setHanyaTodo] = useState(true);
  const isi = useMemo(() => {
    const q = cari.trim().toLowerCase();
    const out: Record<string, FasilLk[]> = {};
    for (const k of data.kom) out[k.kode] = [];
    for (const f of data.fasil) {
      if (hanyaTodo && !f.perlu) continue;
      if (q && !f.nama.toLowerCase().includes(q) && !f.ptn.toLowerCase().includes(q)) continue;
      (out[f.kom ?? "belum"] ??= []).push(f);
    }
    for (const k of Object.keys(out)) {
      out[k].sort((a, b) => (b.waktu_balasan ?? "").localeCompare(a.waktu_balasan ?? "") || b.perlu - a.perlu
        || a.nama.localeCompare(b.nama));
    }
    return out;
  }, [data.fasil, data.kom, cari, hanyaTodo]);

  return (
    <section className={s.card} aria-labelledby="h-papan-kom">
      <div className={s.papanHead}>
        <div>
          <h2 id="h-papan-kom">Status komunikasi minggu ini</h2>
          <p>Tiap fasil ada di satu kolom: dari chat WhatsApp minggu ini dan kode Log Komunikasi hari ini.</p>
        </div>
        <div className={s.papanAlat}>
          <label className={s.cek}><input type="checkbox" checked={hanyaTodo} onChange={(e) => setHanyaTodo(e.target.checked)} /> Hanya yang punya to-do</label>
          <input type="search" placeholder="Cari nama fasil atau PTN" value={cari} aria-label="Cari fasil di papan komunikasi"
            onChange={(e) => setCari(e.target.value)} />
        </div>
      </div>
      <div className={s.board}>
        {data.kom.map((k) => (
          <div key={k.kode} className={`${s.col} ${k.kode === "perlu_balas" && isi[k.kode]?.length ? s.colSorot : ""}`}>
            <div className={s.colHead}>
              <b>{k.label}</b>
              <span className={s.colN}>{isi[k.kode]?.length ?? 0}</span>
              <small>{k.arti}</small>
            </div>
            <ul className={s.colList}>
              {(isi[k.kode] ?? []).map((f) => (
                <li key={f.kunci}>
                  <KartuFasil f={f} kolom="" mode="kom" tone={TONE_KOM[k.kode]} logAda={data.log_hari_ini} kode={data.kode}
                    onBuka={() => onBuka(f.kunci)} onKode={(x) => onKode(f, x)} />
                </li>
              ))}
              {!(isi[k.kode] ?? []).length && <li className={s.colEmpty}>Kosong</li>}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function KartuFasil({ f, kolom, logAda, kode, onBuka, onKode, mode = "komponen", tone }: {
  f: FasilLk; kolom: string; logAda: boolean; kode: { kode: string; arti: string }[];
  onBuka: () => void; onKode: (k: string) => void; mode?: "komponen" | "kom"; tone?: string;
}) {
  const info = KELOMPOK_INFO[f.kelompok];
  const n = f.posisi[kolom] ?? 0;
  return (
    <div className={`${s.kartu} ${s[`kartu_${tone ?? info.tone}`] ?? ""}`}>
      <button type="button" className={s.kartuUtama} onClick={onBuka} aria-label={`Buka ${f.nama}`}>
        <b>{f.nama}</b>
        <small>{f.ptn || "PTN belum tercatat"}</small>
        <span className={s.kartuPil}>
          {mode === "komponen" && kolom !== "hijau" && <em className={s.pilSekolah}>{n} sekolah</em>}
          {mode === "kom" && f.perlu > 0 && <em className={s.pilSekolah}>{f.perlu} sekolah to-do</em>}
          {f.perlu > 0 && (
            <em className={f.lengkap >= f.perlu ? s.pilOk : s.pilIsian} title="Sekolah yang isian Kendala & TL sesi ini sudah lengkap">
              Isian {f.lengkap}/{f.perlu}
            </em>
          )}
          {!f.punya_nomor && <em className={s.pilMerah}>Nomor WA kosong</em>}
          {f.tanpa_progres && <em className={s.pilKuning} title="Sering terhubung tapi laporannya tidak bergerak sejak cutoff sebelumnya">Respon tanpa progres</em>}
          {f.belum_ditelepon && <em className={s.pilKuning} title="Berkali-kali hanya dibaca / tidak sampai, belum pernah ditelepon">Belum ditelepon</em>}
          {f.tag.map((x) => <em key={x} className={s.pilTag}>#{x}</em>)}
        </span>
        {mode === "kom" && f.balasan && (
          <span className={s.kartuBalasan} title={f.balasan}>{jam(f.waktu_balasan) && <i>{jam(f.waktu_balasan)}</i>}“{f.balasan}”</span>
        )}
      </button>
      {logAda && (
        <div className={s.kartuKaki}>
          <span>{mode === "kom" ? (f.kode_hari_ini ? "Log hari ini" : "Catat log hari ini") : info.label}</span>
          <KodePicker nilai={f.kode_hari_ini} kode={kode} onPilih={onKode}
            label={`Kode komunikasi hari ini untuk ${f.nama}`} />
        </div>
      )}
    </div>
  );
}
