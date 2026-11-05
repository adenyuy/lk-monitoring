"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api, post } from "@/lib/api";
import { Button, Notice, Spinner } from "@/components/ui";
import { SlideKanvas, type Slide } from "./SlideKanvas";
import s from "./paparan.module.css";

type Izin = { punya: boolean; status: string; error: string };
type Data = {
  pic: string; week: number; cutoff: string; tanggal: string; dibuat: string;
  daftar: { kunci: string; judul: string; aktif: boolean }[];
  langkah: string[]; catatan: Record<string, string>; slides: Slide[]; jumlah_masalah: number; izin: Izin;
};
type Simpanan = { urutan: string[]; mati: string[]; langkah: string[] | null; catatan: Record<string, string> };
type Gs = { tahap: "idle" | "izin" | "menunggu_izin" | "membuat" | "selesai"; url?: string; judul?: string; galat?: string };

const kunciSimpan = (d: Data) => `paparan:v1:${d.pic}:${d.week}`;

function bacaSimpanan(d: Data): Simpanan | null {
  try {
    const x = localStorage.getItem(kunciSimpan(d));
    return x ? (JSON.parse(x) as Simpanan) : null;
  } catch {
    return null;
  }
}

export function PaparanView() {
  const [d, setD] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);
  const [urutan, setUrutan] = useState<string[]>([]);
  const [mati, setMati] = useState<Set<string>>(new Set());
  const [langkah, setLangkah] = useState<string[] | null>(null);
  const [catatan, setCatatan] = useState<Record<string, string>>({});
  const [pilih, setPilih] = useState(0);
  const [tampilkan, setTampilkan] = useState(false);
  const [gs, setGs] = useState<Gs>({ tahap: "idle" });
  const siap = useRef(false);

  const muat = useCallback(async (paksa = false) => {
    setMemuat(true);
    try {
      const x = await api<Data>(`/api/paparan${paksa ? "?paksa=true" : ""}`);
      setD(x);
      setError(null);
      if (!siap.current) {
        const sv = bacaSimpanan(x);
        const semua = x.daftar.map((k) => k.kunci);
        const urut = sv ? [...sv.urutan.filter((k) => semua.includes(k)), ...semua.filter((k) => !sv.urutan.includes(k))] : semua;
        setUrutan(urut);
        setMati(new Set(sv ? sv.mati : x.daftar.filter((k) => !k.aktif).map((k) => k.kunci)));
        setLangkah(sv?.langkah ?? null);
        setCatatan(sv?.catatan ?? {});
        siap.current = true;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  // pilihan PIC diingat per WEEK di laptop ini
  useEffect(() => {
    if (!d || !siap.current) return;
    try {
      localStorage.setItem(kunciSimpan(d), JSON.stringify({ urutan, mati: [...mati], langkah, catatan } satisfies Simpanan));
    } catch { /* penyimpanan browser tidak tersedia */ }
  }, [d, urutan, mati, langkah, catatan]);

  const isiLangkah = useMemo(() => langkah ?? d?.langkah ?? [], [langkah, d]);
  const catatanDari = useCallback((k: string) => catatan[k] ?? d?.catatan[k] ?? "", [catatan, d]);
  const tampil = useMemo(() => {
    if (!d) return [];
    return urutan.filter((k) => !mati.has(k)).flatMap((k) => d.slides.filter((x) => x.kunci === k))
      .map((x) => (x.lanjutan ? x : { ...x, catatan: catatanDari(x.kunci) }));
  }, [d, urutan, mati, catatanDari]);
  const idx = Math.min(pilih, Math.max(tampil.length - 1, 0));
  const kini = tampil[idx];

  const geser = (k: string, arah: -1 | 1) => {
    setUrutan((u) => {
      const i = u.indexOf(k);
      const j = i + arah;
      if (i < 0 || j < 0 || j >= u.length) return u;
      const v = [...u];
      [v[i], v[j]] = [v[j], v[i]];
      return v;
    });
  };
  const alihkan = (k: string) => setMati((m) => {
    const v = new Set(m);
    if (v.has(k)) v.delete(k); else v.add(k);
    return v;
  });
  const lompatKe = (k: string) => {
    const i = tampil.findIndex((x) => x.kunci === k);
    if (i >= 0) setPilih(i);
  };

  const buat = useCallback(async () => {
    if (!d) return;
    setGs({ tahap: "membuat" });
    try {
      const urut = urutan.filter((k) => !mati.has(k));
      const r = await post<{ url: string; judul: string }>("/api/paparan/slides", {
        urutan: urut, langkah: isiLangkah,
        catatan: Object.fromEntries(urut.map((k) => [k, catatanDari(k)])),
      });
      setGs({ tahap: "selesai", url: r.url, judul: r.judul });
    } catch (e) {
      if (e instanceof ApiError && e.status === 428) {
        setGs({ tahap: "izin" });
        return;
      }
      setGs({ tahap: "idle", galat: e instanceof Error ? e.message : String(e) });
    }
  }, [d, urutan, mati, isiLangkah, catatanDari]);

  const mulaiGs = () => {
    if (!d) return;
    if (d.izin.punya) void buat();
    else setGs({ tahap: "izin" });
  };

  const beriIzin = async () => {
    setGs({ tahap: "menunggu_izin" });
    try {
      await post<Izin>("/api/paparan/izin");
      for (let i = 0; i < 200; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const st = await api<Izin>("/api/paparan/izin");
        if (st.punya) {
          setD((x) => (x ? { ...x, izin: st } : x));
          await buat();
          return;
        }
        if (st.status === "error") throw new Error(st.error || "Izin tidak diberikan.");
      }
      throw new Error("Izin belum diberikan. Coba tekan Buat Google Slides lagi.");
    } catch (e) {
      setGs({ tahap: "idle", galat: e instanceof Error ? e.message : String(e) });
    }
  };

  if (error && !d) return <Notice tone="bad" title="Paparan tidak bisa dimuat">{error}</Notice>;
  if (!d) return <div className={s.loading}><Spinner label="Memuat" /> Menyusun paparan…</div>;

  const jumlahHalaman = (k: string) => d.slides.filter((x) => x.kunci === k).length;

  return (
    <div className={`${s.page} ${memuat ? s.memuat : ""}`}>
      <header className={s.head}>
        <div>
          <p className={s.eyebrow}>WEEK {d.week}{d.cutoff ? `, ${d.cutoff}` : ""}</p>
          <h1>Paparan {d.pic}</h1>
          <p className={s.sub}>Data per {d.dibuat}. {tampil.length} slide akan dipaparkan.</p>
        </div>
        <div className={s.aksi}>
          <Button variant="ghost" onClick={() => void muat(true)} loading={memuat}>Perbarui data</Button>
          <Button variant="secondary" onClick={() => setTampilkan(true)} disabled={!tampil.length}>Presentasi</Button>
          <Button onClick={mulaiGs} disabled={!tampil.length} loading={gs.tahap === "membuat"}>Buat Google Slides</Button>
        </div>
      </header>

      {gs.galat && <Notice tone="bad" title="Google Slides belum jadi">{gs.galat}</Notice>}

      <div className={s.isi}>
        <aside className={s.daftar} aria-label="Susunan slide">
          <h2>Susunan slide</h2>
          <p className={s.ket}>Centang slide yang dipaparkan. Urutan bisa digeser.</p>
          <ol>
            {urutan.map((k, i) => {
              const info = d.daftar.find((x) => x.kunci === k);
              const aktif = !mati.has(k);
              const dipilih = kini?.kunci === k;
              const n = jumlahHalaman(k);
              return (
                <li key={k} className={`${s.item} ${dipilih ? s.itemPilih : ""} ${aktif ? "" : s.itemMati}`}>
                  <input type="checkbox" checked={aktif} onChange={() => alihkan(k)} aria-label={`Paparkan ${info?.judul}`} />
                  <button type="button" className={s.itemJudul} onClick={() => lompatKe(k)} disabled={!aktif}>
                    {info?.judul}
                    {n > 1 && <small>{n} halaman</small>}
                  </button>
                  <span className={s.geser}>
                    <button type="button" onClick={() => geser(k, -1)} disabled={i === 0} aria-label="Naikkan">↑</button>
                    <button type="button" onClick={() => geser(k, 1)} disabled={i === urutan.length - 1} aria-label="Turunkan">↓</button>
                  </span>
                </li>
              );
            })}
          </ol>
        </aside>

        <section className={s.kerja}>
          {kini ? (
            <>
              <div className={s.bingkai}><SlideKanvas slide={kini} langkah={isiLangkah} /></div>
              <div className={s.nav}>
                <Button variant="ghost" size="sm" onClick={() => setPilih(Math.max(idx - 1, 0))} disabled={idx === 0}>Sebelumnya</Button>
                <span>Slide {idx + 1} dari {tampil.length}</span>
                <Button variant="ghost" size="sm" onClick={() => setPilih(Math.min(idx + 1, tampil.length - 1))}
                  disabled={idx >= tampil.length - 1}>Berikutnya</Button>
              </div>
              <div className={s.strip} role="list" aria-label="Semua slide">
                {tampil.map((x, i) => (
                  <button key={i} type="button" role="listitem" className={`${s.mini} ${i === idx ? s.miniPilih : ""}`}
                    onClick={() => setPilih(i)} aria-label={`Slide ${i + 1}: ${x.judul}`}>
                    <SlideKanvas slide={x} langkah={isiLangkah} />
                    <span>{i + 1}</span>
                  </button>
                ))}
              </div>
              {!kini.lanjutan && (
                <div className={s.editor}>
                  {kini.kunci === "langkah" && (
                    <label className={s.field}>
                      <span>Isi slide <small>satu poin per baris</small></span>
                      <textarea rows={5} value={isiLangkah.join("\n")}
                        onChange={(e) => setLangkah(e.target.value.split("\n"))} />
                      {langkah && (
                        <button type="button" className={s.tautan} onClick={() => setLangkah(null)}>
                          Kembalikan ke usulan dari data
                        </button>
                      )}
                    </label>
                  )}
                  <label className={s.field}>
                    <span>Catatan pembicara <small>ikut ke Google Slides, tidak tampil di layar</small></span>
                    <textarea rows={3} value={catatanDari(kini.kunci)}
                      onChange={(e) => setCatatan((c) => ({ ...c, [kini.kunci]: e.target.value }))} />
                    {catatan[kini.kunci] !== undefined && (
                      <button type="button" className={s.tautan}
                        onClick={() => setCatatan((c) => { const v = { ...c }; delete v[kini.kunci]; return v; })}>
                        Kembalikan ke catatan dari data
                      </button>
                    )}
                  </label>
                </div>
              )}
            </>
          ) : (
            <p className={s.kosong}>Belum ada slide yang dicentang. Centang minimal satu slide di sebelah kiri.</p>
          )}
        </section>
      </div>

      {tampilkan && tampil.length > 0 && (
        <Presentasi slides={tampil} langkah={isiLangkah} mulai={idx}
          onTutup={(i) => { setPilih(i); setTampilkan(false); }} />
      )}

      {(gs.tahap === "izin" || gs.tahap === "menunggu_izin") && (
        <div className={s.scrim} role="presentation">
          <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="izin-judul">
            <h2 id="izin-judul">Izinkan aplikasi membuat Google Slides</h2>
            <p>
              Sekali saja: jendela Google akan terbuka. Pilih akun yang sama dengan akun LK Monitoring, lalu izinkan.
              Aplikasi hanya bisa membuka file yang dibuatnya sendiri, bukan isi Google Drive kamu yang lain.
            </p>
            {gs.tahap === "menunggu_izin" && (
              <p className={s.tunggu}><Spinner /> Menunggu izin dari jendela Google…</p>
            )}
            <div className={s.dialogAksi}>
              <Button variant="ghost" onClick={() => setGs({ tahap: "idle" })}>Batal</Button>
              <Button onClick={() => void beriIzin()} loading={gs.tahap === "menunggu_izin"}>Beri izin</Button>
            </div>
          </div>
        </div>
      )}

      {gs.tahap === "membuat" && (
        <div className={s.scrim} role="presentation">
          <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="buat-judul">
            <h2 id="buat-judul">Membuat Google Slides</h2>
            <p className={s.tunggu}><Spinner /> Menyusun {tampil.length} slide di Google Drive kamu. Biasanya 10–30 detik.</p>
          </div>
        </div>
      )}

      {gs.tahap === "selesai" && (
        <div className={s.scrim} role="presentation" onClick={() => setGs({ tahap: "idle" })}>
          <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="jadi-judul" onClick={(e) => e.stopPropagation()}>
            <h2 id="jadi-judul">Google Slides sudah jadi</h2>
            <p><b>{gs.judul}</b> tersimpan di Google Drive kamu. Semua teks, warna, dan grafiknya bisa diedit.</p>
            <div className={s.dialogAksi}>
              <Button variant="ghost" onClick={() => setGs({ tahap: "idle" })}>Tutup</Button>
              <a className={s.bukaLink} href={gs.url} target="_blank" rel="noreferrer">Buka Google Slides</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Presentasi({ slides, langkah, mulai, onTutup }: {
  slides: Slide[]; langkah: string[]; mulai: number; onTutup: (i: number) => void;
}) {
  const [i, setI] = useState(mulai);
  const [catat, setCatat] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const iRef = useRef(i);
  const tutupRef = useRef(onTutup);
  useEffect(() => { iRef.current = i; tutupRef.current = onTutup; });

  useEffect(() => {
    ref.current?.requestFullscreen?.().catch(() => undefined);
  }, []);

  useEffect(() => {
    const keluar = () => {
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
      tutupRef.current(iRef.current);
    };
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); setI((x) => Math.min(x + 1, slides.length - 1)); }
      else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
      else if (e.key === "Escape") keluar();
      else if (e.key.toLowerCase() === "n") setCatat((c) => !c);
      else if (e.key === "Home") setI(0);
      else if (e.key === "End") setI(slides.length - 1);
    };
    const onFs = () => { if (!document.fullscreenElement) tutupRef.current(iRef.current); };
    window.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onFs);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onFs);
    };
  }, [slides.length]);

  const x = slides[i];
  return (
    <div ref={ref} className={s.layar} role="dialog" aria-modal="true" aria-label="Mode presentasi">
      <div className={s.layarSlide} onClick={() => setI((v) => Math.min(v + 1, slides.length - 1))}>
        <SlideKanvas slide={x} langkah={langkah} muat />
      </div>
      {catat && x.catatan && <div className={s.layarCatatan}>{x.catatan}</div>}
      <div className={s.layarBar}>
        <button type="button" onClick={() => setI((v) => Math.max(v - 1, 0))} disabled={i === 0}>Sebelumnya</button>
        <span>{i + 1} / {slides.length}</span>
        <button type="button" onClick={() => setI((v) => Math.min(v + 1, slides.length - 1))} disabled={i >= slides.length - 1}>Berikutnya</button>
        <button type="button" onClick={() => setCatat((c) => !c)} aria-pressed={catat}>Catatan (N)</button>
        <button type="button" onClick={() => {
          if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
          onTutup(i);
        }}>Keluar (Esc)</button>
      </div>
    </div>
  );
}
