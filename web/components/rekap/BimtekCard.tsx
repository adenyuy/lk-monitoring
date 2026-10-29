"use client";

import { useRef, useState } from "react";
import { api, upload } from "@/lib/api";
import type { BimtekInfo, Rekap } from "@/lib/types";
import { Button, Notice } from "@/components/ui";
import s from "./rekap.module.css";

/** Penanda peserta bimtek percepatan laporan yang laporan 50%-nya belum direviu: unggah file, lalu saring tabel. */
export function BimtekCard({ data, onUbah, onLihat }: {
  data: Rekap["bimtek"];
  onUbah: () => void;
  onLihat: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pilih(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await upload<BimtekInfo>("/api/bimtek", file);
      onUbah();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function hapus() {
    setBusy(true);
    try {
      await api<BimtekInfo>("/api/bimtek", { method: "DELETE" });
      onUbah();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${s.card} ${s.bimtek}`} aria-labelledby="h-bimtek">
      <div className={s.cardHead}>
        <h2 id="h-bimtek">Peserta bimtek, laporan 50% belum direviu</h2>
        {data.ada && <span>Data per {data.per_tanggal || "–"}</span>}
      </div>
      {data.ada ? (
        <p className={s.bimtekKet}>
          {data.sekolah > 0
            ? <><b>{data.fasil} fasil</b> Anda punya <b>{data.sekolah} sekolah</b> peserta bimtek yang laporan 50%-nya
              belum direviu. Chat mereka dengan template <i>Bimtek: belum direviu</i> di panel fasil. Tanda hilang
              sendiri begitu LK mencatat sekolahnya sudah direviu.</>
            : <>Tidak ada sekolah binaan Anda di daftar ini yang masih belum direviu menurut LK.</>}
        </p>
      ) : (
        <p className={s.bimtekKet}>
          Unggah file Excel dari koordinator (mis. <i>Hitung_Hari_Lapor_50_Data_28_Okt_dengan_Petugas.xlsx</i>) untuk
          menandai fasil yang sekolah binaannya ikut bimtek dan laporan 50%-nya belum direviu. File tidak dikirim ke
          mana pun; aplikasi hanya menyimpan NPSN sekolahnya.
        </p>
      )}
      {error && <Notice tone="bad" title="File tidak bisa dipakai">{error}</Notice>}
      <div className={s.bimtekAksi}>
        {data.ada && data.fasil > 0 && <Button size="sm" onClick={onLihat}>Lihat {data.fasil} fasil</Button>}
        <Button size="sm" variant={data.ada ? "ghost" : "primary"} loading={busy} onClick={() => input.current?.click()}>
          {data.ada ? "Ganti file" : "Unggah file Excel"}
        </Button>
        {data.ada && <Button size="sm" variant="ghost" disabled={busy} onClick={hapus}>Hapus penanda</Button>}
        {data.ada && data.file && <span className={s.bimtekFile}>{data.file}</span>}
        <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => void pilih(e.target.files?.[0])} />
      </div>
    </section>
  );
}
