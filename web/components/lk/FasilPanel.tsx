"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { KELOMPOK_INFO, KODE_WARNA, TAHAP_LABEL, hariPendek, inisial, type FasilDetail, type OpsiLk,
  type Penerima, type SekolahDetail } from "@/lib/lk";
import { bacaBalasan, cocokkan, isi as isiTemplate, pilihKendala, templateBawaan } from "@/lib/pesan";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { BantuanDialog, type IsiEskalasi } from "@/components/today/BantuanDialog";
import { TemanPanel, type Teman } from "@/components/today/TemanPanel";
import { ChatPanel } from "./ChatPanel";
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

/** Panel geser satu fasil: Log Komunikasi hari ini, to-do & isian per sekolah, dan chat WhatsApp. */
export function FasilPanel({ kunci, onClose, kodeLabel }: {
  kunci: string; onClose: () => void; kodeLabel: { kode: string; arti: string }[];
}) {
  const [data, setData] = useState<FasilDetail | null>(null);
  const [opsi, setOpsi] = useState<OpsiLk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draf, setDraf] = useState<Draf>({});
  const [kotor, setKotor] = useState<Set<string>>(new Set());
  const [simpan, setSimpan] = useState<{ busy: boolean; pesan?: { tone: "ok" | "bad"; teks: string } }>({ busy: false });
  const [semua, setSemua] = useState(false);
  const [bantuan, setBantuan] = useState<{ terusan: string; tab: "teman" | "eskalasi"; awal?: IsiEskalasi } | null>(null);
  const [teman, setTeman] = useState<(Teman & { draf: string; kunci: number }) | null>(null);
  const [isiChat, setIsiChat] = useState<{ teks: string; kunci: number } | null>(null);
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
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !bantuan) onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose, bantuan]);

  const penerima: Penerima | null = useMemo(() => data && ({
    kunci: data.kunci, nama: data.nama, tersamar: data.nomor_tersamar, punya_nomor: data.punya_nomor,
    kelompok: data.kelompok, tag: data.tag, ptn: data.ptn, angkatan: [], kab: [], jumlah_sekolah: data.sekolah,
    perlu: data.perlu, terakhir_blast: "",
    sekolah: data.sekolah_detail.map((x) => ({ nama: x.nama, tahap: x.tahap,
      todo: x.todo.map((t) => ({ judul: t.judul, detail: t.detail, pelaku: t.pelaku })) })),
  }), [data]);

  function ubah(npsn: string, kode: string, field: "kendala" | "tl", v: string) {
    setDraf((d) => ({ ...d, [npsn]: { ...d[npsn], [kode]: { ...d[npsn][kode], [field]: v } } }));
    setKotor((k) => new Set(k).add(npsn));
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
    setSimpan({ busy: true });
    try {
      await post("/api/lk2/isi", { isi, kunci: data.kunci });
      setKotor((k) => { const b = new Set(k); target.forEach((x) => b.delete(x)); return b; });
      setSimpan({ busy: false, pesan: { tone: "ok", teks: `Tersimpan ke LK: ${target.length} sekolah.` } });
      void muat(true);
    } catch (e) {
      setSimpan({ busy: false, pesan: { tone: "bad", teks: e instanceof Error ? e.message : String(e) } });
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
    setSimpan({ busy: false, pesan: { tone: "ok", teks: `${hasil.size} sekolah terisi dari balasan. Periksa lalu tekan Simpan.` } });
    return hasil.size;
  }

  async function setKode(kode: string) {
    if (!data) return;
    setData({ ...data, kode_hari_ini: kode as FasilDetail["kode_hari_ini"] });
    try {
      await post("/api/lk2/komunikasi", { kunci: data.kunci, kode });
      void muat(true);
    } catch (e) {
      setSimpan({ busy: false, pesan: { tone: "bad", teks: e instanceof Error ? e.message : String(e) } });
    }
  }

  async function setTag(tag: string[]) {
    if (!data) return;
    setData({ ...data, tag });
    try { await post("/api/lk2/tag", { kunci: data.kunci, tag }); } catch { void muat(true); }
  }

  const daftarSekolah = data ? (semua ? data.sekolah_detail : data.sekolah_detail.filter((x) => x.todo.length)) : [];
  const hijau = data ? data.sekolah_detail.filter((x) => !x.todo.length).length : 0;
  const pakaiWa = !!data?.wa_otomatis && !!data.nomor;

  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className={s.drawer} role="dialog" aria-modal="true" aria-label={data?.nama ?? "Detail fasil"}>
        <header className={s.drawerHead}>
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
            <Button variant="danger" size="sm" onClick={() => setBantuan({ terusan: "", tab: "eskalasi",
              awal: { npsn: data.sekolah_detail.filter((x) => x.todo.length).map((x) => x.npsn), keterangan: keteranganEskalasi(data) } })}
              title="Tanya teman PIC, atau catat permasalahan di LK Eskalasi">
              Butuh bantuan
            </Button>
          )}
          <button ref={closeRef} type="button" className={s.close} onClick={onClose} aria-label="Tutup">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
        </header>

        {error && <div className={s.drawerNote}><Notice tone="bad" title="Data fasil tidak terbaca">{error}</Notice></div>}
        {!data && !error && <div className={s.loading}><Spinner label="Memuat" /></div>}

        {data && (
          <>
            <div className={s.komStrip}>
              <div className={s.komHari}>
                <span className={s.label}>Log komunikasi {data.log_hari_ini ? "hari ini" : ""}</span>
                {data.log_hari_ini ? (
                  <KodePicker besar nilai={data.kode_hari_ini} kode={kodeLabel} onPilih={(k) => void setKode(k)}
                    label="Kode komunikasi hari ini" />
                ) : (
                  <small className={s.muted}>Kolom tanggal hari ini belum ada di Log Komunikasi.</small>
                )}
              </div>
              <div className={s.komMinggu}>
                <span className={s.label}>Minggu ini</span>
                <span className={s.minggu}>
                  {data.kode_minggu.map((d) => (
                    <i key={d.tanggal} title={`${hariPendek(d.tanggal)}: ${d.kode ? KODE_WARNA[d.kode]?.label : "belum dicatat"}`}
                      className={d.tanggal === data.hari ? s.hariIni : undefined}
                      style={d.kode ? { background: KODE_WARNA[d.kode]?.bg, color: KODE_WARNA[d.kode]?.fg } : undefined}>
                      {d.kode || Number(d.tanggal.slice(8))}
                    </i>
                  ))}
                </span>
              </div>
              <TagEditor tag={data.tag} onChange={(t) => void setTag(t)} />
            </div>

            <div className={`${s.compare} ${pakaiWa ? "" : s.compareSatu}`}>
              <section className={s.kolomLk} aria-label="Sekolah binaan">
                <div className={s.kolomHead}>
                  <h3>Sekolah binaan <span>{data.perlu} perlu tindak lanjut · {hijau} hijau</span></h3>
                  <div className={s.kolomAksi}>
                    <label className={s.cek}>
                      <input type="checkbox" checked={semua} onChange={(e) => setSemua(e.target.checked)} /> Tampilkan yang hijau
                    </label>
                    <Button variant="secondary" size="sm" onClick={() => setTempel(!tempel)} aria-expanded={tempel}>
                      Isi dari balasan
                    </Button>
                    <Button size="sm" loading={simpan.busy} disabled={!kotor.size} onClick={() => void simpanIsian()}>
                      Simpan{kotor.size ? ` (${kotor.size})` : ""}
                    </Button>
                  </div>
                </div>
                <p className={s.kolomKet}>
                  Isian masuk ke sesi <b>{data.blok_label}</b>. Cukup isi komponen yang jadi to-do; komponen lain
                  sudah diberi keterangan otomatis (selesai, belum due, atau menunggu tahap sebelumnya).
                </p>
                {tempel && <TempelBalasan onIsi={(t) => { const n = isiDariBalasan(t); if (n) setTempel(false); return n; }} />}
                {simpan.pesan && (
                  <p className={simpan.pesan.tone === "ok" ? s.okNote : s.errNote} role="status">{simpan.pesan.teks}</p>
                )}
                <Legenda />
                <div className={s.sekolahList}>
                  {daftarSekolah.map((x) => (
                    <SekolahCard key={x.npsn} x={x} draf={draf[x.npsn] ?? {}} opsi={opsi} kotor={kotor.has(x.npsn)}
                      onUbah={(kode, f, v) => ubah(x.npsn, kode, f, v)} onSimpan={() => void simpanIsian(x.npsn)}
                      busy={simpan.busy} />
                  ))}
                  {!daftarSekolah.length && <p className={s.hijauBesar}>Semua sekolah binaan fasil ini sudah hijau.</p>}
                </div>
              </section>

              {pakaiWa && penerima ? (
                <ChatPanel nomor={data.nomor} nama={data.nama} penerima={penerima} isi={isiChat}
                  tersembunyi={!!teman}
                  onIsiLk={(t) => isiDariBalasan(t)}
                  onTeruskan={(t) => setBantuan({ terusan: t, tab: "teman" })} />
              ) : penerima ? (
                <SalinTemplate penerima={penerima} waMati={!data.wa_otomatis} />
              ) : null}
              {teman && (
                <TemanPanel key={teman.kunci} teman={teman} draf={teman.draf} nomorFasil={data.nomor}
                  onKembali={() => setTeman(null)}
                  onPakai={(teks) => { setIsiChat({ teks, kunci: Date.now() }); setTeman(null); }} />
              )}
            </div>
          </>
        )}
      </aside>
      {bantuan && data && (
        <BantuanDialog namaFasil={data.nama} sekolah={data.sekolah_detail} terusan={bantuan.terusan}
          tabAwal={bantuan.tab} awal={bantuan.awal}
          onClose={() => setBantuan(null)}
          onPilihTeman={(t) => {
            const draft = bantuan.terusan
              ? `*Diteruskan dari fasil ${data.nama}:*\n${bantuan.terusan.split("\n").map((b) => `> ${b}`).join("\n")}\n\nPertanyaan saya: `
              : `Halo ${t.nama.split(" ")[0]}, mau tanya soal fasil ${data.nama}: `;
            setTeman({ ...t, draf: draft, kunci: Date.now() });
            setBantuan(null);
          }} />
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

function SekolahCard({ x, draf, opsi, kotor, onUbah, onSimpan, busy }: {
  x: SekolahDetail;
  draf: Record<string, { kendala: string; tl: string }>;
  opsi: OpsiLk | null;
  kotor: boolean;
  onUbah: (kode: string, f: "kendala" | "tl", v: string) => void;
  onSimpan: () => void;
  busy: boolean;
}) {
  const todoKomp = new Set(x.todo.flatMap((t) => t.komponen));
  return (
    <article className={`${s.sekolah} ${x.lengkap && x.todo.length ? s.sekolahLengkap : ""}`}>
      <header className={s.sekolahHead}>
        <div>
          <h4>{x.nama}</h4>
          <small>{x.kab}{x.angkatan && ` · Angkatan ${x.angkatan}`} · NPSN {x.npsn}</small>
        </div>
        <div className={s.sekolahChip}>
          {x.delta !== null && x.delta > 0 && <Chip tone="ok">+{x.delta} sejak cutoff lalu</Chip>}
          <Chip tone={x.todo.length ? (x.lengkap ? "ok" : "warn") : "ok"}>
            {!x.todo.length ? "Semua hijau" : x.lengkap ? "Isian lengkap" : TAHAP_LABEL[x.tahap]}
          </Chip>
        </div>
      </header>
      <Track komponen={x.komponen} todo={todoKomp} />
      {x.todo.length > 0 && (
        <ol className={s.todo}>
          {x.todo.map((t, i) => {
            const v = draf[t.kode] ?? { kendala: "", tl: "" };
            const pil = opsi?.kendala[t.komponen[0]] ?? [];
            const id = `k-${x.npsn}-${t.kode}`;
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
                  <label>
                    <span>Kendala</span>
                    <input list={`${id}-opsi`} value={v.kendala} placeholder="Pilih atau ketik kendala"
                      onChange={(e) => onUbah(t.kode, "kendala", e.target.value)} />
                    <datalist id={`${id}-opsi`}>{pil.map((o) => <option key={o} value={o} />)}</datalist>
                  </label>
                  <label>
                    <span>Tindak lanjut</span>
                    <textarea rows={1} value={v.tl} placeholder="Apa yang sudah / akan dilakukan"
                      onChange={(e) => onUbah(t.kode, "tl", e.target.value)} />
                  </label>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {kotor && (
        <div className={s.sekolahSimpan}>
          <span>Belum disimpan</span>
          <Button size="sm" loading={busy} onClick={onSimpan}>Simpan sekolah ini</Button>
        </div>
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

/** Tanpa WhatsApp otomatis: pilih template, salin, kirim dari HP sendiri. */
function SalinTemplate({ penerima, waMati }: { penerima: Penerima; waMati: boolean }) {
  const daftar = templateBawaan("fasil");
  const [pilih, setPilih] = useState(daftar[0].kode);
  const [disalin, setDisalin] = useState(false);
  const t = daftar.find((x) => x.kode === pilih) ?? daftar[0];
  const teks = isiTemplate(t.teks, penerima, "", false);
  return (
    <section className={s.kolomWa} aria-label="Template pesan">
      <h3>Template pesan</h3>
      <p className={s.kolomKet}>
        {waMati ? "WhatsApp otomatis mati. Salin pesan ini lalu kirim dari WhatsApp di HP Anda. Balasan fasil bisa ditempel lewat “Isi dari balasan”."
          : "Fasil ini belum punya nomor WhatsApp di LK. Salin pesan lalu kirim lewat jalur lain."}
      </p>
      <div className={s.tplList}>
        {daftar.map((x) => (
          <button key={x.kode} type="button" aria-pressed={x.kode === pilih} onClick={() => { setPilih(x.kode); setDisalin(false); }}>
            {x.judul}
          </button>
        ))}
      </div>
      <pre className={s.pratinjau}>{teks}</pre>
      <Button size="sm" onClick={() => { void navigator.clipboard.writeText(teks).then(() => setDisalin(true)); }}>
        {disalin ? "Tersalin ✓" : "Salin pesan"}
      </Button>
    </section>
  );
}
