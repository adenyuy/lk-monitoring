"use client";

import { useMemo, useState } from "react";
import type { LkRingkasan } from "@/lib/lk";
import s from "./lk.module.css";

type Isian = "lengkap" | "belum" | "tanpa";

const LABEL_ISIAN: Record<Isian, string> = { belum: "Belum lengkap", lengkap: "Lengkap", tanpa: "Tanpa to-do" };

/** Satu baris per sekolah binaan, supaya mudah melihat mana yang sudah diisi dan sudah dihubungi. */
export function TabelSekolah({ data, onBuka }: { data: LkRingkasan; onBuka: (kunci: string) => void }) {
  const [cari, setCari] = useState("");
  const [isian, setIsian] = useState<Isian | "">("");
  const [kom, setKom] = useState("");

  const semua = useMemo(() => {
    const fasil = new Map(data.fasil.map((f) => [f.kunci, f]));
    const label = new Map(data.kom.map((k) => [k.kode, k.label]));
    return data.sekolah_tabel.map((x) => {
      const f = fasil.get(x.kunci);
      const kode = f?.kom ?? "belum";
      const st: Isian = !x.todo ? "tanpa" : x.isian >= x.todo ? "lengkap" : "belum";
      return { ...x, st, kom: kode, komLabel: label.get(kode) ?? "", kodeHari: f?.kode_hari_ini ?? "" };
    }).sort((a, b) => a.fasil.localeCompare(b.fasil) || a.nama.localeCompare(b.nama));
  }, [data.fasil, data.kom, data.sekolah_tabel]);

  const baris = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return semua.filter((x) => (!isian || x.st === isian) && (!kom || x.kom === kom)
      && (!q || x.npsn.includes(q) || x.nama.toLowerCase().includes(q) || x.fasil.toLowerCase().includes(q)));
  }, [semua, cari, isian, kom]);

  return (
    <section className={s.card} aria-labelledby="h-tabel-sekolah">
      <div className={s.papanHead}>
        <div>
          <h2 id="h-tabel-sekolah">Tabel sekolah</h2>
          <p>Isian sesi {data.blok_label} dan status komunikasi tiap sekolah. Klik nama fasil untuk membuka LK-nya.</p>
        </div>
        <input type="search" placeholder="Cari NPSN, sekolah, atau fasil" value={cari} aria-label="Cari di tabel sekolah"
          onChange={(e) => setCari(e.target.value)} />
      </div>
      <div className={s.alat}>
        <label className={s.pilihKecil}>
          <span>Isian</span>
          <select value={isian} onChange={(e) => setIsian(e.target.value as Isian | "")}>
            <option value="">Semua</option>
            {(Object.keys(LABEL_ISIAN) as Isian[]).map((k) => (
              <option key={k} value={k}>{LABEL_ISIAN[k]} ({semua.filter((x) => x.st === k).length})</option>
            ))}
          </select>
        </label>
        <label className={s.pilihKecil}>
          <span>Status komunikasi</span>
          <select value={kom} onChange={(e) => setKom(e.target.value)}>
            <option value="">Semua</option>
            {data.kom.map((k) => <option key={k.kode} value={k.kode}>{k.label} ({semua.filter((x) => x.kom === k.kode).length})</option>)}
          </select>
        </label>
        <span className={s.tabelJumlah} aria-live="polite">{baris.length} dari {semua.length} sekolah</span>
      </div>
      <div className={s.tabelGulir} tabIndex={0} role="region" aria-labelledby="h-tabel-sekolah">
        <table className={s.tabelSekolah}>
          <thead>
            <tr>
              <th scope="col">NPSN</th><th scope="col">Sekolah</th><th scope="col">Fasil</th><th scope="col">Akt</th>
              <th scope="col">Isian</th><th scope="col">Status komunikasi</th>
            </tr>
          </thead>
          <tbody>
            {baris.map((x) => (
              <tr key={x.npsn}>
                <td>{x.npsn}</td>
                <td>{x.nama}</td>
                <td><button type="button" onClick={() => onBuka(x.kunci)}>{x.fasil || "(tanpa fasil)"}</button></td>
                <td>{x.angkatan || "–"}</td>
                <td>
                  <span className={`${s.tabelIsian} ${x.st === "lengkap" ? s.tabelLengkap : x.st === "belum" ? s.tabelBelum : ""}`}>
                    {x.st === "tanpa" ? LABEL_ISIAN.tanpa : `${x.isian}/${x.todo}`}
                  </span>
                </td>
                <td>{x.kodeHari && <b className={s.tabelKode}>{x.kodeHari}</b>}{x.komLabel}</td>
              </tr>
            ))}
            {!baris.length && <tr><td colSpan={6} className={s.tabelKosong}>Tidak ada sekolah yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
