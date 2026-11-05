"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { useCountdown, useEvents, usePolling } from "@/lib/hooks";
import { KELOMPOK_INFO, TAHAP_LABEL, type Aturan, type BlastState, type JenisPenerima, type Kelompok, type Penerima,
  type TemplateSaya } from "@/lib/lk";
import { VARIABEL, isi as isiTemplate, kosong, templateBawaan, type Template } from "@/lib/pesan";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { formatWa } from "@/components/today/WaPanel";
import s from "./blast.module.css";

type DataPenerima = {
  jenis: JenisPenerima; penerima: Penerima[]; petugas: string; jumlah_tanpa_nomor: number; tag: string[];
  kelompok: { kode: Kelompok; label: string }[]; angkatan: string[]; kab: string[];
};
type StateResp = { state: BlastState; aturan: Aturan; wa_terbuka: boolean; wa_otomatis: boolean; jam_kirim: boolean;
  template: TemplateSaya[] };

const JENIS: { k: JenisPenerima; label: string; ket: string }[] = [
  { k: "fasil", label: "Fasilitator", ket: "Fasil binaan Anda" },
  { k: "koor", label: "Koordinator", ket: "Koordinator fasil binaan" },
  { k: "sekolah", label: "Kepala sekolah", ket: "Sekolah binaan" },
];
const KELOMPOK_SEKOLAH: { kode: string; label: string }[] = [
  { kode: "pendahuluan", label: TAHAP_LABEL.pendahuluan }, { kode: "berkala", label: TAHAP_LABEL.berkala },
  { kode: "l50", label: TAHAP_LABEL.l50 }, { kode: "l100", label: TAHAP_LABEL.l100 }, { kode: "beres", label: "Semua hijau" },
];

function durasi(detik: number) {
  const m = Math.round(detik / 60);
  if (m < 1) return "kurang dari 1 menit";
  return m >= 60 ? `${Math.floor(m / 60)} jam ${m % 60 ? `${m % 60} menit` : ""}`.trim() : `${m} menit`;
}

