"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { useCountdown, useEvents, usePolling } from "@/lib/hooks";
import { KELOMPOK_INFO, TAHAP_LABEL, type Aturan, type BlastState, type JenisPenerima, type Kelompok, type Penerima,
  type TemplateSaya } from "@/lib/lk";
import { SALAM, VARIABEL, isi as isiTemplate, kosong, persempit, salamSekarang, templateBawaan, type Template } from "@/lib/pesan";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { formatWa } from "@/components/today/WaPanel";
import { GantiWa, WaKartu } from "./GantiWa";
import { PendengarKartu } from "./Pendengar";
import s from "./blast.module.css";

type DataPenerima = {
  jenis: JenisPenerima; penerima: Penerima[]; petugas: string; jumlah_tanpa_nomor: number; tag: string[];
  kelompok: { kode: Kelompok; label: string }[]; angkatan: string[]; kab: string[]; bimtek?: string[];
  komponen?: { kode: string; label: string }[];
};
type StateResp = { state: BlastState; aturan: Aturan; wa_terbuka: boolean; wa_otomatis: boolean; jam_kirim: boolean;
  template: TemplateSaya[] };
type Langkah = 1 | 2 | 3;
/** Template dari tab "BC - ..." sheet Draft Broadcast: pesan siap kirim per penerima (kunci -> teks). */
type BcTpl = { kode: string; judul: string; tab: string; jenis: JenisPenerima; per: Record<string, string>; tanpa_cocok: string[] };
type BcResp = { ada_link: boolean; template: BcTpl[]; error: string };

const CHAT_INFO = {
  dibalas: { label: "Sudah membalas", tone: "ok" },
  dibaca: { label: "Dibaca, belum dibalas", tone: "warn" },
  terkirim: { label: "Terkirim, belum dibaca", tone: "info" },
} as const;
const CHAT_PILIH = [
  { k: "belum", label: "Belum di-chat di sesi ini" },
  { k: "terkirim", label: CHAT_INFO.terkirim.label },
  { k: "dibaca", label: CHAT_INFO.dibaca.label },
  { k: "dibalas", label: CHAT_INFO.dibalas.label },
];

const JENIS: { k: JenisPenerima; label: string; ket: string }[] = [
  { k: "fasil", label: "Fasilitator", ket: "Fasil binaan Anda. Pesan menyebut sekolah dan to-do masing-masing." },
  { k: "koor", label: "Koordinator", ket: "Koordinator dari fasil binaan. Pesan berisi rekap per fasil." },
  { k: "sekolah", label: "Kepala sekolah", ket: "Langsung ke sekolah binaan: laporan yang perlu dilengkapi sekolah." },
];
const KELOMPOK_SEKOLAH: { kode: string; label: string }[] = [
  { kode: "pendahuluan", label: TAHAP_LABEL.pendahuluan }, { kode: "berkala", label: TAHAP_LABEL.berkala },
  { kode: "l50", label: TAHAP_LABEL.l50 }, { kode: "l100", label: TAHAP_LABEL.l100 }, { kode: "beres", label: "Semua hijau" },
];
const KELOMPOK_KOOR: { kode: string; label: string }[] = [
  { kode: "perlu_telepon", label: "Punya fasil sulit dihubungi" }, { kode: "terhubung", label: "Fasilnya bisa dihubungi" },
];
const LANGKAH: { n: Langkah; label: string }[] = [{ n: 1, label: "Target" }, { n: 2, label: "Pesan" }, { n: 3, label: "Tinjau & kirim" }];
const CUSTOM = "custom";

/** Pilihan penerima (yang di-uncentang + angkatan + bimtek) disimpan di browser ini per jenis penerima. */
type Pilihan = { buang: string[]; angkatan: string[]; bimtek: string[] };
const kunciPilihan = (j: JenisPenerima) => `lkm_blast_pilihan:${j}`;
function bacaPilihan(j: JenisPenerima): Pilihan {
  try {
    const x = JSON.parse(localStorage.getItem(kunciPilihan(j)) ?? "null");
    return { buang: Array.isArray(x?.buang) ? x.buang : [], angkatan: Array.isArray(x?.angkatan) ? x.angkatan : [],
      bimtek: Array.isArray(x?.bimtek) ? x.bimtek : [] };
  } catch { return { buang: [], angkatan: [], bimtek: [] }; }
}
function tulisPilihan(j: JenisPenerima, p: Pilihan) {
  try { localStorage.setItem(kunciPilihan(j), JSON.stringify(p)); } catch { /* penyimpanan browser tidak tersedia */ }
}

function durasi(detik: number) {
  const m = Math.round(detik / 60);
  if (m < 1) return "kurang dari 1 menit";
  return m >= 60 ? `${Math.floor(m / 60)} jam ${m % 60 ? `${m % 60} menit` : ""}`.trim() : `${m} menit`;
}

