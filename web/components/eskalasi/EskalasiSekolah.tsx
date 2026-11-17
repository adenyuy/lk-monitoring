"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EskalasiInfo, Masalah } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import { pesan } from "@/components/forum/bersama";
import { FormMasalah } from "./FormMasalah";
import { asalMasalah, Jawaban, PasangLink, StatusChip, tgl, TindakLanjut, WaktuChip } from "./bagian";
import s from "./esk.module.css";

type Sekolah = { npsn: string; nama: string };

/** Eskalasi dari panel fasil: lapor masalah sekolah binaannya + masalah yang sudah tercatat. */
export function EskalasiSekolah({ sekolah, awal }: { sekolah: Sekolah[]; awal?: { npsn?: string[] } }) {
  const [info, setInfo] = useState<EskalasiInfo | null>(null);
  const [galat, setGalat] = useState("");
  const [versi, setVersi] = useState(0);
  const [tab, setTab] = useState<"lapor" | "tercatat">("lapor");
  const [isi, setIsi] = useState<number | null>(null);
  const npsn = sekolah.map((x) => x.npsn).join(",");

  useEffect(() => {
    let batal = false;
    api<EskalasiInfo>(`/api/eskalasi?npsn=${encodeURIComponent(npsn)}`)
      .then((d) => { if (!batal) { setInfo(d); setGalat(""); } })
      .catch((e) => { if (!batal) setGalat(pesan(e)); });
    return () => { batal = true; };
  }, [npsn, versi]);

  const ganti = (baru: Masalah) => setInfo((d) => d && { ...d, masalah: d.masalah.map((m) => (m.baris === baru.baris ? baru : m)) });

  if (info?.perlu_link) return <div className={s.padding}><PasangLink onSelesai={() => setVersi((v) => v + 1)} /></div>;
  if (galat) return <div className={s.padding}><Notice tone="bad" title="LK Eskalasi tidak bisa dibuka">{galat}</Notice></div>;
  if (!info?.opsi) return <p className={`${s.memuat} ${s.padding}`}><Spinner /> Membaca LK Eskalasi…</p>;

  const aktif = info.masalah.filter((m) => m.status !== "Selesai").length;
  return (
    <div className={s.tabWadah}>
      <div className={s.tabBar} role="tablist">
        <button type="button" role="tab" aria-selected={tab === "lapor"} onClick={() => setTab("lapor")}>Laporkan masalah</button>
        <button type="button" role="tab" aria-selected={tab === "tercatat"} onClick={() => setTab("tercatat")}>
          Sudah tercatat <span className={aktif ? s.tabHitungAktif : s.tabHitung}>{info.masalah.length}</span>
        </button>
      </div>
      {tab === "lapor" ? (
        <FormMasalah opsi={info.opsi} saya={info.saya.nama ?? ""} masalah={info.masalah} awal={awal}
          sekolahFasil={sekolah} onSelesai={() => setVersi((v) => v + 1)} />
      ) : (
        <div className={s.tercatat}>
          {info.masalah.length === 0 ? (
            <div className={s.kosong}><b>Belum ada masalah</b>Sekolah binaan fasil ini belum pernah dieskalasi.</div>
          ) : (
            <ul className={s.daftar}>
              {info.masalah.map((m) => (
                <li key={m.baris} className={`${s.kartu} ${s[`garis_${m.status === "Selesai" ? "ok" : "aktif"}`]}`}>
                  <div className={s.kartuAtas}>
                    <span className={s.kode}>{m.id}</span>
                    {m.permasalahan && <span className={s.tag}>{m.permasalahan}</span>}
                    <span>{m.tgl_awal ? tgl(m.tgl_awal) : ""}</span>
                    <span className={s.kanan}><WaktuChip m={m} /><StatusChip m={m} /></span>
                  </div>
                  <b className={s.judulKecil}>{asalMasalah(m)}</b>
                  <p className={s.teksKecil}>{m.keterangan}</p>
                  <Jawaban m={m} />
                  {m.boleh_ubah && (isi === m.baris
                    ? <TindakLanjut m={m} opsi={info.opsi!} saya={info.saya.nama ?? ""} pic={!!info.saya.pic}
                        onTersimpan={ganti} onBatal={() => setIsi(null)} />
                    : <button type="button" className={s.tautan} style={{ alignSelf: "flex-start" }} onClick={() => setIsi(m.baris)}>
                        Isi tindak lanjut</button>)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
