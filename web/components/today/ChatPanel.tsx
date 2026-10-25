"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Fasil } from "@/lib/types";
import { Button, Chip, Notice, Spinner, prioritasTone } from "@/components/ui";
import s from "./today.module.css";

/** Tampilkan *teks* gaya WhatsApp sebagai huruf tebal. */
function formatWa(teks: string) {
  return teks.split(/(\*[^*\n]+\*)/g).map((bagian, i) =>
    bagian.length > 2 && bagian.startsWith("*") && bagian.endsWith("*")
      ? <b key={i}>{bagian.slice(1, -1)}</b>
      : bagian,
  );
}

function prioritasLabel(p: string) {
  if (p.endsWith("1")) return "P1 Belum submit";
  if (p.endsWith("2")) return "P2 Progres < 50%";
  if (p.endsWith("3")) return "P3 Belum reviu";
  return p || "–";
}

export function ChatPanel({ nomor, versi }: { nomor: string | null; versi: number }) {
  const [data, setData] = useState<Fasil | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  useEffect(() => {
    if (!nomor) return;
    let batal = false;
    api<Fasil>(`/api/fasil/${nomor}`)
      .then((d) => { if (!batal) { setData(d); setError(null); } })
      .catch((e) => { if (!batal) setError(e.message); });
    return () => { batal = true; };
  }, [nomor, versi]);

  async function bukaWa() {
    if (!nomor) return;
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

  if (!nomor) {
    return (
      <section className={s.panel}>
        <div className={s.empty} style={{ padding: "64px 24px" }}>
          Pilih fasilitator di daftar sesi untuk melihat sekolah binaan dan chat-nya.
        </div>
      </section>
    );
  }
  if (error) return <section className={s.panel} style={{ padding: 20 }}><Notice tone="bad" title="Data fasilitator tidak terbaca">{error}</Notice></section>;
  if (!data) return <section className={s.panel}><div className={s.empty}><Spinner label="Memuat" /></div></section>;

  const p1 = data.sekolah.filter((x) => x.prioritas.endsWith("1")).length;

  return (
    <section className={s.panel} aria-label={`Chat ${data.nama_fasil}`}>
      <div className={s.chatHead}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>{data.nama_fasil}</div>
          <div className={s.panelSub}>{data.nomor_tersamar}. {data.status}</div>
        </div>
        <Button variant="secondary" size="sm" loading={opening} onClick={bukaWa}>Buka di WhatsApp Web</Button>
      </div>
      {openError && <div style={{ padding: "12px 20px 0" }}><Notice tone="warn" title="Chat belum terbuka">{openError}</Notice></div>}

      <div className={s.schools}>
        <div className={s.schoolsHead}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Sekolah binaan</span>
          <span className={s.panelSub}>{data.sekolah.length} sekolah{p1 ? `, ${p1} belum submit` : ""}</span>
        </div>
        {data.sekolah.length === 0 ? (
          <p className={s.muted} style={{ fontSize: 13, padding: "6px 0 10px" }}>
            Nomor fasilitator ini tidak ditemukan di LK WEEK yang dipilih.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className={s.table}>
              <thead>
                <tr><th>Sekolah</th><th>NPSN</th><th className={s.num}>Progres</th><th>Prioritas</th></tr>
              </thead>
              <tbody>
                {data.sekolah.map((x) => (
                  <tr key={x.npsn}>
                    <td>{x.nama}</td>
                    <td className={s.muted} style={{ fontVariantNumeric: "tabular-nums" }}>{x.npsn}</td>
                    <td className={s.num}>{x.progres === null ? "–" : `${x.progres.toFixed(2).replace(".", ",")}%`}</td>
                    <td><Chip tone={prioritasTone(x.prioritas)}>{prioritasLabel(x.prioritas)}</Chip></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={s.thread}>
        {data.pesan ? (
          <div className={`${s.msg} ${s.msgOut}`}>
            <div className={s.bubble}>{formatWa(data.pesan)}</div>
            <div className={s.msgMeta}>{data.waktu_kirim ? `Dikirim ${data.waktu_kirim}` : "Belum dikirim, pratinjau dari sheet Broadcast"}</div>
          </div>
        ) : (
          <p className={s.muted} style={{ fontSize: 13 }}>Pesan untuk fasilitator ini tidak ada di sheet Broadcast.</p>
        )}
        {data.balasan && (
          <div className={s.msg}>
            <div className={s.bubble}>{formatWa(data.balasan)}</div>
            <div className={s.msgMeta}>Balasan terakhir{data.waktu_balasan ? `, dicek ${data.waktu_balasan.slice(11, 16).replace(":", ".")}` : ""}</div>
          </div>
        )}
      </div>
      <div className={s.chatFoot}>Dibaca dari WhatsApp Web, hanya untuk dilihat. Balas lewat WhatsApp Web.</div>
    </section>
  );
}
