"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { KalenderLog, Perubahan } from "@/lib/types";
import s from "./rekap.module.css";

export const KUNCI_DILIHAT = "lkm-perubahan-dilihat"; // dibaca juga oleh AppShell

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];
const HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const KOLOM = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dariIso = (x: string) => {
  const [y, m, d] = x.split("-").map(Number);
  return new Date(y, m - 1, d || 1);
};
const jamMenit = (w: string) => w.slice(11, 16).replace(":", ".");

function tingkat(n: number) {
  if (!n) return "";
  if (n <= 2) return s.calL1;
  if (n <= 5) return s.calL2;
  return s.calL3;
}

/** Log perubahan Broadcast & LK: kalender per hari, lalu isi hari itu dikelompokkan per sesi. */
export function LogPerubahan() {
  const [kal, setKal] = useState<KalenderLog | null>(null);
  const [bulan, setBulan] = useState<string | null>(null); // YYYY-MM
  const [pilih, setPilih] = useState<string | null>(null); // YYYY-MM-DD
  const [items, setItems] = useState<Perubahan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buka, setBuka] = useState<number | null>(null);
  const kartu = useRef<HTMLElement>(null);

  const muatBulan = useCallback(async (b?: string) => {
    try {
      const k = await api<KalenderLog>(`/api/perubahan/kalender${b ? `?bulan=${b}` : ""}`);
      setKal(k);
      setBulan(k.bulan);
      return k;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);

  // Muat pertama: bulan ini, pilih hari ini (atau hari terakhir yang ada catatannya)
  useEffect(() => {
    void (async () => {
      const k = await muatBulan();
      if (!k) return;
      const adaHariIni = k.hari.some((h) => h.tanggal === k.hari_ini);
      setPilih(adaHariIni || !k.hari.length ? k.hari_ini : k.hari[k.hari.length - 1].tanggal);
    })();
    // Tandai sudah dilihat (titik merah di menu hilang)
    api<{ items: Perubahan[] }>("/api/perubahan?batas=1")
      .then((r) => {
        try {
          if (r.items[0]) localStorage.setItem(KUNCI_DILIHAT, String(r.items[0].id));
          window.dispatchEvent(new Event("lkm-perubahan-dilihat"));
        } catch {
          /* penanda "sudah dilihat" hanya kenyamanan */
        }
      })
      .catch(() => {});
    if (window.location.hash === "#perubahan") kartu.current?.scrollIntoView({ block: "start" });
  }, [muatBulan]);

  useEffect(() => {
    if (!pilih) return;
    let batal = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItems(null);
    setBuka(null);
    api<{ items: Perubahan[] }>(`/api/perubahan?tanggal=${pilih}`)
      .then((r) => { if (!batal) setItems(r.items); })
      .catch((e) => { if (!batal) setError(e.message); });
    return () => { batal = true; };
  }, [pilih]);

  const jumlah = useMemo(() => new Map((kal?.hari ?? []).map((h) => [h.tanggal, h.broadcast + h.lk])), [kal]);

  const sel = useMemo(() => {
    if (!bulan) return [];
    const awal = dariIso(bulan);
    const geser = (awal.getDay() + 6) % 7; // Senin = 0
    const nHari = new Date(awal.getFullYear(), awal.getMonth() + 1, 0).getDate();
    const out: (string | null)[] = Array(geser).fill(null);
    for (let d = 1; d <= nHari; d++) out.push(iso(new Date(awal.getFullYear(), awal.getMonth(), d)));
    while (out.length % 7) out.push(null);
    return out;
  }, [bulan]);

  const grup = useMemo(() => {
    const g = new Map<number, { label: string; items: Perubahan[] }>();
    for (const x of [...(items ?? [])].sort((a, b) => a.waktu.localeCompare(b.waktu))) {
      const e = g.get(x.sesi) ?? { label: x.sesi_label, items: [] };
      e.items.push(x);
      g.set(x.sesi, e);
    }
    return [...g.entries()].sort((a, b) => a[0] - b[0]).map(([no, v]) => ({ no, ...v }));
  }, [items]);

  if (!kal || !bulan) {
    return (
      <section className={`${s.card} ${s.logCard}`} id="perubahan" ref={kartu}>
        <div className={s.cardHead}><h2>Perubahan data</h2></div>
        <p className={s.note}>{error ?? "Memuat log…"}</p>
      </section>
    );
  }

  const bln = dariIso(bulan);
  const bulanIni = kal.hari_ini.slice(0, 7);
  const bisaMundur = !!kal.paling_awal && kal.paling_awal.slice(0, 7) < bulan;
  const bisaMaju = bulan < bulanIni;
  const pindah = (n: number) => void muatBulan(iso(new Date(bln.getFullYear(), bln.getMonth() + n, 1)).slice(0, 7));
  const hariPilih = pilih ? dariIso(pilih) : null;
  const totalBulan = kal.hari.reduce((a, h) => a + h.broadcast + h.lk, 0);

  return (
    <section className={`${s.card} ${s.logCard}`} aria-labelledby="h-log" id="perubahan" data-tour="log" ref={kartu}>
      <div className={s.cardHead}>
        <h2 id="h-log">Perubahan data</h2>
        <span>Dicek setiap Broadcast dan LK dibaca ulang (paling lama 5–10 menit). Disimpan 90 hari.</span>
      </div>
      {error && <p className={s.note}>{error}</p>}

      <div className={s.logGrid}>
        <div className={s.cal}>
          <div className={s.calHead}>
            <button type="button" onClick={() => pindah(-1)} disabled={!bisaMundur} aria-label="Bulan sebelumnya">‹</button>
            <b>{BULAN[bln.getMonth()]} {bln.getFullYear()}</b>
            <button type="button" onClick={() => pindah(1)} disabled={!bisaMaju} aria-label="Bulan berikutnya">›</button>
          </div>
          <div className={s.calGrid}>
            {KOLOM.map((k) => <span key={k} className={s.calDow} aria-hidden="true">{k}</span>)}
            {sel.map((t, i) => {
              if (!t) return <span key={`k${i}`} />;
              const n = jumlah.get(t) ?? 0;
              const nanti = t > kal.hari_ini;
              return (
                <button key={t} type="button" disabled={nanti}
                  className={`${s.calDay} ${tingkat(n)} ${t === kal.hari_ini ? s.calToday : ""} ${t === pilih ? s.calSel : ""}`}
                  aria-pressed={t === pilih} onClick={() => setPilih(t)}
                  aria-label={`${Number(t.slice(8))} ${BULAN[bln.getMonth()]}, ${n ? `${n} perubahan` : "tidak ada perubahan"}`}>
                  <span>{Number(t.slice(8))}</span>
                  {n > 0 && <small>{n}</small>}
                </button>
              );
            })}
          </div>
          <p className={s.calNote}>
            {totalBulan ? `${totalBulan} perubahan bulan ini.` : "Belum ada perubahan bulan ini."} Makin gelap = makin banyak.
          </p>
        </div>

        <div className={s.day}>
          {hariPilih && (
            <div className={s.dayHead}>
              <b>{HARI[hariPilih.getDay()]}, {hariPilih.getDate()} {BULAN[hariPilih.getMonth()]}</b>
              <span>{items ? (items.length ? `${items.length} perubahan` : "") : "Memuat…"}</span>
            </div>
          )}
          {items && items.length === 0 && (
            <p className={s.note}>
              {pilih === kal.hari_ini
                ? "Belum ada perubahan hari ini. Catatan muncul begitu Broadcast atau LK berubah dari bacaan sebelumnya."
                : "Tidak ada perubahan di hari ini."}
            </p>
          )}
          {grup.map((g) => (
            <div key={g.no} className={s.sesiGrup}>
              <h3>{g.label}<span>{g.items.length}</span></h3>
              <ul className={s.log}>
                {g.items.map((x) => (
                  <li key={x.id}>
                    <button type="button" className={s.logRow} aria-expanded={buka === x.id}
                      onClick={() => setBuka(buka === x.id ? null : x.id)}>
                      <span className={s.logTime}>{jamMenit(x.waktu)}</span>
                      <span className={`${s.logSrc} ${x.sumber === "lk" ? s.logLk : s.logBc}`}>{x.judul}</span>
                      <span className={s.logSum}>{x.ringkasan}</span>
                      <span className={s.logMore}>{buka === x.id ? "Tutup" : `${x.rincian.length} rincian`}</span>
                    </button>
                    {buka === x.id && (
                      <ul className={s.logDetail}>
                        {x.rincian.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
