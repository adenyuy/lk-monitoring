"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useEvents, usePolling } from "@/lib/hooks";
import type { SesiDetail, Today } from "@/lib/types";
import { Notice, Spinner } from "@/components/ui";
import { NowCard } from "./NowCard";
import { SessionTabs } from "./SessionTabs";
import { FasilList } from "./FasilList";
import { FasilDrawer } from "./FasilDrawer";
import { UndanganWagBar } from "./UndanganWag";
import s from "./today.module.css";

export function TodayView() {
  const [today, setToday] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sesi, setSesi] = useState<number | null>(null);
  const [detail, setDetail] = useState<SesiDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [nomor, setNomor] = useState<string | null>(null);
  const [versi, setVersi] = useState(0); // naik tiap ada perubahan -> panel fasil ambil ulang
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

  // Muat pertama: buka sesi berjalan, atau sesi berikutnya, atau sesi 1
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

  // Buka panel fasil dari notifikasi: lewat ?fasil=nomor (dari halaman lain) atau event (di halaman ini)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("fasil");
    if (q) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setNomor(q);
      window.history.replaceState(null, "", window.location.pathname);
    }
    const buka = (e: Event) => setNomor((e as CustomEvent<string>).detail);
    window.addEventListener("lkm-buka-fasil", buka);
    return () => window.removeEventListener("lkm-buka-fasil", buka);
  }, []);

  function pilihSesi(no: number) {
    if (no === sesiRef.current) return;
    sesiRef.current = no;
    setSesi(no);
    setDetail(null);
    void loadDetail(no);
  }

  const tutup = useCallback(() => setNomor(null), []);

  useEvents((type) => {
    if (type === "kirim_hasil" || type === "kirim_selesai" || type === "kirim_mulai" || type === "chat_diperbarui") {
      void refresh();
    } else if (type === "kirim_jeda" || type === "kirim_proses" || type === "kirim_stop_diminta"
      || type === "bypass_berubah" || type === "undangan_berubah") {
      void loadToday();
    }
  });
  usePolling(loadToday, 60000, true);

  // Nama / nomor fasil diubah dari panel: daftar sesi ikut diperbarui
  useEffect(() => {
    const ubah = () => { void refresh(); };
    window.addEventListener("lkm-fasil-diubah", ubah);
    return () => window.removeEventListener("lkm-fasil-diubah", ubah);
  }, [refresh]);

  if (error && !today) {
    return <Notice tone="bad" title="Data hari ini tidak bisa dimuat">{error}</Notice>;
  }
  if (!today || sesi === null) {
    return (
      <div className={s.loading}>
        <Spinner label="Memuat" /> Membaca sheet Broadcast…
      </div>
    );
  }

  return (
    <div className={s.page}>
      <div className={s.dateRow}>
        <span className={s.week} title={`Hari ini dan Rekap memakai tab WEEK ${today.week} di LK`}>
          WEEK {today.week}
        </span>
        <span className={s.date}>{today.tanggal_panjang}</span>
        <span className={s.blokLk}>Isi LK: sesi {today.blok_lk}</span>
      </div>
      <UndanganWagBar aktif={today.undangan_wag} berjalan={today.pengiriman.running} onChanged={refresh} />
      <NowCard today={today} onChanged={refresh} />
      <SessionTabs sesi={today.sesi} dipilih={sesi} onPilih={pilihSesi} />
      <FasilList detail={detail} loading={loadingDetail} selected={nomor} onPick={setNomor} />
      {nomor && <FasilDrawer nomor={nomor} versi={versi} onClose={tutup} />}
    </div>
  );
}
