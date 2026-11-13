"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { useEvents, usePolling } from "@/lib/hooks";
import type { Aturan, BlastState } from "@/lib/lk";
import { salamSekarang } from "@/lib/pesan";
import { Button, Notice, Spinner } from "@/components/ui";
import { formatWa } from "@/components/today/WaPanel";
import { AturanDialog, Progres } from "./BlastView";
import { GantiWa, WaKartu } from "./GantiWa";
import s from "./blast.module.css";

type Jenis = "koor" | "fasil" | "sekolah";
type Saring = { pic: string[]; ptn: string[]; provinsi: string[]; angkatan: string[]; bimtek: string[]; belum: string[] };
type Opsi = {
  jumlah: Record<Jenis, number>; pic: string[]; ptn: string[]; provinsi: string[]; angkatan: string[]; bimtek: string[];
  komponen: { kode: string; label: string }[];
  variabel: Record<Jenis, { kode: string; arti: string }[]>; konfirmasi: string;
};
type Hitung = {
  jumlah: number; punya_nomor: number; tanpa_nomor: number; nomor_unik: number; contoh_nama: string[];
  contoh?: { nama: string; pesan: string }[]; sisa_variabel?: string[]; sudah_terkirim?: number;
};
type StateResp = { state: BlastState; aturan: Aturan; wa_terbuka: boolean; wa_otomatis: boolean; jam_kirim: boolean };

const DASAR = "/api/blast-admin";
const JENIS: { k: Jenis; label: string; ket: string }[] = [
  { k: "koor", label: "Koordinator", ket: "Semua koordinator fasil di LK." },
  { k: "fasil", label: "Fasilitator", ket: "Semua fasil di LK, dari seluruh PIC." },
  { k: "sekolah", label: "Kepala sekolah", ket: "Nomor kepala sekolah di LK." },
];
const SARING: { k: "pic" | "ptn" | "provinsi" | "angkatan" | "bimtek"; label: string }[] = [
  { k: "pic", label: "PIC" }, { k: "ptn", label: "PTN" }, { k: "provinsi", label: "Provinsi" },
  { k: "angkatan", label: "Angkatan" }, { k: "bimtek", label: "Bimtek Pelaporan" },
];
const KOSONG: Saring = { pic: [], ptn: [], provinsi: [], angkatan: [], bimtek: [], belum: [] };
const LANGKAH = [{ n: 1, label: "Target" }, { n: 2, label: "Pesan" }, { n: 3, label: "Tinjau & kirim" }] as const;
const fmt = (n: number) => n.toLocaleString("id-ID");

function durasi(detik: number) {
  const m = Math.round(detik / 60);
  if (m < 1) return "kurang dari 1 menit";
  if (m < 60) return `${m} menit`;
  const j = Math.floor(m / 60);
  return j >= 24 ? `${Math.floor(j / 24)} hari ${j % 24} jam` : `${j} jam ${m % 60 ? `${m % 60} menit` : ""}`.trim();
}

