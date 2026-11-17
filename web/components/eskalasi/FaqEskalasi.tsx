"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { EskalasiInfo, FaqResmi, Masalah } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { Pengumuman, pesan, Teks, type Info } from "@/components/forum/bersama";
import { FormMasalah } from "./FormMasalah";
import { IkonCari } from "./EskalasiView";
import { asalMasalah, Dialog, nadaWaktu, PasangLink, Rincian, StatusChip, namaTahap, Tahap, temaAsli, tgl, TindakLanjut, WaktuChip } from "./bagian";
import s from "./esk.module.css";
import h from "./halaman.module.css";

type Saring = "semua" | "dijawab" | "belum" | "saya";
type Grup = { kunci: string; baris: Masalah[]; cari: string };

const rapi = (t: string) => t.replace(/^PRIORITAS TINGGI:\s*/i, "").replace(/\s+/g, " ").trim().toLowerCase();

/** Satu masalah yang dicatat untuk beberapa sekolah sekaligus (keterangan sama) tampil sebagai satu kartu. */
function kelompokkan(masalah: Masalah[]): Grup[] {
  const peta = new Map<string, Masalah[]>();
  for (const m of masalah) {
    const k = `${rapi(m.keterangan)}|${m.permasalahan}`;
    peta.set(k, [...(peta.get(k) ?? []), m]);
  }
  return [...peta.entries()].map(([kunci, baris]) => ({
    kunci, baris,
    cari: baris.map((m) => [m.id, m.npsn, m.nama, m.fasil, m.petugas, m.ptn, m.topik, m.keterangan, m.jawaban, m.tema,
      m.permasalahan, m.kode_tema].join(" ")).join(" ").toLowerCase(),
  }));
}

function IkonCentang() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function JawabanResmi({ daftar }: { daftar: FaqResmi[] }) {
  return (
    <section className={h.resmi} aria-labelledby="judul-resmi">
      <div className={h.pita}>
        <h2 id="judul-resmi"><IkonCentang /> Jawaban resmi</h2>
        <span>{daftar.length} tema</span>
      </div>
      <p>Sudah diputuskan tim. Rujuk jawaban ini ke fasil, tidak perlu dilaporkan lagi.</p>
      {daftar.map((f) => (
        <details key={f.kode} className={h.resmiItem}>
          <summary><span className={`${h.lencana} ${h.lencanaTema}`}>{f.kode}</span>{f.pertanyaan}</summary>
          <div className={h.resmiJawab}><Teks isi={f.jawaban} /></div>
          <div className={h.resmiMeta}>
            {[f.kelompok, f.tim && `dijawab ${f.tim}`, f.jumlah && `${f.jumlah} sekolah`, f.tgl_selesai && `selesai ${tgl(f.tgl_selesai)}`]
              .filter(Boolean).join(", ")}
          </div>
        </details>
      ))}
    </section>
  );
}

