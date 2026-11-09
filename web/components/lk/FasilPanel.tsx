"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { KELOMPOK_INFO, KODE_WARNA, TAHAP_LABEL, HARI_PENDEK, inisial, type FasilDetail, type OpsiLk,
  type Penerima, type SekolahDetail } from "@/lib/lk";
import { bacaBalasan, cocokkan, isi as isiTemplate, kosong, pilihKendala, templateBawaan, templateKoorFasil,
  type Template } from "@/lib/pesan";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { BantuanDialog } from "@/components/today/BantuanDialog";
import { ChatPanel, SalinTemplate } from "./ChatPanel";
import { KodePicker } from "./KodePicker";
import { Track } from "./Track";
import s from "./lk.module.css";

type Draf = Record<string, Record<string, { kendala: string; tl: string }>>; // npsn -> todo kode -> isian

function drafAwal(d: FasilDetail): Draf {
  const out: Draf = {};
  for (const x of d.sekolah_detail) {
    out[x.npsn] = {};
    for (const t of x.todo) {
      const pertama = t.isian[t.komponen[0]] ?? { kendala: "", tl: "" };
      out[x.npsn][t.kode] = { ...pertama };
    }
  }
  return out;
}

export function keteranganEskalasi(d: FasilDetail) {
  const kel = KELOMPOK_INFO[d.kelompok].label.toLowerCase();
  const todo = d.sekolah_detail.filter((x) => x.todo.length)
    .map((x) => `${x.nama}: ${x.todo.map((t) => t.judul).join(", ")}`).slice(0, 6).join("; ");
  return `Fasil ${d.nama} (${kel}). To-do: ${todo}.`;
}

