"use client";

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { Button, Spinner } from "@/components/ui";
import s from "./backup.module.css";

type Item = { nama: string; link: string; cutoff: string; sumber: string; jenis: string; sesi: string; ukuran: number };
type Slot = { kunci: string; judul: string; ket: string; target: string; file: Item | null; link: string };
type Minggu = { week: number; link: string; senin: string; slot: Slot[] };
type Info = {
  folder: { id: string; nama: string; link: string } | null; izin: boolean; izin_status: string; izin_error: string;
  otomatis: boolean; minggu: Minggu[]; error: string; sesi_hari_ini: number;
  tertunda: { waktu: string; week: number; oleh: string } | null;
  status: { jalan: boolean; langkah: string; error: string;
    hasil: null | { week: number; file: { nama: string; link: string }[]; waktu: string; sumber: string; lewati?: string } };
};

const TUJUAN = [
  { v: "mingguan", l: "Mingguan" },
  { v: "sesi1", l: "Sesi 1" },
  { v: "sesi2", l: "Sesi 2" },
] as const;

const tglJam = (t: string) => {
  const d = new Date(t.replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? t
    : `${d.toLocaleDateString("id-ID", { weekday: "short", day: "2-digit", month: "2-digit" })} ${t.slice(11, 16)}`;
};

/** Backup tab WEEK ke Google Drive: atur sekali (izin + folder), lalu jalan sendiri setiap cutoff. */
export function BackupDrive({ pemicu }: { pemicu: string }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [gagalMuat, setGagalMuat] = useState("");
  const [link, setLink] = useState("");
  const [tujuan, setTujuan] = useState<(typeof TUJUAN)[number]["v"] | null>(null);
  const [busy, setBusy] = useState("");
  const [pesan, setPesan] = useState("");
  const [pilih, setPilih] = useState<number | null>(null);

  const muat = useCallback(async () => {
    try {
      setInfo(await api<Info>("/api/cutoff/backup"));
      setGagalMuat("");
    } catch (e) {
      setGagalMuat(e instanceof Error ? e.message : String(e));
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat, pemicu]);
  usePolling(muat, 2500, !!info && (info.status.jalan || info.izin_status === "running"));
  // cutoff baru selesai: backup mulai di latar beberapa detik kemudian
  usePolling(muat, 10000, !!info && !info.status.jalan && !!info.tertunda && info.otomatis && !!info.folder && info.izin);

  async function aksi(nama: string, url: string, body: unknown = {}) {
    setBusy(nama); setPesan("");
    try {
      setInfo(await post<Info>(url, body));
    } catch (e) {
      setPesan(e instanceof Error ? e.message : String(e));
    } finally { setBusy(""); }
  }

  if (!info) {
    return (
      <section className={s.card}>
        <div className={s.head}><h2>Backup ke Google Drive</h2></div>
        {gagalMuat ? <p className={s.bad}>{gagalMuat}</p> : <p className={s.muted}><Spinner /> Memuat…</p>}
      </section>
    );
  }

  const siap = !!(info.folder && info.izin);
  const st = info.status;
  const minggu = info.minggu.find((m) => m.week === pilih) ?? info.minggu[0];
  const tujuanAktif = tujuan ?? (info.sesi_hari_ini === 2 ? "sesi2" : "sesi1");

  return (
    <section className={s.card} aria-labelledby="backup-judul">
      <div className={s.head}>
        <div>
          <h2 id="backup-judul">Backup ke Google Drive</h2>
          <p className={s.sub}>Isi tab WEEK disimpan sebagai CSV setiap ada cutoff baru.</p>
        </div>
        {siap && (
          <label className={s.saklar}>
            <input type="checkbox" checked={info.otomatis} disabled={!!busy}
              onChange={(e) => void aksi("otomatis", "/api/cutoff/backup/otomatis", { aktif: e.target.checked })} />
            <span>Otomatis setiap cutoff</span>
          </label>
        )}
      </div>

      {!siap && (
        <ol className={s.atur}>
          <li className={info.izin ? s.aturBeres : ""}>
            <span className={s.aturNo}>{info.izin ? "✓" : 1}</span>
            <div>
              <b>Izin Google Drive</b>
              <p>Pakai akun yang bisa mengedit folder backup (biasanya akun pemilik folder). Cukup sekali di laptop ini.</p>
              {!info.izin && (
                <Button size="sm" variant="secondary" loading={busy === "izin" || info.izin_status === "running"}
                  onClick={() => void aksi("izin", "/api/cutoff/backup/izin")}>
                  {info.izin_status === "running" ? "Menunggu izin di browser…" : "Beri izin Google Drive"}
                </Button>
              )}
              {info.izin_error && <p className={s.bad}>{info.izin_error}</p>}
            </div>
          </li>
          <li className={info.folder ? s.aturBeres : ""}>
            <span className={s.aturNo}>{info.folder ? "✓" : 2}</span>
            <div>
              <b>Folder backup</b>
              {info.folder ? <p>{info.folder.nama}</p> : (
                <>
                  <p>Tempel link folder Drive. Folder WEEK, Sesi 1, dan Sesi 2 dibuat otomatis di dalamnya.</p>
                  <div className={s.baris}>
                    <input className={s.input} type="url" placeholder="https://drive.google.com/drive/folders/…"
                      value={link} onChange={(e) => setLink(e.target.value)} aria-label="Link folder Drive" />
                    <Button size="sm" disabled={!info.izin || !link.trim()} loading={busy === "folder"}
                      onClick={() => void aksi("folder", "/api/cutoff/backup/folder", { link })}>Simpan</Button>
                  </div>
                  {!info.izin && <p className={s.muted}>Beri izin Drive dulu, supaya folder bisa dicek.</p>}
                </>
              )}
            </div>
          </li>
        </ol>
      )}

      {siap && (
        <>
          <Alur />

          {info.minggu.length > 1 && (
            <div className={s.weekTab} role="tablist" aria-label="Pilih WEEK">
              {info.minggu.map((m) => (
                <button key={m.week} type="button" role="tab" aria-selected={m.week === minggu?.week}
                  onClick={() => setPilih(m.week)}>WEEK {m.week}</button>
              ))}
            </div>
          )}
          {minggu ? <Peta m={minggu} /> : <p className={s.muted}>Belum ada backup.</p>}
          {info.error && <p className={s.bad}>Daftar backup tidak bisa dibaca: {info.error}</p>}

          <div className={s.status} aria-live="polite">
            {st.jalan ? (
              <p className={s.muted}><Spinner /> {st.langkah || "Membuat backup"}…</p>
            ) : st.error ? (
              <p className={s.bad}>Backup terakhir gagal: {st.error}</p>
            ) : info.tertunda ? (
              <p className={s.muted}>Cutoff {tglJam(info.tertunda.waktu)} (WEEK {info.tertunda.week}) belum di-backup.
                {info.otomatis ? " Akan diambil dalam 15 menit." : " Mode otomatis mati."}</p>
            ) : st.hasil?.file.length ? (
              <p className={s.ok}>✓ {st.hasil.file.map((f) => f.nama).join(" dan ")} tersimpan ({st.hasil.sumber}, {tglJam(st.hasil.waktu)}).</p>
            ) : st.hasil?.lewati ? (
              <p className={s.muted}>{st.hasil.lewati} Tidak ada yang perlu di-backup.</p>
            ) : (
              <p className={s.ok}>✓ Cutoff terakhir sudah di-backup.</p>
            )}
          </div>

          <div className={s.manual}>
            <span className={s.manualLabel}>Backup manual ke</span>
            <div className={s.pilih} role="radiogroup" aria-label="Tujuan backup manual">
              {TUJUAN.map((t) => (
                <button key={t.v} type="button" role="radio" aria-checked={tujuanAktif === t.v} onClick={() => setTujuan(t.v)}>{t.l}</button>
              ))}
            </div>
            <Button size="sm" loading={busy === "jalan" || st.jalan} disabled={st.jalan}
              onClick={() => void aksi("jalan", "/api/cutoff/backup/jalan", { tujuan: tujuanAktif })}>Backup sekarang</Button>
          </div>
          <p className={s.muted}>Backup manual menimpa file di slot itu dengan isi tab WEEK saat ini.</p>

          <details className={s.lain}>
            <summary>Pengaturan</summary>
            <p>Folder: <a href={info.folder!.link} target="_blank" rel="noreferrer">{info.folder!.nama}</a>.
              Cutoff dari laptop lain ikut di-backup selama laptop ini menyala (dicek tiap 15 menit).</p>
            <div className={s.baris}>
              <input className={s.input} type="url" placeholder="Link folder baru" value={link}
                onChange={(e) => setLink(e.target.value)} aria-label="Link folder Drive baru" />
              <Button size="sm" variant="secondary" disabled={!link.trim()} loading={busy === "folder"}
                onClick={() => void aksi("folder", "/api/cutoff/backup/folder", { link })}>Ganti folder</Button>
            </div>
            <Button size="sm" variant="ghost" loading={busy === "lepas"}
              onClick={() => void aksi("lepas", "/api/cutoff/backup/lepas")}>Cabut izin Drive</Button>
          </details>
        </>
      )}
      {pesan && <p className={s.bad}>{pesan}</p>}
    </section>
  );
}

/** Ringkasan aturan: ke mana file masuk. */
function Alur() {
  return (
    <div className={s.alur} aria-label="Aturan backup">
      <div><b>Mingguan</b><span>cutoff pertama minggu itu (Senin)</span></div>
      <div><b>Sesi 1</b><span>cutoff hari terakhir sesi (Rabu)</span></div>
      <div><b>Sesi 2</b><span>cutoff hari terakhir sesi (Sabtu)</span></div>
    </div>
  );
}

const tglPendek = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("id-ID", { weekday: "short", day: "2-digit", month: "2-digit" });

function tambahHari(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return d.toLocaleDateString("sv-SE");
}

/** Satu WEEK = tiga slot berurutan (Mingguan → Sesi 1 → Sesi 2), masing-masing satu file. */
function Peta({ m }: { m: Minggu }) {
  const hariIni = new Date().toLocaleDateString("sv-SE");
  const lewatMinggu = hariIni > tambahHari(m.senin, 6);
  return (
    <div className={s.peta}>
      <div className={s.petaHead}>
        <b>WEEK {m.week}</b>
        {m.link && <a href={m.link} target="_blank" rel="noreferrer">Buka folder ↗</a>}
      </div>
      <ol className={s.slotList}>
        {m.slot.map((x) => {
          const mingguan = x.kunci === "mingguan";
          const st = x.file ? "ada"
            : mingguan ? (lewatMinggu ? "lewat" : x.target <= hariIni ? "hari_ini" : "nanti")
            : x.target === hariIni ? "hari_ini" : x.target < hariIni ? "lewat" : "nanti";
          const teks = mingguan
            ? (st === "lewat" ? "Tidak ada backup minggu itu" : "Menunggu cutoff pertama")
            : st === "hari_ini" ? "Menunggu cutoff hari ini" : st === "lewat" ? "Tidak ada cutoff hari itu" : "Belum waktunya";
          return (
            <li key={x.kunci} className={`${s.slot} ${s[`slot_${st}`]}`}>
              <div className={s.slotHead}>
                <span className={s.slotIkon} aria-hidden="true">{x.file ? "✓" : st === "hari_ini" ? "•" : ""}</span>
                <div>
                  <b>{x.judul}</b>
                  <small>{x.ket} · {tglPendek(x.target)}</small>
                </div>
                {x.link && <a className={s.slotFolder} href={x.link} target="_blank" rel="noreferrer"
                  aria-label={`Buka folder ${x.judul}`}>↗</a>}
              </div>
              {x.file ? (
                <a className={s.slotFile} href={x.file.link} target="_blank" rel="noreferrer" title={x.file.nama}>
                  Cutoff {tglJam(x.file.cutoff)}{x.file.sumber === "manual" ? " · manual" : ""}
                  {x.file.ukuran ? <span> · {(x.file.ukuran / 1048576).toFixed(1)} MB</span> : null}
                </a>
              ) : <p className={s.kosong}>{teks}</p>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
