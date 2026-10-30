"use client";

import { useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import type { EskalasiInfo, SekolahLk } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import s from "./eskalasi.module.css";

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const tgl = (iso: string) => (/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${Number(iso.slice(8))} ${BULAN[Number(iso.slice(5, 7)) - 1]}` : iso);

function toneStatus(st: string) {
  const x = st.toLowerCase();
  if (x === "selesai") return "ok" as const;
  if (x === "proses") return "info" as const;
  if (x === "ditunda") return "warn" as const;
  return "muted" as const;
}

type Teman = { nama: string; nomor: string };

/** Popup "Butuh bantuan": tanya teman PIC lewat WhatsApp, atau eskalasi ke stream lain lewat LK Eskalasi. */
export function BantuanDialog({ namaFasil, sekolah, onClose }: { namaFasil: string; sekolah: SekolahLk[]; onClose: () => void }) {
  const [tab, setTab] = useState<"teman" | "eskalasi">("teman");
  const tutupRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    tutupRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopImmediatePropagation(); onClose(); } // jangan ikut menutup panel fasil
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="esk-judul">
        <header className={s.head}>
          <div>
            <h2 id="esk-judul">Butuh bantuan</h2>
            <p>Pertanyaan fasil {namaFasil} belum bisa Anda jawab? Tanya teman dulu. Kasus unik yang harus dijawab
              stream lain? Catat di LK Eskalasi.</p>
          </div>
          <button ref={tutupRef} type="button" className={s.close} onClick={onClose} aria-label="Tutup">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        <div className={s.tabs} role="tablist">
          <button type="button" role="tab" aria-selected={tab === "teman"} onClick={() => setTab("teman")}>Tanya teman PIC</button>
          <button type="button" role="tab" aria-selected={tab === "eskalasi"} onClick={() => setTab("eskalasi")}>Eskalasi ke stream lain</button>
        </div>
        <div className={s.body}>
          {tab === "teman" ? <TanyaTeman namaFasil={namaFasil} /> : <FormEskalasi sekolah={sekolah} />}
        </div>
      </div>
    </div>
  );
}

/** Teman petugas dari tab Kontak PIC (sheet Broadcast). Chat dibuka di jendela WhatsApp aplikasi. */
function TanyaTeman({ namaFasil }: { namaFasil: string }) {
  const [kontak, setKontak] = useState<Teman[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cari, setCari] = useState("");
  const [buka, setBuka] = useState<string | null>(null);
  const [info, setInfo] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);

  useEffect(() => {
    api<{ kontak: Teman[] }>("/api/eskalasi/kontak")
      .then((d) => setKontak(d.kontak))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function chat(t: Teman) {
    setBuka(t.nomor);
    setInfo(null);
    const draf = `Halo ${t.nama.split(" ")[0]}, mau tanya soal fasil ${namaFasil}: `;
    let disalin = false;
    try {
      await navigator.clipboard.writeText(draf);
      disalin = true;
    } catch {
      /* clipboard bisa ditolak browser; chat tetap dibuka */
    }
    try {
      await post(`/api/wa/open/${t.nomor}`);
      setInfo({ tone: "ok", teks: `Chat ${t.nama} terbuka di jendela WhatsApp.${disalin ? " Draf pembuka sudah disalin, tempel dengan Ctrl+V." : ""}` });
    } catch (e) {
      setInfo({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBuka(null);
    }
  }

  if (error) return <Notice tone="bad" title="Kontak PIC tidak terbaca">{error}</Notice>;
  if (!kontak) return <div className={s.muted}><Spinner label="Memuat" /> Membaca Kontak PIC…</div>;
  const q = cari.trim().toLowerCase();
  const daftar = kontak.filter((k) => !q || k.nama.toLowerCase().includes(q));
  return (
    <>
      <label className={s.field}>
        <span className={s.label}>Cari teman</span>
        <input type="search" value={cari} onChange={(e) => setCari(e.target.value)} placeholder="Ketik nama" />
      </label>
      {info && <Notice tone={info.tone}>{info.teks}</Notice>}
      <ul className={s.teman}>
        {daftar.map((k) => (
          <li key={k.nomor}>
            <span className={s.avatar} aria-hidden="true">{k.nama.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span>
            <b>{k.nama}</b>
            <Button variant="secondary" size="sm" loading={buka === k.nomor} disabled={buka !== null} onClick={() => void chat(k)}>
              Chat
            </Button>
          </li>
        ))}
        {daftar.length === 0 && <li className={s.muted}>Tidak ada nama yang cocok.</li>}
      </ul>
      <p className={s.hint}>Nomor dari tab Kontak PIC di sheet Broadcast.</p>
    </>
  );
}

/** Pasang link LK Eskalasi. Admin: berlaku untuk seluruh tim (disimpan di sheet Akses). */
function PasangLink({ onSelesai }: { onSelesai: () => void }) {
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pasang() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/eskalasi/link", { link });
      onSelesai();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.pasang}>
      <Notice tone="warn" title="Link LK Eskalasi belum dipasang">
        Tempel link sheet LK Eskalasi di bawah. Bila akun Anda admin, link ini langsung berlaku untuk seluruh tim.
      </Notice>
      <label className={s.field}>
        <span className={s.label}>Link sheet LK Eskalasi</span>
        <input type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/…" />
      </label>
      {error && <Notice tone="bad" title="Belum bisa dipasang">{error}</Notice>}
      <div className={s.actions}>
        <Button loading={busy} disabled={busy || link.trim().length < 10} onClick={pasang}>Pasang link</Button>
      </div>
    </div>
  );
}

function FormEskalasi({ sekolah }: { sekolah: SekolahLk[] }) {
  const [info, setInfo] = useState<EskalasiInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pilih, setPilih] = useState<string[]>([]);
  const [masalah, setMasalah] = useState("");
  const [ket, setKet] = useState("");
  const [tim, setTim] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);
  const [versi, setVersi] = useState(0);
  const npsn = sekolah.map((x) => x.npsn).join(",");

  useEffect(() => {
    let batal = false;
    api<EskalasiInfo>(`/api/eskalasi?npsn=${encodeURIComponent(npsn)}`)
      .then((d) => { if (!batal) { setInfo(d); setError(null); } })
      .catch((e) => { if (!batal) setError(e instanceof Error ? e.message : String(e)); });
    return () => { batal = true; };
  }, [npsn, versi]);

  const ganti = (daftar: string[], v: string) => (daftar.includes(v) ? daftar.filter((x) => x !== v) : [...daftar, v]);
  const siap = pilih.length > 0 && ket.trim() !== "" && tim.length > 0;

  async function catat() {
    setBusy(true);
    setHasil(null);
    try {
      const r = await post<{ ditulis: { npsn: string }[]; dilewati: string[] }>("/api/eskalasi",
        { npsn: pilih, keterangan: ket, permasalahan: masalah, tim });
      setHasil({
        tone: "ok",
        teks: `Tercatat untuk ${r.ditulis.length} sekolah, ditujukan ke ${tim.join(", ")}.`
          + (r.dilewati.length ? ` ${r.dilewati.length} sekolah tidak ada di LK Eskalasi: ${r.dilewati.join(", ")}.` : ""),
      });
      setPilih([]);
      setKet("");
      setMasalah("");
      setTim([]);
      setInfo(await api<EskalasiInfo>(`/api/eskalasi?npsn=${encodeURIComponent(npsn)}`));
    } catch (e) {
      setHasil({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  const namaSekolah = (n: string) => sekolah.find((x) => x.npsn === n)?.nama;

  if (info?.perlu_link) return <PasangLink onSelesai={() => setVersi((v) => v + 1)} />;

  return (
    <>
          {error && <Notice tone="bad" title="LK Eskalasi tidak bisa dibuka">{error}</Notice>}
          {!info && !error && <div className={s.muted}><Spinner label="Memuat" /> Membaca LK Eskalasi…</div>}

          {info?.opsi && (
            <>
              <fieldset className={s.field}>
                <legend>Sekolah <span>{pilih.length} dipilih</span></legend>
                <div className={s.sekolah}>
                  {sekolah.map((x) => (
                    <label key={x.npsn} className={pilih.includes(x.npsn) ? s.on : ""}>
                      <input type="checkbox" checked={pilih.includes(x.npsn)} onChange={() => setPilih(ganti(pilih, x.npsn))} />
                      <span><b>{x.nama}</b><small>NPSN {x.npsn}</small></span>
                    </label>
                  ))}
                </div>
                {sekolah.length > 1 && (
                  <button type="button" className={s.linkBtn}
                    onClick={() => setPilih(pilih.length === sekolah.length ? [] : sekolah.map((x) => x.npsn))}>
                    {pilih.length === sekolah.length ? "Kosongkan pilihan" : "Pilih semua sekolah"}
                  </button>
                )}
              </fieldset>

              <label className={s.field}>
                <span className={s.label}>Permasalahan</span>
                <select value={masalah} onChange={(e) => setMasalah(e.target.value)}>
                  <option value="">Pilih kelompok permasalahan</option>
                  {info.opsi.permasalahan.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </label>

              <label className={s.field}>
                <span className={s.label}>Keterangan permasalahan</span>
                <textarea rows={4} value={ket} maxLength={2000} onChange={(e) => setKet(e.target.value)}
                  placeholder="Jelaskan masalahnya dan apa yang sudah dicoba, supaya tim terkait bisa langsung menjawab." />
              </label>

              <fieldset className={s.field}>
                <legend>Tim tujuan eskalasi</legend>
                <div className={s.tim}>
                  {info.opsi.tim.map((t) => (
                    <label key={t} className={tim.includes(t) ? s.on : ""}>
                      <input type="checkbox" checked={tim.includes(t)} onChange={() => setTim(ganti(tim, t))} />
                      {t}
                    </label>
                  ))}
                </div>
              </fieldset>

              {hasil && <Notice tone={hasil.tone} title={hasil.tone === "ok" ? "Tersimpan" : "Belum tersimpan"}>{hasil.teks}</Notice>}

              <div className={s.actions}>
                <Button loading={busy} disabled={!siap || busy} onClick={catat}>
                  {busy ? "Mencatat…" : "Catat ke LK Eskalasi"}
                </Button>
                <span className={s.hint}>
                  {siap ? "Tanggal awal diisi hari ini, status Belum Ditindaklanjuti." : "Pilih sekolah, isi keterangan, dan centang minimal satu tim."}
                </span>
              </div>

              <section className={s.riwayat} aria-labelledby="esk-riwayat">
                <h3 id="esk-riwayat">Sudah dieskalasi <span>{info.eskalasi.length}</span></h3>
                {info.eskalasi.length === 0 ? (
                  <p className={s.muted}>Belum ada eskalasi untuk sekolah fasil ini.</p>
                ) : (
                  <ul>
                    {info.eskalasi.map((e) => (
                      <li key={e.baris}>
                        <div className={s.rHead}>
                          <b>{namaSekolah(e.npsn) ?? e.nama}</b>
                          <Chip tone={toneStatus(e.status)}>{e.status || "Belum ada status"}</Chip>
                        </div>
                        <p>{e.keterangan || "Tanpa keterangan"}</p>
                        <small>
                          {[e.permasalahan, e.tgl_awal && `sejak ${tgl(e.tgl_awal)}`, e.tgl_selesai && `selesai ${tgl(e.tgl_selesai)}`,
                            e.tim.length ? `ke ${e.tim.join(", ")}` : ""].filter(Boolean).join(", ")}
                        </small>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
    </>
  );
}
