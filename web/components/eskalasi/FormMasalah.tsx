"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, post } from "@/lib/api";
import type { Masalah, OpsiEskalasi, SekolahEskalasi } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import { idSiap, PilihFoto, pesan, type FotoItem } from "@/components/forum/bersama";
import { hariIni, toneStatus } from "./bagian";
import s from "./esk.module.css";

/** Panduan Pengisian bagian 6: kelompok permasalahan -> tim tujuan yang biasa. Hanya saran awal centang. */
const SARAN_TIM: Record<string, string[]> = {
  "Komunikasi dengan Sekolah": ["Tim Monitoring"],
  "Progres Fisik Pekerjaan": ["Tim Monitoring", "PMO"],
  "Pelaporan & Dokumen": ["Tim Monitoring", "Tim Substansi"],
  "Reviu Fasilitator": ["Tim Monitoring", "PMO"],
  "Penyaluran/Pencairan Dana": ["Tim Penyaluran", "PMO"],
  "Aplikasi & Akun": ["Tim Aplikasi"],
  "RAB, Adendum & CCO": ["Tim Substansi", "PMO"],
  "Pengelola Sekolah & P2SP": ["Tim Substansi", "Tim Regulasi"],
  "Regulasi & Juknis": ["Tim Regulasi", "Tim Substansi"],
};

type SekolahIsi = { npsn: string; data?: SekolahEskalasi; galat?: string };
export type Tercatat = { id: string; npsn: string; nama: string };

/** "Tingkat 2 – Reguler" -> "Reguler" */
const pendek = (t: string) => t.split(/\s[–-]\s/).pop() ?? t;

function Centang() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Langkah({ no, judul, sub, selesai, children }: { no: number; judul: string; sub: string; selesai: boolean; children: ReactNode }) {
  return (
    <section className={s.kolom} aria-labelledby={`langkah-${no}`}>
      <header className={s.kolomHead}>
        <span className={`${s.nomor} ${selesai ? s.nomorOk : ""}`} aria-hidden="true">{selesai ? <Centang /> : no}</span>
        <div>
          <h3 id={`langkah-${no}`}>{judul}</h3>
          <p>{sub}</p>
        </div>
      </header>
      <div className={s.kolomIsi}>{children}</div>
    </section>
  );
}

/** Ringkasan masalah yang sudah tercatat untuk satu sekolah. */
export function StatusSekolah({ npsn, masalah }: { npsn: string; masalah: Masalah[] }) {
  const punya = masalah.filter((m) => m.npsn === npsn);
  if (!punya.length) return <span className={s.stBersih}>Belum ada masalah tercatat</span>;
  const aktif = punya.filter((m) => m.status !== "Selesai");
  return (
    <span className={s.stDaftar}>
      <span className={aktif.length ? s.stAktif : s.stBersih}>
        {aktif.length ? `${aktif.length} masalah aktif` : "Semua masalah selesai"}
        {punya.length > aktif.length && aktif.length ? ` · ${punya.length - aktif.length} selesai` : ""}
      </span>
      {aktif.slice(0, 3).map((m) => (
        <span key={m.baris} className={`${s.stItem} ${s[`nada_${toneStatus(m.status)}`]}`} title={m.keterangan}>
          {m.id} · {m.permasalahan || "–"} · {m.status || "Belum ada status"}
        </span>
      ))}
      {aktif.length > 3 && <span className={s.stItem}>+{aktif.length - 3} lagi</span>}
    </span>
  );
}

