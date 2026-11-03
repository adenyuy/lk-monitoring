"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { SurveiFasil, SurveiProgres, SurveiStatus } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { SurveiDialog } from "@/components/today/SurveiProgres";
import s from "./survei.module.css";

type Saring = "semua" | "belum_kirim" | "belum_isi" | "sebagian" | "tuntas" | "membalas";

const SARING: { k: Saring; label: string; cocok: (f: SurveiFasil) => boolean }[] = [
  { k: "semua", label: "Semua", cocok: () => true },
  { k: "belum_kirim", label: "Link belum terkirim", cocok: (f) => f.kirim !== "terkirim" },
  { k: "belum_isi", label: "Belum mengisi", cocok: (f) => f.terisi === 0 },
  { k: "sebagian", label: "Sebagian", cocok: (f) => f.terisi > 0 && f.terisi < f.total },
  { k: "tuntas", label: "Tuntas", cocok: (f) => f.total > 0 && f.terisi >= f.total },
  { k: "membalas", label: "Membalas", cocok: (f) => f.wa === "dibalas" },
];

const persen = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);

function jam(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(+d) ? iso : d.toLocaleString("id-ID", { weekday: "short", hour: "2-digit", minute: "2-digit" }).replace(":", ".");
}

function ChipKirim({ f }: { f: SurveiFasil }) {
  if (f.kirim === "terkirim") return <Chip tone="ok">Terkirim {jam(f.kirim_waktu)}</Chip>;
  if (f.kirim === "gagal") return <span title={f.kirim_ket}><Chip tone="bad">Gagal</Chip></span>;
  if (f.kirim === "tanpa_nomor") return <Chip tone="warn">Nomor kosong</Chip>;
  if (f.kirim === "dilewati") return <span title={f.kirim_ket}><Chip tone="warn">Dilewati</Chip></span>;
  return <Chip tone="muted">Belum dikirim</Chip>;
}

function ChipWa({ f }: { f: SurveiFasil }) {
  if (f.wa === "dibalas") return <Chip tone="ok">Membalas</Chip>;
  if (f.wa === "dibaca") return <Chip tone="info">Dibaca</Chip>;
  if (f.wa === "terkirim") return <Chip tone="muted">Belum dibaca</Chip>;
  return <span className={s.strip}>–</span>;
}