export function AdminBlastView() {
  const [opsi, setOpsi] = useState<Opsi | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [langkah, setLangkah] = useState<1 | 2 | 3>(1);
  const [jenis, setJenis] = useState<Jenis>("koor");
  const [saring, setSaring] = useState<Saring>(KOSONG);
  const [judul, setJudul] = useState("Blast admin");
  const [teks, setTeks] = useState("{salam} {nama},\n\n");
  const [hitung, setHitung] = useState<Hitung | null>(null);
  const [menghitung, setMenghitung] = useState(false);
  const [aturan, setAturan] = useState<Aturan>({ jeda_min: 20, jeda_max: 45, istirahat_setiap: 20, istirahat_menit: 5 });
  const [coba, setCoba] = useState(true);
  const [lewati, setLewati] = useState(true);
  const [abaikanJam, setAbaikanJam] = useState(false);
  const [konfirmasi, setKonfirmasi] = useState("");
  const [st, setSt] = useState<StateResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [pesanAksi, setPesanAksi] = useState<{ tone: "bad" | "ok"; teks: string } | null>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const [aturanBuka, setAturanBuka] = useState(false);
  const [gantiWa, setGantiWa] = useState(false);

  useEffect(() => {
    api<Opsi>(`${DASAR}/opsi`).then(setOpsi).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  const aturanSiap = useRef(false);
  const muatState = useCallback(async () => {
    try {
      const r = await api<StateResp>(`${DASAR}/state`);
      setSt(r);
      if (!aturanSiap.current) { setAturan(r.aturan); aturanSiap.current = true; }
    } catch { /* ditampilkan lewat pemberitahuan lain */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muatState(); }, [muatState]);
  usePolling(muatState, st?.state.running ? 3000 : 20000, true);
  useEvents((type) => { if (type.startsWith("kirim_")) void muatState(); });

  // hitung penerima (dan contoh pesan) setiap target/pesan berubah
  useEffect(() => {
    if (!opsi) return;
    const h = setTimeout(async () => {
      setMenghitung(true);
      try {
        setHitung(await post<Hitung>(`${DASAR}/hitung`, { jenis, saring, pesan: langkah >= 2 ? teks : "" }));
      } catch (e) {
        setPesanAksi({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
      } finally {
        setMenghitung(false);
      }
    }, 350);
    return () => clearTimeout(h);
  }, [opsi, jenis, saring, teks, langkah]);

  const n = hitung ? Math.max(0, hitung.nomor_unik - (lewati && !coba ? hitung.sudah_terkirim ?? 0 : 0)) : 0;
  const kirimN = coba ? Math.min(3, n) : n;
  const perkiraan = useMemo(() => {
    const jeda = (aturan.jeda_min + aturan.jeda_max) / 2 + 12;
    const rehat = aturan.istirahat_setiap ? Math.floor(kirimN / aturan.istirahat_setiap) * aturan.istirahat_menit * 60 : 0;
    return kirimN * jeda + rehat;
  }, [aturan, kirimN]);
  const hariKirim = perkiraan / (15 * 3600); // jam kirim 07.00–22.00

  const sisaVar = hitung?.sisa_variabel ?? [];
  const bisa2 = !!hitung && hitung.nomor_unik > 0;
  const bisa3 = bisa2 && !!teks.replace("{salam}", "").trim() && sisaVar.length === 0;
  const jalan = !!st?.state.running;
  const sahKonfirmasi = coba || konfirmasi.trim().toLowerCase() === opsi?.konfirmasi;

  const sisipkan = (kode: string) => {
    const el = areaRef.current;
    if (!el) { setTeks((t) => t + kode); return; }
    const a = el.selectionStart ?? teks.length, b = el.selectionEnd ?? teks.length;
    setTeks(teks.slice(0, a) + kode + teks.slice(b));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(a + kode.length, a + kode.length); });
  };

  async function mulai() {
    setBusy(true); setPesanAksi(null);
    try {
      const r = await post<{ jumlah: number; dilewati: number }>(`${DASAR}/start`, {
        jenis, saring, pesan: teks, judul, coba, lewati_terkirim: lewati, aturan, konfirmasi, abaikan_jam: abaikanJam,
      });
      setPesanAksi({ tone: "ok", teks: `Mulai mengirim ${fmt(r.jumlah)} pesan${r.dilewati ? `; ${fmt(r.dilewati)} penerima dilewati karena sudah menerima pesan ini` : ""}.` });
      setKonfirmasi("");
      void muatState();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setPesanAksi({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(false); }
  }

  if (error && !opsi) return <Notice tone="bad" title="Blast admin tidak bisa dimuat">{error}</Notice>;
  if (!opsi) return <div className={s.loading}><Spinner label="Memuat" /> Membaca seluruh LK…</div>;

  const jenisInfo = JENIS.find((j) => j.k === jenis)!;
  const nSaring = Object.values(saring).reduce((a, x) => a + x.length, 0);

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Blast admin</h1>
          <p>Kirim dari nomor WhatsApp kamu ke seluruh koordinator, fasil, atau kepala sekolah di LK.</p>
        </div>
        <div className={s.adminAlat}>
          <WaKartu jalan={jalan} onGanti={() => setGantiWa(true)} />
          <button type="button" className={s.aturanBtn} onClick={() => setAturanBuka(true)} aria-haspopup="dialog">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>
            <span><b>Aturan kirim</b><small>jeda {aturan.jeda_min}–{aturan.jeda_max} dtk{aturan.istirahat_setiap ? ` · istirahat ${aturan.istirahat_menit} mnt / ${aturan.istirahat_setiap} pesan` : " · tanpa istirahat"}</small></span>
          </button>
        </div>
      </header>
      {aturanBuka && <AturanDialog awal={aturan} onSimpan={(a) => { setAturan(a); setAturanBuka(false); }}
        onClose={() => setAturanBuka(false)} />}
      {gantiWa && <GantiWa onTutup={() => { setGantiWa(false); void muatState(); }} />}

      <Notice tone="warn" title="Dikirim dari satu nomor">
        Ribuan pesan dari satu nomor berisiko membuat nomor diblokir WhatsApp. Coba 3 pesan dulu, pakai jeda yang wajar,
        dan pakai nomor khusus bila bisa.
      </Notice>
      {st && !st.wa_otomatis && <Notice tone="warn" title="WhatsApp otomatis sedang mati">Nyalakan lagi lewat saklar di halaman LK.</Notice>}
      {st && !st.jam_kirim && !jalan && (
        <Notice tone={abaikanJam ? "warn" : "info"} title="Di luar jam kirim">
          Blast biasanya dikirim pukul 07.00–22.00 supaya tidak mengganggu penerima.{" "}
          <label className={s.cek}><input type="checkbox" checked={abaikanJam} onChange={(e) => setAbaikanJam(e.target.checked)} />
            Tetap kirim sekarang (abaikan jam kirim)</label>
        </Notice>
      )}
      {st?.state && (jalan || st.state.selesai) && <Progres state={st.state} onUbah={() => void muatState()} dasar={DASAR} />}
      {st?.state && !jalan && st.state.berhenti_karena && !st.state.coba && (
        <Notice tone="info" title="Melanjutkan blast yang terhenti">
          Tekan Mulai lagi dengan target dan pesan yang sama. Penerima yang sudah menerima pesan ini dilewati otomatis.
        </Notice>
      )}

      <div className={s.stepper} role="list" aria-label="Langkah blast admin">
        {LANGKAH.map((l) => {
          const boleh = l.n === 1 || (l.n === 2 && bisa2) || (l.n === 3 && bisa3);
          return (
            <button key={l.n} type="button" role="listitem" disabled={!boleh && l.n > langkah}
              className={`${s.step} ${langkah === l.n ? s.stepAktif : ""} ${langkah > l.n ? s.stepLewat : ""}`}
              aria-current={langkah === l.n ? "step" : undefined} onClick={() => boleh && setLangkah(l.n)}>
              <span className={s.stepNo}>{langkah > l.n ? "✓" : l.n}</span>
              <span className={s.stepTeks}>
                <b>{l.label}</b>
                <small>{l.n === 1 ? `${jenisInfo.label} · ${hitung ? fmt(hitung.nomor_unik) : "…"} nomor`
                  : l.n === 2 ? judul : n ? `${fmt(kirimN)} pesan · ±${durasi(perkiraan)}` : "–"}</small>
              </span>
            </button>
          );
        })}
      </div>

      {langkah === 1 && (
        <section className={s.card} aria-labelledby="h-target">
          <div className={s.cardHead}><h2 id="h-target">Siapa yang dikirimi?</h2></div>
          <div className={s.jenisGrid} role="radiogroup" aria-label="Jenis penerima">
            {JENIS.map((j) => (
              <button key={j.k} type="button" role="radio" aria-checked={jenis === j.k} onClick={() => setJenis(j.k)}>
                <b>{j.label}</b><small>{fmt(opsi.jumlah[j.k])} orang. {j.ket}</small>
              </button>
            ))}
          </div>
          <div className={s.saringAdmin}>
            <PilihBanyak label="Komponen belum" pilihan={opsi.komponen.map((k) => k.kode)} nilai={saring.belum}
              tampil={(v) => opsi.komponen.find((k) => k.kode === v)?.label ?? v}
              onUbah={(v) => setSaring({ ...saring, belum: v })} />
            {SARING.map((x) => (
              <PilihBanyak key={x.k} label={x.label} pilihan={opsi[x.k] ?? []} nilai={saring[x.k]}
                tampil={x.k === "angkatan" ? (v) => `Angkatan ${v}` : undefined}
                onUbah={(v) => setSaring({ ...saring, [x.k]: v })} />
            ))}
            {nSaring > 0 && <button type="button" className={s.linkBtn} onClick={() => setSaring(KOSONG)}>Hapus semua saringan</button>}
          </div>
          <div className={s.ringkasAdmin} aria-live="polite">
            {hitung ? (
              <>
                <b>{fmt(hitung.nomor_unik)}</b> nomor akan dikirimi
                <small>
                  {fmt(hitung.jumlah)} {jenisInfo.label.toLowerCase()} cocok
                  {saring.belum.length ? ` (belum ${saring.belum.map((k) => opsi.komponen.find((x) => x.kode === k)?.label ?? k).join(" / ")})` : ""}
                  {hitung.tanpa_nomor ? `, ${fmt(hitung.tanpa_nomor)} tanpa nomor` : ""}
                  {hitung.punya_nomor > hitung.nomor_unik ? `, ${fmt(hitung.punya_nomor - hitung.nomor_unik)} nomor dobel dikirimi sekali` : ""}
                  {hitung.contoh_nama.length ? `. Contoh: ${hitung.contoh_nama.slice(0, 4).join(", ")}…` : ""}
                </small>
              </>
            ) : <span>Menghitung…</span>}
            {menghitung && <Spinner />}
          </div>
          <div className={s.navBar}>
            <span />
            <Button onClick={() => setLangkah(2)} disabled={!bisa2}>Lanjut: tulis pesan</Button>
          </div>
        </section>
      )}

      {langkah === 2 && (
        <section className={s.card} aria-labelledby="h-pesan">
          <div className={s.cardHead}><h2 id="h-pesan">Pesannya apa?</h2></div>
          <div className={s.tulis}>
            <div className={s.editor}>
              <label className={s.judulInput}>Nama blast (untuk riwayat)
                <input value={judul} maxLength={80} onChange={(e) => setJudul(e.target.value)} />
              </label>
              <div className={s.varBar} aria-label="Sisipkan variabel">
                {opsi.variabel[jenis].map((v) => (
                  <button key={v.kode} type="button" title={v.arti} onClick={() => sisipkan(v.kode)}>{v.kode}</button>
                ))}
              </div>
              <textarea ref={areaRef} className={s.areaAdmin} rows={12} value={teks} onChange={(e) => setTeks(e.target.value)}
                aria-label="Isi pesan" />
              {sisaVar.length > 0 && <p className={s.err}>Variabel {sisaVar.join(", ")} tidak dikenal untuk {jenisInfo.label.toLowerCase()}.</p>}
            </div>
            <div className={s.preview}>
              <div className={s.previewHead}><span>Contoh untuk {hitung?.contoh?.[0]?.nama ?? "penerima pertama"}</span></div>
              <div className={s.hp}>
                {hitung?.contoh?.[0] ? <div className={s.bubble}>{formatWa(hitung.contoh[0].pesan.replace("{salam}", salamSekarang()))}</div>
                  : <p className={s.kosong}>Tulis pesan untuk melihat contohnya.</p>}
              </div>
            </div>
          </div>
          <div className={s.navBar}>
            <Button variant="ghost" onClick={() => setLangkah(1)}>Kembali</Button>
            <Button onClick={() => setLangkah(3)} disabled={!bisa3}>Lanjut: tinjau</Button>
          </div>
        </section>
      )}

      {langkah === 3 && hitung && (
        <section className={s.card} aria-labelledby="h-tinjau">
          <div className={s.cardHead}><h2 id="h-tinjau">Tinjau & kirim</h2></div>
          <div className={s.tinjau}>
            <dl className={s.ringkas}>
              <div><dt>Penerima</dt><dd><b>{fmt(hitung.nomor_unik)}</b> {jenisInfo.label.toLowerCase()}{nSaring ? " (disaring)" : ", seluruh LK"}</dd></div>
              {!!hitung.sudah_terkirim && (
                <div><dt>Sudah menerima pesan ini</dt><dd>{fmt(hitung.sudah_terkirim)} nomor
                  <label className={s.cek}><input type="checkbox" checked={lewati} onChange={(e) => setLewati(e.target.checked)} /> lewati</label></dd></div>
              )}
              <div><dt>Jeda antar pesan (detik)</dt><dd className={s.angkaBaris}>
                <span className={s.angka}><input type="number" min={5} max={600} value={aturan.jeda_min}
                  onChange={(e) => setAturan({ ...aturan, jeda_min: Number(e.target.value) })} aria-label="Jeda minimum" /><span>min</span></span>
                <span className={s.angka}><input type="number" min={5} max={900} value={aturan.jeda_max}
                  onChange={(e) => setAturan({ ...aturan, jeda_max: Number(e.target.value) })} aria-label="Jeda maksimum" /><span>maks</span></span>
              </dd></div>
              <div><dt>Istirahat</dt><dd className={s.angkaBaris}>
                <span className={s.angka}><input type="number" min={0} max={200} value={aturan.istirahat_setiap}
                  onChange={(e) => setAturan({ ...aturan, istirahat_setiap: Number(e.target.value) })} aria-label="Istirahat setiap" /><span>pesan</span></span>
                <span className={s.angka}><input type="number" min={1} max={60} value={aturan.istirahat_menit}
                  onChange={(e) => setAturan({ ...aturan, istirahat_menit: Number(e.target.value) })} aria-label="Lama istirahat" /><span>menit</span></span>
              </dd></div>
              <div className={s.ringkasAksen}><dt>Perkiraan waktu</dt><dd>±{durasi(perkiraan)}
                {!coba && !abaikanJam && hariKirim > 1 && <small>Lewat jam 22.00 pengiriman berhenti; tekan Mulai lagi besok untuk melanjutkan (sekitar {Math.ceil(hariKirim)} hari kirim).</small>}</dd></div>
            </dl>
            <div className={s.preview}>
              <div className={s.previewHead}><span>Contoh untuk {hitung.contoh?.[0]?.nama}</span></div>
              <div className={s.hp}>
                {hitung.contoh?.[0] && <div className={s.bubble}>{formatWa(hitung.contoh[0].pesan.replace("{salam}", salamSekarang()))}</div>}
              </div>
            </div>
          </div>
          <label className={s.cek}><input type="checkbox" checked={coba} onChange={(e) => setCoba(e.target.checked)} />
            Mode coba: buka chat 3 penerima pertama tanpa menekan kirim</label>
          {!coba && (
            <label className={s.judulInput}><span>Ketik <b>{opsi.konfirmasi}</b> untuk mengirim {fmt(kirimN)} pesan</span>
              <input value={konfirmasi} onChange={(e) => setKonfirmasi(e.target.value)} autoComplete="off" />
            </label>
          )}
          {pesanAksi && <Notice tone={pesanAksi.tone === "ok" ? "ok" : "bad"}>{pesanAksi.teks}</Notice>}
          <div className={s.navBar}>
            <Button variant="ghost" onClick={() => setLangkah(2)}>Kembali</Button>
            <div className={s.kirimAksi}>
              <Button onClick={() => void mulai()} loading={busy}
                disabled={jalan || !kirimN || !sahKonfirmasi || !st?.wa_otomatis || !(st?.jam_kirim || abaikanJam)}>
                {coba ? "Coba 3 pesan" : `Kirim ${fmt(kirimN)} pesan`}
              </Button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function PilihBanyak({ label, pilihan, nilai, onUbah, tampil }: {
  label: string; pilihan: string[]; nilai: string[]; onUbah: (v: string[]) => void; tampil?: (v: string) => string;
}) {
  const [cari, setCari] = useState("");
  const t = tampil ?? ((v: string) => v);
  const terlihat = pilihan.filter((p) => t(p).toLowerCase().includes(cari.toLowerCase()));
  const ubah = (p: string) => onUbah(nilai.includes(p) ? nilai.filter((x) => x !== p) : [...nilai, p]);
  return (
    <details className={s.pilih}>
      <summary aria-label={`Saring ${label}`}>
        {label}: {nilai.length === 0 ? (label === "Komponen belum" ? "tidak disaring" : "semua")
          : nilai.length === 1 ? t(nilai[0]) : `${nilai.length} dipilih`}
      </summary>
      <div className={s.pilihPanel}>
        {pilihan.length > 8 && <input type="search" placeholder={`Cari ${label}`} value={cari} onChange={(e) => setCari(e.target.value)} />}
        <ul>
          {terlihat.map((p) => (
            <li key={p}><label><input type="checkbox" checked={nilai.includes(p)} onChange={() => ubah(p)} />{t(p)}</label></li>
          ))}
        </ul>
        {nilai.length > 0 && <button type="button" onClick={() => onUbah([])}>Kosongkan</button>}
      </div>
    </details>
  );
}