export function FormMasalah({ opsi, saya, masalah, awal, sekolahFasil, onSelesai }: {
  opsi: OpsiEskalasi;
  saya: string;
  /** Masalah yang sudah ada (status per sekolah) */
  masalah: Masalah[];
  awal?: { npsn?: string[] };
  /** Dibuka dari panel fasil: cukup centang sekolah binaan fasil ini (tanpa cari NPSN) */
  sekolahFasil?: { npsn: string; nama: string }[];
  onSelesai?: (hasil: Tercatat[]) => void;
}) {
  const modeFasil = !!sekolahFasil?.length;
  const [sumber, setSumber] = useState("Sekolah");
  const [pilih, setPilih] = useState<string[]>(modeFasil ? (awal?.npsn ?? []).filter((n) => sekolahFasil!.some((x) => x.npsn === n)) : []);
  const [cari, setCari] = useState<SekolahIsi[]>([]);
  const [ketik, setKetik] = useState("");
  const [topik, setTopik] = useState("");
  const [permasalahan, setPermasalahan] = useState("");
  const [tingkat, setTingkat] = useState(opsi.tingkat[0] ?? "");
  const [tglAwal, setTglAwal] = useState(hariIni());
  const [ket, setKet] = useState("");
  const [foto, setFoto] = useState<FotoItem[]>([]);
  const [fotoSibuk, setFotoSibuk] = useState(false);
  const [tautan, setTautan] = useState("");
  const [agregasi, setAgregasi] = useState<"Ya" | "Tidak" | "">("");
  const [tim, setTim] = useState<string[]>([]);
  const [timDisentuh, setTimDisentuh] = useState(false);
  const [adaJawaban, setAdaJawaban] = useState(false);
  const [jawaban, setJawaban] = useState("");
  const [status, setStatus] = useState("Selesai");
  const [busy, setBusy] = useState(false);
  const [galat, setGalat] = useState("");
  const [hasil, setHasil] = useState<Tercatat[] | null>(null);
  const awalDipakai = useRef(false);

  const tambah = async (teks: string) => {
    const baru = [...new Set(teks.split(/[\s,;]+/).map((x) => x.replace(/\D/g, "")).filter((x) => x.length >= 6))]
      .filter((x) => !cari.some((y) => y.npsn === x));
    if (!baru.length) return;
    let daftar = [...cari, ...baru.map((npsn) => ({ npsn }))];
    setCari(daftar);
    for (const npsn of baru) {
      try {
        const d = await api<SekolahEskalasi>(`/api/eskalasi/sekolah/${encodeURIComponent(npsn)}`);
        daftar = daftar.map((x) => (x.npsn === npsn ? { npsn, data: d } : x));
      } catch (e) {
        daftar = daftar.map((x) => (x.npsn === npsn ? { npsn, galat: pesan(e) } : x));
      }
      setCari(daftar);
    }
  };

  // Dari luar panel fasil dengan NPSN awal: langsung dicari sekali
  useEffect(() => {
    if (modeFasil || awalDipakai.current || !awal?.npsn?.length) return;
    awalDipakai.current = true;
    void tambah(awal.npsn.join(" "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pilihMasalah = (v: string) => {
    setPermasalahan(v);
    if (!timDisentuh) setTim((SARAN_TIM[v] ?? []).filter((t) => opsi.tim.includes(t)));
  };
  const gantiTim = (t: string) => {
    setTimDisentuh(true);
    setTim(tim.includes(t) ? tim.filter((x) => x !== t) : [...tim, t]);
  };

  const npsn = modeFasil ? pilih : cari.filter((x) => x.data).map((x) => x.npsn);
  const links = tautan.split(/\s+/).map((x) => x.trim()).filter(Boolean);
  const ok1 = sumber === "Sekolah" ? npsn.length > 0 : npsn.length > 0 || topik.trim().length > 0;
  const ok2 = !!permasalahan && ket.trim().length >= 10 && !fotoSibuk && links.every((l) => /^https?:\/\//.test(l));
  const ok3 = agregasi === "Tidak" || (agregasi === "Ya" && tim.length > 0);
  const kurang = [
    !ok1 && (sumber === "Sekolah" ? "pilih sekolah" : "pilih sekolah atau isi topik"),
    cari.some((x) => !x.data && !x.galat) && "tunggu data sekolah",
    cari.some((x) => x.galat) && "hapus NPSN yang tidak ditemukan",
    !permasalahan && "pilih permasalahan",
    ket.trim().length < 10 && "tulis keterangan",
    fotoSibuk && "tunggu foto terunggah",
    links.some((l) => !/^https?:\/\//.test(l)) && "tautan harus diawali http",
    !agregasi && "tentukan perlu agregasi",
    agregasi === "Ya" && !tim.length && "centang tim tujuan",
  ].filter(Boolean) as string[];

  const kirim = async () => {
    setBusy(true);
    setGalat("");
    try {
      const r = await post<{ ditulis: Tercatat[] }>("/api/eskalasi", {
        sumber, npsn, topik, keterangan: ket, permasalahan, tingkat, evidence: [...idSiap(foto), ...links],
        tgl_awal: tglAwal, agregasi, tim: agregasi === "Ya" ? tim : [],
        ...(adaJawaban && jawaban.trim() ? { jawaban, status, pengisi: saya } : {}),
      });
      setHasil(r.ditulis);
      onSelesai?.(r.ditulis);
    } catch (e) {
      setGalat(pesan(e));
    } finally {
      setBusy(false);
    }
  };

  const ulang = () => {
    setHasil(null); setPilih([]); setCari([]); setKetik(""); setTopik(""); setKet(""); setFoto([]); setTautan("");
    setJawaban(""); setAdaJawaban(false); setAgregasi(""); setTim([]); setTimDisentuh(false); setPermasalahan("");
  };

  if (hasil) {
    return (
      <div className={s.sukses}>
        <span className={s.suksesIkon} aria-hidden="true"><Centang /></span>
        <h3>Tercatat di LK Eskalasi</h3>
        <p>{hasil.map((h) => <span key={h.id} className={s.kode}>{h.id}</span>)}</p>
        <p className={s.bantu}>
          {hasil.length > 1 ? `${hasil.length} baris, satu per sekolah. ` : ""}
          {agregasi === "Ya" ? "PIC Eskalasi akan mengelompokkan dan meneruskannya ke tim tujuan." : "Jawabannya diisi di LK untuk sekolah ini."}
        </p>
        <Button variant="secondary" onClick={ulang}>Laporkan masalah lain</Button>
      </div>
    );
  }

  const nomorSekolah = modeFasil ? sekolahFasil!.length : cari.length;
  const ringkas = [
    npsn.length ? `${npsn.length} sekolah` : topik.trim() ? topik.trim() : "",
    permasalahan,
    agregasi === "Ya" && tim.length ? `ke ${tim.join(", ")}` : agregasi === "Tidak" ? "tanpa agregasi" : "",
  ].filter(Boolean).join(" · ");

  return (
    <div className={s.formLebar}>
      <div className={s.langkahGrid}>
        {/* ---------- 1. Sekolah ---------- */}
        <Langkah no={1} judul="Sekolah terdampak" selesai={ok1}
          sub={modeFasil ? "Centang sekolah yang mengalami masalah ini" : "Ketik NPSN; data sekolah terisi dari LK"}>
          <label className={s.field}>
            <span className={s.label}>Sumber masalah</span>
            <select value={sumber} onChange={(e) => setSumber(e.target.value)}>
              {opsi.sumber.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>

          {modeFasil ? (
            <div className={s.field}>
              <span className={s.label}>Sekolah binaan <span>{pilih.length}/{nomorSekolah} dipilih</span>
                {nomorSekolah > 1 && (
                  <button type="button" className={s.tautan} style={{ marginLeft: "auto" }}
                    onClick={() => setPilih(pilih.length === nomorSekolah ? [] : sekolahFasil!.map((x) => x.npsn))}>
                    {pilih.length === nomorSekolah ? "Kosongkan" : "Pilih semua"}
                  </button>
                )}
              </span>
              <div className={s.pilihSekolah}>
                {sekolahFasil!.map((x) => {
                  const on = pilih.includes(x.npsn);
                  return (
                    <label key={x.npsn} className={on ? s.on : ""}>
                      <input type="checkbox" checked={on}
                        onChange={() => setPilih(on ? pilih.filter((y) => y !== x.npsn) : [...pilih, x.npsn])} />
                      <span>
                        <b>{x.nama}</b>
                        <small>NPSN {x.npsn}</small>
                        <StatusSekolah npsn={x.npsn} masalah={masalah} />
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className={s.field}>
              <label className={s.label} htmlFor="esk-npsn">NPSN <span>{sumber === "Sekolah" ? "wajib" : "bila ada sekolah terdampak"}</span></label>
              <div className={s.npsnBaris}>
                <input id="esk-npsn" type="text" inputMode="numeric" value={ketik} placeholder="Ketik NPSN lalu Enter"
                  onChange={(e) => setKetik(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void tambah(ketik); setKetik(""); } }} />
                <Button variant="secondary" disabled={!ketik.trim()} onClick={() => { void tambah(ketik); setKetik(""); }}>Tambah</Button>
              </div>
              {cari.length > 0 && (
                <ul className={s.sekolahKartu}>
                  {cari.map((x) => (
                    <li key={x.npsn}>
                      <div>
                        {!x.data && !x.galat && <span className={s.memuat}><Spinner /> Mencari {x.npsn}…</span>}
                        {x.galat && <><b>NPSN {x.npsn}</b><small className={s.galat}>{x.galat}</small></>}
                        {x.data && (
                          <>
                            <b>{x.data.nama}</b>
                            <small>NPSN {x.npsn} · {x.data.ptn || "PTN –"}</small>
                            <small>Fasil {x.data.fasil || "–"} · Petugas {x.data.petugas || "–"}</small>
                            <StatusSekolah npsn={x.npsn} masalah={masalah} />
                          </>
                        )}
                      </div>
                      <button type="button" className={s.hapusX} aria-label={`Hapus NPSN ${x.npsn}`}
                        onClick={() => setCari(cari.filter((y) => y.npsn !== x.npsn))}>×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {sumber !== "Sekolah" && (
            <label className={s.field}>
              <span className={s.label}>Nama sumber / topik <span>{npsn.length ? "opsional" : "wajib bila tanpa sekolah"}</span></span>
              <input type="text" value={topik} maxLength={200} onChange={(e) => setTopik(e.target.value)}
                placeholder="Mis. nama PTN, dinas, atau menu aplikasi" />
            </label>
          )}
        </Langkah>

        {/* ---------- 2. Permasalahan ---------- */}
        <Langkah no={2} judul="Permasalahan" sub="Apa yang terjadi dan buktinya" selesai={ok2}>
          <div className={s.dua2}>
            <label className={s.field}>
              <span className={s.label}>Kelompok</span>
              <select value={permasalahan} onChange={(e) => pilihMasalah(e.target.value)}>
                <option value="">Pilih kelompok</option>
                {opsi.permasalahan.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className={s.field}>
              <span className={s.label}>Tanggal awal</span>
              <input type="date" value={tglAwal} max={hariIni()} onChange={(e) => setTglAwal(e.target.value)} />
            </label>
          </div>
          {opsi.tingkat.length > 0 && (
            <div className={s.field}>
              <span className={s.label}>Tingkat</span>
              <div className={s.segPilih} role="radiogroup" aria-label="Tingkat">
                {opsi.tingkat.map((o) => (
                  <button key={o} type="button" role="radio" aria-checked={tingkat === o}
                    className={o.startsWith("Tingkat 3") ? s.segBahaya : ""} onClick={() => setTingkat(o)}>{pendek(o)}</button>
                ))}
              </div>
            </div>
          )}
          <label className={`${s.field} ${s.tumbuh}`}>
            <span className={s.label}>Keterangan</span>
            <textarea value={ket} maxLength={2000} onChange={(e) => setKet(e.target.value)}
              placeholder="Apa masalahnya, sejak kapan, dampaknya, apa yang sudah dicoba, dan apa yang dibutuhkan dari tim." />
          </label>
          <div className={s.field}>
            <span className={s.label}>Evidence <span>opsional</span></span>
            <PilihFoto nilai={foto} onChange={setFoto} onSibuk={setFotoSibuk} />
            <input type="url" value={tautan} onChange={(e) => setTautan(e.target.value)} placeholder="atau tempel tautan bukti"
              aria-label="Tautan evidence" />
          </div>
        </Langkah>

        {/* ---------- 3. Agregasi ---------- */}
        <Langkah no={3} judul="Agregasi & tim" sub="Perlu jawaban resmi dari tim?" selesai={ok3}>
          <div className={s.pilihan} role="radiogroup" aria-label="Perlu agregasi">
            <button type="button" role="radio" aria-checked={agregasi === "Ya"} onClick={() => setAgregasi("Ya")}>
              <b>Ya, perlu agregasi</b>
              <small>Bisa dialami sekolah lain atau butuh jawaban resmi. Ragu? Pilih ini.</small>
            </button>
            <button type="button" role="radio" aria-checked={agregasi === "Tidak"} onClick={() => setAgregasi("Tidak")}>
              <b>Tidak</b>
              <small>Kasus khusus sekolah ini saja.</small>
            </button>
          </div>

          {agregasi === "Ya" && (
            <fieldset className={s.field}>
              <legend>Tim tujuan <span>{permasalahan && !timDisentuh && tim.length ? "sesuai panduan, boleh diubah" : "centang yang perlu"}</span></legend>
              <div className={s.tim}>
                {opsi.tim.map((t) => (
                  <label key={t} className={tim.includes(t) ? s.on : ""}>
                    <input type="checkbox" checked={tim.includes(t)} onChange={() => gantiTim(t)} />
                    <span>{t}{opsi.pic[t] && <small>PIC {opsi.pic[t]}</small>}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {agregasi === "Tidak" && (
            <p className={s.infoLembut}>Tidak diteruskan ke tim. Cukup dijawab di LK untuk sekolah ini, dengan batas 3 hari kerja.</p>
          )}

          <div className={s.jawabOpsional}>
            <label className={s.saklar}>
              <input type="checkbox" checked={adaJawaban} onChange={(e) => setAdaJawaban(e.target.checked)} />
              <span>Sudah ada jawabannya</span>
            </label>
            {adaJawaban && (
              <>
                <textarea rows={3} value={jawaban} maxLength={2000} onChange={(e) => setJawaban(e.target.value)}
                  placeholder="Jawaban dari tim terkait" aria-label="Jawaban tim terkait" />
                <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status tindak lanjut">
                  {opsi.status.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </>
            )}
          </div>
        </Langkah>
      </div>

      <footer className={s.kaki}>
        <div className={s.kakiInfo}>
          {galat ? <span className={s.galat}>{galat}</span>
            : kurang.length ? <span>Belum lengkap: {kurang.join(", ")}.</span>
              : <span className={s.kakiSiap}>{ringkas}</span>}
        </div>
        <Button loading={busy} disabled={busy || kurang.length > 0} onClick={() => void kirim()}>
          {busy ? "Mencatat…" : npsn.length > 1 ? `Catat ${npsn.length} sekolah` : "Catat ke LK Eskalasi"}
        </Button>
      </footer>
    </div>
  );
}