/** Layar penuh satu fasil: Log Komunikasi hari ini, to-do & isian per sekolah, chat fasil dan koordinator. */
export function FasilPanel({ kunci, onClose, kodeLabel }: {
  kunci: string; onClose: () => void; kodeLabel: { kode: string; arti: string }[];
}) {
  const [data, setData] = useState<FasilDetail | null>(null);
  const [opsi, setOpsi] = useState<OpsiLk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draf, setDraf] = useState<Draf>({});
  const [kotor, setKotor] = useState<Set<string>>(new Set());
  const [buka, setBuka] = useState<Set<string>>(new Set());
  const [simpan, setSimpan] = useState<{ busy: string | null; pesan?: { tone: "ok" | "bad"; teks: string } }>({ busy: null });
  const [semua, setSemua] = useState(false);
  const [eskalasi, setEskalasi] = useState(false);
  const [kanan, setKanan] = useState<"fasil" | "koor">("fasil");
  const [tempel, setTempel] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  const muat = useCallback(async (jagaDraf = false) => {
    try {
      const d = await api<FasilDetail>(`/api/lk2/fasil/${encodeURIComponent(kunci)}`);
      setData(d);
      setError(null);
      if (!jagaDraf) { setDraf(drafAwal(d)); setKotor(new Set()); }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [kunci]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); }, [muat]);
  useEffect(() => { api<OpsiLk>("/api/lk2/opsi").then(setOpsi).catch(() => undefined); }, []);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !eskalasi) onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose, eskalasi]);

  const penerima: Penerima | null = useMemo(() => data && ({
    kunci: data.kunci, nama: data.nama, tersamar: data.nomor_tersamar, punya_nomor: data.punya_nomor,
    kelompok: data.kelompok, tag: data.tag, ptn: data.ptn, angkatan: [], kab: [], jumlah_sekolah: data.sekolah,
    perlu: data.perlu, terakhir_blast: "",
    sekolah: data.sekolah_detail.map((x) => ({ nama: x.nama, tahap: x.tahap,
      todo: x.todo.map((t) => ({ judul: t.judul, detail: t.detail, pelaku: t.pelaku })) })),
  }), [data]);

  const tplFasil: Template[] = useMemo(() => penerima
    ? templateBawaan("fasil").filter((t) => !kosong(t.teks, penerima).length)
      .map((t) => ({ ...t, teks: isiTemplate(t.teks, penerima, "", false) }))
    : [], [penerima]);
  const tplKoor: Template[] = useMemo(() => (data ? templateKoorFasil(data) : []), [data]);

  function ubah(npsn: string, kode: string, field: "kendala" | "tl", v: string) {
    setDraf((d) => ({ ...d, [npsn]: { ...d[npsn], [kode]: { ...d[npsn][kode], [field]: v } } }));
    setKotor((k) => new Set(k).add(npsn));
  }

  /** Salin Kendala/TL satu to-do ke to-do yang sama di sekolah lain fasil ini yang isiannya masih kosong. */
  function salinKeLain(npsn: string, kode: string, field: "kendala" | "tl") {
    if (!data) return;
    const v = (draf[npsn]?.[kode]?.[field] ?? "").trim();
    if (!v) return;
    const target = data.sekolah_detail.filter((x) => x.npsn !== npsn && x.todo.some((t) => t.kode === kode)
      && !(draf[x.npsn]?.[kode]?.[field] ?? "").trim()).map((x) => x.npsn);
    const nama = field === "kendala" ? "Kendala" : "Tindak lanjut";
    if (!target.length) {
      setSimpan({ busy: null, pesan: { tone: "ok", teks: `Tidak ada sekolah lain dengan to-do ini yang ${nama.toLowerCase()}-nya masih kosong.` } });
      return;
    }
    setDraf((d) => {
      const baru = { ...d };
      for (const n of target) baru[n] = { ...baru[n], [kode]: { ...(baru[n]?.[kode] ?? { kendala: "", tl: "" }), [field]: v } };
      return baru;
    });
    setKotor((k) => { const b = new Set(k); target.forEach((n) => b.add(n)); return b; });
    setSimpan({ busy: null, pesan: { tone: "ok", teks: `${nama} disalin ke ${target.length} sekolah lain. Periksa lalu tekan Simpan semua.` } });
  }

  function toggle(npsn: string) {
    setBuka((b) => { const n = new Set(b); if (n.has(npsn)) n.delete(npsn); else n.add(npsn); return n; });
  }

  async function simpanIsian(npsn?: string) {
    if (!data) return;
    const target = npsn ? [npsn] : [...kotor];
    const isi = target.flatMap((n) => {
      const sk = data.sekolah_detail.find((x) => x.npsn === n);
      if (!sk) return [];
      return sk.todo.flatMap((t) => t.komponen.map((k) => ({ npsn: n, kode: k, kendala: draf[n]?.[t.kode]?.kendala ?? "",
        tl: draf[n]?.[t.kode]?.tl ?? "" })));
    });
    if (!isi.length) return;
    setSimpan({ busy: npsn ?? "semua" });
    try {
      await post("/api/lk2/isi", { isi, kunci: data.kunci });
      setKotor((k) => { const b = new Set(k); target.forEach((x) => b.delete(x)); return b; });
      // tandai lengkap langsung di tampilan; data lengkapnya disegarkan di belakang
      setData((d) => d && { ...d, sekolah_detail: d.sekolah_detail.map((x) => target.includes(x.npsn)
        ? { ...x, lengkap: x.todo.every((t) => (draf[x.npsn]?.[t.kode]?.kendala ?? "").trim()
          && (draf[x.npsn]?.[t.kode]?.tl ?? "").trim()) } : x) });
      setBuka((b) => { const n = new Set(b); target.forEach((x) => n.delete(x)); return n; });
      setSimpan({ busy: null, pesan: { tone: "ok", teks: `Tersimpan ke LK: ${target.length} sekolah.` } });
      void muat(true);
    } catch (e) {
      setSimpan({ busy: null, pesan: { tone: "bad", teks: e instanceof Error ? e.message : String(e) } });
    }
  }

  /** Isi Kendala/TL dari balasan fasil berformat "1. Sekolah … Kendala: … Tindak lanjut: …". */
  function isiDariBalasan(teks: string) {
    if (!data) return 0;
    const sekolahTodo = data.sekolah_detail.filter((x) => x.todo.length).slice().sort((a, b) => a.nama.localeCompare(b.nama));
    const hasil = cocokkan(bacaBalasan(teks), sekolahTodo);
    if (!hasil.size) return 0;
    setDraf((d) => {
      const baru = { ...d };
      hasil.forEach((j, sk) => {
        baru[sk.npsn] = { ...baru[sk.npsn] };
        for (const t of sk.todo) {
          const o = opsi?.kendala[t.komponen[0]] ?? [];
          baru[sk.npsn][t.kode] = { kendala: j.kendala ? pilihKendala(j.kendala, o) : baru[sk.npsn][t.kode]?.kendala ?? "",
            tl: j.tl || baru[sk.npsn][t.kode]?.tl || "" };
        }
      });
      return baru;
    });
    setKotor((k) => { const b = new Set(k); hasil.forEach((_, sk) => b.add(sk.npsn)); return b; });
    setBuka((b) => { const n = new Set(b); hasil.forEach((_, sk) => n.add(sk.npsn)); return n; });
    setSimpan({ busy: null, pesan: { tone: "ok", teks: `${hasil.size} sekolah terisi dari balasan. Periksa lalu tekan Simpan.` } });
    return hasil.size;
  }

  async function setKode(kode: string) {
    if (!data) return;
    const lama = data.kode_hari_ini;
    setData({ ...data, kode_hari_ini: kode as FasilDetail["kode_hari_ini"],
      kode_minggu: data.kode_minggu.map((d) => (d.tanggal === data.hari ? { ...d, kode: kode as FasilDetail["kode_hari_ini"] } : d)) });
    try {
      await post("/api/lk2/komunikasi", { kunci: data.kunci, kode });
    } catch (e) {
      setData((d) => d && { ...d, kode_hari_ini: lama });
      setSimpan({ busy: null, pesan: { tone: "bad", teks: e instanceof Error ? e.message : String(e) } });
    }
  }

  async function setTag(tag: string[]) {
    if (!data) return;
    setData({ ...data, tag });
    try { await post("/api/lk2/tag", { kunci: data.kunci, tag }); } catch { void muat(true); }
  }

  const daftarSekolah = data ? (semua ? data.sekolah_detail : data.sekolah_detail.filter((x) => x.todo.length)) : [];
  const hijau = data ? data.sekolah_detail.filter((x) => !x.todo.length).length : 0;
  const lengkapN = data ? data.sekolah_detail.filter((x) => x.todo.length && x.lengkap).length : 0;
  const waJalan = !!data?.wa_otomatis;

  return (
    <div className={s.layar} role="dialog" aria-modal="true" aria-label={data?.nama ?? "Detail fasil"}>
      <header className={s.layarHead}>
        <button ref={closeRef} type="button" className={s.kembali} onClick={onClose} aria-label="Tutup, kembali ke daftar fasil">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="m15 18-6-6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span>Daftar fasil</span>
        </button>
        <span className={`${s.avatar} ${s.avatarLg} ${data ? s[`av_${KELOMPOK_INFO[data.kelompok].tone}`] : ""}`} aria-hidden="true">
          {data ? inisial(data.nama) : ""}
        </span>
        <div className={s.drawerWho}>
          <h2>{data?.nama ?? "Memuat…"}</h2>
          {data && (
            <span>
              {data.nomor_tersamar || "Nomor WA kosong"} · {data.ptn || "PTN belum tercatat"}
              {data.koor && <> · Koor. {data.koor}</>}
            </span>
          )}
        </div>
        {data && <Chip tone={KELOMPOK_INFO[data.kelompok].tone}>{KELOMPOK_INFO[data.kelompok].label}</Chip>}
        {data && (
          <div className={s.layarAksi}>
            <Button variant="secondary" size="sm" onClick={() => setKanan("koor")} disabled={!data.koor}
              title={data.koor ? "Fasil tidak membalas? Minta bantuan koordinatornya" : "Koordinator belum tercatat di LK"}>
              Hubungi koordinator
            </Button>
            <Button variant="danger" size="sm" onClick={() => setEskalasi(true)}
              title="Catat kasus yang perlu dijawab tim lain di LK Eskalasi">
              Eskalasi ke tim lain
            </Button>
          </div>
        )}
      </header>

      {error && <div className={s.drawerNote}><Notice tone="bad" title="Data fasil tidak terbaca">{error}</Notice></div>}
      {!data && !error && <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>}

      {data && (
        <>
          <div className={s.komStrip}>
            <div className={s.komHari}>
              <span className={s.label}>Log Komunikasi hari ini</span>
              {data.log_hari_ini ? (
                <KodePicker besar nilai={data.kode_hari_ini} kode={kodeLabel} onPilih={(k) => void setKode(k)}
                  label="Kode komunikasi hari ini" />
              ) : (
                <small className={s.muted}>Kolom tanggal hari ini belum ada di Log Komunikasi.</small>
              )}
            </div>
            <div className={s.komMinggu}>
              <span className={s.label}>5 hari terakhir</span>
              <ol className={s.riwayatKode} aria-label="Kode komunikasi 5 hari kerja terakhir">
                {data.kode_minggu.map((d) => {
                  const w = KODE_WARNA[d.kode];
                  const tgl = new Date(`${d.tanggal}T00:00:00`);
                  return (
                    <li key={d.tanggal} className={d.tanggal === data.hari ? s.hariIni : undefined}
                      title={`${HARI_PENDEK[tgl.getDay()]} ${tgl.getDate()}: ${d.kode ? `${d.kode} (${w?.label})` : "belum dicatat"}`}>
                      <small>{HARI_PENDEK[tgl.getDay()]} {tgl.getDate()}</small>
                      <b style={w ? { background: w.bg, color: w.fg } : undefined}>{d.kode || "–"}</b>
                    </li>
                  );
                })}
              </ol>
            </div>
            <TagEditor tag={data.tag} onChange={(t) => void setTag(t)} />
          </div>

          <div className={s.compare}>
            <section className={s.kolomLk} aria-label="Sekolah binaan">
              <div className={s.kolomHead}>
                <h3>Sekolah binaan <span>{data.perlu} punya to-do · {lengkapN} isian lengkap · {hijau} hijau</span></h3>
                <div className={s.kolomAksi}>
                  <label className={s.cek}>
                    <input type="checkbox" checked={semua} onChange={(e) => setSemua(e.target.checked)} /> Tampilkan yang hijau
                  </label>
                  <Button variant="secondary" size="sm" onClick={() => setTempel(!tempel)} aria-expanded={tempel}>
                    Isi dari balasan
                  </Button>
                  {kotor.size > 0 && (
                    <Button size="sm" loading={simpan.busy === "semua"} onClick={() => void simpanIsian()}>
                      Simpan semua ({kotor.size})
                    </Button>
                  )}
                </div>
              </div>
              <p className={s.kolomKet}>
                Klik sekolah untuk membuka isian Kendala & Tindak lanjut. Isian masuk ke sesi <b>{data.blok_label}</b>;
                komponen yang bukan to-do sudah diberi keterangan otomatis.
              </p>
              {tempel && <TempelBalasan onIsi={(t) => { const n = isiDariBalasan(t); if (n) setTempel(false); return n; }} />}
              {simpan.pesan && (
                <p className={simpan.pesan.tone === "ok" ? s.okNote : s.errNote} role="status">{simpan.pesan.teks}</p>
              )}
              <Legenda />
              <div className={s.sekolahList}>
                {daftarSekolah.map((x) => (
                  <SekolahCard key={x.npsn} x={x} draf={draf[x.npsn] ?? {}} opsi={opsi} kotor={kotor.has(x.npsn)}
                    terbuka={buka.has(x.npsn)} onToggle={() => toggle(x.npsn)}
                    onUbah={(kode, f, v) => ubah(x.npsn, kode, f, v)} onSalin={(kode, f) => salinKeLain(x.npsn, kode, f)}
                    bisaSalin={(kode) => data.sekolah_detail.some((y) => y.npsn !== x.npsn && y.todo.some((t) => t.kode === kode))}
                    onSimpan={() => void simpanIsian(x.npsn)}
                    busy={simpan.busy === x.npsn} />
                ))}
                {!daftarSekolah.length && <p className={s.hijauBesar}>Semua sekolah binaan fasil ini sudah hijau.</p>}
              </div>
            </section>

            <aside className={s.kolomWa} aria-label="Pesan">
              <div className={s.kananTab} role="tablist" aria-label="Kirim pesan ke">
                <button type="button" role="tab" aria-selected={kanan === "fasil"} onClick={() => setKanan("fasil")}>
                  Fasil
                </button>
                <button type="button" role="tab" aria-selected={kanan === "koor"} onClick={() => setKanan("koor")} disabled={!data.koor}>
                  Koordinator{data.koor ? "" : " (kosong)"}
                </button>
              </div>
              {kanan === "fasil" ? (
                waJalan && data.nomor ? (
                  <ChatPanel key={`f-${data.nomor}`} nomor={data.nomor} nama={data.nama} peran="fasil" template={tplFasil}
                    onIsiLk={(t) => isiDariBalasan(t)} />
                ) : (
                  <SalinTemplate key="sf" template={tplFasil}
                    ket={!waJalan ? "WhatsApp otomatis mati. Salin pesan ini lalu kirim dari WhatsApp di HP Anda. Balasan fasil bisa ditempel lewat “Isi dari balasan”."
                      : "Fasil ini belum punya nomor WhatsApp di LK. Salin pesan lalu kirim lewat jalur lain."} />
                )
              ) : (
                <>
                  <p className={s.koorInfo}>
                    Koordinator {data.koor_tersamar ? `(${data.koor_tersamar})` : "(nomor kosong)"}: pakai saat fasil tidak
                    membalas, hanya membaca, atau laporannya tidak bergerak.
                  </p>
                  {waJalan && data.nomor_koor ? (
                    <ChatPanel key={`k-${data.nomor_koor}`} nomor={data.nomor_koor} nama={data.koor} peran="koor" template={tplKoor} />
                  ) : (
                    <SalinTemplate key="sk" template={tplKoor}
                      ket={!waJalan ? "WhatsApp otomatis mati. Salin pesan lalu kirim ke koordinator dari HP Anda."
                        : "Nomor koordinator belum ada di LK. Salin pesan lalu kirim lewat jalur lain."} />
                  )}
                </>
              )}
            </aside>
          </div>
        </>
      )}
      {eskalasi && data && (
        <BantuanDialog hanyaEskalasi namaFasil={data.nama} sekolah={data.sekolah_detail} terusan=""
          awal={{ npsn: data.sekolah_detail.filter((x) => x.todo.length).map((x) => x.npsn), keterangan: keteranganEskalasi(data) }}
          onClose={() => setEskalasi(false)} />
      )}
    </div>
  );
}

