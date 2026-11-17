"use client";

/** Bagian bersama LK Eskalasi: format, chip status, dialog, pasang link, form tindak lanjut, rincian masalah. */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { post } from "@/lib/api";
import type { Masalah, OpsiEskalasi } from "@/lib/types";
import { Button, Chip, Notice } from "@/components/ui";
import { Galeri, pesan, Teks } from "@/components/forum/bersama";
import s from "./esk.module.css";
import h from "./halaman.module.css";

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** "2026-11-04" -> "4 Nov 2026" */
export const tgl = (iso: string) =>
  (/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${Number(iso.slice(8))} ${BULAN[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : iso);

export const hariIni = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function toneStatus(st: string) {
  const x = st.toLowerCase();
  if (x === "selesai") return "ok" as const;
  if (x === "proses") return "info" as const;
  if (x === "ditunda" || x === "perlu data tambahan") return "warn" as const;
  return "muted" as const;
}

export const terlambat = (m: Masalah) => m.status !== "Selesai" && /^(Terlambat|Melewati)/.test(m.status_waktu);
/** Tema agregasi yang sungguhan (bukan "(Tidak diagregasi)" dsb.). */
export const temaAsli = (m: Masalah) => (m.tema && !m.tema.startsWith("(") && m.tema !== "Kode tema tidak ditemukan" ? m.tema : "");
export const asalMasalah = (m: Masalah) => (m.npsn ? `${m.nama || "Sekolah"} · NPSN ${m.npsn}` : m.topik || m.sumber || "Tanpa sekolah");

export function StatusChip({ m }: { m: Masalah }) {
  return <Chip tone={toneStatus(m.status)}>{m.status || "Belum ada status"}</Chip>;
}

export function WaktuChip({ m }: { m: Masalah }) {
  if (!m.status_waktu || m.status === "Selesai") return null;
  return <Chip tone={terlambat(m) ? "bad" : "muted"}>{m.status_waktu}</Chip>;
}

export function Dialog({ judul, sub, onClose, children, laci, lebar }: {
  judul: string; sub?: ReactNode; onClose: () => void; children: ReactNode; laci?: boolean;
  /** Dialog lebar tanpa padding isi: form 3 langkah mengatur gulirnya sendiri */
  lebar?: boolean;
}) {
  const tutupRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    tutupRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopImmediatePropagation(); onClose(); }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);
  const isi = (
    <>
      <header className={s.dialogHead}>
        <div>
          <h2 id="esk-dialog-judul">{judul}</h2>
          {sub && <p>{sub}</p>}
        </div>
        <button ref={tutupRef} type="button" className={s.tutup} onClick={onClose} aria-label="Tutup">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      </header>
      <div className={lebar ? s.dialogBodyLebar : s.dialogBody}>{children}</div>
    </>
  );
  if (laci) {
    return (
      <>
        <div className={s.laciScrim} onClick={onClose} />
        <aside className={s.laci} role="dialog" aria-modal="true" aria-labelledby="esk-dialog-judul">{isi}</aside>
      </>
    );
  }
  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`${s.dialog} ${lebar ? s.dialogLebar : ""}`} role="dialog" aria-modal="true" aria-labelledby="esk-dialog-judul">{isi}</div>
    </div>
  );
}

