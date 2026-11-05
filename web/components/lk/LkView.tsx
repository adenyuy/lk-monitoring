"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { KELOMPOK_INFO, KODE_WARNA, hariPendek, inisial, type FasilLk, type Kelompok, type LkRingkasan } from "@/lib/lk";
import { Button, Notice, Spinner } from "@/components/ui";
import { FasilPanel } from "./FasilPanel";
import { KodePicker } from "./KodePicker";
import s from "./lk.module.css";

type Filter = Kelompok | "semua";
const PER_HAL = 30;

/** Halaman LK: fasil binaan dikelompokkan menurut keadaan komunikasi hari ini, lalu to-do sekolahnya. */
export function LkView() {
  const router = useRouter();
  const params = useSearchParams();
  const [data, setData] = useState<LkRingkasan | null>(null);
  const [error, setError] = useState<{ status?: number; pesan: string } | null>(null);
  const [filter, setFilter] = useState<Filter>("semua");
  const [tag, setTag] = useState("");
  const [cari, setCari] = useState("");
  const [hal, setHal] = useState(0);
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

  const baris = useMemo(() => {
    if (!data) return [];
    const q = cari.trim().toLowerCase();
    return data.fasil.filter((f) => (filter === "semua" || f.kelompok === filter) && (!tag || f.tag.includes(tag))
      && (!q || f.nama.toLowerCase().includes(q) || f.ptn.toLowerCase().includes(q)));
  }, [data, filter, tag, cari]);

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
  const tampil = baris.slice(hal * PER_HAL, (hal + 1) * PER_HAL);
  const jmlHal = Math.ceil(baris.length / PER_HAL);
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

      {data.indikator.length > 0 && (
        <section className={s.insight} aria-label="Perlu perhatian">
          {data.indikator.map((x) => (
            <div key={x.kode} className={`${s.insightItem} ${x.nada === "warn" ? s.insightWarn : ""}`}>
              <b>{x.judul}</b>
              <span>{x.isi}</span>
            </div>
          ))}
        </section>
      )}

      <section className={s.card}>
        <div className={s.kelompokBar} role="tablist" aria-label="Kelompok fasil">
          <button type="button" role="tab" aria-selected={filter === "semua"} onClick={() => { setFilter("semua"); setHal(0); }}
            className={s.kelompokTab}>
            <span>Semua</span><b>{t.fasil}</b>
          </button>
          {data.kelompok.map((k) => (
            <button key={k.kode} type="button" role="tab" aria-selected={filter === k.kode} title={k.arti}
              className={`${s.kelompokTab} ${s[`kt_${k.kode}`]}`} disabled={!k.jumlah}
              onClick={() => { setFilter(k.kode); setHal(0); }}>
              <span>{k.label}</span><b>{k.jumlah}</b>
            </button>
          ))}
        </div>

        <div className={s.alat}>
          <input type="search" placeholder="Cari nama fasil atau PTN" value={cari} aria-label="Cari fasil"
            onChange={(e) => { setCari(e.target.value); setHal(0); }} />
          {data.tag.length > 0 && (
            <div className={s.tagFilter} aria-label="Saring tag">
              {data.tag.map((x) => (
                <button key={x} type="button" aria-pressed={tag === x} onClick={() => { setTag(tag === x ? "" : x); setHal(0); }}>
                  #{x}
                </button>
              ))}
            </div>
          )}
          <span className={s.jumlah}>{baris.length} fasil</span>
        </div>

        {filter !== "semua" && (
          <p className={s.artiKelompok}>{data.kelompok.find((k) => k.kode === filter)?.arti}</p>
        )}

        <ul className={s.daftar}>
          {tampil.map((f) => (
            <li key={f.kunci}>
              <FasilBaris f={f} hari={data.hari} logAda={data.log_hari_ini} waOtomatis={data.wa_otomatis}
                kode={data.kode} onBuka={() => setBuka(f.kunci)} onKode={(k) => void setKode(f, k)} />
            </li>
          ))}
          {!tampil.length && <li className={s.kosong}>Tidak ada fasil di kelompok ini.</li>}
        </ul>

        {jmlHal > 1 && (
          <nav className={s.hal} aria-label="Halaman">
            <Button variant="secondary" size="sm" disabled={hal === 0} onClick={() => setHal(hal - 1)}>Sebelumnya</Button>
            <span>{hal + 1} / {jmlHal}</span>
            <Button variant="secondary" size="sm" disabled={hal >= jmlHal - 1} onClick={() => setHal(hal + 1)}>Berikutnya</Button>
          </nav>
        )}
      </section>

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

function FasilBaris({ f, hari, logAda, waOtomatis, kode, onBuka, onKode }: {
  f: FasilLk; hari: string; logAda: boolean; waOtomatis: boolean; kode: { kode: string; arti: string }[];
  onBuka: () => void; onKode: (k: string) => void;
}) {
  const info = KELOMPOK_INFO[f.kelompok];
  const pct = f.perlu ? Math.round((f.lengkap / f.perlu) * 100) : 100;
  return (
    <div className={s.baris}>
      <button type="button" className={s.barisUtama} onClick={onBuka} aria-label={`Buka ${f.nama}`}>
        <span className={`${s.avatar} ${s[`av_${info.tone}`]}`} aria-hidden="true">{inisial(f.nama)}</span>
        <span className={s.barisNama}>
          <b>{f.nama}</b>
          <small>{f.ptn || "PTN belum tercatat"}{!f.punya_nomor && <> · <em>nomor WA kosong</em></>}</small>
          {f.tag.length > 0 && <span className={s.tagKecil}>{f.tag.map((x) => <i key={x}>#{x}</i>)}</span>}
        </span>
        <span className={s.barisFokus}>
          {f.fokus.length ? f.fokus.slice(0, 2).map((x) => (
            <span key={x.judul}>{x.judul}<i>×{x.jumlah}</i></span>
          )) : <span className={s.hijau}>Semua sekolah hijau</span>}
          {f.todo_fasil > 0 && <small>{f.todo_fasil} reviu menunggu fasil{f.tunggu_maks ? `, terlama ${Math.round(f.tunggu_maks)} hari` : ""}</small>}
        </span>
        <span className={s.barisIsian} title="Sekolah yang Kendala & Tindak Lanjut sesi ini sudah lengkap">
          <span className={s.mini}><span style={{ width: `${pct}%` }} /></span>
          <small>{f.lengkap}/{f.perlu} isian</small>
        </span>
        <span className={s.minggu} aria-label="Log komunikasi minggu ini">
          {f.kode_minggu.map((d) => (
            <i key={d.tanggal} title={`${hariPendek(d.tanggal)}: ${d.kode || "belum dicatat"}`}
              className={d.tanggal === hari ? s.hariIni : undefined}
              style={d.kode ? { background: KODE_WARNA[d.kode]?.bg, color: KODE_WARNA[d.kode]?.fg } : undefined}>
              {d.kode || Number(d.tanggal.slice(8))}
            </i>
          ))}
        </span>
      </button>
      <div className={s.barisAksi}>
        {(f.tanpa_progres || f.belum_ditelepon) && (
          <span className={s.flag} title={f.tanpa_progres ? "Sering terhubung tapi laporannya tidak bergerak sejak cutoff sebelumnya"
            : "Berkali-kali hanya dibaca / tidak sampai, belum pernah ditelepon"}>
            {f.tanpa_progres ? "Respon tanpa progres" : "Belum ditelepon"}
          </span>
        )}
        {logAda && (
          <KodePicker nilai={f.kode_hari_ini} kode={kode} onPilih={onKode}
            label={waOtomatis ? "Otomatis dari WA, bisa diubah" : "Catat komunikasi hari ini"} />
        )}
      </div>
    </div>
  );
}
