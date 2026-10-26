"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { LockIcon } from "./NoAccess";
import { IconCutoff, IconHariIni, IconLog, IconPanduan, IconRekap, IconTanya } from "./Icons";
import s from "./app.module.css";

type Jadwal = {
  aktif: { no: number; sampai: string; sisa_detik: number } | null;
  berikutnya: { no: number; mulai: string; hari_ini: boolean; dalam_detik: number } | null;
};

type Posisi = { sisi: "kiri" | "kanan"; y: number };

const UKURAN = 56;
const TEPI = 12;
const KUNCI_POSISI = "lkm-tombol-bulat";

function hms(detik: number) {
  const h = Math.floor(detik / 3600);
  const m = Math.floor((detik % 3600) / 60);
  const d = detik % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(d).padStart(2, "0")}`;
}

function singkat(detik: number) {
  const m = Math.ceil(detik / 60);
  return m >= 60 ? `${Math.floor(m / 60)}j${m % 60 ? String(m % 60).padStart(2, "0") : ""}` : `${m}m`;
}

/** Area yang boleh ditempati tombol: tidak menutupi menu samping (laptop) atau bar atas/bawah (HP). */
function area() {
  let kiri = TEPI;
  let atas = TEPI;
  let bawah = window.innerHeight - TEPI;
  document.querySelectorAll<HTMLElement>("[data-dock-hindari]").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const arah = el.dataset.dockHindari;
    if (arah === "kiri") kiri = Math.max(kiri, r.right + TEPI);
    if (arah === "atas") atas = Math.max(atas, r.bottom + TEPI);
    if (arah === "bawah") bawah = Math.min(bawah, r.top - TEPI);
  });
  return { kiri, kanan: window.innerWidth - TEPI - UKURAN, atas, bawah: bawah - UKURAN };
}

const jepit = (v: number, a: number, b: number) => Math.min(Math.max(v, a), Math.max(a, b));

function useJadwal() {
  const [j, setJ] = useState<Jadwal | null>(null);
  const [dasar, setDasar] = useState(0); // Date.now() saat data diambil
  const [now, setNow] = useState(0);

  const muat = useCallback(async () => {
    try {
      const data = await api<Jadwal>("/api/jadwal");
      setJ(data);
      setDasar(Date.now());
      setNow(Date.now());
    } catch {
      /* hitung mundur hanya informasi */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muat();
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [muat]);
  usePolling(muat, 60000, true);

  const lewat = Math.max(0, Math.round((now - dasar) / 1000));
  const berjalan = !!j?.aktif && j.aktif.sisa_detik - lewat > 0;
  const detik = !j ? 0 : berjalan ? j.aktif!.sisa_detik - lewat : Math.max(0, (j.berikutnya?.dalam_detik ?? 0) - lewat);
  const habis = !!j && detik === 0 && lewat > 1;

  // Waktunya habis: ambil ulang supaya pindah ke sesi berikutnya
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (habis) void muat();
  }, [habis, muat]);

  const judul = !j ? "Memuat jadwal" : berjalan ? `Sesi ${j.aktif!.no} berjalan` : j.berikutnya
    ? `Sesi ${j.berikutnya.no} ${j.berikutnya.hari_ini ? `mulai ${j.berikutnya.mulai}` : "berikutnya"}`
    : "Tidak ada sesi";
  const ket = !j ? "" : berjalan ? `Sisa waktu, sampai ${j.aktif!.sampai}` : j.berikutnya?.hari_ini
    ? "Dimulai dalam" : "Hari kerja berikutnya, dalam";
  const total = berjalan ? Math.max(detik, 2 * 3600) : 2 * 3600; // skala lingkaran 2 jam
  return { ada: !!j, berjalan, detik, judul, ket, pct: Math.min(1, detik / total) };
}

type Props = { onPanduan: () => void; onTerkunci: () => void; bolehCutoff: boolean; adaBaru: boolean };

/**
 * Tombol bulat melayang (seperti AssistiveTouch): bisa digeser ke mana saja dan menempel ke tepi kiri/kanan.
 * Lingkarannya = hitung mundur sesi (detail saat diarahkan). Diketuk = menu cepat pindah halaman.
 */
export function AssistDock({ onPanduan, onTerkunci, bolehCutoff, adaBaru }: Props) {
  const path = usePathname() ?? "";
  const cd = useJadwal();
  const [pos, setPos] = useState<Posisi | null>(null);
  const [geser, setGeser] = useState<{ x: number; y: number } | null>(null);
  const [, setUkuran] = useState(0); // render ulang saat jendela berubah ukuran
  const [menu, setMenu] = useState(false);
  const [diam, setDiam] = useState(false);
  const awal = useRef<{ px: number; py: number; x: number; y: number; pindah: boolean } | null>(null);
  const baruDigeser = useRef(false);
  const tombol = useRef<HTMLButtonElement>(null);
  const timerDiam = useRef<number | undefined>(undefined);

  const bangun = useCallback(() => {
    setDiam(false);
    window.clearTimeout(timerDiam.current);
    timerDiam.current = window.setTimeout(() => setDiam(true), 4000);
  }, []);

  // Posisi tersimpan per browser; bawaan kanan bawah
  useEffect(() => {
    let p: Posisi | null = null;
    try {
      const raw = localStorage.getItem(KUNCI_POSISI);
      if (raw) p = JSON.parse(raw) as Posisi;
    } catch {
      /* posisi hanya kenyamanan */
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPos(p && (p.sisi === "kiri" || p.sisi === "kanan") && typeof p.y === "number"
      ? p : { sisi: "kanan", y: window.innerHeight - UKURAN - 96 });
    bangun();
    const onResize = () => setUkuran((x) => x + 1);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.clearTimeout(timerDiam.current);
    };
  }, [bangun]);

  const tutupMenu = useCallback(() => {
    setMenu(false);
    bangun();
    tombol.current?.focus();
  }, [bangun]);

  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") tutupMenu();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu, tutupMenu]);

  // Tutup menu saat pindah halaman
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMenu(false);
  }, [path]);

  if (!pos) return null;
  const a = area();
  const x = geser ? geser.x : pos.sisi === "kiri" ? a.kiri : a.kanan;
  const y = geser ? geser.y : jepit(pos.y, a.atas, a.bawah);
  const sisiNow = geser ? (geser.x + UKURAN / 2 < window.innerWidth / 2 ? "kiri" : "kanan") : pos.sisi;

  function onDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return;
    awal.current = { px: e.clientX, py: e.clientY, x, y, pindah: false };
    e.currentTarget.setPointerCapture(e.pointerId);
    bangun();
  }

  function onMove(e: React.PointerEvent<HTMLButtonElement>) {
    const st = awal.current;
    if (!st) return;
    const dx = e.clientX - st.px;
    const dy = e.clientY - st.py;
    if (!st.pindah && Math.hypot(dx, dy) < 6) return;
    st.pindah = true;
    const b = area();
    setGeser({ x: jepit(st.x + dx, TEPI, window.innerWidth - TEPI - UKURAN), y: jepit(st.y + dy, b.atas, b.bawah) });
  }

  function onUp(e: React.PointerEvent<HTMLButtonElement>) {
    const st = awal.current;
    awal.current = null;
    if (!st?.pindah || !geser) return;
    baruDigeser.current = true;
    const baru: Posisi = { sisi: e.clientX < window.innerWidth / 2 ? "kiri" : "kanan", y: geser.y };
    setPos(baru);
    setGeser(null);
    bangun();
    try {
      localStorage.setItem(KUNCI_POSISI, JSON.stringify(baru));
    } catch {
      /* posisi hanya kenyamanan */
    }
  }

  function onClick() {
    if (baruDigeser.current) {
      baruDigeser.current = false;
      return;
    }
    setMenu(true);
  }

  const C = 2 * Math.PI * 24;
  const pusat = { x: x + UKURAN / 2, y: y + UKURAN / 2 };
  const kini = (href: string) => (path.startsWith(href.slice(0, -1)) ? "page" : undefined);

  return (
    <>
      <div
        className={`${s.assist} ${cd.berjalan ? s.cdLive : ""} ${geser ? s.assistGeser : ""} ${diam && !menu ? s.assistDiam : ""} ${sisiNow === "kiri" ? s.assistKiri : ""}`}
        style={{ left: x, top: y }}
        onPointerEnter={bangun}
        data-tour="dock"
      >
        <button
          ref={tombol}
          type="button"
          className={s.assistBtn}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={() => { awal.current = null; setGeser(null); }}
          onClick={onClick}
          aria-haspopup="dialog"
          aria-expanded={menu}
          aria-label={`Menu cepat. ${cd.judul}. ${cd.ket} ${hms(cd.detik)}`}
        >
          <svg width={UKURAN} height={UKURAN} viewBox="0 0 56 56" aria-hidden="true">
            <circle cx="28" cy="28" r="24" className={s.cdTrack} />
            <circle cx="28" cy="28" r="24" className={s.cdBar} strokeDasharray={C} strokeDashoffset={C * (1 - cd.pct)} />
          </svg>
          <span aria-hidden="true">{cd.ada ? singkat(cd.detik) : "…"}</span>
          {adaBaru && <i className={s.assistDot} aria-hidden="true" />}
        </button>
        {!geser && cd.ada && (
          <div className={s.assistPop} role="status" aria-live="off">
            <b>{cd.judul}</b>
            <small>{cd.ket}</small>
            <span className={s.cdTime}>{hms(cd.detik)}</span>
            <em>Ketuk untuk menu, seret untuk memindahkan</em>
          </div>
        )}
      </div>

      {menu && (
        <div className={s.amWrap}>
          <div className={s.amBackdrop} onClick={tutupMenu} />
          <div className={s.amStage} style={{ transformOrigin: `${pusat.x}px ${pusat.y}px` } as CSSProperties}
            onClick={(e) => { if (e.target === e.currentTarget) tutupMenu(); }}>
            <div className={`${s.amPanel} ${cd.berjalan ? s.cdLive : ""}`} role="dialog" aria-modal="true"
              aria-label="Menu cepat">
              <div className={s.amHead}>
                <div>
                  <b>{cd.judul}</b>
                  <small>{cd.ket}</small>
                </div>
                <span className={s.cdTime}>{hms(cd.detik)}</span>
              </div>
              <div className={s.amGrid}>
                <Tile href="/rekap/" label="Rekap" icon={<IconRekap />} current={kini("/rekap/")} onPick={tutupMenu}
                  titik={adaBaru} autoFocus />
                <Tile href="/today/" label="Hari ini" icon={<IconHariIni />} current={kini("/today/")} onPick={tutupMenu} />
                {bolehCutoff ? (
                  <Tile href="/cutoff/" label="Tarik Cutoff" icon={<IconCutoff />} current={kini("/cutoff/")}
                    onPick={tutupMenu} />
                ) : (
                  <Tile label="Tarik Cutoff" icon={<IconCutoff />} kunci
                    onPick={() => { setMenu(false); onTerkunci(); }} />
                )}
                <Tile href="/rekap/#perubahan" label="Log perubahan" icon={<IconLog />} onPick={tutupMenu} />
                <Tile label="Panduan" icon={<IconPanduan />} onPick={() => { setMenu(false); onPanduan(); }} />
                <Tile href="/faq/" label="Tanya jawab" icon={<IconTanya />} current={kini("/faq/")} onPick={tutupMenu} />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Tile({ href, label, icon, current, onPick, kunci, titik, autoFocus }: {
  href?: string; label: string; icon: ReactNode; current?: "page"; onPick: () => void;
  kunci?: boolean; titik?: boolean; autoFocus?: boolean;
}) {
  const isi = (
    <>
      <span className={s.amIco}>
        {icon}
        {kunci && <span className={s.lockBadge}><LockIcon size={10} /></span>}
        {titik && <span className={s.newDot} />}
      </span>
      <span>{label}</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className={s.amTile} aria-current={current} onClick={onPick} autoFocus={autoFocus}>
        {isi}
      </Link>
    );
  }
  return (
    <button type="button" className={`${s.amTile} ${kunci ? s.amLocked : ""}`} onClick={onPick}
      aria-label={kunci ? `${label}, terkunci` : undefined}>
      {isi}
    </button>
  );
}
