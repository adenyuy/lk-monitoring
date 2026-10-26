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

function prioritasLabel(p: string) {
  if (p.endsWith("1")) return "Belum submit";
  if (p.endsWith("2")) return "Di bawah 50%";
  if (p.endsWith("3")) return "Belum reviu";
  return p || "–";
}

/** Grup alasan yang relevan untuk kondisi sekolah. */
function grupRelevan(x: SekolahLk): Grup["kode"][] {
  const out: Grup["kode"][] = [];
  if (x.progres === null || x.progres < 50) out.push("a");
  if (x.submit !== "Ya") out.push("b");
  else if (x.reviu !== "Ya") out.push("c");
  return out;
}

const URUT: Record<string, number> = { "1": 0, "2": 1, "3": 2 };

/** Sekolah berikutnya (setelah `npsn`) yang alasannya belum lengkap, supaya bisa langsung lanjut mengisi. */
function berikutnya(urut: SekolahLk[], npsn: string, blok: number | null): string | null {
  const i = urut.findIndex((x) => x.npsn === npsn);
  const sisa = urut.slice(i + 1).find((x) => {
    const isi = { ...KOSONG, ...(blok ? x.isian[String(blok)] : {}) };
    return grupRelevan(x).some((g) => !isi[`${g}1` as IsianKey]);
  });
  return sisa?.npsn ?? null;
}