export function BlastView() {
  const [langkah, setLangkah] = useState<Langkah>(1);
  const [jenis, setJenis] = useState<JenisPenerima>("fasil");
  const [data, setData] = useState<DataPenerima | null>(null);
  const [st, setSt] = useState<StateResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);
  // saringan
  const [kel, setKel] = useState<string[]>([]);
  const [tag, setTag] = useState("");
  const [angkatan, setAngkatan] = useState<string[]>([]);
  const [bimtek, setBimtek] = useState<string[]>([]);
  const [kab, setKab] = useState("");
  const [komp, setKomp] = useState<string[]>([]);
  const [statChat, setStatChat] = useState("");
  const [hanyaTodo, setHanyaTodo] = useState(true);
  const [lewatiHariIni, setLewatiHariIni] = useState(false);
  const [cari, setCari] = useState("");
  const [buang, setBuang] = useState<Set<string>>(new Set());
  const [ambil, setAmbil] = useState("");
  const [pilihanSiap, setPilihanSiap] = useState<JenisPenerima | null>(null);
  // pesan
  const [tpl, setTpl] = useState<string>(() => templateBawaan("fasil")[0].kode);
  const [teks, setTeks] = useState(() => templateBawaan("fasil")[0].teks);
  const [judul, setJudul] = useState(() => templateBawaan("fasil")[0].judul);
  const [lihat, setLihat] = useState(0);
  const [aturan, setAturan] = useState<Aturan>({ jeda_min: 20, jeda_max: 45, istirahat_setiap: 20, istirahat_menit: 5 });
  const [aturanBuka, setAturanBuka] = useState(false);
  const [gantiWa, setGantiWa] = useState(false);
  const [mulai, setMulai] = useState<{ busy: boolean; error?: string; konfirmasi?: boolean }>({ busy: false });
  /** Penerima yang dilewati server karena hari ini sudah dikirimi blast bertopik sama. */
  const [dobel, setDobel] = useState<string[]>([]);
  const [abaikanJam, setAbaikanJam] = useState(false);
  const [bc, setBc] = useState<BcResp | null>(null);
  const [bcMuat, setBcMuat] = useState(false);
  const teksRef = useRef<HTMLTextAreaElement>(null);
  const atasRef = useRef<HTMLDivElement>(null);

  const muatState = useCallback(async () => {
    try {
      const r = await api<StateResp>("/api/blast/state");
      setSt(r);
      return r;
    } catch { return null; }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muatState().then((r) => { if (r) setAturan(r.aturan); });
  }, [muatState]);
  usePolling(muatState, 3000, !!st?.state.running);
  useEvents((t) => { if (t.startsWith("kirim_")) void muatState(); });

  const muatPenerima = useCallback(async (j: JenisPenerima) => {
    setMemuat(true);
    try {
      setData(await api<DataPenerima>(`/api/blast/penerima?jenis=${j}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMemuat(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muatPenerima(jenis); }, [jenis, muatPenerima]);

  // pilihan penerima tersimpan: dibaca saat jenis berganti, ditulis setiap berubah
  useEffect(() => {
    const x = bacaPilihan(jenis);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBuang(new Set(x.buang)); setAngkatan(x.angkatan); setBimtek(x.bimtek); setPilihanSiap(jenis);
  }, [jenis]);
  useEffect(() => {
    if (pilihanSiap === jenis) tulisPilihan(jenis, { buang: [...buang], angkatan, bimtek });
  }, [buang, angkatan, bimtek, jenis, pilihanSiap]);

  const muatBc = useCallback(async (refresh = false) => {
    setBcMuat(true);
    try { setBc(await api<BcResp>(`/api/blast/bc${refresh ? "?refresh=true" : ""}`)); }
    catch (e) { setBc({ ada_link: true, template: [], error: e instanceof Error ? e.message : String(e) }); }
    finally { setBcMuat(false); }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void muatBc(); }, [muatBc]);
  const bcJenis = useMemo(() => (bc?.template ?? []).filter((t) => t.jenis === jenis), [bc, jenis]);
  const bcAktif = bcJenis.find((t) => t.kode === tpl);

  const daftarTpl: Template[] = useMemo(() => [
    ...templateBawaan(jenis),
    ...(st?.template ?? []).filter((t) => t.jenis === jenis)
      .map((t) => ({ kode: `saya:${t.id}`, judul: t.judul, ket: "Template simpanan Anda", teks: t.teks, bawaan: false })),
    ...bcJenis.map((t) => ({ kode: t.kode, judul: t.judul, ket: `Dari sheet Draft Broadcast, tab ${t.tab}`, teks: "", bawaan: false })),
  ], [jenis, st?.template, bcJenis]);

  /** Pesan untuk satu penerima: dari sheet (template BC) atau dari template dengan variabel. */
  const pesanUntuk = (p: Penerima, salamNanti: boolean) => {
    if (!bcAktif) return isiTemplate(teks, p, data?.petugas ?? "", salamNanti);
    const x = bcAktif.per[p.kunci] ?? "";
    return salamNanti ? x : x.split(SALAM).join(salamSekarang().replace(/^Selamat /, ""));
  };
  const tanpaPesan = (t: Template, p: Penerima) => {
    const b = bcJenis.find((x) => x.kode === t.kode);
    return b ? !b.per[p.kunci] : kosong(t.teks, p).length > 0;
  };

  function gantiJenis(j: JenisPenerima) {
    if (j === jenis) return;
    const t = templateBawaan(j)[0];
    setJenis(j); setData(null);
    setPilihanSiap(null);
    setTpl(t.kode); setTeks(t.teks); setJudul(t.judul); setKel([]); setTag(""); setKab("");
    setLihat(0);
  }

  function ke(n: Langkah) {
    setLangkah(n);
    setMulai({ busy: false });
    requestAnimationFrame(() => atasRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  // saringan selain komponen; jumlah di tiap tombol komponen dihitung dari sini
  const dasar = useMemo(() => {
    if (!data) return [];
    const q = cari.trim().toLowerCase();
    return data.penerima.filter((p) => (!kel.length || kel.includes(p.kelompok)) && (!tag || p.tag.includes(tag))
      && (!angkatan.length || p.angkatan.some((a) => angkatan.includes(a))) && (!kab || p.kab.includes(kab))
      && (!bimtek.length || (p.bimtek ?? []).some((b) => bimtek.includes(b)))
      && (!hanyaTodo || p.perlu > 0) && (!statChat || (p.chat ?? "") === (statChat === "belum" ? "" : statChat))
      && (!q || p.nama.toLowerCase().includes(q)));
  }, [data, kel, tag, angkatan, bimtek, kab, hanyaTodo, statChat, cari]);
  const terpilih = useMemo(() => dasar.map((p) => persempit(p, komp)).filter((p): p is Penerima => !!p),
    [dasar, komp]);
  const labelKomp = (data?.komponen ?? []).filter((k) => komp.includes(k.kode)).map((k) => k.label).join(" & ");

  const alasanTarget = (p: Penerima) => !p.punya_nomor ? "Nomor kosong"
    : lewatiHariIni && (p.chat_hari_ini || p.terakhir_blast)
      ? `Sudah di-chat hari ini ${p.chat_hari_ini || p.terakhir_blast}` : "";
  /** Topik blast ini, disimpan bersama kiriman supaya tampil sebagai "sudah di-blast … · topik". */
  const topik = labelKomp || judul;
  const sudahSesi = (p: Penerima) => (p.blast_sesi ?? []).length > 0;
  /** Centang/uncentang sekelompok penerima tanpa mengubah pilihan penerima lain (yang tidak tampil). */
  function aturPilih(daftar: Penerima[], pilih: boolean) {
    const b = new Set(buang);
    for (const p of daftar) { if (pilih) b.delete(p.kunci); else b.add(p.kunci); }
    setBuang(b);
  }
  /** Centang N penerima pertama (urutan daftar) yang bisa dikirimi; sisanya di saringan ini diuncentang. */
  function ambilSejumlah(n: number) {
    const bisa = terpilih.filter((p) => !alasanTarget(p));
    const b = new Set(buang);
    bisa.forEach((p, i) => { if (i < n) b.delete(p.kunci); else b.add(p.kunci); });
    setBuang(b);
  }
  const target =terpilih.filter((p) => !alasanTarget(p) && !buang.has(p.kunci));
  const tplAktif: Template = { kode: tpl, judul, ket: "", teks, bawaan: false };
  const siap = target.filter((p) => !tanpaPesan(tplAktif, p));
  const tanpaIsi = target.filter((p) => tanpaPesan(tplAktif, p));

  const contoh = siap[Math.min(lihat, Math.max(0, siap.length - 1))];
  const sisaVar = bcAktif ? [] : teks.match(/\{[a-z_]+\}/g)?.filter((v) => !VARIABEL[jenis].some((x) => x.kode === v)) ?? [];
  const rata = (aturan.jeda_min + aturan.jeda_max) / 2;
  const n = siap.length;
  const istirahat = aturan.istirahat_setiap ? Math.floor(Math.max(0, n - 1) / aturan.istirahat_setiap) : 0;
  const perkiraan = Math.max(0, n - 1 - istirahat) * rata + istirahat * aturan.istirahat_menit * 60 + n * 12;
  const jenisInfo = JENIS.find((j) => j.k === jenis)!;

  function pakaiTpl(t: Template) {
    setTpl(t.kode); setTeks(t.teks); setJudul(t.judul); setLihat(0);
  }
  function tulisSendiri() {
    setTpl(CUSTOM); setTeks(`${SALAM} Bapak/Ibu {nama},\n\n`); setJudul("Pesan custom"); setLihat(0);
    requestAnimationFrame(() => { const el = teksRef.current; if (el) { el.focus(); el.selectionStart = el.selectionEnd = el.value.length; } });
  }

  function sisip(v: string) {
    const el = teksRef.current;
    if (!el) { setTeks(teks + v); return; }
    const a = el.selectionStart, b = el.selectionEnd;
    setTeks(teks.slice(0, a) + v + teks.slice(b));
    requestAnimationFrame(() => { el.focus(); el.selectionStart = el.selectionEnd = a + v.length; });
  }

  async function simpanTpl() {
    const nama = window.prompt("Nama template", judul === "Pesan custom" ? "" : judul);
    if (!nama?.trim()) return;
    const id = `${Date.now().toString(36)}`;
    const baru = [...(st?.template ?? []), { id, judul: nama.trim().slice(0, 60), jenis, teks }];
    try {
      const r = await post<{ template: TemplateSaya[] }>("/api/blast/template", { template: baru });
      setSt((x) => x && { ...x, template: r.template });
      setTpl(`saya:${id}`);
      setJudul(nama.trim().slice(0, 60));
    } catch (e) {
      setMulai({ busy: false, error: e instanceof Error ? e.message : String(e) });
    }
  }

  async function hapusTpl(kode: string) {
    const id = kode.replace("saya:", "");
    const r = await post<{ template: TemplateSaya[] }>("/api/blast/template",
      { template: (st?.template ?? []).filter((t) => t.id !== id) });
    setSt((x) => x && { ...x, template: r.template });
    pakaiTpl(templateBawaan(jenis)[0]);
  }

  function simpanAturan(a: Aturan) {
    setAturan(a);
    setAturanBuka(false);
  }

  async function kirim(coba: boolean) {
    if (!data) return;
    setMulai({ busy: true });
    try {
      const r = await post<{ dobel?: string[] }>("/api/blast/start", {
        jenis, judul, topik, coba, aturan, abaikan_jam: abaikanJam,
        kirim: siap.map((p) => ({ kunci: p.kunci, pesan: pesanUntuk(p, true) })),
      });
      setDobel(r.dobel ?? []);
      setMulai({ busy: false });
      await muatState();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setMulai({ busy: false, error: e instanceof Error ? e.message : String(e) });
    }
  }

  const state = st?.state;
  const jalan = !!state?.running;
  const bisaLanjut2 = target.length > 0;
  const bisaLanjut3 = n > 0 && (!!bcAktif || (sisaVar.length === 0 && !!teks.trim()));

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Blast</h1>
          <p>Kirim satu pesan ke banyak penerima sekaligus. Isinya menyesuaikan to-do tiap penerima.</p>
        </div>
        <div className={s.adminAlat}>
          <WaKartu jalan={!!st?.state.running} onGanti={() => setGantiWa(true)} />
          <PendengarKartu />
          <button type="button" className={s.aturanBtn} onClick={() => setAturanBuka(true)} aria-haspopup="dialog">
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>
          <span><b>Aturan kirim</b><small>jeda {aturan.jeda_min}–{aturan.jeda_max} dtk{aturan.istirahat_setiap ? ` · istirahat ${aturan.istirahat_menit} mnt / ${aturan.istirahat_setiap} pesan` : " · tanpa istirahat"}</small></span>
          </button>
        </div>
      </header>
      {gantiWa && <GantiWa onTutup={() => { setGantiWa(false); void muatState(); }} />}

      {st && !st.wa_otomatis && (
        <Notice tone="warn" title="WhatsApp otomatis sedang mati">
          Blast butuh WhatsApp otomatis. Nyalakan lagi lewat saklar di halaman LK, atau salin template dari layar fasil
          untuk dikirim dari HP.
        </Notice>
      )}
      {st && !st.jam_kirim && !jalan && (
        <Notice tone={abaikanJam ? "warn" : "info"} title="Di luar jam kirim">
          Blast biasanya dikirim pukul 07.00–22.00 supaya tidak mengganggu penerima.{" "}
          <label className={s.cek}><input type="checkbox" checked={abaikanJam} onChange={(e) => setAbaikanJam(e.target.checked)} />
            Tetap kirim sekarang (abaikan jam kirim)</label>
        </Notice>
      )}

      {dobel.length > 0 && (
        <Notice tone="info" title={`${dobel.length} penerima dilewati agar tidak dobel`}>
          Hari ini mereka sudah dikirimi blast dengan topik yang sama: {dobel.slice(0, 8).join(", ")}
          {dobel.length > 8 ? `, dan ${dobel.length - 8} lainnya` : ""}.{" "}
          <button type="button" className={s.linkBtn} onClick={() => setDobel([])}>Tutup</button>
        </Notice>
      )}
      {state && (jalan || state.selesai) && <Progres state={state} onUbah={muatState} />}
      {st?.wa_otomatis && !jalan && <BlastHp />}

      <div ref={atasRef} className={s.stepper} role="list" aria-label="Langkah blast">
        {LANGKAH.map((l) => {
          const bisa = l.n === 1 || (l.n === 2 && bisaLanjut2) || (l.n === 3 && bisaLanjut2 && bisaLanjut3);
          return (
            <button key={l.n} type="button" role="listitem" disabled={!bisa && l.n > langkah}
              className={`${s.step} ${langkah === l.n ? s.stepAktif : ""} ${langkah > l.n ? s.stepLewat : ""}`}
              aria-current={langkah === l.n ? "step" : undefined} onClick={() => bisa && ke(l.n)}>
              <span className={s.stepNo}>{langkah > l.n ? "✓" : l.n}</span>
              <span className={s.stepTeks}>
                <b>{l.label}</b>
                <small>{l.n === 1 ? `${jenisInfo.label} · ${target.length} penerima`
                  : l.n === 2 ? (tpl === CUSTOM ? "Pesan custom" : judul)
                  : n ? `${n} pesan · ±${durasi(perkiraan)}` : "–"}</small>
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
              <button key={j.k} type="button" role="radio" aria-checked={jenis === j.k} onClick={() => gantiJenis(j.k)}>
                <b>{j.label}</b><small>{j.ket}</small>
              </button>
            ))}
          </div>

          {error && <Notice tone="bad" title="Penerima tidak bisa dimuat">{error}</Notice>}
          {!data && !error && <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>}
          {data && (
            <>
              <div className={s.saring}>
                {!!data.komponen?.length && (
                  <div className={s.komponenBar} aria-label="Komponen (boleh pilih lebih dari satu)">
                    <button type="button" aria-pressed={!komp.length} onClick={() => { setKomp([]); setBuang(new Set()); }}>
                      Semua komponen<i>{dasar.length}</i>
                    </button>
                    {data.komponen.map((k) => {
                      const jml = dasar.filter((p) => p.posisi?.[k.kode]).length;
                      const on = komp.includes(k.kode);
                      return (
                        <button key={k.kode} type="button" aria-pressed={on} disabled={!jml && !on}
                          onClick={() => { setKomp(on ? komp.filter((x) => x !== k.kode) : [...komp, k.kode]); setBuang(new Set()); }}>
                          {k.label}<i>{jml}</i>
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className={s.chipGrup} aria-label="Kelompok">
                  {(jenis === "sekolah" ? KELOMPOK_SEKOLAH : jenis === "koor" ? KELOMPOK_KOOR : data.kelompok).map((k) => {
                    const on = kel.includes(k.kode);
                    const jml = data.penerima.filter((p) => p.kelompok === k.kode).length;
                    if (!jml) return null;
                    return (
                      <button key={k.kode} type="button" aria-pressed={on}
                        onClick={() => setKel(on ? kel.filter((x) => x !== k.kode) : [...kel, k.kode])}>
                        {k.label}<i>{jml}</i>
                      </button>
                    );
                  })}
                </div>
                {data.angkatan.length > 1 && (
                  <div className={s.chipGrup} aria-label="Angkatan">
                    <span className={s.chipLabel}>Angkatan</span>
                    {data.angkatan.map((a) => {
                      const on = angkatan.includes(a);
                      const jml = data.penerima.filter((p) => p.angkatan.includes(a)).length;
                      return (
                        <button key={a} type="button" aria-pressed={on}
                          onClick={() => setAngkatan(on ? angkatan.filter((x) => x !== a) : [...angkatan, a].sort())}>
                          Akt {a}<i>{jml}</i>
                        </button>
                      );
                    })}
                    {angkatan.length > 0 && <button type="button" className={s.linkBtn} onClick={() => setAngkatan([])}>Semua angkatan</button>}
                  </div>
                )}
                {(data.bimtek?.length ?? 0) > 0 && (
                  <div className={s.chipGrup} aria-label="Bimtek Pelaporan">
                    <span className={s.chipLabel}>Bimtek Pelaporan</span>
                    {data.bimtek!.map((b) => {
                      const on = bimtek.includes(b);
                      const jml = data.penerima.filter((p) => p.bimtek?.includes(b)).length;
                      return (
                        <button key={b} type="button" aria-pressed={on}
                          onClick={() => setBimtek(on ? bimtek.filter((x) => x !== b) : [...bimtek, b])}>
                          {b.replace(/^Bimtek\s+/i, "")}<i>{jml}</i>
                        </button>
                      );
                    })}
                    {bimtek.length > 0 && <button type="button" className={s.linkBtn} onClick={() => setBimtek([])}>Semua</button>}
                  </div>
                )}
                <div className={s.saringBaris}>
                  <input type="search" placeholder="Cari nama" value={cari} onChange={(e) => setCari(e.target.value)} aria-label="Cari penerima" />
                  {data.kab.length > 1 && (
                    <select value={kab} onChange={(e) => setKab(e.target.value)} aria-label="Kabupaten/kota">
                      <option value="">Semua kab/kota</option>
                      {data.kab.map((a) => <option key={a} value={a}>{a}</option>)}
                    </select>
                  )}
                  {data.tag.length > 0 && (
                    <select value={tag} onChange={(e) => setTag(e.target.value)} aria-label="Tag">
                      <option value="">Semua tag</option>
                      {data.tag.map((a) => <option key={a} value={a}>#{a}</option>)}
                    </select>
                  )}
                  <label className={s.cek}><input type="checkbox" checked={hanyaTodo} onChange={(e) => setHanyaTodo(e.target.checked)} /> Hanya yang punya to-do</label>
                  <select value={statChat} onChange={(e) => setStatChat(e.target.value)} aria-label="Status chat minggu ini">
                    <option value="">Semua status chat</option>
                    {CHAT_PILIH.map((c) => (
                      <option key={c.k} value={c.k}>{c.label} ({data.penerima.filter((p) => (p.chat ?? "") === (c.k === "belum" ? "" : c.k)).length})</option>
                    ))}
                  </select>
                  <label className={s.cek}><input type="checkbox" checked={lewatiHariIni} onChange={(e) => setLewatiHariIni(e.target.checked)} /> Lewati yang sudah di-chat hari ini</label>
                </div>
              </div>

              <div className={s.penerimaHead}>
                <b>{target.length} penerima dipilih</b>
                <span>dari {terpilih.length} yang cocok saringan{labelKomp ? ` · pesan hanya memuat ${labelKomp}` : ""}{data.jumlah_tanpa_nomor ? ` · ${data.jumlah_tanpa_nomor} tanpa nomor` : ""}</span>
                <div>
                  <form className={s.ambil} title="Centang sejumlah penerima dari atas daftar; sisanya diuncentang"
                    onSubmit={(e) => { e.preventDefault(); const n = parseInt(ambil, 10); if (n > 0) ambilSejumlah(n); }}>
                    <span>Blast</span>
                    <input type="number" min={1} inputMode="numeric" placeholder="50" value={ambil}
                      onChange={(e) => setAmbil(e.target.value)} aria-label="Jumlah penerima yang dicentang" />
                    <button type="submit" className={s.linkBtn} disabled={!(parseInt(ambil, 10) > 0)}>Centang</button>
                  </form>
                  <button type="button" className={s.linkBtn} onClick={() => aturPilih(terpilih, true)}>Pilih semua</button>
                  <button type="button" className={s.linkBtn} onClick={() => aturPilih(terpilih, false)}>Kosongkan</button>
                  {terpilih.some(sudahSesi) && (
                    <button type="button" className={s.linkBtn} title="Untuk blast gelombang berikutnya"
                      onClick={() => aturPilih(terpilih.filter(sudahSesi), false)}>Buang yang sudah di-blast sesi ini</button>
                  )}
                </div>
              </div>
              <ul className={s.penerima}>
                {terpilih.map((p) => {
                  const ket = alasanTarget(p);
                  const on = !ket && !buang.has(p.kunci);
                  return (
                    <li key={p.kunci} className={ket ? s.mati : undefined}>
                      <label>
                        <input type="checkbox" checked={on} disabled={!!ket}
                          onChange={() => { const b = new Set(buang); if (b.has(p.kunci)) b.delete(p.kunci); else b.add(p.kunci); setBuang(b); }} />
                        <span className={s.pNama}>
                          <b>{p.nama}</b>
                          <small>{jenis === "sekolah" ? `${p.kepsek || "Kepala sekolah"} · ${p.tersamar || "tanpa nomor"}`
                            : jenis === "koor" ? `${p.tersamar || "tanpa nomor"} · ${p.fasil?.length ?? 0} fasil, ${p.jumlah_sekolah} sekolah`
                            : `${p.tersamar || "tanpa nomor"} · ${p.jumlah_sekolah} sekolah${p.perlu ? `, ${p.perlu} ${labelKomp ? `di ${labelKomp}` : "punya to-do"}` : ""}`}</small>
                        </span>
                        {p.chat ? <Chip tone={CHAT_INFO[p.chat].tone}>{CHAT_INFO[p.chat].label}</Chip>
                          : jenis === "fasil" && KELOMPOK_INFO[p.kelompok as Kelompok] ? (
                            <Chip tone={KELOMPOK_INFO[p.kelompok as Kelompok].tone}>{KELOMPOK_INFO[p.kelompok as Kelompok].label}</Chip>
                          ) : <Chip tone="muted">Belum di-chat</Chip>}
                        {ket && <small className={s.alasan}>{ket}</small>}
                        {!ket && sudahSesi(p) && (
                          <small className={s.sudahBlast} title="Blast terkirim di sesi ini. Tetap bisa dikirim lagi.">
                            Sudah di-blast {(p.blast_sesi ?? []).map((b) => `${b.waktu}${b.topik ? ` · ${b.topik}` : ""}`).join("; ")}
                          </small>
                        )}
                      </label>
                    </li>
                  );
                })}
                {!terpilih.length && <li className={s.kosong}>{memuat ? "Memuat…" : "Tidak ada penerima yang cocok dengan saringan."}</li>}
              </ul>
            </>
          )}
          <div className={s.navBar}>
            <span />
            <Button disabled={!bisaLanjut2} onClick={() => ke(2)}>Lanjut: tulis pesan</Button>
          </div>
        </section>
      )}

      {langkah === 2 && (
        <section className={s.card} aria-labelledby="h-pesan">
          <div className={s.cardHead}>
            <h2 id="h-pesan">Pesannya apa?</h2>
            <span className={s.ket}>Pilih template atau tulis sendiri. Variabel seperti {"{nama}"} diisi otomatis per penerima.</span>
          </div>
          <div className={s.tplGrid}>
            {daftarTpl.map((t) => {
              const cocok = target.filter((p) => !tanpaPesan(t, p)).length;
              return (
                <button key={t.kode} type="button" aria-pressed={tpl === t.kode} onClick={() => pakaiTpl(t)}>
                  <b>{t.judul}</b><small>{t.ket}</small>
                  <em className={cocok ? undefined : s.tplKosong}>{cocok} dari {target.length} penerima</em>
                </button>
              );
            })}
            <button type="button" aria-pressed={tpl === CUSTOM} onClick={tulisSendiri} className={s.tplCustom}>
              <b>+ Tulis sendiri</b><small>Pesan custom dari nol. Bisa disimpan jadi template.</small>
            </button>
          </div>
          {bc?.error && <Notice tone="warn" title="Template BC dari sheet belum terbaca">{bc.error}</Notice>}
          <div className={s.tulis}>
            <div className={s.editor}>
              <label className={s.judulInput}>
                <span>Judul blast (untuk riwayat)</span>
                <input value={judul} maxLength={80} onChange={(e) => setJudul(e.target.value)} />
              </label>
              {bcAktif ? (
                <Notice tone="info" title={`Pesan dari tab ${bcAktif.tab}`}>
                  Tiap penerima mendapat pesan siap kirim dari sheet Draft Broadcast (sudah berisi daftar sekolahnya sendiri).
                  Salam menyesuaikan jam kirim. Ubah isinya langsung di sheet, lalu muat ulang.
                  {bcAktif.tanpa_cocok.length > 0 && <> {bcAktif.tanpa_cocok.length} nama di tab ini tidak ditemukan di LK Anda:
                    {" "}{bcAktif.tanpa_cocok.slice(0, 3).join(", ")}{bcAktif.tanpa_cocok.length > 3 ? ", dst." : ""}</>}
                  <div><Button variant="secondary" size="sm" loading={bcMuat} onClick={() => void muatBc(true)}>Muat ulang dari sheet</Button></div>
                </Notice>
              ) : (<>
              <textarea ref={teksRef} value={teks} rows={14} maxLength={4000} aria-label="Isi pesan"
                onChange={(e) => { setTeks(e.target.value); if (tpl !== CUSTOM && !tpl.startsWith("saya:")) setTpl(CUSTOM); }} />
              <div className={s.varBar} aria-label="Sisipkan variabel">
                {VARIABEL[jenis].map((v) => (
                  <button key={v.kode} type="button" title={v.arti} onClick={() => sisip(v.kode)}>{v.kode}</button>
                ))}
              </div>
              </>)}
              {sisaVar.length > 0 && <p className={s.err}>Variabel tidak dikenal: {sisaVar.join(", ")}</p>}
              {tanpaIsi.length > 0 && (
                <Notice tone="warn" title={`${tanpaIsi.length} penerima dilewati`}>
                  {bcAktif ? "Tab ini tidak punya pesan untuk" : "Variabel di pesan ini tidak punya isi untuk"} {tanpaIsi.slice(0, 3).map((p) => p.nama).join(", ")}
                  {tanpaIsi.length > 3 ? `, dan ${tanpaIsi.length - 3} lainnya` : ""}. Pilih template lain bila semua perlu dikirimi.
                </Notice>
              )}
              <div className={s.editorAksi}>
                {!bcAktif && <Button variant="secondary" size="sm" disabled={!teks.trim()} onClick={() => void simpanTpl()}>Simpan sebagai template</Button>}
                {tpl.startsWith("saya:") && <Button variant="ghost" size="sm" onClick={() => void hapusTpl(tpl)}>Hapus template ini</Button>}
              </div>
            </div>
            <Pratinjau siap={siap} lihat={lihat} setLihat={setLihat} contoh={contoh} pesan={(p) => pesanUntuk(p, false)} />
          </div>
          <div className={s.navBar}>
            <Button variant="ghost" onClick={() => ke(1)}>Kembali</Button>
            <Button disabled={!bisaLanjut3} onClick={() => ke(3)}>Lanjut: tinjau ({n} pesan)</Button>
          </div>
        </section>
      )}

      {langkah === 3 && (
        <section className={s.card} aria-labelledby="h-tinjau">
          <div className={s.cardHead}><h2 id="h-tinjau">Tinjau lalu kirim</h2></div>
          <div className={s.tinjau}>
            <dl className={s.ringkas}>
              <div><dt>Penerima</dt><dd><b>{n} {jenisInfo.label.toLowerCase()}</b>
                {tanpaIsi.length > 0 && <small>{tanpaIsi.length} dilewati karena variabel kosong</small>}
                <button type="button" className={s.linkBtn} onClick={() => ke(1)}>Ubah</button></dd></div>
              <div><dt>Pesan</dt><dd><b>{judul}</b><button type="button" className={s.linkBtn} onClick={() => ke(2)}>Ubah</button></dd></div>
              <div><dt>Aturan kirim</dt><dd>
                <b>Jeda {aturan.jeda_min}–{aturan.jeda_max} detik</b>
                <small>{aturan.istirahat_setiap ? `Istirahat ${aturan.istirahat_menit} menit tiap ${aturan.istirahat_setiap} pesan` : "Tanpa istirahat"}</small>
                <button type="button" className={s.linkBtn} onClick={() => setAturanBuka(true)}>Ubah</button></dd></div>
              <div className={s.ringkasAksen}><dt>Perkiraan selesai</dt><dd><b>{n ? durasi(perkiraan) : "–"}</b>
                <small>{n} pesan{istirahat ? `, ${istirahat}× istirahat` : ""}</small></dd></div>
            </dl>
            <Pratinjau siap={siap} lihat={lihat} setLihat={setLihat} contoh={contoh} pesan={(p) => pesanUntuk(p, false)} />
          </div>
          {aturan.jeda_min < 15 && (
            <Notice tone="warn" title="Jeda sangat pendek">Di bawah 15 detik meningkatkan risiko nomor dibatasi WhatsApp.</Notice>
          )}
          {mulai.error && <Notice tone="bad" title="Blast belum bisa dimulai">{mulai.error}</Notice>}
          <div className={s.navBar}>
            <Button variant="ghost" onClick={() => ke(2)}>Kembali</Button>
            <div className={s.kirimAksi}>
              {mulai.konfirmasi ? (
                <>
                  <span>Kirim <b>{n} pesan</b> sekarang?</span>
                  <Button variant="ghost" onClick={() => setMulai({ busy: false })}>Batal</Button>
                  <Button loading={mulai.busy} onClick={() => void kirim(false)}>Ya, kirim</Button>
                </>
              ) : (
                <>
                  <Button variant="secondary" disabled={jalan || !n || !st?.wa_otomatis || sisaVar.length > 0} loading={mulai.busy}
                    onClick={() => void kirim(true)} title="Membuka chat 3 penerima pertama tanpa menekan kirim">
                    Coba 3 penerima
                  </Button>
                  <Button disabled={jalan || !n || !st?.wa_otomatis || !(st?.jam_kirim || abaikanJam) || sisaVar.length > 0}
                    onClick={() => setMulai({ busy: false, konfirmasi: true })}>
                    Kirim ke {n} penerima
                  </Button>
                </>
              )}
            </div>
          </div>
        </section>
      )}

      {aturanBuka && <AturanDialog awal={aturan} onSimpan={simpanAturan} onClose={() => setAturanBuka(false)} />}
    </div>
  );
}

function Pratinjau({ siap, lihat, setLihat, contoh, pesan }: {
  siap: Penerima[]; lihat: number; setLihat: (n: number) => void; contoh: Penerima | undefined; pesan: (p: Penerima) => string;
}) {
  return (
    <div className={s.preview}>
      <div className={s.previewHead}>
        <span>Pratinjau{contoh ? `: ${contoh.nama}` : ""}</span>
        {siap.length > 1 && (
          <span className={s.previewNav}>
            <button type="button" aria-label="Penerima sebelumnya" disabled={lihat <= 0} onClick={() => setLihat(lihat - 1)}>‹</button>
            {Math.min(lihat, siap.length - 1) + 1}/{siap.length}
            <button type="button" aria-label="Penerima berikutnya" disabled={lihat >= siap.length - 1} onClick={() => setLihat(lihat + 1)}>›</button>
          </span>
        )}
      </div>
      <div className={s.hp}>
        {contoh ? <div className={s.bubble}>{formatWa(pesan(contoh))}</div>
          : <p className={s.kosong}>Belum ada penerima yang bisa dikirimi pesan ini.</p>}
      </div>
    </div>
  );
}

export function AturanDialog({ awal, onSimpan, onClose }: { awal: Aturan; onSimpan: (a: Aturan) => void; onClose: () => void }) {
  const [a, setA] = useState(awal);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector("input")?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  const contoh = 50;
  const rata = (a.jeda_min + a.jeda_max) / 2;
  const ist = a.istirahat_setiap ? Math.floor((contoh - 1) / a.istirahat_setiap) : 0;
  const lama = (contoh - 1 - ist) * rata + ist * a.istirahat_menit * 60 + contoh * 12;
  return (
    <div className={s.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={ref} className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="h-aturan">
        <h2 id="h-aturan">Aturan kirim</h2>
        <p className={s.ket}>Jeda acak dan istirahat berkala membuat pola kirim mirip manusia, supaya nomor lebih aman.</p>
        <fieldset className={s.field}>
          <legend>Jeda antar pesan</legend>
          <div className={s.angkaBaris}>
            <Angka label="paling cepat" nilai={a.jeda_min} min={5} max={600} langkah={5} satuan="detik"
              onChange={(v) => setA({ ...a, jeda_min: v, jeda_max: Math.max(v, a.jeda_max) })} />
            <span>sampai</span>
            <Angka label="paling lama" nilai={a.jeda_max} min={a.jeda_min} max={900} langkah={5} satuan="detik"
              onChange={(v) => setA({ ...a, jeda_max: v })} />
          </div>
        </fieldset>
        <fieldset className={s.field}>
          <legend>Istirahat</legend>
          <div className={s.angkaBaris}>
            <span>setiap</span>
            <Angka label="jumlah pesan" nilai={a.istirahat_setiap} min={0} max={200} satuan="pesan"
              onChange={(v) => setA({ ...a, istirahat_setiap: v })} />
            <span>selama</span>
            <Angka label="lama istirahat" nilai={a.istirahat_menit} min={1} max={60} satuan="menit"
              onChange={(v) => setA({ ...a, istirahat_menit: v })} />
          </div>
          {a.istirahat_setiap === 0 && <small className={s.err}>0 = tanpa istirahat</small>}
        </fieldset>
        <p className={s.estimasiKecil}>Contoh: {contoh} pesan selesai dalam ±{durasi(lama)}.</p>
        {a.jeda_min < 15 && <p className={s.err}>Jeda di bawah 15 detik meningkatkan risiko nomor dibatasi WhatsApp.</p>}
        <div className={s.dialogAksi}>
          <Button variant="ghost" onClick={() => setA({ jeda_min: 20, jeda_max: 45, istirahat_setiap: 20, istirahat_menit: 5 })}>Kembalikan bawaan</Button>
          <Button variant="secondary" onClick={onClose}>Batal</Button>
          <Button onClick={() => onSimpan(a)}>Pakai aturan ini</Button>
        </div>
      </div>
    </div>
  );
}

function Angka({ label, nilai, min, max, satuan, langkah = 1, onChange }: {
  label: string; nilai: number; min: number; max: number; satuan: string; langkah?: number; onChange: (v: number) => void;
}) {
  // Ketikan disimpan apa adanya dan baru dirapikan (batas min/max) saat kolom ditinggalkan,
  // supaya mengetik "30" tidak berubah jadi "5" di tengah jalan.
  const [teks, setTeks] = useState<string | null>(null);
  const pakai = (v: number) => onChange(Math.max(min, Math.min(max, Math.round(v))));
  const selesai = () => { if (teks !== null && teks !== "") pakai(Number(teks)); setTeks(null); };
  const geser = (arah: 1 | -1) => { const dasar = teks ? Number(teks) : nilai; setTeks(null); pakai(dasar + arah * langkah); };
  return (
    <div className={s.angka} role="group" aria-label={label}>
      <button type="button" tabIndex={-1} aria-label={`Kurangi ${label}`} disabled={nilai <= min} onClick={() => geser(-1)}>−</button>
      <label>
        <input type="text" inputMode="numeric" value={teks ?? String(nilai)} aria-label={label}
          onFocus={(e) => e.target.select()}
          onChange={(e) => setTeks(e.target.value.replace(/\D/g, "").slice(0, 3))}
          onBlur={selesai}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            else if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); geser(e.key === "ArrowUp" ? 1 : -1); }
          }} />
        <span>{satuan}</span>
      </label>
      <button type="button" tabIndex={-1} aria-label={`Tambah ${label}`} disabled={nilai >= max} onClick={() => geser(1)}>+</button>
    </div>
  );
}

export function Progres({ state, onUbah, dasar = "/api/blast" }: { state: BlastState; onUbah: () => void; dasar?: string }) {
  const hitung = useCountdown(state.istirahat_sampai ?? state.berikutnya_pada);
  const [busy, setBusy] = useState(false);
  const pct = state.total ? Math.round((state.diproses / state.total) * 100) : 0;
  async function aksi(path: string, body?: unknown) {
    setBusy(true);
    try { await post(path, body); onUbah(); } finally { setBusy(false); }
  }
  const status = !state.running ? (state.berhenti_karena ? "Berhenti" : "Selesai")
    : state.paused ? "Dijeda" : state.istirahat_sampai ? "Istirahat" : state.sekarang ? "Mengirim" : "Menunggu jeda";
  return (
    <section className={`${s.card} ${s.progres} ${state.running ? s.progresJalan : ""}`} aria-live="polite">
      <div className={s.progresHead}>
        <div>
          <span className={s.ket}>{state.coba ? "Mode coba · " : ""}{state.judul}</span>
          <h2>{status}{state.running && state.sekarang ? `: ${state.sekarang}` : ""}
            {state.running && !state.sekarang && hitung !== null && ` (${state.istirahat_sampai ? "lanjut" : state.berikutnya} dalam ${hitung} dtk)`}
          </h2>
        </div>
        {state.running && (
          <div className={s.progresAksi}>
            <Button variant="secondary" size="sm" loading={busy} onClick={() => void aksi(`${dasar}/jeda`, { aktif: !state.paused })}>
              {state.paused ? "Lanjutkan" : "Jeda"}
            </Button>
            <Button variant="danger" size="sm" loading={busy} onClick={() => void aksi(`${dasar}/stop`)}>Hentikan</Button>
          </div>
        )}
      </div>
      <div className={s.bar}><span style={{ width: `${pct}%` }} /></div>
      <div className={s.progresAngka}>
        <span><b>{state.diproses}</b>/{state.total} diproses</span>
        <span className={s.okT}><b>{state.terkirim}</b> terkirim</span>
        {state.gagal > 0 && <span className={s.badT}><b>{state.gagal}</b> gagal</span>}
      </div>
      {state.berhenti_karena && <Notice tone={state.berhenti_karena.startsWith("Dihentikan") ? "info" : "warn"}>{state.berhenti_karena}</Notice>}
      {state.hasil.length > 0 && (
        <details className={s.hasil}>
          <summary>Rincian {state.hasil.length} pesan terakhir</summary>
          <ul>
            {[...state.hasil].reverse().map((h, i) => (
              <li key={i}>
                <span>{h.waktu}</span><b>{h.nama}</b>
                <Chip tone={h.status === "terkirim" ? "ok" : h.status === "dicoba" ? "info" : "bad"}>{h.status}</Chip>
                {h.keterangan && <small>{h.keterangan}</small>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}


type Pindai = { berjalan: boolean; dicek: number; total: number; selesai: string; langsung?: boolean };

/** Blast dikirim dari HP: minta aplikasi membaca chat semua fasil supaya Log Komunikasi ikut terisi. */
function BlastHp() {
  const [p, setP] = useState<Pindai | null>(null);
  const [galat, setGalat] = useState("");
  const [minta, setMinta] = useState(false);

  const cek = useCallback(async () => {
    try { setP(await api<Pindai>("/api/chat/pindai")); } catch { /* hanya info */ }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cek(); }, [cek]);
  usePolling(cek, 3000, !!p?.berjalan);

  const mulai = async () => {
    setGalat("");
    setMinta(true);
    try { setP(await post<Pindai>("/api/chat/pindai")); } catch (e) { setGalat(e instanceof Error ? e.message : String(e)); }
    finally { setMinta(false); }
  };

  if (p?.langsung) return null;  // status chat sudah dibaca langsung: blast lewat HP terbaca sendiri
  const selesai = p?.selesai ? new Date(p.selesai).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <section className={s.hp} aria-labelledby="blast-hp">
      <div>
        <b id="blast-hp">Sudah blast lewat HP?</b>
        <p>
          {p?.berjalan
            ? (p.total ? `Membaca chat fasil ${p.dicek} dari ${p.total}…` : "Menunggu giliran membaca chat…")
            : "Aplikasi akan membuka chat semua fasil, mencatat tanggal pesan yang kamu kirim, lalu mengisi Log "
              + "Komunikasi sejak hari itu. Chat juga dicek otomatis sekali sehari."}
          {!p?.berjalan && selesai && <> Terakhir dibaca pukul {selesai}.</>}
        </p>
        {galat && <p className={s.hpGalat}>{galat}</p>}
      </div>
      <Button variant="secondary" size="sm" onClick={() => void mulai()} loading={minta || !!p?.berjalan}>
        {p?.berjalan ? "Sedang membaca" : "Baca chat sekarang"}
      </Button>
    </section>
  );
}
