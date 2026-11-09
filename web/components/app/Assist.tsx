"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { LockIcon } from "./NoAccess";
import { DaftarFasil, IzinDesktop, NotifList, useNotif, type Notif } from "./Notif";
import { IconBlast, IconCutoff, IconDashboard, IconForum, IconLk, IconLog, IconPaparan } from "./Icons";
import s from "./app.module.css";

type Bubble = {
  blok_label: string; perlu: number; lengkap: number; fasil: number; dicatat: number; log_hari_ini: boolean;
  blast: { berjalan: boolean; diproses: number; total: number; jeda: boolean };
};

type Posisi = { sisi: "kiri" | "kanan"; y: number };

const UKURAN = 56;
const TEPI = 12;
const KUNCI_POSISI = "lkm-tombol-bulat";


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

/** Ringkasan untuk lingkaran: isian sesi hari ini (atau progres blast bila sedang berjalan). */
function useRingkas() {
  const [b, setB] = useState<Bubble | null>(null);
  const muat = useCallback(async () => {
    try {
      setB(await api<Bubble>("/api/lk2/bubble"));
    } catch {
      /* lingkaran hanya informasi */
    }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muat();
  }, [muat]);
  usePolling(muat, b?.blast.berjalan ? 5000 : 120000, true);

  if (!b) return { ada: false, berjalan: false, pct: 0, angka: "…", judul: "Memuat", ket: "", baris: [] as string[] };
  if (b.blast.berjalan) {
    const pct = b.blast.total ? b.blast.diproses / b.blast.total : 0;
    return { ada: true, berjalan: true, pct, angka: `${b.blast.diproses}/${b.blast.total}`,
      judul: b.blast.jeda ? "Blast dijeda" : "Blast berjalan", ket: `${b.blast.diproses} dari ${b.blast.total} pesan diproses`,
      baris: [`Isian sesi ${b.blok_label}: ${b.lengkap}/${b.perlu} sekolah`] };
  }
  const pct = b.perlu ? b.lengkap / b.perlu : 1;
  return {
    ada: true, berjalan: false, pct, angka: `${Math.round(pct * 100)}%`,
    judul: `Isian sesi ${b.blok_label}`, ket: `${b.lengkap} dari ${b.perlu} sekolah lengkap`,
    baris: b.log_hari_ini ? [`Log komunikasi hari ini: ${b.dicatat}/${b.fasil} fasil`] : [],
  };
}

type Props = { onTerkunci: () => void; bolehCutoff: boolean; adaBaru: boolean };

/**
 * Tombol bulat melayang (seperti AssistiveTouch): bisa digeser ke mana saja dan menempel ke tepi kiri/kanan.
 * Lingkarannya = hitung mundur sesi (detail saat diarahkan). Diketuk = menu cepat pindah halaman.
 */
export function AssistDock({ onTerkunci, bolehCutoff, adaBaru }: Props) {
  const path = usePathname() ?? "";
  const cd = useRingkas();
  const [pos, setPos] = useState<Posisi | null>(null);
  const [geser, setGeser] = useState<{ x: number; y: number } | null>(null);
  const [, setUkuran] = useState(0); // render ulang saat jendela berubah ukuran
  const [menu, setMenu] = useState(false);
  const [diam, setDiam] = useState(false);
  const awal = useRef<{ px: number; py: number; x: number; y: number; pindah: boolean } | null>(null);
  const baruDigeser = useRef(false);
  const tombol = useRef<HTMLButtonElement>(null);
  const timerDiam = useRef<number | undefined>(undefined);
  const nf = useNotif(adaBaru);
  const [daftar, setDaftar] = useState<Notif | null>(null);
  const router = useRouter();

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
    nf.tandaiDilihat();
    void nf.muat();
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
          aria-label={`Menu cepat${nf.baru ? `, ${nf.baru} notifikasi baru` : ""}. ${cd.judul}: ${cd.ket}`}
        >
          <svg width={UKURAN} height={UKURAN} viewBox="0 0 56 56" aria-hidden="true">
            <circle cx="28" cy="28" r="24" className={s.cdTrack} />
            <circle cx="28" cy="28" r="24" className={s.cdBar} strokeDasharray={C} strokeDashoffset={C * (1 - cd.pct)} />
          </svg>
          <span aria-hidden="true" className={cd.angka.length > 4 ? s.assistKecil : undefined}>{cd.angka}</span>
          {nf.baru > 0 && <i className={s.assistDot} aria-hidden="true">{nf.baru}</i>}
        </button>
        {!geser && cd.ada && (
          <div className={s.assistPop} role="status" aria-live="off">
            <b>{cd.judul}</b>
            <small>{cd.ket}</small>
            {cd.baris.map((x) => <small key={x}>{x}</small>)}
            {nf.baru > 0 && <strong className={s.assistPopNf}>{nf.baru} notifikasi baru</strong>}
            <em>Ketuk untuk notifikasi dan menu, seret untuk memindahkan</em>
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
                  <small>{cd.ket}{cd.baris.length ? ` · ${cd.baris.join(" · ")}` : ""}</small>
                </div>
                <span className={s.cdTime}>{cd.angka}</span>
              </div>
              <div className={s.amNotif}>
                <h3>Notifikasi{nf.items.length > 0 && <span>{nf.items.length}</span>}<IzinDesktop /></h3>
                <NotifList items={nf.items} onTutup={nf.sembunyikan} onLink={tutupMenu}
                  onDaftar={(x) => { setMenu(false); setDaftar(x); }} />
              </div>
              <div className={s.amGrid}>
                <Tile href="/lk/" label="LK" icon={<IconLk />} current={kini("/lk/")} onPick={tutupMenu} autoFocus />
                <Tile href="/blast/" label="Blast" icon={<IconBlast />} current={kini("/blast/")} onPick={tutupMenu} />
                <Tile href="/dashboard/" label="Dashboard" icon={<IconDashboard />} current={kini("/dashboard/")}
                  onPick={tutupMenu} />
                <Tile href="/paparan/" label="Paparan" icon={<IconPaparan />} current={kini("/paparan/")}
                  onPick={tutupMenu} />
                <Tile href="/log/" label="Log" icon={<IconLog />} current={kini("/log/")} onPick={tutupMenu}
                  titik={adaBaru} />
                {bolehCutoff ? (
                  <Tile href="/cutoff/" label="Tarik Cutoff" icon={<IconCutoff />} current={kini("/cutoff/")}
                    onPick={tutupMenu} />
                ) : (
                  <Tile label="Tarik Cutoff" icon={<IconCutoff />} kunci
                    onPick={() => { setMenu(false); onTerkunci(); }} />
                )}
                <Tile href="/forum/" label="Forum tim" icon={<IconForum />} current={kini("/forum/")} onPick={tutupMenu} />
              </div>
            </div>
          </div>
        </div>
      )}
      {daftar && (
        <DaftarFasil item={daftar} onClose={() => setDaftar(null)} onBuka={(n) => {
          setDaftar(null);
          if (path.startsWith("/lk")) window.dispatchEvent(new CustomEvent("lkm-buka-fasil", { detail: n }));
          else router.push(`/lk/?fasil=${encodeURIComponent(n)}`);
        }} />
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
