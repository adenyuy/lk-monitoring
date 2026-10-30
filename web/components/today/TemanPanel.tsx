"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Percakapan } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import { CENTANG, formatWa } from "./WaPanel";
import s from "./today.module.css";

export type Teman = { nama: string; nomor: string };
type Chat = Pick<Percakapan, "pesan" | "dibaca_pada">;

/** Pengganti sementara kolom "Di WhatsApp": chat dengan teman PIC, dibaca dan dibalas dari aplikasi. */
export function TemanPanel({ teman, draf, nomorFasil, onKembali, onPakai }: {
  teman: Teman;
  draf: string;
  nomorFasil: string;
  onKembali: () => void;
  onPakai: (teks: string) => void;
}) {
  const [chat, setChat] = useState<Chat | null>(null);
  const [membaca, setMembaca] = useState(false);
  const [catatan, setCatatan] = useState<string | null>(null);
  const [teks, setTeks] = useState(draf);
  const [mengirim, setMengirim] = useState(false);
  const [kirimError, setKirimError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const isiRef = useRef<HTMLTextAreaElement>(null);

  const baca = useCallback(async () => {
    setMembaca(true);
    setCatatan(null);
    try {
      setChat(await post<Chat>(`/api/eskalasi/teman/${teman.nomor}/baca`));
    } catch (e) {
      setCatatan(e instanceof Error ? e.message : String(e));
    } finally {
      setMembaca(false);
    }
  }, [teman.nomor]);

  useEffect(() => {
    // Baca chat teman begitu panel dibuka
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void baca();
  }, [baca]);

  useEffect(() => {
    const el = isiRef.current;
    if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
  }, []);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat]);

  async function kirim() {
    const isi = teks.trim();
    if (!isi) return;
    setMengirim(true);
    setKirimError(null);
    try {
      setChat(await post<Chat>(`/api/eskalasi/teman/${teman.nomor}/kirim`, { pesan: isi, fasil: nomorFasil }));
      setTeks("");
    } catch (e) {
      setKirimError(e instanceof Error ? e.message : String(e));
    } finally {
      setMengirim(false);
    }
  }

  const pesan = chat?.pesan ?? [];

  return (
    <section className={`${s.side} ${s.sideWa} ${s.sideTeman}`} aria-label={`Chat dengan ${teman.nama}`}>
      <h3>
        <span className={s.temanJudul}>
          <button type="button" className={s.linkBtn} onClick={onKembali}>← Kembali ke chat fasil</button>
          <span>Teman PIC: <b>{teman.nama}</b></span>
        </span>
        <button type="button" className={s.linkBtn} onClick={() => void baca()} disabled={membaca}>
          {membaca ? <><Spinner /> Membaca chat…</> : chat ? `Dibaca ${chat.dibaca_pada}, baca ulang` : "Baca chat"}
        </button>
      </h3>

      <div className={s.thread} ref={threadRef}>
        {pesan.length > 0 ? (
          pesan.map((m, i) => (
            <div key={i} className={`${s.msg} ${m.keluar ? s.msgOut : ""}`}>
              <div className={s.bubble}>
                {m.kutipan && <div className={s.kutipan}>{m.kutipan}</div>}
                {formatWa(m.teks)}
              </div>
              <div className={s.msgMeta}>
                {m.waktu || (m.keluar ? "Kamu" : teman.nama)}
                {m.keluar && m.status ? `, ${CENTANG[m.status] ?? m.status}` : ""}
                {!m.keluar && (
                  <button type="button" className={s.msgAksi} onClick={() => onPakai(m.teks)}
                    title="Salin jawaban ini ke kotak balasan fasil">
                    Pakai untuk balas fasil
                  </button>
                )}
              </div>
            </div>
          ))
        ) : !membaca ? (
          <p className={s.waiting}>Belum ada percakapan dengan {teman.nama}.</p>
        ) : null}
      </div>

      {catatan && <p className={s.waNote}>{catatan}</p>}

      <div className={s.composer}>
        <textarea ref={isiRef} rows={teks.length > 120 ? 6 : 3} maxLength={2000} value={teks}
          placeholder={`Tulis pesan untuk ${teman.nama}…`} aria-label={`Pesan untuk ${teman.nama}`}
          onChange={(e) => setTeks(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void kirim(); } }} />
        <div className={s.composerRow}>
          <span>Ctrl + Enter untuk kirim. Terkirim dari WhatsApp yang tertaut di aplikasi.</span>
          <Button size="sm" loading={mengirim} disabled={!teks.trim()} onClick={() => void kirim()}>
            {mengirim ? "Mengirim…" : `Kirim ke ${teman.nama.split(" ")[0]}`}
          </Button>
        </div>
        {kirimError && <p className={s.errNote}>{kirimError}</p>}
      </div>
    </section>
  );
}
