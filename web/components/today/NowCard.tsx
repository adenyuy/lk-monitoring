"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { useCountdown } from "@/lib/hooks";
import type { Today } from "@/lib/types";
import { Button, Notice } from "@/components/ui";
import s from "./today.module.css";

function mmss(detik: number) {
  return `${String(Math.floor(detik / 60)).padStart(2, "0")}:${String(detik % 60).padStart(2, "0")}`;
}

function durasi(menit: number) {
  const j = Math.floor(menit / 60);
  const m = menit % 60;
  if (!j) return `${m} menit`;
  return m ? `${j} jam ${m} menit` : `${j} jam`;
}

/** Kartu utama: apa yang terjadi sekarang dan satu tombol untuk bertindak. */
export function NowCard({ today, onChanged }: { today: Today; onChanged: () => void }) {
  const [coba, setCoba] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kirim = today.pengiriman;
  const k = today.kondisi;
  const sisaDetik = useCountdown(kirim.running ? kirim.berikutnya_pada : null);

  const fokusNo = kirim.running ? kirim.sesi : today.sesi_aktif ?? k.sesi_berikutnya;
  const fokus = today.sesi.find((x) => x.no === fokusNo) ?? null;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/send/start", { coba });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    try {
      await post("/api/send/stop");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // Titik per slot kuota: terisi = terkirim, berdenyut = sedang diproses, garis = direncanakan
  const dots = fokus
    ? Array.from({ length: fokus.kuota }, (_, i) => {
        const terkirimSesi = fokus.terkirim;
        if (i < terkirimSesi) return "done";
        if (kirim.running && kirim.sesi === fokus.no && i === terkirimSesi) return "now";
        if (i < terkirimSesi + fokus.perkiraan) return "plan";
        return "empty";
      })
    : [];

  let sub = "";
  if (kirim.running) sub = "Biarkan jendela WhatsApp tetap terbuka.";
  else if (today.sisa_menit_sesi !== null && k.bisa_kirim) sub = `Sisa waktu sesi ${durasi(today.sisa_menit_sesi)}.`;
  else if (today.menit_ke_berikutnya !== null) sub = `Dimulai dalam ${durasi(today.menit_ke_berikutnya)}.`;

  const hariPersen = Math.min(100, (today.terkirim_hari_ini / Math.max(1, today.batas_harian)) * 100);

  return (
    <section className={`${s.now} ${kirim.running ? s.nowLive : ""}`} aria-label="Sekarang">
      <div className={s.nowMain}>
        <div className={s.nowLabel}>
          {kirim.running && <span className={s.liveDot} aria-hidden="true" />}
          {kirim.running ? (kirim.coba ? "Sedang mencoba" : "Sedang mengirim") : "Sekarang"}, {today.jam_sekarang}
        </div>
        <h1 className={s.nowTitle}>
          {kirim.running
            ? `${kirim.coba ? "Mencoba" : "Mengirim"} ${Math.min(kirim.dicoba + 1, kirim.target)} dari ${kirim.target} pesan`
            : k.judul}
        </h1>
        {sub && <p className={s.nowSub}>{sub}</p>}

        {fokus && (
          <div className={s.dotsWrap}>
            <div className={s.dots} role="img"
              aria-label={`Sesi ${fokus.no}: ${fokus.terkirim} dari ${fokus.kuota} terkirim`}>
              {dots.map((d, i) => <span key={i} className={`${s.dot} ${s[`dot_${d}`]}`} />)}
            </div>
            <span className={s.dotsText}>
              Sesi {fokus.no}, {fokus.terkirim} dari {fokus.kuota} terkirim
            </span>
          </div>
        )}

        {kirim.running && (
          <p className={s.nowNext}>
            {kirim.berikutnya && sisaDetik !== null ? (
              <>Berikutnya ke <b>{kirim.berikutnya}</b> dalam <b className={s.tab}>{mmss(sisaDetik)}</b></>
            ) : kirim.sekarang ? (
              <>Memproses <b>{kirim.sekarang}</b></>
            ) : "Menyiapkan…"}
          </p>
        )}

        <div className={s.nowActions}>
          {!kirim.running && k.bisa_kirim && (
            <>
              <Button loading={busy} onClick={start} className={s.cta}>
                {coba ? `Coba ${k.kuota} pesan` : `Kirim ${k.kuota} pesan`}
              </Button>
              <button type="button" className={s.toggle} aria-pressed={coba} onClick={() => setCoba(!coba)}>
                <span className={s.knob} aria-hidden="true" />
                Mode coba, tidak menekan kirim
              </button>
            </>
          )}
          {kirim.running && (
            <Button variant="danger" size="sm" disabled={kirim.stop_diminta} onClick={stop}>
              {kirim.stop_diminta ? "Berhenti setelah pesan ini…" : "Berhenti setelah pesan ini"}
            </Button>
          )}
        </div>
        {!kirim.running && k.bisa_kirim && (
          <p className={s.hint}>Dikirim satu per satu dengan jeda acak 45–120 detik, lalu berhenti sendiri.</p>
        )}
        {error && <Notice tone="bad" title="Belum bisa mulai">{error}</Notice>}
        {!kirim.running && kirim.selesai && kirim.berhenti_karena && (
          <Notice tone={kirim.berhenti_karena.startsWith("Dihentikan") ? "info" : "warn"} title="Pengiriman berhenti">
            {kirim.berhenti_karena}
          </Notice>
        )}
      </div>

      <dl className={s.nowStats}>
        <div>
          <dt>Terkirim hari ini</dt>
          <dd>{today.terkirim_hari_ini}<small> / {today.batas_harian}</small></dd>
          <div className={s.meter} aria-hidden="true"><span style={{ width: `${hariPersen}%` }} /></div>
        </div>
        <div>
          <dt>Dibalas</dt>
          <dd>{today.dibalas_hari_ini}</dd>
        </div>
        <div>
          <dt>Belum dikirim</dt>
          <dd>{today.belum_dikirim}<small> / {today.total_fasil} fasil</small></dd>
        </div>
      </dl>
    </section>
  );
}
