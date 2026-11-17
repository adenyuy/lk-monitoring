"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui";
import {
  KUADRAN, fmt, hrefKelompok, kuadranDari, labelBimtek, tgl, type Kelompok, type Kuadran, type Rekap,
} from "./BimtekView";
import { Tip } from "./Tip";
import b from "./bimtekRekap.module.css";

/** Satu sekolah peserta untuk daftar nasional. */
type Baris = {
  npsn: string; nama: string; kab: string; kode: string; hotel: string; pic: string; fasil: string; koor: string; ptn: string; angkatan: string;
  l50: string; rev50: string; tunggu50: number | null; kuadran: Kuadran;
};
type Tampilan = "sekolah" | "fasil" | "koor" | "ptn";
const TAMPILAN: { k: Tampilan; label: string }[] = [
  { k: "sekolah", label: "Sekolah" }, { k: "fasil", label: "Fasil" }, { k: "koor", label: "Koordinator" }, { k: "ptn", label: "PTN" },
];
const PER_HAL = 25;
const L50: Record<string, string> = { S: "Sudah kirim", B: "Belum kirim", P: "Sudah kirim" };
const BELUM_TEMPO = "Belum jatuh tempo";
const BERMASALAH: Record<Kuadran, string> = { sekolah: "Sekolah", fasil: "Fasil", aman: "" };
const REV: Record<string, string> = { setuju: "Disetujui", tolak: "Dikembalikan", menunggu: "Menunggu reviu" };

export function barisNasional(r: Rekap, kel: Kelompok[], batas: number): Baris[] {
  const kol = r.kolom_sekolah ?? [], i = (c: string) => kol.indexOf(c);
  const i50 = (r.komponen_urut ?? []).indexOf("l50");
  const ambil = (x: (string | number | null)[], c: string) => (i(c) >= 0 ? String(x[i(c)] ?? "") : "");
  return kel.flatMap((k) => (k.sekolah_baris ?? []).map((x) => {
    const fasil = ambil(x, "fasil"), kode50 = ambil(x, "akhir_kode")[i50];
    const t = i("tunggu50") >= 0 ? x[i("tunggu50")] : null;
    return {
      npsn: ambil(x, "npsn"), nama: ambil(x, "nama"), kab: ambil(x, "kab"), kode: k.kode, hotel: ambil(x, "hotel"),
      pic: ambil(x, "pic"), fasil, koor: ambil(x, "koor"), ptn: ambil(x, "ptn"), angkatan: ambil(x, "angkatan"), l50: kode50 ?? "", rev50: ambil(x, "rev50"),
      tunggu50: typeof t === "number" ? t : null,
      kuadran: kuadranDari(kode50, ambil(x, "rev50"), typeof t === "number" ? t : null, batas),
    };
  }));
}

type Grup = { nama: string; sub: string; sekolah: number; belum: number; menunggu: number; tunggu: number | null; telat: number;
  fasil: number };

