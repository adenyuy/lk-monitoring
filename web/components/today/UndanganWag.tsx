"use client";

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { UndanganWag } from "@/lib/types";
import { Button } from "@/components/ui";
import { formatWa } from "./WaPanel";
import s from "./wag.module.css";

const POLA_LINK = /^https:\/\/chat\.whatsapp\.com\/[A-Za-z0-9_-]{10,}$/;

function rapikanLink(link: string) {
  let l = link.trim().split("?")[0].replace(/\/+$/, "");
  if (l.startsWith("chat.whatsapp.com/")) l = "https://" + l;
  return l.replace(/^http:\/\//, "https://");
}

function salam() {
  const h = new Date().getHours();
  return h < 11 ? "pagi" : h < 15 ? "siang" : h < 18 ? "sore" : "malam";
}

function contoh(teks: string, nama: string, tim: string, link: string) {
  return teks.replaceAll("{salam}", salam()).replaceAll("{nama}", nama).replaceAll("{tim}", tim.trim())
    .replaceAll("{link}", link || "https://chat.whatsapp.com/…").replace(/ {2,}/g, " ").replace(/[ \t]+\n/g, "\n");
}

/** Mode blast Undangan WAG: bar di atas kartu kirim + popup pengaturan (link grup ditempel petugas sendiri). */
export function UndanganWagBar({ aktif, berjalan, onChanged }: { aktif: boolean; berjalan: boolean;
  onChanged: () => void }) {
  const [data, setData] = useState<UndanganWag | null>(null);
  const [buka, setBuka] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const muat = useCallback(async () => {
    try {
      setData(await api<UndanganWag>("/api/undangan-wag"));
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
      setData(await post<UndanganWag>("/api/undangan-wag", { aktif: false, link: data.link, tim: data.tim,
        teks: data.teks }));
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
            <b>Blast sedang mengirim Undangan WAG</b>
            <span>
              {r ? `${r.terkirim} dari ${r.total} fasil sudah diundang` : "Memuat…"}
              {r && r.belum === 0 ? ". Semua sudah diundang, kembali ke pesan Broadcast." : ". Pesan Broadcast minggu ini menunggu sampai mode ini dimatikan."}
            </span>
          </div>
          <div className={s.barAksi}>
            <Button variant="secondary" size="sm" disabled={berjalan} onClick={() => setBuka(true)}>Ubah undangan</Button>
            <Button variant={r && r.belum === 0 ? "primary" : "secondary"} size="sm" disabled={berjalan}
              title={berjalan ? "Tunggu pengiriman selesai" : undefined} onClick={() => void matikan()}>
              Kembali ke pesan Broadcast
            </Button>
          </div>
        </div>
      ) : (
        <div className={s.barOff}>
          <span>
            <b>Undangan WAG</b> Ajak fasil binaan bergabung ke grup WhatsApp tim Anda lewat blast.
            {r && r.terkirim > 0 && ` ${r.terkirim} dari ${r.total} fasil sudah diundang.`}
          </span>
          <Button variant="secondary" size="sm" disabled={berjalan} onClick={() => setBuka(true)}>Atur undangan</Button>
        </div>
      )}
      {error && <p className={s.err}>{error}</p>}
      {buka && data && (
        <UndanganDialog data={data} onClose={() => setBuka(false)}
          onSaved={(d) => { setData(d); setBuka(false); onChanged(); }} />
      )}
    </>
  );
}

function UndanganDialog({ data, onClose, onSaved }: { data: UndanganWag; onClose: () => void;
  onSaved: (d: UndanganWag) => void }) {
  const [link, setLink] = useState(data.link);
  const [tim, setTim] = useState(data.tim);
  const [teks, setTeks] = useState(data.teks);
  const [busy, setBusy] = useState<"" | "simpan" | "pakai">("");
  const [error, setError] = useState<string | null>(null);

  const l = rapikanLink(link);
  const linkSalah = l !== "" && !POLA_LINK.test(l);
  const tanpaLink = !teks.includes("{link}");
  const nama = data.nama_contoh;

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
      onSaved(await post<UndanganWag>("/api/undangan-wag", { aktif, link: l, tim, teks }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy("");
    }
  }

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className={s.modal} role="dialog" aria-modal="true" aria-labelledby="wag-judul">
        <div className={s.kepala}>
          <h2 id="wag-judul">Undangan WAG</h2>
          <p>Blast mengirim undangan ini langsung ke semua fasil binaan Anda hari ini, sekali per fasil, tanpa menunggu
            jam sesi, kuota, atau batas harian. Jeda acak 15–30 detik untuk fasil yang pernah membalas, 25–50 detik untuk lainnya, pukul 07.00–22.00.</p>
        </div>

        <div className={s.isi}>
          <div className={s.form}>
            <label className={s.field}>
              <span>Link grup WhatsApp</span>
              <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://chat.whatsapp.com/…"
                autoComplete="off" spellCheck={false} autoFocus aria-invalid={linkSalah} />
              <small className={linkSalah ? s.salah : undefined}>
                {linkSalah ? "Bukan link undangan grup WhatsApp." : "Di grup: Info grup › Undang lewat link › Salin link."}
              </small>
            </label>
            <label className={s.field}>
              <span>Nomor tim <i>(opsional)</i></span>
              <input value={tim} onChange={(e) => setTim(e.target.value)} placeholder="Contoh: 7" autoComplete="off" />
            </label>
            <label className={s.field}>
              <span>Teks undangan</span>
              <textarea value={teks} onChange={(e) => setTeks(e.target.value)} rows={12} aria-invalid={tanpaLink} />
              <small className={tanpaLink ? s.salah : undefined}>
                {tanpaLink ? "Teks harus memuat {link}." : <>Diisi otomatis: <code>{"{salam}"}</code> pagi/siang/sore/malam,{" "}
                  <code>{"{nama}"}</code> nama fasil, <code>{"{tim}"}</code>, <code>{"{link}"}</code>.</>}
                {teks !== data.teks_awal && (
                  <button type="button" className={s.reset} onClick={() => setTeks(data.teks_awal)}>Pakai teks awal</button>
                )}
              </small>
            </label>
          </div>

          <div className={s.pratinjau} aria-label="Contoh pesan">
            <span className={s.pratinjauJudul}>Contoh untuk {nama}</span>
            <div className={s.bubble}>{formatWa(contoh(teks, nama, tim, POLA_LINK.test(l) ? l : ""))}</div>
            {data.ringkasan && (
              <p className={s.catatan}>{data.ringkasan.terkirim} dari {data.ringkasan.total} fasil sudah diundang dengan
                link ini. Mengganti link membuat semua fasil diundang lagi.</p>
            )}
          </div>
        </div>

        {error && <p className={s.err}>{error}</p>}
        <div className={s.aksi}>
          <Button variant="ghost" disabled={!!busy} onClick={onClose}>Batal</Button>
          <Button variant="secondary" loading={busy === "simpan"} disabled={!!busy || linkSalah || tanpaLink}
            onClick={() => void simpan(data.aktif)}>Simpan</Button>
          {!data.aktif && (
            <Button loading={busy === "pakai"} disabled={!!busy || !l || linkSalah || tanpaLink}
              onClick={() => void simpan(true)}>Simpan dan pakai untuk blast</Button>
          )}
        </div>
      </div>
    </div>
  );
}
