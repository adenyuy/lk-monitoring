"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { EskalasiInfo, Masalah } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import { pesan } from "@/components/forum/bersama";
import { FormMasalah } from "./FormMasalah";
import { Dialog, Jawaban, nadaWaktu, namaTahap, PasangLink, Rincian, Tahap, tahapKe, terlambat, tgl, TindakLanjut } from "./bagian";
import h from "./halaman.module.css";

type Saring = "aktif" | "perlu" | "menunggu" | "dijawab" | "selesai" | "lewat" | "tanpa_tema";

const PIPA: { k: Saring; nama: string; ket: string }[] = [
  { k: "perlu", nama: "Perlu dieskalasi", ket: "Belum diteruskan ke tim" },
  { k: "menunggu", nama: "Menunggu jawaban", ket: "Sudah di tim tujuan" },
  { k: "dijawab", nama: "Sudah dijawab", ket: "Tinggal ditutup" },
  { k: "selesai", nama: "Selesai", ket: "Status tindak lanjut Selesai" },
];
const PER_HALAMAN = 40;

const lolos: Record<Saring, (m: Masalah) => boolean> = {
  aktif: (m) => m.status !== "Selesai",
  perlu: (m) => tahapKe(m) === 0,
  menunggu: (m) => tahapKe(m) === 1,
  dijawab: (m) => tahapKe(m) === 2,
  selesai: (m) => tahapKe(m) === 3,
  lewat: terlambat,
  tanpa_tema: (m) => m.status !== "Selesai" && m.agregasi === "Ya" && !m.kode_tema,
};

export function IkonCari({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
    </svg>
  );
}

const judulKasus = (m: Masalah) => (m.npsn ? m.nama || `NPSN ${m.npsn}` : m.topik || m.sumber || "Tanpa sekolah");

function Kasus({ m, aktif, onBuka }: { m: Masalah; aktif: boolean; onBuka: () => void }) {
  const nada = nadaWaktu(m);
  return (
    <button type="button" className={`${h.kasus} ${h[`rail_${nada}`] ?? ""}`} aria-current={aktif} onClick={onBuka}>
      <span className={h.kasusUtama}>
        <span className={h.kasusAtas}>
          <span className={h.idKasus}>{m.id || `baris ${m.baris}`}</span>
          <span className={h.namaKasus}>{judulKasus(m)}</span>
          {m.tingkat.startsWith("Tingkat 3") && <span className={`${h.lencana} ${h.lencanaPrioritas}`}>Prioritas</span>}
          {m.kode_tema && <span className={`${h.lencana} ${h.lencanaTema}`} title={m.tema}>{m.kode_tema}</span>}
        </span>
        <span className={h.ketKasus}>{m.keterangan.replace(/^PRIORITAS TINGGI:\s*/i, "")}</span>
        <span className={h.metaKasus}>
          {m.permasalahan && <span><b>{m.permasalahan}</b></span>}
          <span>{m.agregasi === "Tidak" ? "Tanpa agregasi" : m.tim.length ? `Ke ${m.tim.join(", ")}` : "Tim belum dipilih"}</span>
          {m.petugas && <span>Petugas {m.petugas}</span>}
        </span>
      </span>
      <span className={h.kasusTahap}>
        <Tahap m={m} />
        <small>{namaTahap(m)}</small>
      </span>
      <span className={`${h.kasusWaktu} ${nada === "lewat" ? h.waktuLewat : nada === "dekat" ? h.waktuDekat : nada === "selesai" ? h.waktuSelesai : ""}`}>
        <b>{m.status === "Selesai" ? (m.tgl_selesai ? `Selesai ${tgl(m.tgl_selesai)}` : "Selesai") : m.status_waktu || "Tanpa tenggat"}</b>
        <span>Dicatat {m.tgl_awal ? tgl(m.tgl_awal) : "–"}</span>
      </span>
    </button>
  );
}

