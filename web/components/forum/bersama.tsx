"use client";

/** Komponen bersama halaman FAQ & Eskalasi: teks, avatar, foto Google Drive (unggah + galeri), pengumuman. */

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { api, post, upload } from "@/lib/api";
import { Button, Spinner } from "@/components/ui";
import s from "./forum.module.css";

export type Pos = {
  id: string; isi: string; foto: string[]; nama: string; dibuat: string; diubah: string; milik_saya: boolean;
  boleh_ubah: boolean;
};
export type Info = Pos & { judul: string };
export type Izin = { punya: boolean; status: string; error: string };

export const pesan = (e: unknown) => (e instanceof Error ? e.message : String(e));

// ---------- format ----------

export function waktu(iso: string): string {
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

export const lengkap = (iso: string) => (iso ? new Date(iso).toLocaleString("id-ID", {
  weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

/** Tautan di dalam satu baris teks jadi bisa diklik. */
export function Sebaris({ t }: { t: string }) {
  return (
    <>
      {t.split(/(https?:\/\/[^\s]+)/g).map((b, i) => (/^https?:\/\//.test(b)
        ? <a key={i} href={b} target="_blank" rel="noreferrer">{b}</a>
        : <Fragment key={i}>{b}</Fragment>))}
    </>
  );
}

type Blok = { k: "p" | "ul" | "ol"; baris: string[] };

/** Teks biasa -> paragraf; baris berawalan "-", "•", "*" jadi poin, "1." / "1)" jadi nomor. */
export function Teks({ isi }: { isi: string }) {
  const blok: Blok[] = [];
  for (const mentah of isi.replace(/\r/g, "").split("\n")) {
    const b = mentah.trimEnd();
    const poin = b.match(/^\s*[-•*]\s+(.*)$/);
    const nomor = b.match(/^\s*\d+[.)]\s+(.*)$/);
    const k: Blok["k"] | null = !b.trim() ? null : poin ? "ul" : nomor ? "ol" : "p";
    const terakhir = blok[blok.length - 1];
    if (!k) { blok.push({ k: "p", baris: [] }); continue; }
    const teks = poin?.[1] ?? nomor?.[1] ?? b;
    if (terakhir && terakhir.k === k && terakhir.baris.length) terakhir.baris.push(teks);
    else if (terakhir && !terakhir.baris.length) { terakhir.k = k; terakhir.baris.push(teks); }
    else blok.push({ k, baris: [teks] });
  }
  return (
    <div className={s.teks}>
      {blok.filter((x) => x.baris.length).map((x, i) => {
        if (x.k === "p") {
          return <p key={i}>{x.baris.map((t, j) => <Fragment key={j}>{j > 0 && <br />}<Sebaris t={t} /></Fragment>)}</p>;
        }
        const L = x.k;
        return <L key={i}>{x.baris.map((t, j) => <li key={j}><Sebaris t={t} /></li>)}</L>;
      })}
    </div>
  );
}

const WARNA = ["#2346a0", "#1e7a4c", "#9a5b00", "#7a3fa0", "#a6282b", "#0f6f86", "#5b6474"];

export function Avatar({ nama, kecil }: { nama: string; kecil?: boolean }) {
  const kata = nama.trim().split(/\s+/);
  const inisial = ((kata[0]?.[0] ?? "?") + (kata.length > 1 ? kata[kata.length - 1][0] : "")).toUpperCase();
  const w = WARNA[[...nama].reduce((a, c) => a + c.charCodeAt(0), 0) % WARNA.length];
  return <span className={`${s.avatar} ${kecil ? s.avatarKecil : ""}`} style={{ background: w }} aria-hidden="true">{inisial}</span>;
}

export function Penulis({ nama, dibuat, diubah, label }: { nama: string; dibuat: string; diubah?: string; label?: ReactNode }) {
  return (
    <div className={s.penulis}>
      <Avatar nama={nama} />
      <div>
        <div className={s.penulisNama}><b>{nama}</b>{label}</div>
        <time dateTime={dibuat} title={lengkap(dibuat)}>{waktu(dibuat)}{diubah ? " · diubah" : ""}</time>
      </div>
    </div>
  );
}

export const fotoUrl = (id: string, w = 1600) => `https://lh3.googleusercontent.com/d/${id}=w${w}`;
const fotoCadangan = (id: string, w = 1600) => `https://drive.google.com/thumbnail?id=${id}&sz=w${w}`;

export function Foto({ id, w, onClick }: { id: string; w?: number; onClick?: () => void }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={fotoUrl(id, w)} alt="Foto lampiran" loading="lazy" referrerPolicy="no-referrer" onClick={onClick}
      onError={(e) => {
        const img = e.currentTarget;
        if (!img.dataset.cadangan) { img.dataset.cadangan = "1"; img.src = fotoCadangan(id, w); }
      }} />
  );
}

export function Galeri({ foto }: { foto: string[] }) {
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

export type FotoItem = { kunci: string; id?: string; pratinjau: string; galat?: string };

export function PilihFoto({ nilai, onChange, onSibuk }: {
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

export const keItem = (ids: string[]): FotoItem[] => ids.map((id) => ({ kunci: id, id, pratinjau: fotoUrl(id, 300) }));
export const idSiap = (f: FotoItem[]) => f.filter((x) => x.id).map((x) => x.id as string);

// ---------- tombol hapus dua langkah ----------

export function Hapus({ onHapus }: { onHapus: () => Promise<void> }) {
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

// ---------- pengumuman (kolom kanan) ----------

function IkonToa() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true"><path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M18.5 5.5a9 9 0 0 1 0 13" /></svg>
  );
}

function FormInfo({ awal, onTutup, onSimpan }: { awal?: Info; onTutup: () => void; onSimpan: () => void }) {
  const [judul, setJudul] = useState(awal?.judul ?? "");
  const [isi, setIsi] = useState(awal?.isi ?? "");
  const [jalan, setJalan] = useState(false);
  const [galat, setGalat] = useState("");
  const simpan = async () => {
    setGalat("");
    if (isi.trim().length < 5) return setGalat("Isi pengumuman minimal 5 huruf.");
    setJalan(true);
    try {
      if (awal) await post(`/api/forum/${awal.id}/ubah`, { judul, isi });
      else await post("/api/forum/pengumuman", { judul, isi });
      onSimpan();
    } catch (e) {
      setGalat(pesan(e));
      setJalan(false);
    }
  };
  return (
    <div className={s.infoForm}>
      <input value={judul} onChange={(e) => setJudul(e.target.value)} maxLength={200} placeholder="Judul (opsional)"
        aria-label="Judul pengumuman" />
      <textarea value={isi} onChange={(e) => setIsi(e.target.value)} rows={6} maxLength={8000} autoFocus
        placeholder="Tulis pengumuman. Baris diawali - atau 1. jadi daftar." aria-label="Isi pengumuman" />
      {galat && <small className={s.galat}>{galat}</small>}
      <div className={s.aksiBaris}>
        <Button size="sm" variant="ghost" onClick={onTutup} disabled={jalan}>Batal</Button>
        <Button size="sm" onClick={() => void simpan()} loading={jalan}>{awal ? "Simpan" : "Umumkan"}</Button>
      </div>
    </div>
  );
}

function ItemInfo({ p, onUbah }: { p: Info; onUbah: () => void }) {
  const [buka, setBuka] = useState(false);
  const [ubah, setUbah] = useState(false);
  const panjang = p.isi.length > 220 || p.isi.split("\n").length > 4;
  if (ubah) return <li className={s.infoItem}><FormInfo awal={p} onTutup={() => setUbah(false)} onSimpan={() => { setUbah(false); onUbah(); }} /></li>;
  return (
    <li className={s.infoItem}>
      <span className={s.infoIkon}><IkonToa /></span>
      <div className={s.infoIsi}>
        {p.judul && <b>{p.judul}</b>}
        <div className={buka || !panjang ? "" : s.infoPotong}><Teks isi={p.isi} /></div>
        {panjang && (
          <button type="button" className={s.tautan} onClick={() => setBuka(!buka)}>
            {buka ? "Tutup" : "Selengkapnya"}
          </button>
        )}
        <small>
          {p.nama} · <time dateTime={p.dibuat} title={lengkap(p.dibuat)}>{waktu(p.dibuat)}</time>
          {p.boleh_ubah && (
            <>
              {" · "}<button type="button" className={s.tautan} onClick={() => setUbah(true)}>Ubah</button>
              {" · "}<Hapus onHapus={async () => { await post(`/api/forum/${p.id}/hapus`); onUbah(); }} />
            </>
          )}
        </small>
      </div>
    </li>
  );
}

export function Pengumuman({ daftar, admin, onUbah }: { daftar: Info[]; admin: boolean; onUbah: () => void }) {
  const [tulis, setTulis] = useState(false);
  const [semua, setSemua] = useState(false);
  if (!daftar.length && !admin) return null;
  const tampil = semua ? daftar : daftar.slice(0, 4);
  return (
    <section className={s.info} aria-labelledby="judul-info">
      <header>
        <h2 id="judul-info">Pengumuman</h2>
        {admin && !tulis && <button type="button" className={s.tautan} onClick={() => setTulis(true)}>+ Tulis</button>}
      </header>
      {tulis && <FormInfo onTutup={() => setTulis(false)} onSimpan={() => { setTulis(false); onUbah(); }} />}
      {!daftar.length && !tulis && <p className={s.infoKosong}>Belum ada pengumuman. Info penting untuk tim bisa ditulis di sini.</p>}
      <ul>
        {tampil.map((p) => <ItemInfo key={`${p.id}${p.diubah}`} p={p} onUbah={onUbah} />)}
      </ul>
      {daftar.length > 4 && (
        <button type="button" className={`${s.tautan} ${s.infoSemua}`} onClick={() => setSemua(!semua)}>
          {semua ? "Tampilkan lebih sedikit" : `Lihat semua (${daftar.length})`}
        </button>
      )}
    </section>
  );
}

// ---------- halaman daftar ----------