function KartuTanya({ g, info, onUbah }: { g: Grup; info: EskalasiInfo; onUbah: (m: Masalah) => void }) {
  const [buka, setBuka] = useState(false);
  const [isi, setIsi] = useState<number | null>(null);
  const m = g.baris[0];
  const opsi = info.opsi!;
  const tema = temaAsli(m);
  const jawab = g.baris.find((x) => x.jawaban);
  const selesai = g.baris.filter((x) => x.status === "Selesai").length;
  const sekolah = g.baris.filter((x) => x.npsn);
  const nada = g.baris.length > 1 ? (selesai === g.baris.length ? "selesai" : "biasa") : nadaWaktu(m);
  const ket = m.keterangan.replace(/^PRIORITAS TINGGI:\s*/i, "");
  return (
    <li className={`${h.qaKartu} ${h[`rail_${nada}`] ?? ""}`}>
      <div className={h.qaAtas}>
        <span className={h.idKasus}>{m.id}{g.baris.length > 1 ? ` +${g.baris.length - 1}` : ""}</span>
        {m.permasalahan && <span className={h.lencana}>{m.permasalahan}</span>}
        {m.kode_tema && <span className={`${h.lencana} ${h.lencanaTema}`} title={tema}>{m.kode_tema}</span>}
        <span>{m.tgl_awal ? tgl(m.tgl_awal) : ""}</span>
        <span className={h.kanan}>
          {g.baris.length > 1 && selesai < g.baris.length
            ? <Chip tone="info">{selesai} dari {g.baris.length} selesai</Chip>
            : <StatusChip m={m} />}
        </span>
      </div>
      <button type="button" className={h.qaTanya} onClick={() => setBuka(!buka)} aria-expanded={buka}>
        <h3 className={buka ? "" : h.potong2}>{tema || ket}</h3>
      </button>
      <div className={h.qaSekolah}>
        {sekolah.length > 1
          ? <span><b>{sekolah.length} sekolah</b> {sekolah.slice(0, 3).map((x) => x.nama).join(", ")}{sekolah.length > 3 ? `, dan ${sekolah.length - 3} lainnya` : ""}</span>
          : <span><b>{asalMasalah(m)}</b></span>}
        {sekolah.length <= 1 && m.fasil && <span>Fasil {m.fasil}</span>}
        {m.petugas && <span>Petugas {m.petugas}</span>}
      </div>
      {jawab ? (
        <div className={h.qaJawab}>
          <span className={h.qaJawabIkon}><IkonCentang /></span>
          <div className={h.qaJawabIsi}>
            <small>Dijawab{jawab.pengisi ? ` oleh ${jawab.pengisi}` : ""}{jawab.tgl_selesai ? `, ${tgl(jawab.tgl_selesai)}` : ""}</small>
            <div className={buka ? "" : h.potong2}><Teks isi={jawab.jawaban} /></div>
          </div>
        </div>
      ) : (
        <span className={h.qaBelum}>Belum ada jawaban dari tim terkait</span>
      )}
      {buka && (
        <div className={h.qaRinci}>
          {tema && (
            <div className={s.field}>
              <span className={s.label}>Keterangan dari petugas</span>
              <Teks isi={ket} />
            </div>
          )}
          <Rincian m={m} opsi={opsi} />
          {g.baris.length > 1 && (
            <ul className={s.sekolahList}>
              {g.baris.map((x) => (
                <li key={x.baris}>
                  <span><span className={h.idKasus}>{x.id}</span> {asalMasalah(x)}</span>
                  <WaktuChip m={x} />
                  <StatusChip m={x} />
                  {x.boleh_ubah && <button type="button" className={h.tautan} onClick={() => setIsi(isi === x.baris ? null : x.baris)}>Tindak lanjut</button>}
                  {isi === x.baris && (
                    <div style={{ flexBasis: "100%" }}>
                      <TindakLanjut m={x} opsi={opsi} saya={info.saya.nama ?? ""} pic={!!info.saya.pic}
                        onTersimpan={onUbah} onBatal={() => setIsi(null)} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {g.baris.length === 1 && (m.boleh_ubah || info.saya.pic) && (
            isi === m.baris
              ? <TindakLanjut m={m} opsi={opsi} saya={info.saya.nama ?? ""} pic={!!info.saya.pic} onTersimpan={onUbah} onBatal={() => setIsi(null)} />
              : <div><Button size="sm" variant="secondary" onClick={() => setIsi(m.baris)}>Isi tindak lanjut</Button></div>
          )}
        </div>
      )}
      <div className={h.qaBawah}>
        <div className={h.tahapBaris}>
          <div className={h.tahapKecil}><Tahap m={m} /></div>
          <small>{namaTahap(m)}</small>
        </div>
        <button type="button" className={h.tautan} onClick={() => setBuka(!buka)}>{buka ? "Tutup rincian" : "Lihat rincian"}</button>
      </div>
    </li>
  );
}

export function FaqEskalasi() {
  const [info, setInfo] = useState<EskalasiInfo | null>(null);
  const [galat, setGalat] = useState("");
  const [segar, setSegar] = useState(false);
  const [info2, setInfo2] = useState<{ pengumuman: Info[]; admin: boolean } | null>(null);
  const [saring, setSaring] = useState<Saring>("semua");
  const [cari, setCari] = useState("");
  const [kelompok, setKelompok] = useState("");
  const [batas, setBatas] = useState(20);
  const [lapor, setLapor] = useState(false);

  const muat = useCallback(async (paksa = false) => {
    setSegar(paksa);
    try {
      setInfo(await api<EskalasiInfo>(`/api/eskalasi?semua=true${paksa ? "&paksa=true" : ""}`));
      setGalat("");
    } catch (e) {
      setGalat(e instanceof ApiError ? e.message : pesan(e));
    } finally {
      setSegar(false);
    }
  }, []);
  const muatInfo = useCallback(async () => {
    try { setInfo2(await api("/api/forum/pengumuman")); } catch { /* pengumuman hanya pelengkap */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muat(); void muatInfo(); }, [muat, muatInfo]);

  const adaSamping = !!info2 && (info2.pengumuman.length > 0 || info2.admin);
  const grup = useMemo(() => kelompokkan(info?.masalah ?? []), [info]);
  const q = cari.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const cocokCari = (g: Grup) => q.every((k) => g.cari.includes(k));
  const diKelompok = (g: Grup, o: string) => !o || g.baris[0].permasalahan === o;
  const lolos: Record<Saring, (g: Grup) => boolean> = {
    semua: () => true,
    dijawab: (g) => g.baris.some((m) => m.jawaban),
    belum: (g) => !g.baris.some((m) => m.jawaban),
    saya: (g) => g.baris.some((m) => m.milik_saya),
  };
  const dasar = grup.filter((g) => cocokCari(g) && diKelompok(g, kelompok));
  const jumlahKelompok = (o: string) => grup.filter((g) => cocokCari(g) && lolos[saring](g) && diKelompok(g, o)).length;
  const tampil = dasar.filter(lolos[saring]);
  const resmi = (info?.faq ?? []).filter((f) => (!kelompok || f.kelompok === kelompok)
    && q.every((k) => `${f.kode} ${f.pertanyaan} ${f.jawaban} ${f.kelompok}`.toLowerCase().includes(k)));

  const ganti = (baru: Masalah) => setInfo((d) => d && { ...d, masalah: d.masalah.map((m) => (m.baris === baru.baris ? baru : m)) });
  const TAB: [Saring, string][] = [["semua", "Semua masalah"], ["dijawab", "Sudah dijawab"], ["belum", "Belum dijawab"], ["saya", "Laporan saya"]];
  const adaSaring = saring !== "semua" || !!kelompok || q.length > 0;
  const hapusSaring = () => { setSaring("semua"); setKelompok(""); setCari(""); setBatas(20); };

  return (
    <div className={h.page}>
      <header className={h.faqKepala}>
        <div className={h.faqJudul}>
          <div>
            <p className="chips">
              <span className="chip">LK Eskalasi</span>
              {info && <span className="chip">{grup.length} masalah tercatat</span>}
            </p>
            <h1>FAQ</h1>
            <p>Masalah sekolah yang pernah dilaporkan, beserta jawaban dari tim terkait.</p>
          </div>
          <div className={h.aksiKepala}>
            <Button variant="secondary" onClick={() => void muat(true)} loading={segar} disabled={!info}>Muat ulang</Button>
            <Button onClick={() => setLapor(true)} disabled={!info?.opsi}>Laporkan masalah</Button>
          </div>
        </div>
        <section className={h.alur} aria-labelledby="judul-alur">
          <div className={h.pita}><h2 id="judul-alur">Cari dulu sebelum melapor</h2></div>
          <label className={h.cariBesar}>
            <IkonCari size={20} />
            <input type="search" value={cari} onChange={(e) => { setCari(e.target.value); setBatas(20); }}
              placeholder="Cari masalah, nama sekolah, NPSN, atau ID" aria-label="Cari di FAQ" />
          </label>
          <ol className={h.langkah}>
            <li><b>1</b><span><strong>Cari</strong> kata kunci masalah, nama sekolah, NPSN, atau ID.</span></li>
            <li><b>2</b><span><strong>Sudah dijawab?</strong> Rujuk jawaban tim ke fasil.</span></li>
            <li><b>3</b><span><strong>Belum ada?</strong> Tekan Laporkan masalah, tim terkait yang menjawab.</span></li>
          </ol>
        </section>
      </header>

      {info?.perlu_link && <PasangLink onSelesai={() => void muat(true)} />}
      {galat && <Notice tone="bad" title="LK Eskalasi tidak bisa dibuka">{galat}</Notice>}
      {!info && !galat && <p className={h.memuat}><Spinner /> Membaca LK Eskalasi…</p>}

      {info?.opsi && (
        <div className={h.faqLayout}>
          <aside className={h.faqSamping} aria-label="Saring dan pengumuman">
            <section className={h.saringKartu} aria-labelledby="judul-status">
              <h2 id="judul-status">Status</h2>
              <div className={h.saringList} role="group" aria-labelledby="judul-status">
                {TAB.map(([k, l]) => (
                  <button key={k} type="button" aria-pressed={saring === k} onClick={() => { setSaring(k); setBatas(20); }}>
                    <span>{l}</span><b>{dasar.filter(lolos[k]).length}</b>
                  </button>
                ))}
              </div>
            </section>
            <section className={h.saringKartu} aria-labelledby="judul-kelompok">
              <h2 id="judul-kelompok">Permasalahan</h2>
              <div className={h.saringList} role="group" aria-labelledby="judul-kelompok">
                {["", ...info.opsi.permasalahan].map((o) => (
                  <button key={o || "semua"} type="button" aria-pressed={kelompok === o} onClick={() => { setKelompok(o); setBatas(20); }}>
                    <span>{o || "Semua permasalahan"}</span><b>{jumlahKelompok(o)}</b>
                  </button>
                ))}
              </div>
            </section>
            {adaSamping && <Pengumuman daftar={info2!.pengumuman} admin={info2!.admin} onUbah={() => void muatInfo()} />}
          </aside>

          <div className={h.faqUtama}>
            <div className={h.hasilKepala}>
              <h2>{TAB.find(([k]) => k === saring)![1]}{kelompok && <small>{kelompok}</small>}</h2>
              <span>
                {tampil.length} masalah
                {adaSaring && <button type="button" className={h.tautan} onClick={hapusSaring}>Hapus saringan</button>}
              </span>
            </div>

            {saring === "semua" && resmi.length > 0 && <JawabanResmi daftar={resmi} />}

            {tampil.length ? (
              <>
                <ul className={h.qa}>
                  {tampil.slice(0, batas).map((g) => <KartuTanya key={g.kunci} g={g} info={info} onUbah={ganti} />)}
                </ul>
                <div className={h.bawahDaftar}>
                  <span>Menampilkan {Math.min(batas, tampil.length)} dari {tampil.length} masalah</span>
                  {tampil.length > batas && (
                    <Button variant="secondary" size="sm" onClick={() => setBatas(batas + 20)}>Tampilkan 20 lagi</Button>
                  )}
                </div>
              </>
            ) : (
              <div className={h.kosong}>
                <b>{q.length ? "Belum ada yang cocok" : "Belum ada masalah di sini"}</b>
                <span>{q.length ? "Belum pernah dilaporkan? Catat supaya tim terkait bisa menjawab." : "Coba status atau permasalahan lain."}</span>
                {q.length > 0 && <Button onClick={() => setLapor(true)}>Laporkan masalah</Button>}
              </div>
            )}
          </div>
        </div>
      )}

      {lapor && info?.opsi && (
        <Dialog lebar judul="Laporkan masalah" onClose={() => setLapor(false)}
          sub="Tiga langkah, dicatat ke LK Eskalasi dengan ID Masalah baru.">
          <FormMasalah opsi={info.opsi} saya={info.saya.nama ?? ""} masalah={info.masalah} onSelesai={() => void muat(true)} />
        </Dialog>
      )}
    </div>
  );
}