function Legenda() {
  return (
    <ul className={s.legenda} aria-label="Arti warna">
      <li><i className={s.seg_selesai} />Selesai</li>
      <li><i className={s.seg_todo} />To-do</li>
      <li><i className={s.seg_menunggu} />Menunggu tahap sebelumnya</li>
      <li><i className={s.seg_due} />Belum due / belum ada laporan</li>
    </ul>
  );
}

function SekolahCard({ x, draf, opsi, kotor, terbuka, onToggle, onUbah, onSalin, bisaSalin, onSimpan, busy }: {
  x: SekolahDetail;
  draf: Record<string, { kendala: string; tl: string }>;
  opsi: OpsiLk | null;
  kotor: boolean;
  terbuka: boolean;
  onToggle: () => void;
  onUbah: (kode: string, f: "kendala" | "tl", v: string) => void;
  onSalin: (kode: string, f: "kendala" | "tl") => void;
  bisaSalin: (kode: string) => boolean;
  onSimpan: () => void;
  busy: boolean;
}) {
  const todoKomp = new Set(x.todo.flatMap((t) => t.komponen));
  const ada = x.todo.length > 0;
  const terisi = x.todo.filter((t) => (draf[t.kode]?.kendala ?? "").trim() && (draf[t.kode]?.tl ?? "").trim()).length;
  return (
    <article className={`${s.sekolah} ${x.lengkap && ada ? s.sekolahLengkap : ""} ${terbuka ? s.sekolahBuka : ""}`}>
      <button type="button" className={s.sekolahHead} onClick={ada ? onToggle : undefined} aria-expanded={ada ? terbuka : undefined}
        disabled={!ada}>
        <div>
          <h4>{x.nama}</h4>
          <small>{x.kab}{x.angkatan && ` · Angkatan ${x.angkatan}`} · NPSN {x.npsn}</small>
        </div>
        <div className={s.sekolahChip}>
          {x.delta !== null && x.delta > 0 && <Chip tone="ok">+{x.delta} sejak cutoff lalu</Chip>}
          {kotor && <Chip tone="warn">Belum disimpan</Chip>}
          <Chip tone={ada ? (x.lengkap ? "ok" : "muted") : "ok"}>
            {!ada ? "Semua hijau" : x.lengkap ? "Isian lengkap ✓" : `Isian ${terisi}/${x.todo.length}`}
          </Chip>
          {ada && (
            <svg className={s.chevron} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          )}
        </div>
      </button>
      <Track komponen={x.komponen} todo={todoKomp} />
      {ada && !terbuka && (
        <p className={s.todoRingkas}>
          <span>{TAHAP_LABEL[x.tahap]}:</span> {x.todo.map((t, i) => (
            <span key={t.kode} className={t.pelaku === "fasil" ? s.todoRingkasFasil : undefined}>
              {i > 0 && " · "}{t.judul}
            </span>
          ))}
        </p>
      )}
      {ada && terbuka && (
        <>
          <ol className={s.todo}>
            {x.todo.map((t, i) => {
              const v = draf[t.kode] ?? { kendala: "", tl: "" };
              const pil = opsi?.kendala[t.komponen[0]] ?? [];
              const id = `k-${x.npsn}-${t.kode}`;
              const salin = bisaSalin(t.kode);
              return (
                <li key={t.kode} className={i === 0 ? s.todoFokus : undefined}>
                  <div className={s.todoJudul}>
                    <span className={s.todoNo}>{i === 0 ? "Fokus" : i + 1}</span>
                    <b>{t.judul}</b>
                    <span className={`${s.pelaku} ${t.pelaku === "fasil" ? s.pelakuFasil : ""}`}>
                      {t.pelaku === "fasil" ? "Tugas fasil" : "Tugas sekolah"}
                    </span>
                    {t.detail && !/^(Belum|Sudah)$/.test(t.detail) && <small>{t.detail}</small>}
                    {t.tunggu !== null && t.tunggu > 0 && (
                      <small className={t.tunggu > 3 ? s.lama : undefined}>menunggu reviu {Math.round(t.tunggu)} hari</small>
                    )}
                  </div>
                  <div className={s.isian}>
                    <div>
                      <div className={s.isianLabel}>
                        <label htmlFor={`${id}-k`}>Kendala</label>
                        {salin && v.kendala.trim() && (
                          <button type="button" className={s.salinLain} onClick={() => onSalin(t.kode, "kendala")}
                            title="Isi Kendala yang sama di sekolah lain dengan to-do ini (yang masih kosong)">
                            Salin ke sekolah lain
                          </button>
                        )}
                      </div>
                      <input id={`${id}-k`} list={`${id}-opsi`} value={v.kendala} placeholder="Pilih atau ketik kendala"
                        onChange={(e) => onUbah(t.kode, "kendala", e.target.value)} />
                      <datalist id={`${id}-opsi`}>{pil.map((o) => <option key={o} value={o} />)}</datalist>
                    </div>
                    <div>
                      <div className={s.isianLabel}>
                        <label htmlFor={`${id}-t`}>Tindak lanjut</label>
                        {salin && v.tl.trim() && (
                          <button type="button" className={s.salinLain} onClick={() => onSalin(t.kode, "tl")}
                            title="Isi Tindak lanjut yang sama di sekolah lain dengan to-do ini (yang masih kosong)">
                            Salin ke sekolah lain
                          </button>
                        )}
                      </div>
                      <textarea id={`${id}-t`} rows={1} value={v.tl} placeholder="Apa yang sudah / akan dilakukan"
                        onChange={(e) => onUbah(t.kode, "tl", e.target.value)} />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          <div className={s.sekolahSimpan}>
            <Button variant="ghost" size="sm" onClick={onToggle}>Tutup</Button>
            <Button size="sm" loading={busy} disabled={!kotor} onClick={onSimpan}>Simpan sekolah ini</Button>
          </div>
        </>
      )}
    </article>
  );
}

function TempelBalasan({ onIsi }: { onIsi: (teks: string) => number }) {
  const [teks, setTeks] = useState("");
  const [gagal, setGagal] = useState(false);
  return (
    <div className={s.tempel}>
      <label htmlFor="tempel-balasan">Tempel balasan fasil (format “1. Sekolah … Kendala: … Tindak lanjut: …”)</label>
      <textarea id="tempel-balasan" rows={5} value={teks} onChange={(e) => { setTeks(e.target.value); setGagal(false); }}
        placeholder={"1. SD Negeri 1 …\n   Kendala: …\n   Tindak lanjut: …"} />
      <div className={s.tempelAksi}>
        {gagal && <small className={s.errNote}>Tidak ada jawaban per sekolah yang terbaca. Pastikan ada baris “Kendala:”.</small>}
        <Button size="sm" variant="secondary" disabled={!teks.trim()} onClick={() => setGagal(!onIsi(teks))}>Isi ke LK</Button>
      </div>
    </div>
  );
}

function TagEditor({ tag, onChange }: { tag: string[]; onChange: (t: string[]) => void }) {
  const [baru, setBaru] = useState("");
  const tambah = () => {
    const t = baru.trim().replace(/^#/, "");
    if (t && !tag.includes(t)) onChange([...tag, t].slice(0, 6));
    setBaru("");
  };
  return (
    <div className={s.tagEdit}>
      <span className={s.label}>Tag</span>
      <div>
        {tag.map((t) => (
          <span key={t} className={s.tagChip}>#{t}
            <button type="button" aria-label={`Hapus tag ${t}`} onClick={() => onChange(tag.filter((x) => x !== t))}>×</button>
          </span>
        ))}
        {tag.length < 6 && (
          <input value={baru} onChange={(e) => setBaru(e.target.value)} placeholder="+ tag, mis. via koor"
            maxLength={30} aria-label="Tambah tag"
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); tambah(); } }} onBlur={tambah} />
        )}
      </div>
    </div>
  );
}