/** Halaman PIC Eskalasi: pantau seluruh LK Eskalasi per tahap, isi Kode Tema / Status Eskalasi / jawaban. */
export function EskalasiView() {
  const [info, setInfo] = useState<EskalasiInfo | null>(null);
  const [galat, setGalat] = useState("");
  const [segar, setSegar] = useState(false);
  const [saring, setSaring] = useState<Saring>("aktif");
  const [pic, setPic] = useState<string | null>(null);
  const [tim, setTim] = useState("");
  const [kelompok, setKelompok] = useState("");
  const [cari, setCari] = useState("");
  const [hal, setHal] = useState(0);
  const [pilih, setPilih] = useState<number | null>(null);
  const [lapor, setLapor] = useState(false);

  const muat = useCallback(async (paksa = false) => {
    setSegar(paksa);
    try {
      const d = await api<EskalasiInfo>(`/api/eskalasi?semua=true${paksa ? "&paksa=true" : ""}`);
      setInfo(d);
      setGalat("");
      // Saringan PIC bawaan: nama saya bila saya PIC salah satu tim
      setPic((p) => p ?? (Object.values(d.opsi?.pic ?? {}).find((x) => x.toLowerCase() === (d.saya.nama ?? "").toLowerCase()) ?? ""));
    } catch (e) {
      setGalat(e instanceof ApiError ? e.message : pesan(e));
    } finally {
      setSegar(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);

  const opsi = info?.opsi;
  const daftarPic = useMemo(() => [...new Set(Object.values(opsi?.pic ?? {}))].sort(), [opsi]);
  const timPic = useMemo(() => new Set(Object.entries(opsi?.pic ?? {}).filter(([, p]) => p === pic).map(([t]) => t)), [opsi, pic]);

  const q = cari.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const dasar = (info?.masalah ?? []).filter((m) =>
    (!pic || m.tim.some((t) => timPic.has(t)))
    && (!tim || m.tim.includes(tim))
    && (!kelompok || m.permasalahan === kelompok)
    && q.every((k) => [m.id, m.npsn, m.nama, m.topik, m.fasil, m.petugas, m.ptn, m.keterangan, m.jawaban, m.kode_tema]
      .join(" ").toLowerCase().includes(k)));
  const tampil = dasar.filter(lolos[saring]).sort((a, b) =>
    Number(terlambat(b)) - Number(terlambat(a)) || b.tgl_awal.localeCompare(a.tgl_awal) || b.baris - a.baris);
  const halaman = Math.max(1, Math.ceil(tampil.length / PER_HALAMAN));
  const potong = tampil.slice(hal * PER_HALAMAN, (hal + 1) * PER_HALAMAN);
  const dipilih = info?.masalah.find((m) => m.baris === pilih) ?? null;
  const adaSaring = !!(pic || tim || kelompok || cari);

  const ganti = (baru: Masalah) => setInfo((d) => d && { ...d, masalah: d.masalah.map((m) => (m.baris === baru.baris ? baru : m)) });
  const pakai = (k: Saring) => { setSaring(saring === k ? "aktif" : k); setHal(0); };

  if (info && !info.saya.pic) {
    return (
      <div className={h.page}>
        <Notice tone="warn" title="Halaman ini untuk PIC Eskalasi">
          Minta admin menambahkan fitur &quot;eskalasi&quot; ke akunmu di sheet Akses. Masalah dan jawabannya tetap bisa dilihat di menu FAQ.
        </Notice>
      </div>
    );
  }

  const judulDaftar = saring === "aktif" ? "Kasus belum selesai"
    : saring === "lewat" ? "Lewat batas waktu" : saring === "tanpa_tema" ? "Agregasi tanpa kode tema"
      : PIPA.find((x) => x.k === saring)?.nama ?? "";

  return (
    <div className={h.page}>
      <header className={h.kepala}>
        <div>
          <h1>Eskalasi</h1>
          <p>Teruskan kasus ke tim tujuan, kelompokkan dengan kode tema, lalu tutup begitu jawabannya masuk.
            Kasus yang belum selesai dieskalasikan ulang tiap 3 hari.</p>
        </div>
        <div className={h.aksiKepala}>
          <Button variant="ghost" onClick={() => void muat(true)} loading={segar} disabled={!info}>Muat ulang</Button>
          <Button onClick={() => setLapor(true)} disabled={!opsi}>Laporkan masalah</Button>
        </div>
      </header>

      {info?.perlu_link && <PasangLink onSelesai={() => void muat(true)} />}
      {galat && <Notice tone="bad" title="LK Eskalasi tidak bisa dibuka">{galat}</Notice>}
      {!info && !galat && <p className={h.memuat}><Spinner /> Membaca LK Eskalasi…</p>}

      {opsi && (
        <>
          <nav className={h.pipa} aria-label="Tahap kasus">
            {PIPA.map((x) => (
              <button key={x.k} type="button" aria-pressed={saring === x.k} onClick={() => pakai(x.k)}>
                <span className={h.pipaAngka}>{dasar.filter(lolos[x.k]).length}</span>
                <span className={h.pipaNama}>{x.nama}</span>
                <span className={h.pipaKet}>{x.ket}</span>
              </button>
            ))}
          </nav>

          <div className={h.peringatan}>
            <button type="button" className={h.pLewat} aria-pressed={saring === "lewat"} onClick={() => pakai("lewat")}>
              <b>{dasar.filter(lolos.lewat).length}</b> lewat batas waktu
            </button>
            <button type="button" aria-pressed={saring === "tanpa_tema"} onClick={() => pakai("tanpa_tema")}>
              <b>{dasar.filter(lolos.tanpa_tema).length}</b> perlu kode tema
            </button>
          </div>

          <div className={h.toolbar}>
            <label className={h.cari}>
              <IkonCari />
              <input type="search" value={cari} onChange={(e) => { setCari(e.target.value); setHal(0); }}
                placeholder="Cari ID, NPSN, sekolah, petugas, atau isi" aria-label="Cari kasus" />
            </label>
            <select className={h.pilih} value={pic ?? ""} onChange={(e) => { setPic(e.target.value); setHal(0); }} aria-label="PIC eskalasi">
              <option value="">Semua PIC</option>
              {daftarPic.map((p) => <option key={p} value={p}>PIC {p}</option>)}
            </select>
            <select className={h.pilih} value={tim} onChange={(e) => { setTim(e.target.value); setHal(0); }} aria-label="Tim tujuan">
              <option value="">Semua tim</option>
              {opsi.tim.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select className={h.pilih} value={kelompok} onChange={(e) => { setKelompok(e.target.value); setHal(0); }} aria-label="Permasalahan">
              <option value="">Semua permasalahan</option>
              {opsi.permasalahan.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            {adaSaring && (
              <button type="button" className={h.hapusSaring} onClick={() => { setPic(""); setTim(""); setKelompok(""); setCari(""); setHal(0); }}>
                Hapus saringan
              </button>
            )}
          </div>

          <div className={h.bawahDaftar}>
            <span><b style={{ color: "var(--ink)" }}>{judulDaftar}</b>&nbsp; {tampil.length} kasus{pic ? ` untuk PIC ${pic}` : ""}</span>
            {saring !== "aktif" && <button type="button" className={h.hapusSaring} onClick={() => pakai(saring)}>Tampilkan semua yang belum selesai</button>}
          </div>

          {tampil.length === 0 ? (
            <div className={h.kosong}><b>Tidak ada kasus di sini</b>Coba tahap lain atau hapus saringan.</div>
          ) : (
            <>
              <ul className={h.daftarKasus}>
                {potong.map((m) => (
                  <li key={m.baris}><Kasus m={m} aktif={pilih === m.baris} onBuka={() => setPilih(m.baris)} /></li>
                ))}
              </ul>
              {halaman > 1 && (
                <div className={h.bawahDaftar}>
                  <span>Halaman {hal + 1} dari {halaman}</span>
                  <span style={{ display: "flex", gap: 8 }}>
                    <Button size="sm" variant="secondary" disabled={hal === 0} onClick={() => setHal(hal - 1)}>Sebelumnya</Button>
                    <Button size="sm" variant="secondary" disabled={hal >= halaman - 1} onClick={() => setHal(hal + 1)}>Berikutnya</Button>
                  </span>
                </div>
              )}
            </>
          )}
        </>
      )}

      {dipilih && opsi && info && (
        <Dialog laci judul={`${dipilih.id} ${judulKasus(dipilih)}`} onClose={() => setPilih(null)}
          sub={[dipilih.permasalahan, dipilih.status !== "Selesai" ? dipilih.status_waktu : ""].filter(Boolean).join(", ")}>
          <div className={h.laciTahap}><Tahap m={dipilih} lengkap /></div>
          <Jawaban m={dipilih} />
          <TindakLanjut key={`${dipilih.baris}-${dipilih.jawaban}-${dipilih.status}-${dipilih.kode_tema}-${dipilih.status_eskalasi}`}
            m={dipilih} opsi={opsi} saya={info.saya.nama ?? ""} pic={!!info.saya.pic} onTersimpan={ganti} />
          <Rincian m={dipilih} opsi={opsi} />
        </Dialog>
      )}

      {lapor && opsi && info && (
        <Dialog lebar judul="Laporkan masalah" onClose={() => setLapor(false)}
          sub="Tiga langkah, dicatat ke LK Eskalasi dengan ID Masalah baru.">
          <FormMasalah opsi={opsi} saya={info.saya.nama ?? ""} masalah={info.masalah} onSelesai={() => void muat(true)} />
        </Dialog>
      )}
    </div>
  );
}