export function BlastView() {
  const [jenis, setJenis] = useState<JenisPenerima>("fasil");
  const [data, setData] = useState<DataPenerima | null>(null);
  const [st, setSt] = useState<StateResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);
  // saringan
  const [kel, setKel] = useState<string[]>([]);
  const [tag, setTag] = useState("");
  const [angkatan, setAngkatan] = useState("");
  const [kab, setKab] = useState("");
  const [hanyaTodo, setHanyaTodo] = useState(true);
  const [lewatiHariIni, setLewatiHariIni] = useState(true);
  const [cari, setCari] = useState("");
  const [buang, setBuang] = useState<Set<string>>(new Set());
  // pesan
  const [tpl, setTpl] = useState<string>("tanya");
  const [teks, setTeks] = useState(() => templateBawaan("fasil")[0].teks);
  const [judul, setJudul] = useState("Tanya kendala per sekolah");
  const [lihat, setLihat] = useState(0);
  const [aturan, setAturan] = useState<Aturan>({ jeda_min: 20, jeda_max: 45, istirahat_setiap: 20, istirahat_menit: 5 });
  const [mulai, setMulai] = useState<{ busy: boolean; error?: string; konfirmasi?: boolean }>({ busy: false });
  const teksRef = useRef<HTMLTextAreaElement>(null);

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

  const daftarTpl: Template[] = useMemo(() => [
    ...templateBawaan(jenis),
    ...(st?.template ?? []).filter((t) => t.jenis === jenis)
      .map((t) => ({ kode: `saya:${t.id}`, judul: t.judul, ket: "Template simpanan Anda", teks: t.teks, bawaan: false })),
  ], [jenis, st?.template]);

  // ganti jenis -> pakai template pertama jenis itu dan kosongkan saringan
  function gantiJenis(j: JenisPenerima) {
    const t = templateBawaan(j)[0];
    setJenis(j); setData(null);
    setTpl(t.kode); setTeks(t.teks); setJudul(t.judul); setKel([]); setTag(""); setAngkatan(""); setKab("");
    setBuang(new Set()); setLihat(0);
  }


  const terpilih = useMemo(() => {
    if (!data) return [];
    const q = cari.trim().toLowerCase();
    return data.penerima.filter((p) => (!kel.length || kel.includes(p.kelompok)) && (!tag || p.tag.includes(tag))
      && (!angkatan || p.angkatan.includes(angkatan)) && (!kab || p.kab.includes(kab))
      && (!hanyaTodo || p.perlu > 0) && (!q || p.nama.toLowerCase().includes(q)));
  }, [data, kel, tag, angkatan, kab, hanyaTodo, cari]);

  const siap = terpilih.filter((p) => p.punya_nomor && !buang.has(p.kunci) && !(lewatiHariIni && p.terakhir_blast)
    && !kosong(teks, p).length);
  const alasan = (p: Penerima) => !p.punya_nomor ? "Nomor kosong" : lewatiHariIni && p.terakhir_blast
    ? `Sudah diblast ${p.terakhir_blast}` : kosong(teks, p).length ? "Tidak ada isi untuk variabel" : "";

  const contoh = siap[Math.min(lihat, Math.max(0, siap.length - 1))];
  const sisaVar = teks.match(/\{[a-z_]+\}/g)?.filter((v) => !VARIABEL[jenis].some((x) => x.kode === v)) ?? [];
  const rata = (aturan.jeda_min + aturan.jeda_max) / 2;
  const n = siap.length;
  const istirahat = aturan.istirahat_setiap ? Math.floor(Math.max(0, n - 1) / aturan.istirahat_setiap) : 0;
  const perkiraan = Math.max(0, n - 1 - istirahat) * rata + istirahat * aturan.istirahat_menit * 60 + n * 12;

  function pakaiTpl(t: Template) {
    setTpl(t.kode); setTeks(t.teks); setJudul(t.judul); setLihat(0);
  }

  function sisip(v: string) {
    const el = teksRef.current;
    if (!el) { setTeks(teks + v); return; }
    const a = el.selectionStart, b = el.selectionEnd;
    const baru = teks.slice(0, a) + v + teks.slice(b);
    setTeks(baru);
    requestAnimationFrame(() => { el.focus(); el.selectionStart = el.selectionEnd = a + v.length; });
  }

  async function simpanTpl() {
    const nama = window.prompt("Nama template", judul.startsWith("Template") ? "" : judul);
    if (!nama?.trim()) return;
    const lama = st?.template ?? [];
    const id = `${Date.now().toString(36)}`;
    const baru = [...lama, { id, judul: nama.trim().slice(0, 60), jenis, teks }];
    try {
      const r = await post<{ template: TemplateSaya[] }>("/api/blast/template", { template: baru });
      setSt((x) => x && { ...x, template: r.template });
      setTpl(`saya:${id}`);
    } catch (e) {
      setMulai({ busy: false, error: e instanceof Error ? e.message : String(e) });
    }
  }

  async function hapusTpl(kode: string) {
    const id = kode.replace("saya:", "");
    const baru = (st?.template ?? []).filter((t) => t.id !== id);
    const r = await post<{ template: TemplateSaya[] }>("/api/blast/template", { template: baru });
    setSt((x) => x && { ...x, template: r.template });
    pakaiTpl(templateBawaan(jenis)[0]);
  }

  async function kirim(coba: boolean) {
    if (!data) return;
    setMulai({ busy: true });
    try {
      await post("/api/blast/start", {
        jenis, judul, coba, aturan,
        kirim: siap.map((p) => ({ kunci: p.kunci, pesan: isiTemplate(teks, p, data.petugas, true) })),
      });
      setMulai({ busy: false });
      await muatState();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setMulai({ busy: false, error: e instanceof Error ? e.message : String(e) });
    }
  }

  const state = st?.state;
  const jalan = !!state?.running;

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Blast</h1>
          <p>Kirim satu pesan ke banyak fasil, koordinator, atau kepala sekolah. Isinya menyesuaikan to-do tiap penerima.</p>
        </div>
      </header>

      {st && !st.wa_otomatis && (
        <Notice tone="warn" title="WhatsApp otomatis sedang mati">
          Blast butuh WhatsApp otomatis. Nyalakan lagi lewat saklar di halaman LK, atau salin template dari panel fasil
          untuk dikirim dari HP.
        </Notice>
      )}
      {st && !st.jam_kirim && !jalan && (
        <Notice tone="info" title="Di luar jam kirim">Blast bisa dikirim pukul 07.00–22.00 supaya tidak mengganggu penerima.</Notice>
      )}

      {state && (jalan || state.selesai) && <Progres state={state} onUbah={muatState} />}

      <section className={s.card} aria-labelledby="h-penerima">
        <div className={s.cardHead}>
          <h2 id="h-penerima"><span className={s.no}>1</span>Penerima</h2>
          <div className={s.segmen} role="tablist" aria-label="Jenis penerima">
            {JENIS.map((j) => (
              <button key={j.k} type="button" role="tab" aria-selected={jenis === j.k} onClick={() => gantiJenis(j.k)} title={j.ket}>
                {j.label}
              </button>
            ))}
          </div>
        </div>

        {error && <Notice tone="bad" title="Penerima tidak bisa dimuat">{error}</Notice>}
        {!data && !error && <div className={s.loading}><Spinner label="Memuat" /> Membaca LK…</div>}
        {data && (
          <>
            <div className={s.saring}>
              <div className={s.chipGrup} aria-label="Kelompok">
                {(jenis === "sekolah" ? KELOMPOK_SEKOLAH : data.kelompok).map((k) => {
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
              <div className={s.saringBaris}>
                <input type="search" placeholder="Cari nama" value={cari} onChange={(e) => setCari(e.target.value)} aria-label="Cari penerima" />
                {data.angkatan.length > 1 && (
                  <select value={angkatan} onChange={(e) => setAngkatan(e.target.value)} aria-label="Angkatan">
                    <option value="">Semua angkatan</option>
                    {data.angkatan.map((a) => <option key={a} value={a}>Angkatan {a}</option>)}
                  </select>
                )}
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
                <label className={s.cek}><input type="checkbox" checked={lewatiHariIni} onChange={(e) => setLewatiHariIni(e.target.checked)} /> Lewati yang sudah diblast hari ini</label>
              </div>
            </div>

            <div className={s.penerimaHead}>
              <b>{siap.length} akan dikirimi</b>
              <span>dari {terpilih.length} yang cocok saringan{data.jumlah_tanpa_nomor ? ` · ${data.jumlah_tanpa_nomor} tanpa nomor` : ""}</span>
              <div>
                <button type="button" className={s.linkBtn} onClick={() => setBuang(new Set())}>Pilih semua</button>
                <button type="button" className={s.linkBtn} onClick={() => setBuang(new Set(terpilih.map((p) => p.kunci)))}>Kosongkan</button>
              </div>
            </div>
            <ul className={s.penerima}>
              {terpilih.map((p) => {
                const ket = alasan(p);
                const on = !ket && !buang.has(p.kunci);
                return (
                  <li key={p.kunci} className={ket ? s.mati : undefined}>
                    <label>
                      <input type="checkbox" checked={on} disabled={!!ket}
                        onChange={() => { const b = new Set(buang); if (b.has(p.kunci)) b.delete(p.kunci); else b.add(p.kunci); setBuang(b); }} />
                      <span className={s.pNama}>
                        <b>{p.nama}</b>
                        <small>{jenis === "sekolah" ? `${p.kepsek || "Kepala sekolah"} · ${p.tersamar || "tanpa nomor"}`
                          : `${p.tersamar || "tanpa nomor"} · ${p.jumlah_sekolah} sekolah${p.perlu ? `, ${p.perlu} punya to-do` : ""}`}</small>
                      </span>
                      {jenis !== "sekolah" && KELOMPOK_INFO[p.kelompok as Kelompok] && (
                        <Chip tone={KELOMPOK_INFO[p.kelompok as Kelompok].tone}>{KELOMPOK_INFO[p.kelompok as Kelompok].label}</Chip>
                      )}
                      {ket && <small className={s.alasan}>{ket}</small>}
                    </label>
                  </li>
                );
              })}
              {!terpilih.length && <li className={s.kosong}>{memuat ? "Memuat…" : "Tidak ada penerima yang cocok dengan saringan."}</li>}
            </ul>
          </>
        )}
      </section>

      <section className={s.card} aria-labelledby="h-pesan">
        <div className={s.cardHead}>
          <h2 id="h-pesan"><span className={s.no}>2</span>Pesan</h2>
          <span className={s.ket}>Pilih template lalu ubah sesukanya. Variabel diisi otomatis per penerima.</span>
        </div>
        <div className={s.tplGrid}>
          {daftarTpl.map((t) => (
            <button key={t.kode} type="button" aria-pressed={tpl === t.kode} onClick={() => pakaiTpl(t)}>
              <b>{t.judul}</b><small>{t.ket}</small>
            </button>
          ))}
        </div>
        <div className={s.tulis}>
          <div className={s.editor}>
            <label className={s.judulInput}>
              <span>Judul blast (untuk riwayat)</span>
              <input value={judul} maxLength={80} onChange={(e) => setJudul(e.target.value)} />
            </label>
            <textarea ref={teksRef} value={teks} rows={14} maxLength={4000} aria-label="Isi pesan"
              onChange={(e) => { setTeks(e.target.value); if (!tpl.startsWith("saya:")) setTpl(""); }} />
            <div className={s.varBar} aria-label="Sisipkan variabel">
              {VARIABEL[jenis].map((v) => (
                <button key={v.kode} type="button" title={v.arti} onClick={() => sisip(v.kode)}>{v.kode}</button>
              ))}
            </div>
            {sisaVar.length > 0 && <p className={s.err}>Variabel tidak dikenal: {sisaVar.join(", ")}</p>}
            <div className={s.editorAksi}>
              <Button variant="secondary" size="sm" disabled={!teks.trim()} onClick={() => void simpanTpl()}>Simpan sebagai template</Button>
              {tpl.startsWith("saya:") && <Button variant="ghost" size="sm" onClick={() => void hapusTpl(tpl)}>Hapus template ini</Button>}
            </div>
          </div>
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
              {contoh && data ? <div className={s.bubble}>{formatWa(isiTemplate(teks, contoh, data.petugas, false))}</div>
                : <p className={s.kosong}>Belum ada penerima yang dipilih.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className={s.card} aria-labelledby="h-aturan">
        <div className={s.cardHead}>
          <h2 id="h-aturan"><span className={s.no}>3</span>Aturan kirim</h2>
          <span className={s.ket}>Jeda acak dan istirahat berkala membuat pola kirim mirip manusia, supaya nomor lebih aman.</span>
        </div>
        <div className={s.aturan}>
          <fieldset>
            <legend>Jeda antar pesan</legend>
            <div className={s.angkaBaris}>
              <Angka label="paling cepat" nilai={aturan.jeda_min} min={5} max={600} satuan="detik"
                onChange={(v) => setAturan({ ...aturan, jeda_min: v, jeda_max: Math.max(v, aturan.jeda_max) })} />
              <span>sampai</span>
              <Angka label="paling lama" nilai={aturan.jeda_max} min={aturan.jeda_min} max={900} satuan="detik"
                onChange={(v) => setAturan({ ...aturan, jeda_max: v })} />
            </div>
          </fieldset>
          <fieldset>
            <legend>Istirahat</legend>
            <div className={s.angkaBaris}>
              <span>setiap</span>
              <Angka label="jumlah pesan" nilai={aturan.istirahat_setiap} min={0} max={200} satuan="pesan"
                onChange={(v) => setAturan({ ...aturan, istirahat_setiap: v })} />
              <span>selama</span>
              <Angka label="lama istirahat" nilai={aturan.istirahat_menit} min={1} max={60} satuan="menit"
                onChange={(v) => setAturan({ ...aturan, istirahat_menit: v })} />
            </div>
            {aturan.istirahat_setiap === 0 && <small className={s.err}>0 = tanpa istirahat</small>}
          </fieldset>
          <div className={s.estimasi}>
            <span>Perkiraan selesai</span>
            <b>{n ? durasi(perkiraan) : "–"}</b>
            <small>{n} pesan{istirahat ? `, ${istirahat}× istirahat` : ""}</small>
          </div>
        </div>
        {aturan.jeda_min < 15 && (
          <Notice tone="warn" title="Jeda sangat pendek">Di bawah 15 detik meningkatkan risiko nomor dibatasi WhatsApp. Pakai hanya untuk penerima yang sudah sering membalas.</Notice>
        )}
        {mulai.error && <Notice tone="bad" title="Blast belum bisa dimulai">{mulai.error}</Notice>}
        <div className={s.kirimBar}>
          {mulai.konfirmasi ? (
            <>
              <span>Kirim <b>{n} pesan</b> “{judul}” sekarang?</span>
              <Button variant="ghost" onClick={() => setMulai({ busy: false })}>Batal</Button>
              <Button loading={mulai.busy} onClick={() => void kirim(false)}>Ya, kirim</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" disabled={jalan || !n || !st?.wa_otomatis || sisaVar.length > 0} loading={mulai.busy}
                onClick={() => void kirim(true)} title="Membuka chat 3 penerima pertama tanpa menekan kirim">
                Coba 3 penerima
              </Button>
              <Button disabled={jalan || !n || !st?.wa_otomatis || !st?.jam_kirim || sisaVar.length > 0}
                onClick={() => setMulai({ busy: false, konfirmasi: true })}>
                Kirim ke {n} penerima
              </Button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

function Angka({ label, nilai, min, max, satuan, onChange }: {
  label: string; nilai: number; min: number; max: number; satuan: string; onChange: (v: number) => void;
}) {
  return (
    <label className={s.angka}>
      <input type="number" inputMode="numeric" min={min} max={max} value={nilai} aria-label={label}
        onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))} />
      <span>{satuan}</span>
    </label>
  );
}

function Progres({ state, onUbah }: { state: BlastState; onUbah: () => void }) {
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
            <Button variant="secondary" size="sm" loading={busy} onClick={() => void aksi("/api/blast/jeda", { aktif: !state.paused })}>
              {state.paused ? "Lanjutkan" : "Jeda"}
            </Button>
            <Button variant="danger" size="sm" loading={busy} onClick={() => void aksi("/api/blast/stop")}>Hentikan</Button>
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
