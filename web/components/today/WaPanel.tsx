"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Fasil, Percakapan } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import s from "./today.module.css";

/** Tampilkan *teks* gaya WhatsApp sebagai huruf tebal. */
function formatWa(teks: string) {
  return teks.split(/(\*[^*\n]+\*)/g).map((bagian, i) =>
    bagian.length > 2 && bagian.startsWith("*") && bagian.endsWith("*")
      ? <b key={i}>{bagian.slice(1, -1)}</b>
      : bagian,
  );
}

const CENTANG: Record<string, string> = { read: "Dibaca", delivered: "Diterima", sent: "Terkirim", pending: "Menunggu" };

/** Kolom "Di WhatsApp": baca percakapan langsung dari WhatsApp app dan balas dari sini. */
export function WaPanel({ nomor, data, onChanged }: { nomor: string; data: Fasil; onChanged: () => void }) {
  const [chat, setChat] = useState<Percakapan | null>(null);
  const [membaca, setMembaca] = useState(false);
  const [catatan, setCatatan] = useState<string | null>(null);
  const [teks, setTeks] = useState("");
  const [mengirim, setMengirim] = useState(false);
  const [kirimError, setKirimError] = useState<string | null>(null);
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

  useEffect(() => {
    // Baca chat terbaru begitu panel dibuka
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void baca();
  }, [baca]);

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
      setChat(await post<Percakapan>(`/api/chat/${nomor}/balas`, { pesan: isi }));
      setTeks("");
      onChanged();
    } catch (e) {
      setKirimError(e instanceof Error ? e.message : String(e));
    } finally {
      setMengirim(false);
    }
  }

  const gagal = data.status_kirim === "gagal";
  const pesan = chat?.pesan ?? [];

  return (
    <section className={`${s.side} ${s.sideWa}`} aria-label="Di WhatsApp">
      <h3>
        Di WhatsApp
        <button type="button" className={s.linkBtn} onClick={() => void baca()} disabled={membaca}>
          {membaca ? <><Spinner /> Membaca chat…</> : chat ? `Dibaca ${chat.dibaca_pada}, baca ulang` : "Baca chat"}
        </button>
      </h3>

      <div className={s.thread} ref={threadRef}>
        {pesan.length > 0 ? (
          pesan.map((m, i) => (
            <div key={i} className={`${s.msg} ${m.keluar ? s.msgOut : ""}`}>
              <div className={s.bubble}>{formatWa(m.teks)}</div>
              <div className={s.msgMeta}>
                {m.waktu || (m.keluar ? "Kamu" : "Fasil")}
                {m.keluar && m.status ? `, ${CENTANG[m.status] ?? m.status}` : ""}
              </div>
            </div>
          ))
        ) : (
          <>
            {/* Belum bisa membaca langsung: tampilkan yang tersimpan di aplikasi */}
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
                <div className={s.msgMeta}>Balasan terakhir yang tersimpan</div>
              </div>
            ) : chat && chat.status === "belum_ada" ? (
              <p className={s.waiting}>Belum ada percakapan dengan nomor ini.</p>
            ) : null}
          </>
        )}
      </div>

      {catatan && <p className={s.waNote}>{catatan}</p>}

      <div className={s.composer}>
        <textarea rows={2} maxLength={2000} placeholder="Tulis balasan untuk fasil…" value={teks}
          onChange={(e) => setTeks(e.target.value)} aria-label="Balasan"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void kirim(); } }} />
        <div className={s.composerRow}>
          <span>Ctrl + Enter untuk kirim</span>
          <Button size="sm" loading={mengirim} disabled={!teks.trim()} onClick={() => void kirim()}>
            {mengirim ? "Mengirim…" : "Kirim balasan"}
          </Button>
        </div>
        {kirimError && <p className={s.errNote}>{kirimError}</p>}
      </div>
    </section>
  );
}
