"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import type { Fasil, Tahap } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { LkPanel } from "./LkPanel";
import { WaPanel } from "./WaPanel";
import { inisial } from "./FasilList";
import s from "./today.module.css";

function toneStatus(st: string) {
  if (st.startsWith("Sudah")) return "ok" as const;
  if (st.startsWith("Dibaca")) return "info" as const;
  if (st.startsWith("Gagal")) return "bad" as const;
  return "muted" as const;
}


/** Panel geser: LK sekolah binaan di kiri, chat WhatsApp di kanan. */
export function FasilDrawer({ nomor, versi, onClose }: { nomor: string; versi: number; onClose: () => void }) {
  const [data, setData] = useState<Fasil | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let batal = false;
    api<Fasil>(`/api/fasil/${nomor}`)
      .then((d) => { if (!batal) { setData(d); setError(null); } })
      .catch((e) => { if (!batal) setError(e.message); });
    return () => { batal = true; };
  }, [nomor, versi]);

  const muatUlang = useCallback(async () => {
    try {
      setData(await api<Fasil>(`/api/fasil/${nomor}`));
    } catch {
      /* status di kepala panel cukup diperbarui saat dibuka lagi */
    }
  }, [nomor]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  async function bukaWa() {
    setOpening(true);
    setOpenError(null);
    try {
      await post(`/api/wa/open/${nomor}`);
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpening(false);
    }
  }

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className={s.drawer} role="dialog" aria-modal="true" aria-label={data ? data.nama_fasil : "Detail fasil"}>
        <header className={s.drawerHead}>
          <span className={`${s.avatar} ${s.avatarLg}`} aria-hidden="true">{data ? inisial(data.nama_fasil) : ""}</span>
          <div className={s.drawerWho}>
            <h2>{data?.nama_fasil ?? "Memuat…"}</h2>
            {data && <span>{data.nomor_tersamar} <Chip tone={toneStatus(data.status)}>{data.status}</Chip></span>}
          </div>
          <Button variant="secondary" size="sm" loading={opening} onClick={bukaWa}>Buka di WhatsApp Web</Button>
          <button ref={closeRef} type="button" className={s.close} onClick={onClose} aria-label="Tutup">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        {data && <TahapBar nomor={nomor} data={data} onChange={setData} />}
        {openError && <div className={s.drawerNote}><Notice tone="warn" title="Chat belum terbuka">{openError}</Notice></div>}
        {error && <div className={s.drawerNote}><Notice tone="bad" title="Data fasil tidak terbaca">{error}</Notice></div>}
        {!data && !error && <div className={s.empty}><Spinner label="Memuat" /></div>}

        {data && (
          <div className={s.compare}>
            <LkPanel sekolah={data.sekolah}
              onSaved={(npsn, ubah) => {
                setData((d) => d && { ...d, sekolah: d.sekolah.map((x) => (x.npsn === npsn ? ubah(x) : x)) });
                void muatUlang(); // perbarui tahap "Isian LK lengkap"
              }} />

            <WaPanel nomor={nomor} data={data} onChanged={() => void muatUlang()} />
          </div>
        )}
      </aside>
    </div>
  );
}

/** Urutan komunikasi dengan fasil. Klik tahap untuk mencentang manual (mis. bila chat lewat HP). */
function TahapBar({ nomor, data, onChange }: {
  nomor: string;
  data: Fasil;
  onChange: (f: Fasil) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const { tahap, di_broadcast: diBroadcast, kirim_ulang: ulang } = data;

  async function kirimUlang(aktif: boolean) {
    setBusy("ulang");
    try {
      onChange(await post<Fasil>(`/api/fasil/${nomor}/kirim-ulang`, { aktif }));
    } finally {
      setBusy(null);
    }
  }

  async function ubah(t: Tahap) {
    if (t.kode === "lk_lengkap") return;
    setBusy(t.kode);
    try {
      // manual -> kembali otomatis; otomatis -> centang/hapus centang manual
      const selesai = t.sumber === "manual" ? null : !t.selesai;
      onChange(await post<Fasil>(`/api/fasil/${nomor}/tahap`, { kode: t.kode, selesai }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={s.tahapWrap}>
      <ol className={s.tahap} aria-label="Tahap komunikasi">
        {tahap.map((t, i) => (
          <li key={t.kode} className={`${t.selesai ? s.tahapOk : ""} ${t.sumber === "manual" ? s.tahapManual : ""}`}>
            <button type="button" disabled={t.kode === "lk_lengkap" || busy !== null} onClick={() => void ubah(t)}
              title={t.kode === "lk_lengkap" ? "Terisi otomatis dari isian LK"
                : t.sumber === "manual" ? "Dicentang manual. Klik untuk kembali ke deteksi otomatis"
                : "Klik untuk menandai manual, misalnya bila chat lewat HP"}>
              <span className={s.tahapDot} aria-hidden="true">{t.selesai ? "✓" : i + 1}</span>
              <span className={s.tahapLabel}>{t.label}{t.sumber === "manual" ? " (manual)" : ""}</span>
            </button>
          </li>
        ))}
      </ol>
      {!diBroadcast && <span className={s.luarBc}>Tidak masuk Broadcast</span>}
      {ulang.diminta ? (
        <span className={s.ulang}>
          Dikirim ulang di sesi berikutnya
          <button type="button" className={s.linkBtn} disabled={busy !== null} onClick={() => void kirimUlang(false)}>Batalkan</button>
        </span>
      ) : ulang.bisa ? (
        <button type="button" className={s.ulangBtn} disabled={busy !== null} onClick={() => void kirimUlang(true)}
          title="Pesan Broadcast sudah terkirim minggu ini. Tekan untuk mengirim sekali lagi di sesi berikutnya.">
          Kirim ulang broadcast
        </button>
      ) : null}
    </div>
  );
}
