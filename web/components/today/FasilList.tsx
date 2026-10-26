"use client";

import type { BarisSesi, LkRingkas, SesiDetail } from "@/lib/types";
import { Chip, Spinner, statusTone } from "@/components/ui";
import s from "./today.module.css";

export function inisial(nama: string) {
  const kata = nama.replace(/[^\p{L}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
  return ((kata[0]?.[0] ?? "") + (kata[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Batang kecil sebaran prioritas sekolah binaan. */
export function LkBar({ lk }: { lk: LkRingkas }) {
  if (!lk.jumlah) return null;
  const seg = [
    ["p1", lk.p1], ["p2", lk.p2], ["p3", lk.p3], ["ok", lk.selesai],
  ] as const;
  return (
    <span className={s.lkBar} aria-hidden="true">
      {seg.map(([k, n]) => n > 0 && <span key={k} className={s[`lk_${k}`]} style={{ flexGrow: n }} />)}
    </span>
  );
}

function ringkas(lk: LkRingkas) {
  if (!lk.jumlah) return "Tidak ada di LK";
  const bagian = [`${lk.jumlah} sekolah`];
  if (lk.p1) bagian.push(`${lk.p1} belum submit`);
  if (lk.p2) bagian.push(`${lk.p2} di bawah 50%`);
  if (lk.p3) bagian.push(`${lk.p3} belum reviu`);
  if (!lk.p1 && !lk.p2 && !lk.p3 && lk.selesai) bagian.push("semua selesai");
  return bagian.join(", ");
}

function Rows({ items, onPick, selected }: { items: BarisSesi[]; onPick: (n: string) => void; selected: string | null }) {
  return (
    <ul className={s.list}>
      {items.map((r, i) => (
        <li key={`${r.nomor}-${r.jam}-${i}`}>
          <button type="button" className={`${s.item} ${r.nomor === selected ? s.itemOn : ""}`} onClick={() => onPick(r.nomor)}>
            <span className={`${s.avatar} ${s[`av_${statusTone(r.status)}`] ?? ""}`} aria-hidden="true">{inisial(r.nama_fasil)}</span>
            <span className={s.itemMain}>
              <span className={s.itemName}>{r.nama_fasil}</span>
              <span className={s.itemSub}>
                <LkBar lk={r.lk} />
                <span>{ringkas(r.lk)}{r.keterangan ? `. ${r.keterangan}` : ""}</span>
              </span>
            </span>
            {r.jam && <span className={s.itemTime}>{r.jam}</span>}
            {r.status !== "Menunggu" && <Chip tone={statusTone(r.status)}>{r.status}</Chip>}
            <svg className={s.chev} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Daftar fasil satu sesi: yang sudah diproses lalu yang berikutnya. */
export function FasilList({ detail, loading, selected, onPick }: {
  detail: SesiDetail | null;
  loading: boolean;
  selected: string | null;
  onPick: (nomor: string) => void;
}) {
  if (!detail) {
    return <section className={s.card}><div className={s.empty}>{loading ? <Spinner label="Memuat sesi" /> : "Pilih sesi di atas."}</div></section>;
  }
  const kosong = detail.sudah.length === 0 && detail.akan.length === 0;
  return (
    <section className={s.card} aria-label={`Fasil sesi ${detail.no}`}>
      <header className={s.cardHead}>
        <h2>Sesi {detail.no}, {detail.mulai}–{detail.sampai}</h2>
        <span>Pilih fasil untuk membandingkan LK dengan chat-nya</span>
      </header>
      {detail.sudah.length > 0 && (
        <>
          <div className={s.group}>Sudah diproses <b>{detail.sudah.length}</b></div>
          <Rows items={detail.sudah} onPick={onPick} selected={selected} />
        </>
      )}
      {detail.akan.length > 0 && (
        <>
          <div className={s.group}>{detail.aktif ? "Urutan kirim berikutnya" : "Perkiraan yang akan dikirimi"} <b>{detail.akan.length}</b></div>
          <Rows items={detail.akan} onPick={onPick} selected={selected} />
        </>
      )}
      {kosong && <div className={s.empty}>Tidak ada fasil di sesi ini. Sesi yang sudah lewat tanpa kiriman tetap kosong.</div>}
    </section>
  );
}
