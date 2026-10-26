"use client";

import { useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import type { Fasil } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { LkPanel } from "./LkPanel";
import { inisial } from "./FasilList";
import s from "./today.module.css";

/** Tampilkan *teks* gaya WhatsApp sebagai huruf tebal. */
function formatWa(teks: string) {
  return teks.split(/(\*[^*\n]+\*)/g).map((bagian, i) =>
    bagian.length > 2 && bagian.startsWith("*") && bagian.endsWith("*")
      ? <b key={i}>{bagian.slice(1, -1)}</b>
      : bagian,
  );
}


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

  const gagal = data?.status_kirim === "gagal";

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
        {openError && <div className={s.drawerNote}><Notice tone="warn" title="Chat belum terbuka">{openError}</Notice></div>}
        {error && <div className={s.drawerNote}><Notice tone="bad" title="Data fasil tidak terbaca">{error}</Notice></div>}
        {!data && !error && <div className={s.empty}><Spinner label="Memuat" /></div>}

        {data && (
          <div className={s.compare}>
            <LkPanel sekolah={data.sekolah}
              onSaved={(npsn, ubah) => setData((d) => d && {
                ...d, sekolah: d.sekolah.map((x) => (npsn.includes(x.npsn) ? ubah(x) : x)),
              })} />

            <section className={`${s.side} ${s.sideWa}`} aria-label="Di WhatsApp">
              <h3>Di WhatsApp <span>{!data.waktu_kirim ? "belum dikirim" : gagal ? "gagal terkirim" : `dikirim ${data.waktu_kirim}`}</span></h3>
              <div className={s.thread}>
                {data.pesan ? (
                  <div className={`${s.msg} ${s.msgOut} ${gagal ? s.msgFail : ""}`}>
                    <div className={s.bubble}>{formatWa(data.pesan)}</div>
                    <div className={s.msgMeta}>
                      {!data.waktu_kirim ? "Belum dikirim, pratinjau dari sheet Broadcast"
                        : gagal ? `Gagal dikirim ${data.waktu_kirim}, akan dicoba ulang` : `Dikirim ${data.waktu_kirim}`}
                    </div>
                  </div>
                ) : (
                  <p className={s.muted}>Pesan untuk fasil ini tidak ada di sheet Broadcast.</p>
                )}
                {data.balasan ? (
                  <div className={s.msg}>
                    <div className={s.bubble}>{formatWa(data.balasan)}</div>
                    <div className={s.msgMeta}>Balasan terakhir{data.waktu_balasan ? `, dicek ${data.waktu_balasan.slice(11, 16).replace(":", ".")}` : ""}</div>
                  </div>
                ) : data.waktu_kirim && !gagal ? (
                  <p className={s.waiting}>Belum ada balasan.</p>
                ) : null}
              </div>
              <p className={s.waFoot}>Dibaca dari WhatsApp Web, hanya untuk dilihat. Balas lewat WhatsApp Web.</p>
            </section>
          </div>
        )}
      </aside>
    </div>
  );
}