/** Kolom "Di LK": status komunikasi per fasil + form alasan per sekolah, langsung tersimpan ke sheet LK. */
export function LkPanel({ sekolah, onSaved }: {
  sekolah: SekolahLk[];
  onSaved: (npsn: string[], ubah: (x: SekolahLk) => SekolahLk) => void;
}) {
  const [opsi, setOpsi] = useState<LkOpsi | null>(null);
  const [opsiError, setOpsiError] = useState<string | null>(null);
  const [blok, setBlok] = useState<number | null>(null);
  const [buka, setBuka] = useState<string | null>(null);
  const [komBusy, setKomBusy] = useState(false);
  const [komInfo, setKomInfo] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  useEffect(() => {
    api<LkOpsi>("/api/lk/opsi")
      .then((o) => { setOpsi(o); setBlok((b) => b ?? o.blok_default); })
      .catch((e) => setOpsiError(e.message));
  }, []);

  const urut = [...sekolah].sort((a, b) => (URUT[a.prioritas.slice(-1)] ?? 3) - (URUT[b.prioritas.slice(-1)] ?? 3));
  const komSama = sekolah.length && sekolah.every((x) => x.komunikasi === sekolah[0].komunikasi) ? sekolah[0].komunikasi : null;

  async function simpanKomunikasi(nilai: string) {
    if (!blok) return;
    setKomBusy(true);
    setKomInfo(null);
    try {
      await post("/api/lk/isi", { blok, sekolah: sekolah.map((x) => ({ npsn: x.npsn, komunikasi: nilai })) });
      onSaved(sekolah.map((x) => x.npsn), (x) => ({ ...x, komunikasi: nilai }));
      setKomInfo({ tone: "ok", teks: `Tersimpan ke ${sekolah.length} sekolah` });
    } catch (e) {
      setKomInfo({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setKomBusy(false);
    }
  }

  return (
    <section className={s.side} aria-label="Di LK">
      <h3>Di LK <span>{sekolah.length} sekolah</span></h3>

      {opsiError && <Notice tone="warn" title="Pilihan isian LK belum terbaca">{opsiError}</Notice>}
      {!opsi && !opsiError && <div className={s.muted}><Spinner label="Memuat pilihan" /> Memuat pilihan isian…</div>}

      {opsi && blok && sekolah.length > 0 && (
        <div className={s.lkTop}>
          <div className={s.seg} role="radiogroup" aria-label="Kolom sesi LK">
            {opsi.blok.map((b) => (
              <button key={b.no} type="button" role="radio" aria-checked={blok === b.no}
                onClick={() => setBlok(b.no)}>
                Sesi {b.label}
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
                onSaved([x.npsn], (y) => ({ ...y, isian: { ...y.isian, [String(blok)]: isi } }));
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
  blok: number | null;
  terbuka: boolean;
  onToggle: () => void;
  onSaved: (isi: Isian) => void;
}) {
  const p = x.progres ?? 0;
  const tersimpan: Isian = { ...KOSONG, ...(blok ? x.isian[String(blok)] : {}) };
  const relevan = grupRelevan(x);
  const nTerisi = relevan.filter((g) => tersimpan[`${g}1` as IsianKey]).length;

  return (
    <li className={`${s.school} ${terbuka ? s.schoolOpen : ""}`}>
      <button type="button" className={s.schoolBtn} onClick={onToggle} aria-expanded={terbuka}>
        <div className={s.schoolTop}>
          <span className={s.schoolName}>{x.nama}</span>
          <Chip tone={prioritasTone(x.prioritas)}>{prioritasLabel(x.prioritas)}</Chip>
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
          {relevan.length === 0 ? null
            : nTerisi === relevan.length ? <span className={s.filled}>Alasan terisi</span>
            : nTerisi > 0 ? <span className={s.toFill}>{nTerisi} dari {relevan.length} terisi</span>
            : <span className={s.toFill}>Isi alasan</span>}
        </div>
      </button>
      {terbuka && opsi && blok && (
        <SchoolForm x={x} opsi={opsi} blok={blok} awal={tersimpan} relevan={relevan}
          onDone={(isi) => (isi ? onSaved(isi) : onToggle())} />
      )}
    </li>
  );
}

function SchoolForm({ x, opsi, blok, awal, relevan, onDone }: {
  x: SekolahLk;
  opsi: LkOpsi;
  blok: number;
  awal: Isian;
  relevan: Grup["kode"][];
  onDone: (isi: Isian | null) => void;
}) {
  const [isi, setIsi] = useState<Isian>(awal);
  const [semua, setSemua] = useState(relevan.length === 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const berubah = (Object.keys(isi) as IsianKey[]).filter((k) => isi[k] !== awal[k]);
  const tampil = GRUP.filter((g) => semua || relevan.includes(g.kode));

  async function simpan() {
    setBusy(true);
    setError(null);
    try {
      const ubah = Object.fromEntries(berubah.map((k) => [k, isi[k]]));
      await post("/api/lk/isi", { blok, sekolah: [{ npsn: x.npsn, isian: ubah }] });
      onDone(isi);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.form}>
      {relevan.length === 0 && !semua && <p className={s.muted}>Sekolah ini tidak butuh alasan.</p>}
      {tampil.map((g) => {
        const k1 = `${g.kode}1` as IsianKey;
        const k2 = `${g.kode}2` as IsianKey;
        const pilihan = opsi.opsi[g.opsi];
        return (
          <fieldset key={g.kode} className={s.fieldset}>
            <legend>{g.judul}</legend>
            <select value={isi[k1]} onChange={(e) => setIsi({ ...isi, [k1]: e.target.value })} aria-label={`Alasan: ${g.judul}`}>
              <option value="">Pilih alasan</option>
              {isi[k1] && !pilihan.includes(isi[k1]) && <option value={isi[k1]}>{isi[k1]}</option>}
              {pilihan.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <textarea rows={2} maxLength={500} placeholder="Tindak lanjut, misalnya: fasil akan mendampingi sekolah unggah laporan Kamis"
              value={isi[k2]} onChange={(e) => setIsi({ ...isi, [k2]: e.target.value })} aria-label={`Tindak lanjut: ${g.judul}`} />
          </fieldset>
        );
      })}
      {error && <Notice tone="bad" title="Belum tersimpan">{error}</Notice>}
      <div className={s.formActions}>
        <Button size="sm" loading={busy} disabled={berubah.length === 0} onClick={simpan}>Simpan ke LK</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone(null)}>Batal</Button>
        {!semua && relevan.length < 3 && (
          <button type="button" className={s.linkBtn} onClick={() => setSemua(true)}>Tampilkan semua isian</button>
        )}
      </div>
    </div>
  );
}
