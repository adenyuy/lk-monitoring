"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { Button, Notice } from "@/components/ui";
import s from "./admin.module.css";

type Info = { terpasang: boolean; admin: boolean; link?: string };

/** Link sheet LK Monitoring Pelaporan untuk seluruh tim (ditulis ke tab Pengaturan sheet Akses). */
export function LinkLk() {
  const [info, setInfo] = useState<Info | null>(null);
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  const muat = () => api<Info>("/api/lk2/link").then(setInfo).catch(() => undefined);
  useEffect(() => { void muat(); }, []);

  async function simpan() {
    setBusy(true);
    setHasil(null);
    try {
      const r = await post<{ untuk_tim: boolean }>("/api/lk2/link", { link });
      setHasil({ tone: "ok", teks: r.untuk_tim ? "Terpasang untuk seluruh tim (tab Pengaturan sheet Akses)." : "Terpasang di laptop ini." });
      setLink("");
      void muat();
    } catch (e) {
      setHasil({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={s.card} aria-labelledby="h-lk">
      <h2 id="h-lk">Sheet LK Monitoring <span>{info?.terpasang ? "terpasang" : "belum terpasang"}</span></h2>
      <p className={s.ketKecil}>
        Sheet berisi tab WEEK n, Log Komunikasi, dan Log Progres. Cukup dipasang sekali; anggota tim otomatis memakainya.
        {info?.link && <> Saat ini: <a href={info.link} target="_blank" rel="noreferrer">buka sheet</a>.</>}
      </p>
      <div className={s.linkBaris}>
        <input className={s.cari} type="url" value={link} onChange={(e) => setLink(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/…" aria-label="Link sheet LK" />
        <Button size="sm" loading={busy} disabled={link.trim().length < 10} onClick={() => void simpan()}>
          {info?.terpasang ? "Ganti link" : "Pasang"}
        </Button>
      </div>
      {hasil && <Notice tone={hasil.tone}>{hasil.teks}</Notice>}
    </section>
  );
}