/** Link LK Eskalasi belum dipasang. Admin: berlaku untuk seluruh tim (disimpan di sheet Akses). */
export function PasangLink({ onSelesai }: { onSelesai: () => void }) {
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pasang = async () => {
    setBusy(true);
    setError(null);
    try {
      await post("/api/eskalasi/link", { link });
      onSelesai();
    } catch (e) {
      setError(pesan(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={s.form}>
      <Notice tone="warn" title="Link LK Eskalasi belum dipasang">
        Tempel link sheet LK Eskalasi di bawah. Bila akun Anda admin, link ini langsung berlaku untuk seluruh tim.
      </Notice>
      <label className={s.field}>
        <span className={s.label}>Link sheet LK Eskalasi</span>
        <input type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/…" />
      </label>
      {error && <Notice tone="bad" title="Belum bisa dipasang">{error}</Notice>}
      <div className={s.aksi}>
        <Button loading={busy} disabled={busy || link.trim().length < 10} onClick={pasang}>Pasang link</Button>
      </div>
    </div>
  );
}

/** Bukti: foto Drive (galeri) + tautan lain. */
export function Bukti({ m }: { m: Masalah }) {
  if (!m.foto.length && !m.tautan.length) return null;
  return (
    <div className={s.field}>
      <span className={s.label}>Evidence</span>
      <Galeri foto={m.foto} />
      {m.tautan.length > 0 && (
        <div className={s.tautanBukti}>
          {m.tautan.map((t) => <a key={t} href={t} target="_blank" rel="noreferrer">{t}</a>)}
        </div>
      )}
    </div>
  );
}

/** Rincian lengkap satu masalah (tanpa form). */
export function Rincian({ m, opsi }: { m: Masalah; opsi: OpsiEskalasi }) {
  const pic = [...new Set(m.tim.map((t) => opsi.pic[t]).filter(Boolean))];
  const item: [string, ReactNode][] = [
    ["Sumber masalah", m.sumber || "–"],
    ["Sekolah", m.npsn ? <>{m.nama}<br /><small>NPSN {m.npsn}</small></> : "–"],
    ...(m.topik ? [["Nama sumber / topik", m.topik] as [string, ReactNode]] : []),
    ["Fasilitator", m.fasil || "–"],
    ["Petugas monitoring", m.petugas || "–"],
    ["PTN", m.ptn || "–"],
    ["Permasalahan", m.permasalahan || "–"],
    ["Tingkat", m.tingkat || "–"],
    ["Tanggal awal", m.tgl_awal ? tgl(m.tgl_awal) : "–"],
    ["Batas waktu", m.batas ? tgl(m.batas) : "–"],
    ["Perlu agregasi", m.agregasi || "–"],
    ["Tim tujuan", m.tim.join(", ") || "–"],
    ["PIC eskalasi", pic.join(", ") || "–"],
    ["Kode tema", m.kode_tema ? `${m.kode_tema}${temaAsli(m) ? ` · ${temaAsli(m)}` : ""}` : m.saran_tema && m.saran_tema !== "Belum ada tema yang cocok" ? `Saran: ${m.saran_tema}` : "–"],
    ["Status eskalasi", m.status_eskalasi || "–"],
    ...(m.aktif && m.aktif > 1 ? [["Masalah aktif di sekolah ini", String(m.aktif)] as [string, ReactNode]] : []),
  ];
  return (
    <div className={s.rinci}>
      <div className={s.field}>
        <span className={s.label}>Keterangan permasalahan</span>
        <Teks isi={m.keterangan} />
      </div>
      <Bukti m={m} />
      <dl className={s.rinciGrid}>
        {item.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    </div>
  );
}

/** Blok jawaban (hijau) atau keterangan belum dijawab. */
export function Jawaban({ m }: { m: Masalah }) {
  if (!m.jawaban) return <p className={s.belumJawab}>Belum ada jawaban tim terkait.</p>;
  return (
    <div className={s.jawab}>
      <small>Jawaban{m.pengisi ? ` · ${m.pengisi}` : ""}{m.tgl_selesai ? ` · selesai ${tgl(m.tgl_selesai)}` : ""}</small>
      <Teks isi={m.jawaban} />
    </div>
  );
}

/** Isi Jawaban / Status / Pengisi; PIC Eskalasi juga Kode Tema dan Status Eskalasi. */
export function TindakLanjut({ m, opsi, saya, pic, onTersimpan, onBatal }: {
  m: Masalah; opsi: OpsiEskalasi; saya: string; pic: boolean; onTersimpan: (m: Masalah) => void; onBatal?: () => void;
}) {
  const [jawaban, setJawaban] = useState(m.jawaban);
  const [status, setStatus] = useState(m.status || opsi.status[0] || "");
  const [pengisi, setPengisi] = useState(m.pengisi || saya);
  const [selesai, setSelesai] = useState(m.tgl_selesai || hariIni());
  const [kode, setKode] = useState(m.kode_tema);
  const [eskal, setEskal] = useState(m.status_eskalasi || opsi.status_eskalasi[1] || "");
  const [busy, setBusy] = useState(false);
  const [galat, setGalat] = useState("");
  const [ok, setOk] = useState(false);

  const ubah: Record<string, string> = {};
  if (m.boleh_ubah) {
    if (jawaban.trim() !== m.jawaban) ubah.jawaban = jawaban.trim();
    if (status !== m.status) ubah.status = status;
    if (jawaban.trim() && pengisi.trim() !== m.pengisi) ubah.pengisi = pengisi.trim();
    if (status === "Selesai" && selesai !== m.tgl_selesai) ubah.tgl_selesai = selesai;
  }
  if (pic) {
    if (kode !== m.kode_tema) ubah.kode_tema = kode;
    if (eskal !== m.status_eskalasi) ubah.status_eskalasi = eskal;
  }
  const ada = Object.keys(ubah).length > 0;
  const saran = m.saran_tema && /^T\d+$/.test(m.saran_tema) ? m.saran_tema : "";

  const simpan = async () => {
    setBusy(true);
    setGalat("");
    setOk(false);
    try {
      const r = await post<{ masalah: Masalah }>(`/api/eskalasi/${encodeURIComponent(m.id || "-")}/ubah`,
        { ...ubah, baris: m.baris, sidik: m.sidik });
      setOk(true);
      onTersimpan(r.masalah);
    } catch (e) {
      setGalat(pesan(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={s.form}>
      {m.boleh_ubah && (
        <>
          <label className={s.field}>
            <span className={s.label}>Jawaban tim terkait <span>kosongkan bila belum ada</span></span>
            <textarea rows={4} value={jawaban} maxLength={2000} onChange={(e) => setJawaban(e.target.value)}
              placeholder="Tulis jawaban/keputusan dari tim tujuan." />
          </label>
          <div className={s.dua}>
            <label className={s.field}>
              <span className={s.label}>Status tindak lanjut</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {opsi.status.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className={s.field}>
              <span className={s.label}>Pengisi jawaban</span>
              <input type="text" value={pengisi} maxLength={100} onChange={(e) => setPengisi(e.target.value)} />
            </label>
            {status === "Selesai" && (
              <label className={s.field}>
                <span className={s.label}>Tanggal selesai</span>
                <input type="date" value={selesai} max={hariIni()} onChange={(e) => setSelesai(e.target.value)} />
              </label>
            )}
          </div>
        </>
      )}
      {pic && (
        <div className={s.pic}>
          <h4>Diisi PIC Eskalasi</h4>
          <div className={s.dua} style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)" }}>
            <label className={s.field}>
              <span className={s.label}>Kode tema {saran && saran !== kode && (
                <button type="button" className={s.tautan} onClick={() => setKode(saran)}>pakai saran {saran}</button>
              )}</span>
              <select value={kode} onChange={(e) => setKode(e.target.value)}>
                <option value="">Belum dikelompokkan</option>
                {opsi.tema.map((t) => (
                  <option key={t.kode} value={t.kode}>{t.kode} · {t.tema.length > 90 ? `${t.tema.slice(0, 90)}…` : t.tema}</option>
                ))}
              </select>
            </label>
            <label className={s.field}>
              <span className={s.label}>Status eskalasi</span>
              <select value={eskal} onChange={(e) => setEskal(e.target.value)}>
                {opsi.status_eskalasi.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          </div>
        </div>
      )}
      {galat && <Notice tone="bad" title="Belum tersimpan">{galat}</Notice>}
      <div className={s.aksi}>
        <Button loading={busy} disabled={!ada || busy} onClick={() => void simpan()}>Simpan ke LK Eskalasi</Button>
        {onBatal && <Button variant="ghost" onClick={onBatal} disabled={busy}>Tutup</Button>}
        {ok && !ada && <span className={s.bantu}>Tersimpan.</span>}
        {!ok && !ada && <span className={s.bantu}>Belum ada yang diubah.</span>}
      </div>
    </div>
  );
}

// ---------- tahap kasus: Dicatat -> Dieskalasi -> Dijawab -> Selesai ----------

export const TAHAP = ["Dicatat", "Dieskalasi", "Dijawab", "Selesai"] as const;

/** Tahap tertinggi yang sudah dicapai (0..3). Kasus tanpa agregasi tidak perlu dieskalasi ke tim. */
export function tahapKe(m: Masalah): number {
  if (m.status === "Selesai") return 3;
  if (m.jawaban) return 2;
  if (m.status_eskalasi === "Sudah Dieskalasi" || m.agregasi === "Tidak") return 1;
  return 0;
}

/** Nama tahap untuk ditampilkan; tanpa agregasi tidak ada langkah eskalasi ke tim. */
export function namaTahap(m: Masalah): string {
  const ke = tahapKe(m);
  return m.agregasi === "Tidak" && ke === 1 ? "Menunggu jawaban" : TAHAP[ke];
}

/** Pelacak 4 titik. `lengkap` menampilkan nama tahap di bawahnya. */
export function Tahap({ m, lengkap }: { m: Masalah; lengkap?: boolean }) {
  const ke = tahapKe(m);
  const lewati = m.agregasi === "Tidak";
  return (
    <ol className={`${h.tahap} ${lengkap ? h.tahapLengkap : ""}`} aria-label={`Tahap: ${TAHAP[ke]}`}>
      {TAHAP.map((t, i) => (
        <li key={t} className={[i <= ke ? h.tahapOn : "", i === ke ? h.tahapKini : "", lewati && i === 1 ? h.tahapLewat : ""].join(" ")}
          title={lewati && i === 1 ? "Tanpa agregasi: tidak diteruskan ke tim" : t}>
          <span className={h.titik} aria-hidden="true" />
          {lengkap && <span className={h.tahapNama}>{lewati && i === 1 ? "Tanpa agregasi" : t}</span>}
        </li>
      ))}
    </ol>
  );
}

/** Nada garis kiri kartu/baris berdasarkan tenggat. */
export function nadaWaktu(m: Masalah): "lewat" | "dekat" | "selesai" | "biasa" {
  if (m.status === "Selesai") return "selesai";
  if (terlambat(m)) return "lewat";
  if (/^Sisa [01] hari/.test(m.status_waktu)) return "dekat";
  return "biasa";
}
