"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { SurveiProgres } from "@/lib/types";
import { Button } from "@/components/ui";
import { formatWa } from "./WaPanel";
import s from "./wag.module.css";

const POLA_SHEET = /\/d\/([A-Za-z0-9_-]{20,})/;

function salam() {
  const h = new Date().getHours();
  return h < 11 ? "pagi" : h < 15 ? "siang" : h < 18 ? "sore" : "malam";
}

function contoh(teks: string, link: string, f: SurveiProgres["contoh_fasil"]) {
  return teks.replaceAll("{salam}", salam()).replaceAll("{nama}", f.nama).replaceAll("{link}", link || "https://…")
    .replaceAll("{jumlah}", String(f.sekolah.length)).replaceAll("{sekolah}", f.sekolah.map((x) => "• " + x).join("\n") || "-")
    .replaceAll("{nomor}", f.nomor || "yang terdaftar");
}

/** Penanda di halaman Blast saat mode Survei Progres aktif (pengaturan & pemantauan ada di halaman Survei). */
export function SurveiProgresBar({ aktif, berjalan, onChanged }: { aktif: boolean; berjalan: boolean;
  onChanged: () => void }) {
  const [data, setData] = useState<SurveiProgres | null>(null);
  const [error, setError] = useState<string | null>(null);

  const muat = useCallback(async () => {
    try {
      setData(await api<SurveiProgres>("/api/survei-progres"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat, aktif]);

  async function matikan() {
    if (!data) return;
    setError(null);
    try {
      setData(await post<SurveiProgres>("/api/survei-progres", { aktif: false, sheet: data.dari_tim ? "" : data.sheet,
        link: data.dari_tim ? "" : data.link, teks: data.teks }));
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const r = data?.ringkasan;
  return (
    <>
      {aktif ? (
        <div className={s.barOn} role="status">
          <div className={s.barTeks}>
            <b>Blast sedang mengirim link Survei Progres</b>
            <span>
              {r ? `${r.terkirim} dari ${r.total} fasil sudah dikirimi link` : "Memuat…"}
              {r && r.belum === 0 ? ". Semua sudah dikirimi, kembali ke progres mingguan." : ". Progres mingguan menunggu sampai mode ini dimatikan."}
            </span>
          </div>
          <div className={s.barAksi}>
            <Link href="/survei/" className={s.barLink}>Buka halaman Survei</Link>
            <Button variant={r && r.belum === 0 ? "primary" : "secondary"} size="sm" disabled={berjalan}
              title={berjalan ? "Tunggu pengiriman selesai" : undefined} onClick={() => void matikan()}>
              Kembali ke progres mingguan
            </Button>
          </div>
        </div>
      ) : null}
      {error && <p className={s.err}>{error}</p>}
    </>
  );
}

export function SurveiDialog({ data, onClose, onSaved }: { data: SurveiProgres; onClose: () => void;
  onSaved: (d: SurveiProgres) => void }) {
  const [sheet, setSheet] = useState(data.sheet ? `https://docs.google.com/spreadsheets/d/${data.sheet}/edit` : "");
  const [link, setLink] = useState(data.link);
  const [teks, setTeks] = useState(data.teks);
  const [busy, setBusy] = useState<"" | "simpan" | "pakai">("");
  const [error, setError] = useState<string | null>(null);

  const sheetSalah = sheet.trim() !== "" && !POLA_SHEET.test(sheet) && !/^[A-Za-z0-9_-]{20,}$/.test(sheet.trim());
  const linkSalah = link.trim() !== "" && !/^(https?:\/\/)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(\/\S*)?$/.test(link.trim());
  const tanpaLink = !teks.includes("{link}");
  const siap = (data.dari_tim || (sheet.trim() && link.trim() && !sheetSalah && !linkSalah)) && !tanpaLink;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function simpan(aktif: boolean) {
    setBusy(aktif ? "pakai" : "simpan");
    setError(null);
    try {
      onSaved(await post<SurveiProgres>("/api/survei-progres", data.dari_tim ? { aktif, sheet: "", link: "", teks }
        : { aktif, sheet: sheet.trim(), link: link.trim(), teks }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy("");
    }
  }

  const f = data.contoh_fasil;
  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className={s.modal} role="dialog" aria-modal="true" aria-labelledby="svy-judul">
        <div className={s.kepala}>
          <h2 id="svy-judul">{data.dari_tim ? "Teks pesan survei" : "Survei Progres"}</h2>
          <p>Blast mengirim link survei ke fasil binaan Anda di LK Survey (kolom PETUGAS PIC sesuai nama petugas di
            aplikasi), satu pesan per fasil berisi daftar sekolahnya. Dikirim langsung tanpa menunggu sesi, kuota, atau
            batas harian, dengan jeda acak 15–50 detik, pukul 07.00–22.00. Tiap fasil dikirimi sekali per link.</p>
        </div>

        <div className={s.isi}>
          <div className={s.form}>
            {data.dari_tim ? (
              <p className={s.catatan}>Sheet LK Survey dan link pengisian sudah diatur untuk seluruh tim.
                {data.galat ? ` ${data.galat}` : ` ${data.fasil} fasil, ${data.sekolah} sekolah binaan Anda.`}</p>
            ) : (<>
            <label className={s.field}>
              <span>Link sheet LK Survey</span>
              <input value={sheet} onChange={(e) => setSheet(e.target.value)} autoComplete="off" spellCheck={false}
                placeholder="https://docs.google.com/spreadsheets/d/…" autoFocus={!data.sheet} aria-invalid={sheetSalah} />
              <small className={sheetSalah || data.galat ? s.salah : undefined}>
                {sheetSalah ? "Bukan link Google Sheets." : data.galat ? data.galat
                  : data.sheet ? `${data.fasil} fasil, ${data.sekolah} sekolah binaan Anda di tab Survei Progres.`
                  : "Sheet harus punya tab Survei Progres dengan kolom NO TELP dan PETUGAS PIC."}
              </small>
            </label>
            <label className={s.field}>
              <span>Link pengisian survei</span>
              <input value={link} onChange={(e) => setLink(e.target.value)} autoComplete="off" spellCheck={false}
                placeholder="https://survey-progress.netlify.app/" aria-invalid={linkSalah} />
              <small className={linkSalah ? s.salah : undefined}>
                {linkSalah ? "Link tidak valid." : "Mengganti link membuat semua fasil dikirimi lagi."}
              </small>
            </label>
            </>)}
            <label className={s.field}>
              <span>Teks pesan</span>
              <textarea value={teks} onChange={(e) => setTeks(e.target.value)} rows={14} aria-invalid={tanpaLink} />
              <small className={tanpaLink ? s.salah : undefined}>
                {tanpaLink ? "Teks harus memuat {link}." : <>Diisi otomatis: <code>{"{salam}"}</code>, <code>{"{nama}"}</code>,{" "}
                  <code>{"{link}"}</code>, <code>{"{nomor}"}</code>, <code>{"{jumlah}"}</code>, <code>{"{sekolah}"}</code>.</>}
                {teks !== data.teks_awal && (
                  <button type="button" className={s.reset} onClick={() => setTeks(data.teks_awal)}>Pakai teks awal</button>
                )}
              </small>
            </label>
          </div>

          <div className={s.pratinjau} aria-label="Contoh pesan">
            <span className={s.pratinjauJudul}>Contoh untuk {f.nama}</span>
            <div className={s.bubble}>{formatWa(contoh(teks, link.trim(), f))}</div>
            {data.ringkasan && (
              <p className={s.catatan}>{data.ringkasan.terkirim} dari {data.ringkasan.total} fasil sudah dikirimi link
                ini.{data.ringkasan.total < data.fasil ? ` ${data.fasil - data.ringkasan.total} fasil tanpa nomor WhatsApp dilewati.` : ""}</p>
            )}
          </div>
        </div>

        {error && <p className={s.err}>{error}</p>}
        <div className={s.aksi}>
          <Button variant="ghost" disabled={!!busy} onClick={onClose}>Batal</Button>
          <Button variant="secondary" loading={busy === "simpan"} disabled={!!busy || sheetSalah || linkSalah || tanpaLink}
            onClick={() => void simpan(data.aktif)}>Simpan</Button>
          {!data.aktif && (
            <Button loading={busy === "pakai"} disabled={!!busy || !siap}
              onClick={() => void simpan(true)}>Simpan dan pakai untuk blast</Button>
          )}
        </div>
      </div>
    </div>
  );
}
