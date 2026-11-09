"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, post, upload } from "@/lib/api";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import s from "./forum.module.css";

type Ringkas = {
  id: string; judul: string; cuplikan: string; topik: string; nama: string; dibuat: string; aktif: string;
  jawaban: number; selesai: boolean; ada_foto: boolean; milik_saya: boolean; cari: string;
};
type Daftar = { items: Ringkas[]; topik: string[]; admin: boolean };
type Pos = {
  id: string; isi: string; foto: string[]; nama: string; dibuat: string; diubah: string; milik_saya: boolean;
  boleh_ubah: boolean;
};
type Detail = Pos & { judul: string; topik: string; solusi: string; jawaban: Pos[] };
type Izin = { punya: boolean; status: string; error: string };

const pesan = (e: unknown) => (e instanceof Error ? e.message : String(e));

// ---------- format ----------

function waktu(iso: string): string {
  if (!iso) return "";
  const t = new Date(iso);
  const detik = (Date.now() - t.getTime()) / 1000;
  if (detik < 60) return "baru saja";
  if (detik < 3600) return `${Math.floor(detik / 60)} menit lalu`;
  if (detik < 86400) return `${Math.floor(detik / 3600)} jam lalu`;
  if (detik < 172800) return "kemarin";
  if (detik < 7 * 86400) return `${Math.floor(detik / 86400)} hari lalu`;
  return t.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

/** Teks biasa dengan baris baru dan tautan yang bisa diklik. */
function Teks({ isi }: { isi: string }) {
  const bagian = isi.split(/(https?:\/\/[^\s]+)/g);
  return (
    <div className={s.teks}>
      {bagian.map((b, i) => (/^https?:\/\//.test(b)
        ? <a key={i} href={b} target="_blank" rel="noreferrer">{b}</a>
        : <Fragment key={i}>{b}</Fragment>))}
    </div>
  );
}

const fotoUrl = (id: string, w = 1600) => `https://lh3.googleusercontent.com/d/${id}=w${w}`;
const fotoCadangan = (id: string, w = 1600) => `https://drive.google.com/thumbnail?id=${id}&sz=w${w}`;

function Foto({ id, w, onClick }: { id: string; w?: number; onClick?: () => void }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={fotoUrl(id, w)} alt="Foto lampiran" loading="lazy" referrerPolicy="no-referrer" onClick={onClick}
      onError={(e) => {
        const img = e.currentTarget;
        if (!img.dataset.cadangan) { img.dataset.cadangan = "1"; img.src = fotoCadangan(id, w); }
      }} />
  );
}

function Galeri({ foto }: { foto: string[] }) {
  const [besar, setBesar] = useState<string | null>(null);
  if (!foto.length) return null;
  return (
    <>
      <div className={s.galeri}>
        {foto.map((f) => (
          <button key={f} type="button" className={s.galeriItem} onClick={() => setBesar(f)} aria-label="Perbesar foto">
            <Foto id={f} w={600} />
          </button>
        ))}
      </div>
      {besar && (
        <div className={s.lightbox} role="dialog" aria-modal="true" aria-label="Foto" onClick={() => setBesar(null)}>
          <Foto id={besar} />
          <a href={`https://drive.google.com/file/d/${besar}/view`} target="_blank" rel="noreferrer"
            onClick={(e) => e.stopPropagation()}>Buka di Google Drive</a>
        </div>
      )}
    </>
  );
}

// ---------- unggah foto ----------

/** Perkecil foto di browser (maks 1600 px, JPEG) supaya unggah cepat. GIF dibiarkan. */
async function perkecil(file: File): Promise<File> {
  if (file.type === "image/gif" || !file.type.startsWith("image/")) return file;
  const bmp = await createImageBitmap(file).catch(() => null);
  if (!bmp) return file;
  const skala = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * skala);
  c.height = Math.round(bmp.height * skala);
  c.getContext("2d")?.drawImage(bmp, 0, 0, c.width, c.height);
  const blob = await new Promise<Blob | null>((r) => c.toBlob(r, "image/jpeg", 0.85));
  if (!blob || blob.size >= file.size) return file;
  return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
}

type FotoItem = { kunci: string; id?: string; pratinjau: string; galat?: string };

