"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Isian, IsianKey, LkOpsi, SekolahLk } from "@/lib/types";
import { Button, Chip, Notice, Spinner, prioritasTone } from "@/components/ui";
import s from "./today.module.css";

const KOSONG: Isian = { a1: "", a2: "", b1: "", b2: "", c1: "", c2: "" };

type Grup = { kode: "a" | "b" | "c"; judul: string; opsi: keyof LkOpsi["opsi"] };
const GRUP: Grup[] = [
  { kode: "a", judul: "Kenapa progres fisik belum 50%?", opsi: "alasan_progres" },
  { kode: "b", judul: "Kenapa belum submit laporan 50%?", opsi: "alasan_submit" },
  { kode: "c", judul: "Kenapa belum direviu?", opsi: "alasan_reviu" },
];

export function prioritasLabel(p: string) {
  if (p.endsWith("1")) return "Belum submit";
  if (p.endsWith("2")) return "Di bawah 50%";
  if (p.endsWith("3")) return "Belum reviu";
  return p || "–";
}

/** Alasan yang wajib diisi di LK, mengikuti tahapan sekolah (sama dengan backend/app/tahap.py):
 *  progres < 50% -> tiga alasan; sudah 50% tapi belum submit -> submit + reviu;
 *  sudah submit tapi belum direviu -> reviu saja. */
function wajib(x: SekolahLk): Grup["kode"][] {
  if (x.progres === null || x.progres < 50) return ["a", "b", "c"];
  if (x.submit !== "Ya") return ["b", "c"];
  if (x.reviu !== "Ya") return ["c"];
  return [];
}

const cari = (pilihan: string[], kata: string) => pilihan.find((o) => o.toLowerCase().includes(kata)) ?? "";

/** Jawaban yang sudah pasti dari data LK, diisikan otomatis bila kolomnya masih kosong:
 *  belum submit + progres < 50% -> alasan submit "Progres fisik belum mencapai 50%";
 *  belum submit -> alasan reviu "Sekolah Belum Submit" (belum bisa direviu). */
export function isianOtomatis(x: SekolahLk, opsi: LkOpsi): Partial<Isian> {
  const out: Partial<Isian> = {};
  if (x.submit === "Ya") return out;
  if (x.progres === null || x.progres < 50) {
    const b = cari(opsi.opsi.alasan_submit, "belum mencapai 50");
    if (b) out.b1 = b;
  }
  const c = cari(opsi.opsi.alasan_reviu, "belum submit");
  if (c) out.c1 = c;
  return out;
}

const selesai = (x: SekolahLk) => x.prioritas.trim().toLowerCase() === "selesai";

/** Jumlah isian yang terisi dari yang dibutuhkan: status komunikasi + alasan yang relevan. */
function kelengkapan(x: SekolahLk, blok: number) {
  const isi = { ...KOSONG, ...x.isian[String(blok)] };
  const relevan = wajib(x);
  const perlu = 1 + relevan.length;
  const ada = (x.komunikasi ? 1 : 0) + relevan.filter((g) => isi[`${g}1` as IsianKey]).length;
  return { ada, perlu };
}

const URUT: Record<string, number> = { "1": 0, "2": 1, "3": 2 };

/** Sekolah berikutnya (setelah `npsn`) yang isiannya belum lengkap, supaya bisa langsung lanjut mengisi. */
function berikutnya(urut: SekolahLk[], npsn: string, blok: number): string | null {
  const i = urut.findIndex((x) => x.npsn === npsn);
  const sisa = urut.slice(i + 1).find((x) => {
    if (selesai(x)) return false;
    const k = kelengkapan(x, blok);
    return k.ada < k.perlu;
  });
  return sisa?.npsn ?? null;
}