export function SurveiView() {
  const [st, setSt] = useState<SurveiStatus | null>(null);
  const [cfg, setCfg] = useState<SurveiProgres | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [atur, setAtur] = useState(false);
  const [coba, setCoba] = useState(false);
  const [busy, setBusy] = useState<"" | "kirim" | "stop" | "selesai" | "muat">("");
  const [saring, setSaring] = useState<Saring>("semua");
  const [cari, setCari] = useState("");
  const [buka, setBuka] = useState<string | null>(null);

  const muat = useCallback(async (segar = false) => {
    try {
      const [a, b] = await Promise.all([
        api<SurveiStatus>(`/api/survei-progres/status${segar ? "?segar=1" : ""}`),
        api<SurveiProgres>("/api/survei-progres"),
      ]);
      setSt(a);
      setCfg(b);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  usePolling(() => muat(), st?.kirim.running ? 4000 : 30000, true);

  const daftar = useMemo(() => {
    const q = cari.trim().toLowerCase();
    const f = SARING.find((x) => x.k === saring)!;
    return (st?.fasil ?? []).filter((x) => f.cocok(x) && (!q || x.nama.toLowerCase().includes(q)
      || x.sekolah.some((y) => y.nama.toLowerCase().includes(q) || y.npsn.includes(q))));
  }, [st, saring, cari]);

  async function aksi(jenis: typeof busy, fn: () => Promise<unknown>) {
    setBusy(jenis);
    setError(null);
    try {
      await fn();
      await muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  function kirim() {
    void aksi("kirim", async () => {
      if (!st?.aktif && cfg) {
        await post("/api/survei-progres", { aktif: true, sheet: cfg.dari_tim ? "" : cfg.sheet,
          link: cfg.dari_tim ? "" : cfg.link, teks: cfg.teks });
      }
      await post("/api/send/start", { coba });
    });
  }

  function selesai() {
    if (!cfg) return;
    void aksi("selesai", () => post("/api/survei-progres", { aktif: false, sheet: cfg.dari_tim ? "" : cfg.sheet,
      link: cfg.dari_tim ? "" : cfg.link, teks: cfg.teks }));
  }

  if (!st || !cfg) {
    return error ? <Notice tone="bad" title="Halaman Survei tidak bisa dimuat">{error}</Notice>
      : <div className={s.loading}><Spinner label="Memuat" /> Membaca LK Survey…</div>;
  }

  const r = st.ringkasan;
  const k = st.kirim;
  const sisa = st.bisa_kirim ?? 0;

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Survei Progres</h1>
          <p>Kirim link survei realisasi progres fisik ke fasil binaan Anda, lalu pantau siapa yang sudah membaca,
            membalas, dan mengisi.</p>
        </div>
        <div className={s.headAksi}>
          {st.siap && (
            <Button variant="ghost" size="sm" loading={busy === "muat"} onClick={() => void aksi("muat", () => muat(true))}>
              Muat ulang data
            </Button>
          )}
          <Button variant="secondary" size="sm" disabled={k.running} onClick={() => setAtur(true)}>
            {cfg.dari_tim ? "Ubah teks pesan" : "Atur survei"}</Button>
        </div>
      </header>

      {error && <Notice tone="bad" title="Ada kendala">{error}</Notice>}
      {st.galat && <Notice tone="bad" title="LK Survey belum bisa dibaca">{st.galat}</Notice>}

      {!st.siap ? (
        <section className={s.kosong}>
          <h2>Link LK Survey belum dipasang</h2>
          <p>Biasanya link ini sudah diatur admin untuk seluruh tim. Bila belum, tempel link sheet LK Survey di sini.
            Penerima diambil otomatis dari baris yang kolom PETUGAS PIC-nya nama Anda.</p>
          <Button onClick={() => setAtur(true)}>Atur survei</Button>
        </section>
      ) : (
        <>
          {r && (
            <section className={s.kpi} aria-label="Ringkasan">
              <div className={s.tile}>
                <span>Link terkirim</span>
                <b>{r.terkirim}<small> / {r.fasil} fasil</small></b>
                <div className={s.meter}><i style={{ width: `${persen(r.terkirim, r.fasil)}%` }} /></div>
              </div>
              <div className={s.tile}>
                <span>Dibaca</span>
                <b>{r.dibaca}<small> fasil</small></b>
                <div className={s.meter}><i style={{ width: `${persen(r.dibaca, r.fasil)}%` }} /></div>
              </div>
              <div className={s.tile}>
                <span>Membalas</span>
                <b>{r.dibalas}<small> fasil</small></b>
                <div className={s.meter}><i style={{ width: `${persen(r.dibalas, r.fasil)}%` }} /></div>
              </div>
              <div className={`${s.tile} ${s.tileUtama}`}>
                <span>Sekolah terisi</span>
                <b>{r.terisi}<small> / {r.sekolah} ({persen(r.terisi, r.sekolah)}%)</small></b>
                <div className={s.meter}><i className={s.hijau} style={{ width: `${persen(r.terisi, r.sekolah)}%` }} /></div>
                <em>{r.tuntas} dari {r.fasil} fasil sudah tuntas</em>
              </div>
            </section>
          )}

          <section className={s.kontrol} aria-label="Kirim link">
            {k.running ? (
              <>
                <div className={s.kontrolTeks}>
                  <span className={s.live} aria-hidden="true" />
                  <div>
                    <b>{k.coba ? "Mencoba" : "Mengirim"} {Math.min(k.dicoba + 1, k.target)} dari {k.target} pesan</b>
                    <span>{k.berikutnya ? `Berikutnya ke ${k.berikutnya}.` : k.sekarang ? `Memproses ${k.sekarang}.` : "Menyiapkan…"}
                      {" "}Biarkan aplikasi dan WhatsApp tetap terbuka.</span>
                  </div>
                </div>
                <Button variant="danger" size="sm" loading={busy === "stop"} disabled={k.stop_diminta}
                  onClick={() => void aksi("stop", () => post("/api/send/stop", {}))}>
                  {k.stop_diminta ? "Berhenti setelah pesan ini…" : "Berhenti setelah pesan ini"}
                </Button>
              </>
            ) : sisa > 0 ? (
              <>
                <div className={s.kontrolTeks}>
                  <div>
                    <b>{sisa} fasil belum dikirimi link</b>
                    <span>Dikirim langsung tanpa menunggu sesi, jeda acak 15–50 detik, pukul 07.00–22.00. Tiap fasil
                      dikirimi sekali.</span>
                  </div>
                </div>
                <div className={s.kontrolAksi}>
                  <button type="button" className={s.toggle} aria-pressed={coba} onClick={() => setCoba(!coba)}>
                    <span className={s.knob} aria-hidden="true" />Mode coba
                  </button>
                  <Button loading={busy === "kirim"} onClick={kirim}>
                    {coba ? `Coba ${Math.min(3, sisa)} pesan` : `Kirim link ke ${sisa} fasil`}
                  </Button>
                </div>
              </>
            ) : (
              <div className={s.kontrolTeks}>
                <div>
                  <b>Link sudah terkirim ke semua fasil yang punya nomor WhatsApp</b>
                  <span>Pantau pengisiannya di tabel. Data pengisian diperbarui otomatis tiap 30 detik.</span>
                </div>
              </div>
            )}
            {st.aktif && !k.running && (
              <div className={s.modeAktif}>
                <span>Halaman Blast sedang memakai mode Survei, jadi progres mingguan menunggu.</span>
                <Button variant={sisa === 0 ? "primary" : "secondary"} size="sm" loading={busy === "selesai"} onClick={selesai}>
                  Kembali ke progres mingguan
                </Button>
              </div>
            )}
            {k.berhenti_karena && !k.running && <p className={s.berhenti}>{k.berhenti_karena}</p>}
          </section>

          <section className={s.tabelKartu} aria-label="Per fasil">
            <div className={s.alat}>
              <div className={s.tabs} role="tablist">
                {SARING.map((x) => {
                  const n = (st.fasil ?? []).filter(x.cocok).length;
                  return (
                    <button key={x.k} type="button" role="tab" aria-selected={saring === x.k} className={s.tab}
                      onClick={() => setSaring(x.k)}>{x.label} <span>{n}</span></button>
                  );
                })}
              </div>
              <input className={s.cari} type="search" value={cari} onChange={(e) => setCari(e.target.value)}
                placeholder="Cari fasil, sekolah, atau NPSN" aria-label="Cari" />
            </div>

            <div className={s.tabel}>
              <div className={`${s.baris} ${s.judul}`}>
                <span>Fasil</span>
                <span>Link survei</span>
                <span>WhatsApp</span>
                <span>Pengisian</span>
                <span>Terakhir isi</span>
              </div>
              {daftar.length === 0 && <p className={s.kosongTabel}>Tidak ada fasil yang cocok.</p>}
              {daftar.map((f) => {
                const kunci = f.nomor || f.nama;
                const terbuka = buka === kunci;
                const p = persen(f.terisi, f.total);
                return (
                  <div key={kunci} className={`${s.grup} ${terbuka ? s.grupBuka : ""}`}>
                    <button type="button" className={s.baris} aria-expanded={terbuka}
                      onClick={() => setBuka(terbuka ? null : kunci)}>
                      <span className={s.fasil}>
                        <b>{f.nama}</b>
                        <small>{f.nomor_tersamar || "Nomor kosong"} · {f.total} sekolah</small>
                      </span>
                      <span data-label="Link survei"><ChipKirim f={f} /></span>
                      <span data-label="WhatsApp" className={s.wa}>
                        <ChipWa f={f} />
                        {f.balasan && <small title={f.balasan}>“{f.balasan}”</small>}
                      </span>
                      <span data-label="Pengisian" className={s.isi}>
                        <span className={s.isiAtas}><b>{f.terisi}/{f.total}</b><small>{p}%</small></span>
                        <span className={s.bar}><i className={p >= 100 ? s.hijau : ""} style={{ width: `${p}%` }} /></span>
                      </span>
                      <span data-label="Terakhir isi" className={s.waktu}>{f.terakhir_isi || "–"}</span>
                    </button>
                    {terbuka && (
                      <ul className={s.sekolah}>
                        {f.sekolah.map((x) => (
                          <li key={x.npsn || x.nama}>
                            <span><b>{x.nama}</b><small>NPSN {x.npsn}</small></span>
                            {x.isian ? <Chip tone="ok">{x.isian.replace(".", ",")}%{x.waktu ? ` · ${x.waktu}` : ""}</Chip>
                              : <Chip tone="warn">Belum diisi</Chip>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}

      {atur && (
        <SurveiDialog data={cfg} onClose={() => setAtur(false)}
          onSaved={(d) => { setCfg(d); setAtur(false); void muat(true); }} />
      )}
    </div>
  );
}
