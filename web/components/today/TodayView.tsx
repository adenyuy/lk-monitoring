"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useEvents, usePolling } from "@/lib/hooks";
import type { SesiDetail, Today } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import { SessionRail } from "./SessionRail";
import { SessionPanel } from "./SessionPanel";
import { ChatPanel } from "./ChatPanel";
import s from "./today.module.css";

export function TodayView() {
  const [today, setToday] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sesi, setSesi] = useState<number | null>(null);
  const [detail, setDetail] = useState<SesiDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [nomor, setNomor] = useState<string | null>(null);
  const [versi, setVersi] = useState(0); // naik tiap ada perubahan -> panel chat ambil ulang
  const sesiRef = useRef<number | null>(null);

  const loadToday = useCallback(async () => {
    try {
      const t = await api<Today>("/api/today");
      setToday(t);
      setError(null);
      return t;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  const loadDetail = useCallback(async (no: number) => {
    setLoadingDetail(true);
    try {
      const d = await api<SesiDetail>(`/api/sessions/${no}`);
      if (sesiRef.current === no) setDetail(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    await loadToday();
    if (sesiRef.current) await loadDetail(sesiRef.current);
    setVersi((v) => v + 1);
  }, [loadToday, loadDetail]);

  // Muat pertama: pilih sesi berjalan, atau sesi berikutnya, atau sesi 1
  useEffect(() => {
    void (async () => {
      const t = await loadToday();
      if (!t) return;
      const awal = t.sesi_aktif ?? t.kondisi.sesi_berikutnya ?? 1;
      sesiRef.current = awal;
      setSesi(awal);
      await loadDetail(awal);
    })();
  }, [loadToday, loadDetail]);

  function pilihSesi(no: number) {
    sesiRef.current = no;
    setSesi(no);
    setDetail(null);
    setNomor(null); // panel chat pindah ke fasil pertama di sesi ini
    void loadDetail(no);
  }

  // Pilih fasil pertama di sesi bila belum ada yang dipilih
  useEffect(() => {
    if (!nomor && detail) {
      const pertama = detail.sudah[0] ?? detail.akan[0];
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (pertama) setNomor(pertama.nomor);
    }
  }, [detail, nomor]);

  // Progres kirim langsung dari backend
  useEvents((type, data) => {
    if (type === "kirim_hasil" || type === "kirim_selesai" || type === "kirim_mulai" || type === "chat_diperbarui") {
      void refresh();
    } else if (type === "kirim_jeda" || type === "kirim_proses" || type === "kirim_stop_diminta") {
      void loadToday();
    }
    void data;
  });
  // Jam & status sesi bergeser seiring waktu
  usePolling(loadToday, 60000, true);

  if (error && !today) {
    return <Notice tone="bad" title="Data hari ini tidak bisa dimuat">{error}</Notice>;
  }
  if (!today || sesi === null) {
    return (
      <div className={s.empty} style={{ display: "flex", justifyContent: "center", gap: 10 }}>
        <Spinner label="Memuat" /> Membaca sheet Broadcast…
      </div>
    );
  }

  return (
    <div className={s.page}>
      <div className={s.top}>
        <div>
          <div className={s.date}>{today.tanggal_panjang}</div>
          <h1 className={s.title}>{today.kondisi.judul}</h1>
        </div>
        <dl className={s.stats}>
          <div><dt>Terkirim hari ini</dt><dd>{today.terkirim_hari_ini} <small>/ {today.batas_harian}</small></dd></div>
          <div><dt>Dibalas</dt><dd>{today.dibalas_hari_ini}</dd></div>
          <div><dt>Belum dikirim</dt><dd>{today.belum_dikirim} <small>/ {today.total_fasil}</small></dd></div>
        </dl>
      </div>

      <SessionRail sesi={today.sesi} dipilih={sesi} posisi={today.posisi_sekarang} jam={today.jam_sekarang}
        onPilih={pilihSesi} />

      <div className={s.cols}>
        <SessionPanel detail={detail} loading={loadingDetail} kirim={today.pengiriman} selected={nomor}
          onPick={setNomor} onChanged={refresh} />
        <ChatPanel nomor={nomor} versi={versi} />
      </div>
    </div>
  );
}