/** Daftar sekolah peserta, atau rekap per fasil / koordinator / PTN. Mengikuti pilihan bimtek, batas hari, dan kuadran. */
export function DaftarNasional({ r, rows, kuadran, setKuadran, batas }: {
  r: Rekap; rows: Baris[]; kuadran: Kuadran | ""; setKuadran: (q: Kuadran | "") => void; batas: number;
}) {
  const [lihat, setLihat] = useState<Tampilan>("sekolah");
  const [cari, setCari] = useState("");
  const [hal, setHal] = useState(0);
  const q = cari.trim().toLowerCase();
  const tersaring = useMemo(() => rows.filter((s) => (!kuadran || s.kuadran === kuadran)
    && (!q || [s.nama, s.npsn, s.fasil, s.koor, s.ptn, s.pic, s.kab, s.hotel].some((v) => v.toLowerCase().includes(q)))), [rows, kuadran, q]);

  const grup = useMemo((): Grup[] => {
    if (lihat === "sekolah") return [];
    const kunci = (s: Baris) => (lihat === "fasil" ? s.fasil : lihat === "koor" ? s.koor : s.ptn) || "(kosong)";
    const m = new Map<string, Baris[]>();
    for (const s of tersaring) m.set(kunci(s), [...(m.get(kunci(s)) ?? []), s]);
    return [...m.entries()].map(([nama, xs]) => {
      const fasilSet = new Set(xs.map((s) => s.fasil).filter(Boolean));
      const tunggu = Math.max(-1, ...xs.map((s) => (s.rev50 === "menunggu" ? s.tunggu50 ?? -1 : -1)));
      return {
        nama, sekolah: xs.length, fasil: fasilSet.size,
        sub: lihat === "fasil" ? [xs[0].koor, xs[0].ptn].filter(Boolean).join(" · ") : lihat === "koor" ? xs[0].ptn : "",
        belum: xs.filter((s) => s.l50 === "B").length, menunggu: xs.filter((s) => s.rev50 === "menunggu").length,
        tunggu: tunggu < 0 ? null : tunggu, telat: xs.filter((s) => s.kuadran === "fasil").length,
      };
    }).sort((a, z) => z.belum - a.belum || z.telat - a.telat || (z.tunggu ?? -1) - (a.tunggu ?? -1) || a.nama.localeCompare(z.nama));
  }, [lihat, tersaring]);

  const sekolahUrut = useMemo(() => [...tersaring].sort((a, z) => {
    const urut: Record<Kuadran, number> = { fasil: 0, sekolah: 1, aman: 2 };
    return urut[a.kuadran] - urut[z.kuadran] || (z.tunggu50 ?? -1) - (a.tunggu50 ?? -1) || a.nama.localeCompare(z.nama);
  }), [tersaring]);
  const jumlah = lihat === "sekolah" ? sekolahUrut.length : grup.length;
  const halMaks = Math.max(0, Math.ceil(jumlah / PER_HAL) - 1), halIni = Math.min(hal, halMaks);
  const potong = <T,>(xs: T[]) => xs.slice(halIni * PER_HAL, (halIni + 1) * PER_HAL);
  const namaLihat = TAMPILAN.find((t) => t.k === lihat)!.label;

  const unduh = () => {
    const sel = (v: unknown) => { const t = String(v ?? ""); return /[;"\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
    const kq = (k: Kuadran) => KUADRAN.find((x) => x.k === k)?.label ?? "";
    const isi = lihat === "sekolah"
      ? [["NPSN", "Nama Sekolah", "Kab/Kota", "Angkatan", "Bimtek", "Hotel", "PIC", "Fasilitator", "Koordinator", "PTN", "Lap. 50%",
        "Reviu Lap. 50%", "Waktu tunggu reviu (hari)", `Status (batas reviu ${batas} hari)`],
        ...sekolahUrut.map((s) => [s.npsn, s.nama, s.kab, s.angkatan, labelBimtek(s.kode), s.hotel, s.pic, s.fasil, s.koor, s.ptn,
          L50[s.l50] ?? BELUM_TEMPO, REV[s.rev50] ?? "", s.rev50 === "menunggu" ? s.tunggu50 ?? "" : "", kq(s.kuadran)])]
      : [[namaLihat, ...(lihat === "fasil" ? ["Koordinator · PTN"] : lihat === "koor" ? ["PTN"] : []), "Sekolah",
        ...(lihat !== "fasil" ? ["Fasil"] : []), "Belum kirim Lap. 50%", "Menunggu reviu", "Waktu tunggu reviu terlama (hari)",
        `Telat direviu (> ${batas} hari)`],
        ...grup.map((g) => [g.nama, ...(lihat === "fasil" || lihat === "koor" ? [g.sub] : []), g.sekolah,
          ...(lihat !== "fasil" ? [g.fasil] : []), g.belum, g.menunggu, g.tunggu ?? "", g.telat])];
    const csv = "﻿" + isi.map((x) => x.map(sel).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `bimtek_${lihat}${kuadran ? `_${kuadran}-${batas}hari` : ""}_${r.data_terbaru.waktu.slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className={b.panel} aria-labelledby="h-daftar">
      <div className={b.panelHead}>
        <h2 id="h-daftar" className={b.h2}>
          <Tip isi={<>Daftar sekolah peserta bimtek, atau dirangkum per fasil, koordinator, dan PTN. Mengikuti pilihan bimtek dan
            batas hari di atas. Klik kotak matriks untuk menyaring.</>}>Daftar {namaLihat.toLowerCase()}</Tip>
        </h2>
        <Button size="sm" variant="secondary" onClick={unduh} disabled={!jumlah}>Unduh CSV ({fmt(jumlah)})</Button>
      </div>
      <div className={b.saring}>
        <div className={b.saringKuadran}>
          <div className={b.segmen} role="tablist" aria-label="Tampilan daftar">
            {TAMPILAN.map((t) => (
              <button key={t.k} type="button" role="tab" aria-selected={lihat === t.k} onClick={() => { setLihat(t.k); setHal(0); }}>
                {t.label}
              </button>
            ))}
          </div>
          {kuadran && (
            <button type="button" className={`${b.saringAktif} ${b[`kq_${kuadran}`]}`} onClick={() => setKuadran("")}>
              {KUADRAN.find((x) => x.k === kuadran)?.label}<span aria-hidden="true">×</span>
            </button>
          )}
        </div>
        <div className={b.saringBaris}>
          <input type="search" placeholder="Cari sekolah, NPSN, fasil, koordinator, PTN, atau hotel" value={cari}
            onChange={(e) => { setCari(e.target.value); setHal(0); }} aria-label="Cari" />
        </div>
      </div>
      <div className={b.gulir}>
        {lihat === "sekolah" ? (
          <table className={`${b.tabel} ${b.rincian}`}>
            <thead>
              <tr>
                <th>Sekolah</th><th>Angkatan</th><th>Bimtek</th><th>Fasil</th><th>PIC</th><th>PTN</th><th>Lap. 50%</th>
                <th><Tip isi="Sekolah: Lap. 50% jatuh tempo tapi belum dikirim. Fasil: sudah dikirim tapi menunggu reviu lebih lama dari batas hari.">Bermasalah</Tip></th>
                <th className={b.angka}><Tip kanan isi="Berapa hari Lap. 50% sekolah ini sudah menunggu reviu fasil.">Waktu tunggu reviu</Tip></th>
              </tr>
            </thead>
            <tbody>
              {potong(sekolahUrut).map((s) => {
                const t = s.rev50 === "menunggu" ? s.tunggu50 : null;
                return (
                  <tr key={s.npsn}>
                    <td className={b.kolomSekolah}><b>{s.nama}</b><small>{s.kab}</small></td>
                    <td>{s.angkatan || <span className={b.redup}>–</span>}</td>
                    <td className={b.kolomKirim}><Link href={hrefKelompok(s.kode)} className={b.tautanBiasa}>{labelBimtek(s.kode).replace(" ke-", " ")}</Link></td>
                    <td className={b.kolomPic}>{s.fasil || "–"}</td>
                    <td className={b.kolomPic}>{s.pic || "–"}</td>
                    <td className={b.kolomPic}>{s.ptn || "–"}</td>
                    <td className={`${b.kolomKirim} ${s.l50 === "B" ? b.turun : s.l50 ? "" : b.redup}`}>{L50[s.l50] ?? BELUM_TEMPO}</td>
                    <td>{s.kuadran === "aman" ? <span className={b.redup}>–</span>
                      : <span className={`${b.kq} ${b[`kq_${s.kuadran}`]}`}>{BERMASALAH[s.kuadran]}</span>}</td>
                    <td className={b.angka}>{t === null ? <span className={b.redup}>–</span> : <b className={t > batas ? b.turun : undefined}>{t} hari</b>}</td>
                  </tr>
                );
              })}
              {!jumlah && <tr><td colSpan={9} className={b.kosongBaris}>Tidak ada sekolah yang cocok.</td></tr>}
            </tbody>
          </table>
        ) : (
          <table className={b.tabel}>
            <thead>
              <tr>
                <th>{namaLihat}</th>
                <th className={b.angka}>Sekolah</th>
                {lihat !== "fasil" && <th className={b.angka}>Fasil</th>}
                <th className={b.angka}><Tip isi="Sekolah yang Lap. 50%-nya sudah wajib tapi belum dikirim.">Belum kirim Lap. 50%</Tip></th>
                <th className={b.angka}><Tip isi="Sekolah yang Lap. 50%-nya sudah dikirim dan masih menunggu reviu fasil.">Menunggu reviu</Tip></th>
                <th className={b.angka}><Tip isi="Lap. 50% yang paling lama menunggu reviu di grup ini.">Waktu tunggu reviu</Tip></th>
                <th className={b.angka}><Tip kanan isi={`Sekolah yang Lap. 50%-nya menunggu reviu lebih dari ${batas} hari.`}>Telat direviu</Tip></th>
              </tr>
            </thead>
            <tbody>
              {potong(grup).map((g) => (
                <tr key={g.nama}>
                  <td className={b.kolomPic}><b>{g.nama}</b>{g.sub && <small>{g.sub}</small>}</td>
                  <td className={b.angka}>{fmt(g.sekolah)}</td>
                  {lihat !== "fasil" && <td className={b.angka}>{fmt(g.fasil)}</td>}
                  <td className={b.angka}><b className={g.belum ? b.turun : undefined}>{fmt(g.belum)}</b></td>
                  <td className={b.angka}>{fmt(g.menunggu)}</td>
                  <td className={b.angka}>{g.tunggu === null ? <span className={b.redup}>–</span>
                    : <b className={g.tunggu > batas ? b.turun : undefined}>{g.tunggu} hari</b>}</td>
                  <td className={b.angka}><b className={g.telat ? b.turun : undefined}>{fmt(g.telat)}</b></td>
                </tr>
              ))}
              {!jumlah && <tr><td colSpan={7} className={b.kosongBaris}>Tidak ada data yang cocok.</td></tr>}
            </tbody>
          </table>
        )}
      </div>
      {jumlah > PER_HAL && (
        <div className={b.halaman2}>
          <span>{fmt(halIni * PER_HAL + 1)}–{fmt(Math.min(jumlah, (halIni + 1) * PER_HAL))} dari {fmt(jumlah)}</span>
          <button type="button" disabled={halIni === 0} onClick={() => setHal(halIni - 1)}>‹ Sebelumnya</button>
          <button type="button" disabled={halIni >= halMaks} onClick={() => setHal(halIni + 1)}>Berikutnya ›</button>
        </div>
      )}
      <p className={b.ket}>Data per {tgl(r.data_terbaru.waktu)}. Lap. 50% disebut telat direviu bila menunggu lebih dari {batas} hari.</p>
    </section>
  );
}
