"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Percakapan } from "@/lib/types";
import type { Penerima } from "@/lib/lk";
import { bacaBalasan, isi as isiTemplate, kosong, templateBawaan } from "@/lib/pesan";
import { Button, Spinner } from "@/components/ui";
import { formatWa } from "@/components/today/WaPanel";
import s from "./lk.module.css";

const CENTANG: Record<string, string> = { read: "Dibaca", delivered: "Diterima", sent: "Terkirim", pending: "Menunggu" };

/** Chat WhatsApp fasil: baca, balas dengan template sesuai to-do, dan isi LK langsung dari balasan fasil. */
export function ChatPanel({ nomor, nama, penerima, onIsiLk, onTeruskan, isi, tersembunyi }: {
  nomor: string;
  nama: string;
  penerima: Penerima;
  onIsiLk: (teks: string) => number;
  onTeruskan: (teks: string) => void;
  isi: { teks: string; kunci: number } | null;
  tersembunyi: boolean;
}) {
  const [chat, setChat] = useState<Percakapan | null>(null);
  const [membaca, setMembaca] = useState(false);
  const [catatan, setCatatan] = useState<string | null>(null);
  const [teks, setTeks] = useState("");
  const [mengirim, setMengirim] = useState(false);
  const [kirimError, setKirimError] = useState<string | null>(null);
  const [terisi, setTerisi] = useState<Record<number, number>>({});
  const threadRef = useRef<HTMLDivElement>(null);

  const baca = useCallback(async () => {
    setMembaca(true);
    setCatatan(null);
    try {
      setChat(await post<Percakapan>(`/api/chat/${nomor}/baca`));
    } catch (e) {
      setCatatan(e instanceof Error ? e.message : String(e));
    } finally {
      setMembaca(false);
    }
  }, [nomor]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void baca(); }, [baca]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (isi) setTeks(isi.teks); }, [isi]);
  useEffect(() => { const el = threadRef.current; if (el) el.scrollTop = el.scrollHeight; }, [chat]);

  async function kirim() {
    const t = teks.trim();
    if (!t) return;
    setMengirim(true);
    setKirimError(null);
    try {
      setChat(await post<Percakapan>(`/api/chat/${nomor}/balas`, { pesan: t, jenis: /Kendala:/.test(t) ? "tanya_lk" : "" }));
      setTeks("");
    } catch (e) {
      setKirimError(e instanceof Error ? e.message : String(e));
    } finally {
      setMengirim(false);
    }
  }

  const pesan = chat?.pesan ?? [];
  const template = templateBawaan("fasil").filter((t) => !kosong(t.teks, penerima).length);

  return (
    <section className={`${s.kolomWa} ${tersembunyi ? s.hide : ""}`} aria-label="WhatsApp">
      <div className={s.kolomHead}>
        <h3>WhatsApp <span>{nama}</span></h3>
        <button type="button" className={s.linkBtn} onClick={() => void baca()} disabled={membaca}>
          {membaca ? <><Spinner /> Membaca…</> : chat ? `Dibaca ${chat.dibaca_pada} · baca ulang` : "Baca chat"}
        </button>
      </div>

      <div className={s.thread} ref={threadRef}>
        {pesan.length > 0 ? pesan.map((m, i) => {
          const bisaIsi = !m.keluar && bacaBalasan(m.teks).length > 0;
          return (
            <div key={i} className={`${s.msg} ${m.keluar ? s.msgOut : ""}`}>
              <div className={s.bubble}>
                {m.kutipan && <div className={s.kutipan}>{m.kutipan}</div>}
                {formatWa(m.teks)}
              </div>
              <div className={s.msgMeta}>
                {m.waktu || (m.keluar ? "Anda" : "Fasil")}
                {m.keluar && m.status ? `, ${CENTANG[m.status] ?? m.status}` : ""}
                {!m.keluar && (
                  <>
                    {bisaIsi && (
                      <button type="button" className={s.msgAksiUtama}
                        onClick={() => setTerisi({ ...terisi, [i]: onIsiLk(m.teks) })}>
                        {terisi[i] ? `${terisi[i]} sekolah terisi ✓` : "Isi LK dari pesan ini"}
                      </button>
                    )}
                    <button type="button" className={s.msgAksi} onClick={() => onTeruskan(m.teks)}>Teruskan ke teman</button>
                  </>
                )}
              </div>
            </div>
          );
        }) : chat?.status === "belum_ada" ? (
          <p className={s.muted}>Belum ada percakapan dengan nomor ini. Mulai dengan template di bawah.</p>
        ) : !membaca && catatan ? null : <p className={s.muted}>Membuka chat…</p>}
      </div>
      {catatan && <p className={s.errNote}>{catatan}</p>}

      <div className={s.composer}>
        <div className={s.tplList} aria-label="Template pesan">
          {template.map((t) => (
            <button key={t.kode} type="button" title={t.ket}
              onClick={() => setTeks(isiTemplate(t.teks, penerima, "", false))}>{t.judul}</button>
          ))}
        </div>
        <textarea rows={teks.length > 160 ? 8 : 3} maxLength={4000} placeholder="Tulis pesan untuk fasil…" value={teks}
          onChange={(e) => setTeks(e.target.value)} aria-label="Pesan"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void kirim(); } }} />
        <div className={s.composerRow}>
          <span>Ctrl + Enter untuk kirim</span>
          <Button size="sm" loading={mengirim} disabled={!teks.trim()} onClick={() => void kirim()}>
            {mengirim ? "Mengirim…" : "Kirim"}
          </Button>
        </div>
        {kirimError && <p className={s.errNote}>{kirimError}</p>}
      </div>
    </section>
  );
}
