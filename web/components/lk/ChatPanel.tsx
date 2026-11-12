"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Percakapan } from "@/lib/types";
import { bacaBalasan, type Template } from "@/lib/pesan";
import { Button, Spinner } from "@/components/ui";
import { formatWa } from "@/components/today/WaPanel";
import s from "./lk.module.css";

const CENTANG: Record<string, string> = { read: "Dibaca", delivered: "Diterima", sent: "Terkirim", pending: "Menunggu" };

/** Chat WhatsApp (fasil atau koordinator): baca, balas dengan template, dan untuk fasil: isi LK dari balasannya. */
export function ChatPanel({ nomor, nama, peran, template, onIsiLk }: {
  nomor: string;
  nama: string;
  peran: "fasil" | "koor" | "sekolah";
  /** Template yang sudah terisi, siap kirim */
  template: Template[];
  onIsiLk?: (teks: string) => number;
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
  useEffect(() => { const el = threadRef.current; if (el) el.scrollTop = el.scrollHeight; }, [chat]);

  async function kirim() {
    const t = teks.trim();
    if (!t) return;
    setMengirim(true);
    setKirimError(null);
    try {
      setChat(await post<Percakapan>(`/api/chat/${nomor}/balas`,
        { pesan: t, jenis: peran === "fasil" && /Kendala:/.test(t) ? "tanya_lk" : "" }));
      setTeks("");
    } catch (e) {
      setKirimError(e instanceof Error ? e.message : String(e));
    } finally {
      setMengirim(false);
    }
  }

  const pesan = chat?.pesan ?? [];
  const lawan = peran === "fasil" ? "Fasil" : peran === "koor" ? "Koordinator" : "Kepala sekolah";

  return (
    <section className={s.chat} aria-label={`WhatsApp ${nama}`}>
      <div className={s.chatHead}>
        <span>{nama}</span>
        <button type="button" className={s.linkBtn} onClick={() => void baca()} disabled={membaca}>
          {membaca ? <><Spinner /> Membaca…</> : chat ? `Dibaca ${chat.dibaca_pada} · baca ulang` : "Baca chat"}
        </button>
      </div>

      <div className={s.thread} ref={threadRef}>
        {pesan.length > 0 ? pesan.map((m, i) => {
          const bisaIsi = !!onIsiLk && !m.keluar && bacaBalasan(m.teks).length > 0;
          return (
            <div key={i} className={`${s.msg} ${m.keluar ? s.msgOut : ""}`}>
              <div className={s.bubble}>
                {m.kutipan && <div className={s.kutipan}>{m.kutipan}</div>}
                {formatWa(m.teks)}
              </div>
              <div className={s.msgMeta}>
                {m.waktu || (m.keluar ? "Anda" : lawan)}
                {m.keluar && m.status ? `, ${CENTANG[m.status] ?? m.status}` : ""}
                {bisaIsi && (
                  <button type="button" className={s.msgAksiUtama}
                    onClick={() => setTerisi({ ...terisi, [i]: onIsiLk!(m.teks) })}>
                    {terisi[i] ? `${terisi[i]} sekolah terisi ✓` : "Isi LK dari pesan ini"}
                  </button>
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
            <button key={t.kode} type="button" title={t.ket} onClick={() => setTeks(t.teks)}>{t.judul}</button>
          ))}
        </div>
        <textarea rows={teks.length > 160 ? 8 : 3} maxLength={6000} placeholder={`Tulis pesan untuk ${lawan.toLowerCase()}…`}
          value={teks} onChange={(e) => setTeks(e.target.value)} aria-label="Pesan"
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

/** Tanpa WhatsApp otomatis: pilih template, salin, kirim dari HP sendiri. */
export function SalinTemplate({ template, ket }: { template: Template[]; ket: string }) {
  const [pilih, setPilih] = useState(template[0]?.kode ?? "");
  const [teks, setTeks] = useState(template[0]?.teks ?? "");
  const [disalin, setDisalin] = useState(false);
  return (
    <section className={s.chat} aria-label="Template pesan">
      <p className={s.kolomKet}>{ket}</p>
      <div className={s.tplList}>
        {template.map((x) => (
          <button key={x.kode} type="button" aria-pressed={x.kode === pilih} title={x.ket}
            onClick={() => { setPilih(x.kode); setTeks(x.teks); setDisalin(false); }}>
            {x.judul}
          </button>
        ))}
      </div>
      <textarea className={s.pratinjau} rows={14} value={teks} onChange={(e) => { setTeks(e.target.value); setDisalin(false); }}
        aria-label="Isi pesan" />
      <Button size="sm" onClick={() => { void navigator.clipboard.writeText(teks).then(() => setDisalin(true)); }}>
        {disalin ? "Tersalin ✓" : "Salin pesan"}
      </Button>
    </section>
  );
}