/** Kolom "Di LK": klik sekolah untuk mengisi status komunikasi, alasan, dan tindak lanjut ke sheet LK. */
export function LkPanel({ sekolah, onSaved }: {
  sekolah: SekolahLk[];
  onSaved: (npsn: string, ubah: (x: SekolahLk) => SekolahLk) => void;
}) {
  const [opsi, setOpsi] = useState<LkOpsi | null>(null);
  const [opsiError, setOpsiError] = useState<string | null>(null);
  const [buka, setBuka] = useState<string | null>(null);
  const [pilihBlok, setPilihBlok] = useState<number | null>(null);
  const [komBusy, setKomBusy] = useState(false);
  const [komInfo, setKomInfo] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  useEffect(() => {
    api<LkOpsi>("/api/lk/opsi").then(setOpsi).catch((e) => setOpsiError(e.message));
  }, []);

  const urut = [...sekolah].sort((a, b) => (URUT[a.prioritas.slice(-1)] ?? 3) - (URUT[b.prioritas.slice(-1)] ?? 3));
  const blok = pilihBlok ?? opsi?.blok_default ?? 1;
  const komSama = sekolah.length && sekolah.every((x) => x.komunikasi === sekolah[0].komunikasi) ? sekolah[0].komunikasi : null;

  async function simpanKomunikasi(nilai: string) {
    setKomBusy(true);
    setKomInfo(null);
    try {
      await post("/api/lk/isi", { blok, sekolah: sekolah.map((x) => ({ npsn: x.npsn, komunikasi: nilai })) });
      sekolah.forEach((x) => onSaved(x.npsn, (y) => ({ ...y, komunikasi: nilai })));
      setKomInfo({ tone: "ok", teks: `Tersimpan ke ${sekolah.length} sekolah` });
    } catch (e) {
      setKomInfo({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setKomBusy(false);
    }
  }
  const perlu = sekolah.filter((x) => !selesai(x));
  const lengkap = perlu.filter((x) => { const k = kelengkapan(x, blok); return k.ada === k.perlu; }).length;

  return (
    <section className={s.side} aria-label="Di LK">
      <h3>Di LK <span>{perlu.length ? `${lengkap} dari ${perlu.length} sekolah lengkap` : `${sekolah.length} sekolah`}</span></h3>

      {opsiError && <Notice tone="warn" title="Pilihan isian LK belum terbaca">{opsiError}</Notice>}
      {!opsi && !opsiError && <div className={s.muted}><Spinner label="Memuat pilihan" /> Memuat pilihan isian…</div>}
      {opsi && sekolah.length > 0 && (
        <div className={s.lkTop}>
          <div className={s.seg} role="radiogroup" aria-label="Kolom sesi LK">
            {opsi.blok.map((b) => (
              <button key={b.no} type="button" role="radio" aria-checked={blok === b.no}
                onClick={() => { setPilihBlok(b.no); setBuka(null); }}>
                Sesi {b.label}{b.no === opsi.blok_default ? " (hari ini)" : ""}
              </button>
            ))}
          </div>
          <label className={s.field}>
            <span>Status komunikasi fasil, untuk semua sekolahnya</span>
            <span className={s.selectRow}>
              <select value={komSama ?? "__beda"} disabled={komBusy}
                onChange={(e) => void simpanKomunikasi(e.target.value)}>
                {komSama === null && <option value="__beda" disabled>Berbeda antar sekolah</option>}
                <option value="">Belum diisi</option>
                {opsi.opsi.komunikasi.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
              {komBusy && <Spinner label="Menyimpan" />}
            </span>
          </label>
          {komInfo && <span className={komInfo.tone === "ok" ? s.savedNote : s.errNote}>{komInfo.teks}</span>}
        </div>
      )}

      {sekolah.length === 0 ? (
        <p className={s.muted}>Nomor ini tidak ditemukan di LK WEEK yang dipilih.</p>
      ) : (
        <ul className={s.schools}>
          {urut.map((x) => (
            <SchoolItem key={x.npsn} x={x} opsi={opsi} blok={blok} terbuka={buka === x.npsn}
              onToggle={() => setBuka(buka === x.npsn ? null : x.npsn)}
              onSaved={(isi) => {
                onSaved(x.npsn, (y) => ({ ...y, isian: { ...y.isian, [String(blok)]: isi } }));
                setBuka(berikutnya(urut, x.npsn, blok));
              }} />
          ))}
        </ul>
      )}
    </section>
  );
}

function SchoolItem({ x, opsi, blok, terbuka, onToggle, onSaved }: {
  x: SekolahLk;
  opsi: LkOpsi | null;
  blok: number;
  terbuka: boolean;
  onToggle: () => void;
  onSaved: (isi: Isian) => void;
}) {
  const p = x.progres ?? 0;
  const tersimpan: Isian = { ...KOSONG, ...x.isian[String(blok)] };
  const k = kelengkapan(x, blok);

  return (
    <li className={`${s.school} ${terbuka ? s.schoolOpen : ""}`}>
      <button type="button" className={s.schoolBtn} onClick={onToggle} aria-expanded={terbuka}>
        <div className={s.schoolTop}>
          <span className={s.schoolName}>{x.nama}</span>
          <span className={s.schoolChips}>
            {x.bimtek && <span className={s.bimtekTag} title={`Peserta bimtek (${x.bimtek.hotel}), laporan 50% belum direviu`}>Bimtek</span>}
            <Chip tone={prioritasTone(x.prioritas)}>{prioritasLabel(x.prioritas)}</Chip>
          </span>
        </div>
        <div className={s.schoolBar}>
          <span className={s.track}>
            <span className={p >= 50 ? s.fillOk : s.fillLow} style={{ width: `${Math.min(100, p)}%` }} />
            <span className={s.half} aria-hidden="true" />
          </span>
          <span className={s.pct}>{x.progres === null ? "–" : `${x.progres.toFixed(1).replace(".", ",")}%`}</span>
        </div>
        <div className={s.schoolMeta}>
          <span>NPSN {x.npsn}, submit {x.submit || "Tidak"}, reviu {x.reviu || "–"}</span>
          {selesai(x) ? null
            : k.ada === k.perlu ? <span className={s.filled}>✓ Selesai</span>
            : k.ada > 0 ? <span className={s.toFill}>{k.ada} dari {k.perlu} terisi</span>
            : <span className={s.toFill}>Isi LK</span>}
        </div>
      </button>
      {terbuka && opsi && (
        <SchoolForm x={x} opsi={opsi} blok={blok} awal={tersimpan}
          onDone={(isi) => (isi ? onSaved(isi) : onToggle())} />
      )}
    </li>
  );
}

function SchoolForm({ x, opsi, blok, awal, onDone }: {
  x: SekolahLk;
  opsi: LkOpsi;
  blok: number;
  awal: Isian;
  onDone: (isi: Isian | null) => void;
}) {
  const oto = isianOtomatis(x, opsi);
  // Kolom kosong yang jawabannya sudah pasti langsung terisi; tetap bisa diganti sebelum disimpan
  const [isi, setIsi] = useState<Isian>(() => {
    const awalIsi = { ...awal };
    (Object.keys(oto) as IsianKey[]).forEach((k) => { if (!awalIsi[k]) awalIsi[k] = oto[k] ?? ""; });
    return awalIsi;
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const berubah = (Object.keys(isi) as IsianKey[]).filter((k) => isi[k] !== awal[k]);
  const tampil = GRUP.filter((g) => wajib(x).includes(g.kode));

  /** Salin tindak lanjut dari satu alasan ke alasan lain yang tampil. */
  function samakan(dari: IsianKey) {
    const baru = { ...isi };
    tampil.forEach((g) => { baru[`${g.kode}2` as IsianKey] = isi[dari]; });
    setIsi(baru);
  }

  async function simpan() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/lk/isi", {
        blok,
        sekolah: [{
          npsn: x.npsn,
          isian: Object.fromEntries(berubah.map((k) => [k, isi[k]])),
        }],
      });
      onDone(isi);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.form}>
      {tampil.map((g) => {
        const k1 = `${g.kode}1` as IsianKey;
        const k2 = `${g.kode}2` as IsianKey;
        const pilihan = opsi.opsi[g.opsi];
        return (
          <fieldset key={g.kode} className={s.fieldset}>
            <legend className={s.legend}>
              {g.judul}
              {!awal[k1] && oto[k1] && isi[k1] === oto[k1] && <em className={s.otomatis}>terisi otomatis</em>}
            </legend>
            <select value={isi[k1]} onChange={(e) => setIsi({ ...isi, [k1]: e.target.value })} aria-label={`Alasan: ${g.judul}`}>
              <option value="">Pilih alasan</option>
              {isi[k1] && !pilihan.includes(isi[k1]) && <option value={isi[k1]}>{isi[k1]}</option>}
              {pilihan.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <textarea rows={2} maxLength={500} placeholder="Tindak lanjut, misalnya: fasil akan mendampingi sekolah unggah laporan Kamis"
              value={isi[k2]} onChange={(e) => setIsi({ ...isi, [k2]: e.target.value })} aria-label={`Tindak lanjut: ${g.judul}`} />
            {isi[k2].trim() && tampil.some((h) => isi[`${h.kode}2` as IsianKey] !== isi[k2]) && (
              <button type="button" className={s.linkBtn} onClick={() => samakan(k2)}>
                Pakai tindak lanjut ini untuk semua alasan
              </button>
            )}
          </fieldset>
        );
      })}
      {error && <Notice tone="bad" title="Belum tersimpan">{error}</Notice>}
      <div className={s.formActions}>
        <Button size="sm" loading={busy} disabled={berubah.length === 0} onClick={simpan}>Simpan ke LK</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone(null)}>Batal</Button>
      </div>
    </div>
  );
}