function PilihFoto({ nilai, onChange, onSibuk }: {
  nilai: FotoItem[]; onChange: (f: FotoItem[]) => void; onSibuk: (b: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [izin, setIzin] = useState<"tutup" | "tanya" | "menunggu">("tutup");
  const [galat, setGalat] = useState("");
  const tunda = useRef<File[]>([]);
  const kini = useRef(nilai);
  useEffect(() => { kini.current = nilai; }, [nilai]);

  const kirim = async (files: File[]) => {
    const baru = files.slice(0, Math.max(0, 4 - kini.current.length)).map((f) => ({
      kunci: Math.random().toString(36).slice(2), pratinjau: URL.createObjectURL(f), file: f }));
    if (!baru.length) return;
    let daftar = [...kini.current, ...baru.map(({ kunci, pratinjau }) => ({ kunci, pratinjau }))];
    kini.current = daftar;
    onChange(daftar);
    onSibuk(true);
    for (const b of baru) {
      try {
        const r = await upload<{ id: string }>("/api/forum/foto", await perkecil(b.file));
        daftar = kini.current.map((x) => (x.kunci === b.kunci ? { ...x, id: r.id } : x));
      } catch (e) {
        daftar = kini.current.map((x) => (x.kunci === b.kunci ? { ...x, galat: pesan(e) } : x));
      }
      kini.current = daftar;
      onChange(daftar);
    }
    onSibuk(false);
  };

  const pilih = async (files: File[]) => {
    setGalat("");
    if (!files.length) return;
    try {
      const st = await api<Izin>("/api/forum/izin");
      if (!st.punya) {
        tunda.current = files;
        setIzin("tanya");
        return;
      }
    } catch (e) {
      setGalat(pesan(e));
      return;
    }
    await kirim(files);
  };

  const beriIzin = async () => {
    setIzin("menunggu");
    try {
      await post<Izin>("/api/forum/izin");
      for (let i = 0; i < 200; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const st = await api<Izin>("/api/forum/izin");
        if (st.punya) {
          setIzin("tutup");
          await kirim(tunda.current);
          return;
        }
        if (st.status === "error") throw new Error(st.error || "Izin tidak diberikan.");
      }
      throw new Error("Izin belum diberikan. Coba pilih fotonya lagi.");
    } catch (e) {
      setIzin("tutup");
      setGalat(pesan(e));
    }
  };

  return (
    <div className={s.foto}>
      <div className={s.fotoDaftar}>
        {nilai.map((f) => (
          <div key={f.kunci} className={`${s.fotoKecil} ${f.galat ? s.fotoGagal : ""}`} title={f.galat}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={f.pratinjau} alt="" />
            {!f.id && !f.galat && <span className={s.fotoProses}><Spinner /></span>}
            {f.galat && <span className={s.fotoProses}>Gagal</span>}
            <button type="button" aria-label="Hapus foto" onClick={() => onChange(nilai.filter((x) => x.kunci !== f.kunci))}>×</button>
          </div>
        ))}
        {nilai.length < 4 && (
          <button type="button" className={s.fotoTambah} onClick={() => input.current?.click()}>
            <span aria-hidden="true">+</span> Foto
          </button>
        )}
      </div>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden
        onChange={(e) => { void pilih([...(e.target.files ?? [])]); e.target.value = ""; }} />
      <small className={s.bantu}>Opsional, maks 4 foto. Disimpan di Google Drive kamu dan bisa dilihat tim lewat link.</small>
      {nilai.some((f) => f.galat) && <small className={s.galat}>{nilai.find((f) => f.galat)?.galat}</small>}
      {galat && <small className={s.galat}>{galat}</small>}

      {izin !== "tutup" && (
        <div className={s.scrim} role="presentation">
          <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="izin-foto">
            <h2 id="izin-foto">Izinkan aplikasi menyimpan foto</h2>
            <p>Sekali saja: jendela Google akan terbuka. Pilih akun yang sama dengan akun LK Monitoring, lalu izinkan.
              Aplikasi hanya bisa membuka file yang dibuatnya sendiri, bukan isi Google Drive kamu yang lain.</p>
            {izin === "menunggu" && <p className={s.tunggu}><Spinner /> Menunggu izin dari jendela Google…</p>}
            <div className={s.dialogAksi}>
              <Button variant="ghost" onClick={() => setIzin("tutup")}>Batal</Button>
              <Button onClick={() => void beriIzin()} loading={izin === "menunggu"}>Beri izin</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const keItem = (ids: string[]): FotoItem[] => ids.map((id) => ({ kunci: id, id, pratinjau: fotoUrl(id, 300) }));
const idSiap = (f: FotoItem[]) => f.filter((x) => x.id).map((x) => x.id as string);

// ---------- form pertanyaan ----------

function FormTanya({ topik, awal, onTutup, onSimpan }: {
  topik: string[];
  awal?: Detail;
  onTutup: () => void;
  onSimpan: (id: string) => void;
}) {
  const [judul, setJudul] = useState(awal?.judul ?? "");
  const [isi, setIsi] = useState(awal?.isi ?? "");
  const [tp, setTp] = useState(awal?.topik ?? "");
  const [foto, setFoto] = useState<FotoItem[]>(keItem(awal?.foto ?? []));
  const [tahu, setTahu] = useState(false);
  const [jawab, setJawab] = useState("");
  const [fotoJ, setFotoJ] = useState<FotoItem[]>([]);
  const [sibuk, setSibuk] = useState(0);
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState("");
  const tandai = (b: boolean) => setSibuk((n) => n + (b ? 1 : -1));

  const simpan = async () => {
    setGalat("");
    if (judul.trim().length < 5) return setGalat("Judul minimal 5 huruf.");
    if (tahu && jawab.trim().length < 2) return setGalat("Tulis jawabannya, atau hapus centang “Saya sudah tahu jawabannya”.");
    setKirim(true);
    try {
      if (awal) {
        await post(`/api/forum/${awal.id}/ubah`, { judul, isi, topik: tp, foto: idSiap(foto) });
        onSimpan(awal.id);
      } else {
        const r = await post<{ id: string }>("/api/forum/tanya", {
          judul, isi, topik: tp, foto: idSiap(foto), jawaban: tahu ? jawab : "", foto_jawaban: tahu ? idSiap(fotoJ) : [] });
        onSimpan(r.id);
      }
    } catch (e) {
      setGalat(pesan(e));
      setKirim(false);
    }
  };

  return (
    <div className={s.scrim} role="presentation">
      <div className={`${s.dialog} ${s.dialogBesar}`} role="dialog" aria-modal="true" aria-labelledby="form-tanya">
        <h2 id="form-tanya">{awal ? "Ubah pertanyaan" : "Tulis pertanyaan"}</h2>
        <label className={s.field}>
          <span>Judul</span>
          <input value={judul} onChange={(e) => setJudul(e.target.value)} maxLength={200} autoFocus
            placeholder="Contoh: Kolom Tindak Lanjut tidak bisa diisi untuk sekolah pindahan" />
        </label>
        <label className={s.field}>
          <span>Topik</span>
          <input value={tp} onChange={(e) => setTp(e.target.value)} maxLength={40} list="forum-topik"
            placeholder="Pilih atau ketik topik" />
          <datalist id="forum-topik">{topik.map((t) => <option key={t} value={t} />)}</datalist>
        </label>
        <label className={s.field}>
          <span>Ceritakan masalahnya</span>
          <textarea value={isi} onChange={(e) => setIsi(e.target.value)} rows={5} maxLength={8000}
            placeholder="Apa yang terjadi, di halaman mana, sudah coba apa saja." />
        </label>
        <PilihFoto nilai={foto} onChange={setFoto} onSibuk={tandai} />

        {!awal && (
          <>
            <label className={s.centang}>
              <input type="checkbox" checked={tahu} onChange={(e) => setTahu(e.target.checked)} />
              Saya sudah tahu jawabannya (bagikan supaya teman tidak bertanya lagi)
            </label>
            {tahu && (
              <div className={s.blokJawab}>
                <label className={s.field}>
                  <span>Jawaban / solusi</span>
                  <textarea value={jawab} onChange={(e) => setJawab(e.target.value)} rows={4} maxLength={8000}
                    placeholder="Langkah yang berhasil menyelesaikan masalah ini." />
                </label>
                <PilihFoto nilai={fotoJ} onChange={setFotoJ} onSibuk={tandai} />
              </div>
            )}
          </>
        )}

        {galat && <Notice tone="bad">{galat}</Notice>}
        <div className={s.dialogAksi}>
          <Button variant="ghost" onClick={onTutup} disabled={kirim}>Batal</Button>
          <Button onClick={() => void simpan()} loading={kirim} disabled={sibuk > 0}>
            {sibuk > 0 ? "Mengunggah foto…" : awal ? "Simpan" : "Kirim"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------- tombol hapus dua langkah ----------

function Hapus({ onHapus }: { onHapus: () => Promise<void> }) {
  const [yakin, setYakin] = useState(false);
  const [jalan, setJalan] = useState(false);
  if (!yakin) return <button type="button" className={s.aksiKecil} onClick={() => setYakin(true)}>Hapus</button>;
  return (
    <span className={s.yakin}>
      Yakin hapus?
      <button type="button" className={`${s.aksiKecil} ${s.aksiBahaya}`} disabled={jalan}
        onClick={async () => { setJalan(true); try { await onHapus(); } finally { setJalan(false); setYakin(false); } }}>
        Ya, hapus
      </button>
      <button type="button" className={s.aksiKecil} onClick={() => setYakin(false)}>Batal</button>
    </span>
  );
}

// ---------- satu jawaban ----------

function Jawaban({ j, terpilih, bolehPilih, onPilih, onUbah }: {
  j: Pos; terpilih: boolean; bolehPilih: boolean; onPilih: () => Promise<void>; onUbah: () => void;
}) {
  const [ubah, setUbah] = useState(false);
  const [isi, setIsi] = useState(j.isi);
  const [foto, setFoto] = useState<FotoItem[]>(keItem(j.foto));
  const [sibuk, setSibuk] = useState(0);
  const [galat, setGalat] = useState("");
  const [jalan, setJalan] = useState(false);

  const simpan = async () => {
    setJalan(true);
    setGalat("");
    try {
      await post(`/api/forum/${j.id}/ubah`, { isi, foto: idSiap(foto) });
      setUbah(false);
      onUbah();
    } catch (e) {
      setGalat(pesan(e));
    } finally {
      setJalan(false);
    }
  };

  return (
    <article className={`${s.jawab} ${terpilih ? s.jawabTerpilih : ""}`}>
      {terpilih && <div className={s.pita}>✓ Jawaban yang dipakai penanya</div>}
      <header className={s.meta}>
        <b>{j.nama}</b>
        <span>{waktu(j.dibuat)}{j.diubah ? " · diubah" : ""}</span>
      </header>
      {ubah ? (
        <div className={s.ubahInline}>
          <textarea value={isi} onChange={(e) => setIsi(e.target.value)} rows={4} maxLength={8000} />
          <PilihFoto nilai={foto} onChange={setFoto} onSibuk={(b) => setSibuk((n) => n + (b ? 1 : -1))} />
          {galat && <Notice tone="bad">{galat}</Notice>}
          <div className={s.aksiBaris}>
            <Button size="sm" variant="ghost" onClick={() => setUbah(false)}>Batal</Button>
            <Button size="sm" onClick={() => void simpan()} loading={jalan} disabled={sibuk > 0}>Simpan</Button>
          </div>
        </div>
      ) : (
        <>
          <Teks isi={j.isi} />
          <Galeri foto={j.foto} />
        </>
      )}
      {!ubah && (
        <footer className={s.aksiBaris}>
          {bolehPilih && (
            <button type="button" className={`${s.aksiKecil} ${terpilih ? "" : s.aksiUtama}`} onClick={() => void onPilih()}>
              {terpilih ? "Batalkan pilihan" : "Tandai sebagai jawaban"}
            </button>
          )}
          {j.boleh_ubah && <button type="button" className={s.aksiKecil} onClick={() => setUbah(true)}>Ubah</button>}
          {j.boleh_ubah && <Hapus onHapus={async () => { await post(`/api/forum/${j.id}/hapus`); onUbah(); }} />}
        </footer>
      )}
    </article>
  );
}

// ---------- halaman detail ----------

function DetailView({ id, topik, onKembali }: { id: string; topik: string[]; onKembali: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [galat, setGalat] = useState("");
  const [ubah, setUbah] = useState(false);
  const [isi, setIsi] = useState("");
  const [foto, setFoto] = useState<FotoItem[]>([]);
  const [sibuk, setSibuk] = useState(0);
  const [kirim, setKirim] = useState(false);
  const [galatJ, setGalatJ] = useState("");

  const muat = useCallback(async () => {
    try {
      setD(await api<Detail>(`/api/forum/${encodeURIComponent(id)}`));
      setGalat("");
    } catch (e) {
      setGalat(pesan(e));
    }
  }, [id]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  const jawab = async () => {
    setGalatJ("");
    if (isi.trim().length < 2) return setGalatJ("Jawaban masih kosong.");
    setKirim(true);
    try {
      await post(`/api/forum/${id}/jawab`, { isi, foto: idSiap(foto) });
      setIsi("");
      setFoto([]);
      await muat();
    } catch (e) {
      setGalatJ(pesan(e));
    } finally {
      setKirim(false);
    }
  };

  const pilih = async (jid: string) => {
    try {
      await post(`/api/forum/${id}/solusi`, { jawaban: d?.solusi === jid ? "" : jid });
      await muat();
    } catch (e) {
      setGalat(pesan(e));
    }
  };

  const kembali = (
    <button type="button" className={s.kembali} onClick={onKembali}><span aria-hidden="true">←</span> Semua pertanyaan</button>
  );

  if (!d) {
    return (
      <div className={s.page}>
        {kembali}
        {galat ? <Notice tone="bad">{galat}</Notice> : <p className={s.memuat}><Spinner /> Memuat pertanyaan…</p>}
      </div>
    );
  }

  return (
    <div className={s.page}>
      {kembali}
      {galat && <Notice tone="bad">{galat}</Notice>}
      <article className={s.tanya}>
        <div className={s.chipBaris}>
          {d.topik && <Chip tone="muted">{d.topik}</Chip>}
          {d.solusi ? <Chip tone="ok">Selesai</Chip> : d.jawaban.length ? <Chip tone="info">Terjawab</Chip>
            : <Chip tone="warn">Belum dijawab</Chip>}
        </div>
        <h1>{d.judul}</h1>
        <header className={s.meta}>
          <b>{d.nama}</b>
          <span>{waktu(d.dibuat)}{d.diubah ? " · diubah" : ""}</span>
        </header>
        {d.isi && <Teks isi={d.isi} />}
        <Galeri foto={d.foto} />
        {d.boleh_ubah && (
          <footer className={s.aksiBaris}>
            <button type="button" className={s.aksiKecil} onClick={() => setUbah(true)}>Ubah</button>
            <Hapus onHapus={async () => { await post(`/api/forum/${d.id}/hapus`); onKembali(); }} />
          </footer>
        )}
      </article>

      <section className={s.jawabanSeksi} aria-labelledby="judul-jawaban">
        <h2 id="judul-jawaban">{d.jawaban.length ? `${d.jawaban.length} jawaban` : "Belum ada jawaban"}</h2>
        {d.jawaban.map((j) => (
          <Jawaban key={j.id} j={j} terpilih={d.solusi === j.id} bolehPilih={d.boleh_ubah}
            onPilih={() => pilih(j.id)} onUbah={() => void muat()} />
        ))}
      </section>

      <section className={s.formJawab} aria-labelledby="tulis-jawaban">
        <h2 id="tulis-jawaban">Tulis jawaban</h2>
        <textarea value={isi} onChange={(e) => setIsi(e.target.value)} rows={4} maxLength={8000}
          placeholder={d.milik_saya ? "Sudah ketemu solusinya? Tulis di sini supaya teman lain tahu."
            : "Pernah mengalami hal yang sama? Bagikan caranya."} />
        <PilihFoto nilai={foto} onChange={setFoto} onSibuk={(b) => setSibuk((n) => n + (b ? 1 : -1))} />
        {galatJ && <Notice tone="bad">{galatJ}</Notice>}
        <div className={s.aksiBaris}>
          <Button onClick={() => void jawab()} loading={kirim} disabled={sibuk > 0}>
            {sibuk > 0 ? "Mengunggah foto…" : "Kirim jawaban"}
          </Button>
        </div>
      </section>

      {ubah && (
        <FormTanya topik={topik} awal={d} onTutup={() => setUbah(false)}
          onSimpan={() => { setUbah(false); void muat(); }} />
      )}
    </div>
  );
}

// ---------- halaman daftar ----------

type Saring = "semua" | "belum" | "terjawab" | "saya";
const SARING: { k: Saring; label: string }[] = [
  { k: "semua", label: "Semua" }, { k: "belum", label: "Belum dijawab" }, { k: "terjawab", label: "Terjawab" },
  { k: "saya", label: "Pertanyaan saya" },
];

function Status({ x }: { x: Ringkas }): ReactNode {
  if (x.selesai) return <Chip tone="ok">Selesai</Chip>;
  if (x.jawaban) return <Chip tone="info">{x.jawaban} jawaban</Chip>;
  return <Chip tone="warn">Belum dijawab</Chip>;
}

export function ForumView() {
  const router = useRouter();
  const params = useSearchParams();
  const id = params.get("id");
  const [d, setD] = useState<Daftar | null>(null);
  const [galat, setGalat] = useState("");
  const [cari, setCari] = useState("");
  const [saring, setSaring] = useState<Saring>("semua");
  const [tp, setTp] = useState("");
  const [tulis, setTulis] = useState(false);
  const [segar, setSegar] = useState(false);

  const muat = useCallback(async (paksa = false) => {
    setSegar(paksa);
    try {
      setD(await api<Daftar>(`/api/forum${paksa ? "?paksa=true" : ""}`));
      setGalat("");
    } catch (e) {
      setGalat(e instanceof ApiError && e.status === 428 ? e.message : pesan(e));
    } finally {
      setSegar(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (!id) void muat(); }, [id, muat]);

  const buka = (x: string | null) => {
    router.push(x ? `/forum/?id=${encodeURIComponent(x)}` : "/forum/");
    window.scrollTo({ top: 0 });
  };

  if (id) return <DetailView key={id} id={id} topik={d?.topik ?? []} onKembali={() => buka(null)} />;

  const q = cari.trim().toLowerCase();
  const kata = q.split(/\s+/).filter(Boolean);
  const tampil = (d?.items ?? []).filter((x) =>
    (saring === "semua" || (saring === "belum" && !x.jawaban) || (saring === "terjawab" && x.jawaban > 0)
      || (saring === "saya" && x.milik_saya))
    && (!tp || x.topik === tp)
    && kata.every((k) => x.cari.includes(k)));
  const topikAda = [...new Set((d?.items ?? []).map((x) => x.topik).filter(Boolean))];

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Forum tim</h1>
          <p>Tanya masalah di lapangan atau bagikan solusi yang sudah kamu temukan. Cari dulu, mungkin sudah pernah dijawab.</p>
        </div>
        <Button onClick={() => setTulis(true)} disabled={!d}>+ Tulis pertanyaan</Button>
      </header>

      <div className={s.tools}>
        <input type="search" className={s.search} placeholder="Cari judul, isi, atau jawaban" value={cari}
          onChange={(e) => setCari(e.target.value)} aria-label="Cari di forum" />
        <div className={s.saringBaris}>
          <div className={s.chips} role="group" aria-label="Saring">
            {SARING.map((x) => (
              <button key={x.k} type="button" aria-pressed={saring === x.k} onClick={() => setSaring(x.k)}>{x.label}</button>
            ))}
          </div>
          {topikAda.length > 0 && (
            <select className={s.pilihTopik} value={tp} onChange={(e) => setTp(e.target.value)} aria-label="Topik">
              <option value="">Semua topik</option>
              {topikAda.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          )}
          <button type="button" className={s.aksiKecil} onClick={() => void muat(true)} disabled={segar}>
            {segar ? "Memuat…" : "Muat ulang"}
          </button>
        </div>
      </div>

      {galat && <Notice tone="bad">{galat}</Notice>}
      {!d && !galat && <p className={s.memuat}><Spinner /> Memuat forum…</p>}

      {d && d.items.length === 0 && (
        <div className={s.kosongBesar}>
          <b>Belum ada pertanyaan</b>
          <p>Jadilah yang pertama. Pertanyaan yang sudah kamu tahu jawabannya juga boleh dibagikan.</p>
          <Button onClick={() => setTulis(true)}>+ Tulis pertanyaan</Button>
        </div>
      )}
      {d && d.items.length > 0 && tampil.length === 0 && (
        <p className={s.kosong}>Tidak ada yang cocok. <button type="button" className={s.tautan} onClick={() => setTulis(true)}>
          Tanyakan saja</button></p>
      )}

      <div className={s.daftar}>
        {tampil.map((x) => (
          <Link key={x.id} href={`/forum/?id=${encodeURIComponent(x.id)}`} className={s.kartu}>
            <div className={s.kartuAtas}>
              <h3>{x.judul}</h3>
              <Status x={x} />
            </div>
            {x.cuplikan && <p>{x.cuplikan}</p>}
            <div className={s.kartuBawah}>
              {x.topik && <span className={s.topik}>{x.topik}</span>}
              {x.ada_foto && <span>Ada foto</span>}
              <span>{x.nama} · {waktu(x.aktif)}</span>
            </div>
          </Link>
        ))}
      </div>

      {tulis && d && (
        <FormTanya topik={d.topik} onTutup={() => setTulis(false)}
          onSimpan={(nid) => { setTulis(false); buka(nid); }} />
      )}
    </div>
  );
}
