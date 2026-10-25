"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { useCountdown } from "@/lib/hooks";
import type { BarisSesi, Pengiriman, SesiDetail } from "@/lib/types";
import { Button, Chip, Notice, Spinner, statusTone } from "@/components/ui";
import s from "./today.module.css";

function mmss(detik: number) {
  return `${String(Math.floor(detik / 60)).padStart(2, "0")}:${String(detik % 60).padStart(2, "0")}`;
}

function Rows({ items, selected, onPick }: { items: BarisSesi[]; selected: string | null; onPick: (n: string) => void }) {
  return (
    <ul className={s.rows}>
      {items.map((r, i) => (
        <li key={`${r.nomor}-${r.jam}-${i}`}>
          <button type="button" className={`${s.row} ${r.nomor === selected ? s.rowSelected : ""}`}
            onClick={() => onPick(r.nomor)}>
            <span className={s.rowTime}>{r.jam || "–"}</span>
            <span className={s.rowMain}>
              <span className={s.rowName}>{r.nama_fasil}</span>
              <span className={s.rowSub}>
                {r.jumlah_sekolah ? `${r.jumlah_sekolah} sekolah` : "Sekolah belum terbaca dari LK"}
                {r.keterangan ? `. ${r.keterangan}` : ""}
              </span>
            </span>
            <Chip tone={statusTone(r.status)}>{r.status}</Chip>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function SessionPanel({
  detail,
  loading,
  kirim,
  selected,
  onPick,
  onChanged,
}: {
  detail: SesiDetail | null;
  loading: boolean;
  kirim: Pengiriman;
  selected: string | null;
  onPick: (nomor: string) => void;
  onChanged: () => void;
}) {
  const [coba, setCoba] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sisaDetik = useCountdown(kirim.running ? kirim.berikutnya_pada : null);

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

  if (!detail) {
    return (
      <section className={s.panel}>
        <div className={s.empty}>{loading ? <Spinner label="Memuat sesi" /> : "Pilih sesi di atas."}</div>
      </section>
    );
  }

  const berjalanDiSini = kirim.running && kirim.sesi === detail.no;
  const kuota = detail.kondisi.kuota;
  const persen = kirim.target ? Math.round((kirim.dicoba / kirim.target) * 100) : 0;
  const selesaiTadi = !kirim.running && kirim.selesai && kirim.sesi === detail.no;

  return (
    <section className={s.panel} aria-label={`Sesi ${detail.no}`}>
      <div className={s.panelHead}>
        <h2 className={s.panelTitle}>Sesi {detail.no}, {detail.mulai}–{detail.sampai}</h2>
        <span className={s.panelSub}>{detail.terkirim} dari {detail.kuota} terkirim</span>
      </div>

      {(detail.aktif || berjalanDiSini) && (
        <div className={s.control}>
          {!berjalanDiSini && (
            <>
              <div className={s.controlRow}>
                <Button loading={busy} onClick={start}>
                  {coba ? `Coba ${kuota} pesan` : `Kirim ${kuota} pesan`}
                </Button>
                <button type="button" className={s.toggle} aria-pressed={coba} onClick={() => setCoba(!coba)}>
                  <span className={s.knob} aria-hidden="true" />
                  Mode coba, tidak menekan kirim
                </button>
              </div>
              <span className={`${s.muted}`} style={{ fontSize: 13 }}>
                Dikirim satu per satu dengan jeda acak 45–120 detik, lalu berhenti sendiri.
              </span>
            </>
          )}
          {berjalanDiSini && (
            <>
              <div className={s.progressText}>
                <b>{kirim.coba ? "Mencoba" : "Mengirim"} {Math.min(kirim.dicoba + 1, kirim.target)} dari {kirim.target}</b>
                <span className={s.muted}>
                  {kirim.berikutnya && sisaDetik !== null
                    ? <>berikutnya ke <b style={{ color: "var(--ink)" }}>{kirim.berikutnya}</b> dalam{" "}
                        <b style={{ color: "var(--ink)", fontVariantNumeric: "tabular-nums" }}>{mmss(sisaDetik)}</b></>
                    : kirim.sekarang ? <>memproses <b style={{ color: "var(--ink)" }}>{kirim.sekarang}</b></> : "menyiapkan…"}
                </span>
              </div>
              <div className={s.bar}><span style={{ width: `${persen}%` }} /></div>
              <div className={s.controlRow}>
                <Button variant="danger" size="sm" disabled={kirim.stop_diminta} onClick={stop}>
                  {kirim.stop_diminta ? "Berhenti setelah pesan ini…" : "Berhenti setelah pesan ini"}
                </Button>
                <span className={s.muted} style={{ fontSize: 13 }}>
                  Biarkan jendela WhatsApp tetap terbuka.
                </span>
              </div>
            </>
          )}
          {error && <Notice tone="bad" title="Belum bisa mulai">{error}</Notice>}
        </div>
      )}

      {!detail.aktif && !berjalanDiSini && detail.kondisi.sesi === detail.no && (
        <div className={s.control}><span style={{ fontSize: 14 }}>{detail.kondisi.judul}</span></div>
      )}

      {selesaiTadi && kirim.berhenti_karena && (
        <div style={{ padding: "14px 20px 0" }}>
          <Notice tone={kirim.berhenti_karena.startsWith("Dihentikan") ? "info" : "warn"} title="Pengiriman berhenti">
            {kirim.berhenti_karena}
          </Notice>
        </div>
      )}

      {detail.sudah.length > 0 && (
        <>
          <div className={s.groupLabel}>Sudah diproses ({detail.sudah.length})</div>
          <Rows items={detail.sudah} selected={selected} onPick={onPick} />
        </>
      )}
      {detail.akan.length > 0 && (
        <>
          <div className={s.groupLabel}>{detail.aktif ? "Urutan kirim berikutnya" : "Perkiraan yang akan dikirimi"} ({detail.akan.length})</div>
          <Rows items={detail.akan} selected={selected} onPick={onPick} />
        </>
      )}
      {detail.sudah.length === 0 && detail.akan.length === 0 && (
        <div className={s.empty}>Belum ada kiriman di sesi ini.</div>
      )}
    </section>
  );
}
