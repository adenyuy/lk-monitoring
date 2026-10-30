"use client";

import { useMemo, useState } from "react";
import type { FasilRekap, TahapKini } from "@/lib/types";
import s from "./rekap.module.css";

const KOLOM: { k: TahapKini[]; label: string; lanjut: string }[] = [
  { k: ["belum", "gagal"], label: "Belum dihubungi", lanjut: "Kirim Broadcast atau chat" },
  { k: ["terkirim"], label: "Sudah dihubungi", lanjut: "Tunggu dibaca" },
  { k: ["dibaca"], label: "Dibaca, belum membalas", lanjut: "Sapa lagi" },
  { k: ["dibalas"], label: "Membalas", lanjut: "Tanyakan isian LK" },
  { k: ["ditanya"], label: "Isian ditanyakan", lanjut: "Isi LK" },
  { k: ["lk_lengkap"], label: "LK lengkap", lanjut: "Beres minggu ini" },
];

type Saring = "semua" | "balas" | "p1" | "p2" | "p3" | "luar";
const SARING: { k: Saring; label: string; cocok: (r: FasilRekap) => boolean }[] = [
  { k: "semua", label: "Semua", cocok: () => true },
  { k: "balas", label: "Perlu dibalas", cocok: (r) => r.perlu_balas },
  { k: "p1", label: "P1", cocok: (r) => r.p1 > 0 },
  { k: "p2", label: "P2", cocok: (r) => r.p2 > 0 },
  { k: "p3", label: "P3", cocok: (r) => r.p3 > 0 },
  { k: "luar", label: "Di luar Broadcast", cocok: (r) => !r.di_broadcast },
];

const HARI = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"];

function kapan(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${HARI[d.getDay()]} ${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Papan tahap chat minggu ini: tiap fasil ada di kolom tahap terjauh yang sudah dicapai. */
export function TahapBoard({ fasil, onBuka }: { fasil: FasilRekap[]; onBuka: (nomor: string) => void }) {
  const [saring, setSaring] = useState<Saring>("semua");
  const [cari, setCari] = useState("");

  const aktif = useMemo(() => fasil.filter((r) => r.tahap_kini !== "selesai"), [fasil]);
  const selesai = fasil.length - aktif.length;

  const kolom = useMemo(() => {
    const f = SARING.find((x) => x.k === saring)!;
    const q = cari.trim().toLowerCase();
    const pilih = aktif.filter((r) => f.cocok(r) && (!q || r.nama.toLowerCase().includes(q)));
    return KOLOM.map((c) => ({
      ...c,
      // Yang paling lama tidak ada kabar di atas, supaya disapa lebih dulu; yang belum pernah dihubungi urut P1 terbanyak
      isi: pilih.filter((r) => c.k.includes(r.tahap_kini)).sort((a, b) =>
        Number(b.perlu_balas) - Number(a.perlu_balas)
        || (a.terakhir || "~").localeCompare(b.terakhir || "~") || b.p1 - a.p1 || a.nama.localeCompare(b.nama)),
    }));
  }, [aktif, saring, cari]);

  return (
    <section className={s.card} aria-labelledby="h-tahap" data-tour="tahap">
      <div className={s.cardHead}>
        <h2 id="h-tahap">Tahap chat minggu ini</h2>
        <input className={s.search} type="search" placeholder="Cari nama fasil" value={cari}
          onChange={(e) => setCari(e.target.value)} aria-label="Cari fasil di papan tahap" />
      </div>
      <div className={s.filters} role="group" aria-label="Saring papan">
        {SARING.map((x) => (
          <button key={x.k} type="button" aria-pressed={saring === x.k} onClick={() => setSaring(x.k)}>
            {x.label} <span>{aktif.filter(x.cocok).length}</span>
          </button>
        ))}
      </div>

      <div className={s.board}>
        {kolom.map((c, i) => (
          <div key={c.label} className={s.col} aria-labelledby={`kol-${i}`}>
            <div className={s.colHead}>
              <b id={`kol-${i}`}>{c.label}</b>
              <span className={s.colN}>{c.isi.length}</span>
              <small>Berikutnya: {c.lanjut}</small>
            </div>
            <ul className={s.colList}>
              {c.isi.map((r) => (
                <li key={r.nomor || r.nama}>
                  <button type="button" className={`${s.tCard} ${r.perlu_balas ? s.tCardBalas : ""}`}
                    disabled={!r.nomor} onClick={() => onBuka(r.nomor)}
                    title={r.nomor ? undefined : "Nomor WhatsApp fasil ini kosong di sheet Broadcast dan di kolom No Fasil LK. Isi nomornya dulu supaya bisa dibuka."}>
                    <b>{r.nama}</b>
                    {r.isian_perlu > 0 && (
                      <span className={s.tLk} title={`Isian LK lengkap ${r.isian_lengkap} dari ${r.isian_perlu} sekolah yang perlu diisi`}>
                        <span className={s.tLkTrack}>
                          <span style={{ width: `${Math.round((r.isian_lengkap / r.isian_perlu) * 100)}%` }} />
                        </span>
                        <span className={r.isian_lengkap >= r.isian_perlu ? s.tLkOk : undefined}>
                          LK {r.isian_lengkap}/{r.isian_perlu}
                        </span>
                      </span>
                    )}
                    <span className={s.tPills}>
                      {!r.nomor && <em className={s.tGagal}>Nomor WA kosong</em>}
                      {r.perlu_balas && <em className={s.tBalas}>Perlu dibalas</em>}
                      {r.p1 > 0 && <em className={s.tP1}>P1 {r.p1}</em>}
                      {r.p2 > 0 && <em className={s.tP2}>P2 {r.p2}</em>}
                      {r.p3 > 0 && <em className={s.tP3}>P3 {r.p3}</em>}
                      {r.tahap_kini === "gagal" && <em className={s.tGagal}>Gagal kirim</em>}
                      {!r.di_broadcast && <em className={s.tLuar}>Luar Broadcast</em>}
                    </span>
                    <small>
                      {r.terakhir ? `${kapan(r.terakhir)}, ${r.terakhir_label.toLowerCase()}` : "Belum ada kontak minggu ini"}
                    </small>
                  </button>
                </li>
              ))}
              {c.isi.length === 0 && <li className={s.colEmpty}>Kosong</li>}
            </ul>
          </div>
        ))}
      </div>
      <p className={s.note}>
        Tiap fasil ada di tahap terjauh yang sudah dicapai minggu ini, dan mulai dari awal lagi tiap Senin. Klik fasil
        untuk membuka LK dan chat-nya. {selesai > 0 && `${selesai} fasil tidak ditampilkan karena semua sekolahnya sudah selesai.`}
      </p>
    </section>
  );
}
