"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Fasil, Percakapan, SekolahLk } from "@/lib/types";
import { grupRelevan } from "./LkPanel";
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

function salam() {
  const h = new Date().getHours();
  return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 18 ? "Selamat sore" : "Selamat malam";
}

const persen = (x: SekolahLk) => (x.progres === null ? "" : ` (${x.progres.toFixed(1).replace(".", ",")}%)`);
const daftar = (xs: SekolahLk[], pakaiPersen = false) =>
  xs.map((x, i) => `${i + 1}. ${x.nama}${pakaiPersen ? persen(x) : ""}`).join("\n");

type Template = { kode: string; label: string; teks: string; tanya: boolean };

/** Template pesan untuk menanyakan isian LK, hanya yang relevan dengan sekolah fasil ini. */
function templates(nama: string, sekolah: SekolahLk[]): Template[] {
  const aktif = sekolah.filter((x) => x.prioritas.trim().toLowerCase() !== "selesai");
  const pembuka = `${salam()} Bapak/Ibu ${nama}, izin menindaklanjuti informasi sebelumnya.`;
  const tutup = "Terima kasih 🙏";
  const progres = aktif.filter((x) => grupRelevan(x).includes("a"));
  const submit = aktif.filter((x) => x.submit !== "Ya");
  const reviu = aktif.filter((x) => grupRelevan(x).includes("c"));
  const out: Template[] = [];
  if (submit.length) out.push({ kode: "submit", label: `Tanya belum submit (${submit.length})`, tanya: true,
    teks: `${pembuka} Untuk sekolah berikut, laporan kemajuan pekerjaan 50% belum disubmit di aplikasi:

${daftar(submit)}

Boleh dibantu informasikan kendalanya apa, dan kapan rencana laporannya diunggah? ${tutup}` });
  if (progres.length) out.push({ kode: "progres", label: `Tanya progres < 50% (${progres.length})`, tanya: true,
    teks: `${pembuka} Untuk sekolah berikut, progres fisiknya masih di bawah 50%:

${daftar(progres, true)}

Boleh dibantu informasikan kendala di lapangan dan rencana tindak lanjutnya? ${tutup}` });
  if (reviu.length) out.push({ kode: "reviu", label: `Tanya belum reviu (${reviu.length})`, tanya: true,
    teks: `${pembuka} Laporan kemajuan 50% sekolah berikut sudah diajukan, tetapi belum direviu:

${daftar(reviu)}

Mohon bantuannya untuk mereviu, atau informasikan bila ada kendala. ${tutup}` });
  out.push({ kode: "makasih", label: "Terima kasih", tanya: false,
    teks: `Terima kasih atas informasinya, Bapak/Ibu ${nama}. Sudah kami catat ${"🙏"}` });
  return out;
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
  const [jenis, setJenis] = useState("");
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
      setChat(await post<Percakapan>(`/api/chat/${nomor}/balas`, { pesan: isi, jenis }));
      setTeks("");
      setJenis("");
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
              <div className={s.bubble}>
                {m.kutipan && <div className={s.kutipan}>{m.kutipan}</div>}
                {formatWa(m.teks)}
              </div>
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
        <div className={s.templates} aria-label="Template pesan">
          {templates(data.nama_fasil, data.sekolah).map((t) => (
            <button key={t.kode} type="button" className={s.tpl}
              onClick={() => { setTeks(t.teks); setJenis(t.tanya ? "tanya_lk" : ""); }}>
              {t.label}
            </button>
          ))}
        </div>
        <textarea rows={teks.length > 120 ? 6 : 2} maxLength={2000} placeholder="Tulis balasan untuk fasil…" value={teks}
          onChange={(e) => { setTeks(e.target.value); if (!e.target.value) setJenis(""); }} aria-label="Balasan"
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
