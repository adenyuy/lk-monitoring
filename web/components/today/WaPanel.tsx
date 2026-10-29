"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "@/lib/api";
import type { Fasil, Percakapan, SekolahLk } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import { JawabPicker } from "./JawabPicker";
import s from "./today.module.css";

/** Tampilkan *teks* gaya WhatsApp sebagai huruf tebal. */
function formatWa(teks: string) {
  return teks.split(/(\*[^*\n]+\*)/g).map((bagian, i) =>
    bagian.length > 2 && bagian.startsWith("*") && bagian.endsWith("*")
      ? <b key={i}>{bagian.slice(1, -1)}</b>
      : bagian,
  );
}

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function salam() {
  const h = new Date().getHours();
  return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 18 ? "Selamat sore" : "Selamat malam";
}

const persen = (x: SekolahLk) => (x.progres === null ? "" : ` (${x.progres.toFixed(1).replace(".", ",")}%)`);

type Template = { kode: string; label: string; teks: string; tanya: boolean };

/** Template pesan untuk menanyakan isian LK, hanya yang relevan dengan sekolah fasil ini.
 *  Daftar sekolah diberi tempat jawaban per nomor supaya balasan fasil mudah direkap per sekolah. */
function templates(nama: string, sekolah: SekolahLk[]): Template[] {
  const aktif = sekolah.filter((x) => x.prioritas.trim().toLowerCase() !== "selesai");
  const pembuka = `${salam()} Bapak/Ibu ${nama}, izin menindaklanjuti informasi sebelumnya.`;
  const minta = "Mohon dibantu dijawab *per sekolah* sesuai nomor di atas (cukup ganti titik-titiknya), supaya kendalanya mudah kami rekap.";
  const tutup = "Terima kasih 🙏";
  const isian = (xs: SekolahLk[], label: string, pakaiPersen = false) =>
    xs.map((x, i) => `${i + 1}. ${x.nama}${pakaiPersen ? persen(x) : ""}\n   ${label}: ...`).join("\n");
  const progres = aktif.filter((x) => x.progres === null || x.progres < 50);
  const submit = aktif.filter((x) => x.submit !== "Ya");
  const reviu = aktif.filter((x) => x.submit === "Ya" && x.reviu !== "Ya");
  // Semua sekaligus: tiap sekolah ditanya sesuai tahapannya (sama dengan alasan yang wajib di LK).
  // Alasan yang sudah pasti (belum submit karena < 50%, belum reviu karena belum submit) tidak ditanyakan lagi.
  const pertanyaan = (x: SekolahLk) => {
    const q: string[] = [];
    if (x.progres === null || x.progres < 50) q.push("Kendala progres fisik & rencana tindak lanjut");
    else if (x.submit !== "Ya") q.push("Kendala submit laporan 50% & rencana unggah");
    if (x.submit === "Ya" && x.reviu !== "Ya") q.push("Kendala reviu & perkiraan selesai");
    return q;
  };
  const status = (x: SekolahLk) => {
    const p = x.progres === null ? "progres belum ada" : `${x.progres.toFixed(1).replace(".", ",")}%`;
    const tahap = x.submit !== "Ya" ? "belum submit" : x.reviu !== "Ya" ? "belum direviu" : "sudah direviu";
    return ` (${p}, ${tahap})`;
  };
  const semua = aktif.filter((x) => pertanyaan(x).length);
  const bimtek = aktif.filter((x) => x.bimtek);
  const tgl = (iso: string) => {
    const d = iso ? new Date(`${iso}T00:00:00`) : null;
    return d ? ` (disubmit ${d.getDate()} ${BULAN[d.getMonth()]})` : "";
  };
  const out: Template[] = [];
  if (bimtek.length) out.push({ kode: "bimtek", label: `Bimtek: belum direviu (${bimtek.length})`, tanya: true,
    teks: `${pembuka} Laporan kemajuan 50% sekolah binaan Bapak/Ibu berikut (peserta bimtek percepatan pelaporan) sudah disubmit, tetapi sampai saat ini belum direviu:

${bimtek.map((x, i) => `${i + 1}. ${x.nama}${tgl(x.bimtek?.submit ?? "")}\n   Kendala reviu & perkiraan selesai: ...`).join("\n")}

Mohon dibantu segera direviu. ${minta} ${tutup}` });
  if (semua.length) out.push({ kode: "semua", label: `Tanya semua sekaligus (${semua.length})`, tanya: true,
    teks: `${pembuka} Berikut sekolah dampingan Bapak/Ibu yang laporan kemajuan 50%-nya belum tuntas:

${semua.map((x, i) => `${i + 1}. ${x.nama}${status(x)}\n${pertanyaan(x).map((q) => `   ${q}: ...`).join("\n")}`).join("\n")}

${minta} ${tutup}` });
  if (submit.length) out.push({ kode: "submit", label: `Tanya belum submit (${submit.length})`, tanya: true,
    teks: `${pembuka} Laporan kemajuan pekerjaan 50% sekolah berikut belum disubmit di aplikasi:

${isian(submit, "Kendala & rencana unggah", true)}

${minta} ${tutup}` });
  if (progres.length) out.push({ kode: "progres", label: `Tanya progres < 50% (${progres.length})`, tanya: true,
    teks: `${pembuka} Progres fisik sekolah berikut masih di bawah 50%:

${isian(progres, "Kendala di lapangan & rencana tindak lanjut", true)}

${minta} ${tutup}` });
  if (reviu.length) out.push({ kode: "reviu", label: `Tanya belum reviu (${reviu.length})`, tanya: true,
    teks: `${pembuka} Laporan kemajuan 50% sekolah berikut sudah diajukan, tetapi belum direviu:

${isian(reviu, "Kendala reviu & perkiraan selesai")}

${minta} ${tutup}` });
  // Pengingat sesuai sekolah yang dipegang: percepatan (progres < 50%), submit laporan 50%, reviu
  const ingat: string[] = [];
  if (progres.length) ingat.push(`mempercepat pekerjaan ${progres.length} sekolah yang progresnya masih di bawah 50%`);
  const submit50 = submit.filter((x) => x.progres !== null && x.progres >= 50);
  if (submit50.length) ingat.push(`segera submit laporan 50% untuk ${submit50.length} sekolah yang progresnya sudah 50%`);
  if (reviu.length) ingat.push(`segera mereviu laporan 50% ${reviu.length} sekolah yang sudah disubmit`);
  const pesanIngat = ingat.length
    ? `\n\nMohon Bapak/Ibu selalu mengingatkan dan mendampingi sekolah binaan untuk ${ingat.length > 1 ? `${ingat.slice(0, -1).join(", ")}, serta ${ingat[ingat.length - 1]}` : ingat[0]}.`
    : "";
  out.push({ kode: "makasih", label: "Terima kasih", tanya: false,
    teks: `Terima kasih atas informasinya, Bapak/Ibu ${nama}. Sudah kami catat.${pesanIngat} ${"🙏"}` });
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
  const [jawabBuka, setJawabBuka] = useState(false);
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
        {jawabBuka && (
          <JawabPicker nama={data.nama_fasil} onClose={() => setJawabBuka(false)}
            onPilih={(isi) => { setTeks(isi); setJenis(""); setJawabBuka(false); }} />
        )}
        <div className={s.templates} aria-label="Template pesan">
          <button type="button" className={`${s.tpl} ${s.tplJawab}`} aria-expanded={jawabBuka}
            onClick={() => setJawabBuka(!jawabBuka)}>
            Jawab pertanyaan…
          </button>
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
