"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, post } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import type { Petugas } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import { NoAccess } from "@/components/app/NoAccess";
import { LinkLk } from "./LinkLk";
import s from "./admin.module.css";

type Pengguna = { baris: number; email: string; nama_petugas: string; fitur: string[]; catatan: string };
type Data = { pengguna: Pengguna[]; fitur: string[] };
type Form = { email: string; nama_petugas: string; fitur: string[]; admin: boolean; email_lama: string };
type Peran = "" | "admin" | "pengguna";

const LABEL_FITUR: Record<string, string> = { wa_blast: "LK & Blast", cutoff: "Tarik Cutoff", blast_admin: "Blast admin", eskalasi: "PIC Eskalasi" };
const KOSONG: Form = { email: "", nama_petugas: "", fitur: ["wa_blast"], admin: false, email_lama: "" };
const inisial = (nama: string, email: string) =>
  (nama.trim() ? nama.trim().split(/\s+/).slice(0, 2).map((x) => x[0]).join("") : email[0] ?? "?").toUpperCase();

export function AdminView() {
  const router = useRouter();
  const { me } = useMe();
  const [data, setData] = useState<Data | null>(null);
  const [petugas, setPetugas] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [terkunci, setTerkunci] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [info, setInfo] = useState<{ tone: "ok" | "bad"; teks: string } | null>(null);
  const [cari, setCari] = useState("");
  const [peran, setPeran] = useState<Peran>("");

  const muat = useCallback(async () => {
    try {
      setData(await api<Data>("/api/admin/akses"));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setTerkunci(true);
      else setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void muat();
    api<{ petugas: Petugas[] }>("/api/petugas").then((d) => setPetugas(d.petugas.map((p) => p.nama))).catch(() => {});
  }, [muat]);

  async function simpan() {
    if (!form) return;
    setBusy("simpan");
    setInfo(null);
    try {
      const r = await post<Data & { baru: boolean }>("/api/admin/akses", form);
      setData((d) => d && { ...d, pengguna: r.pengguna });
      setInfo({ tone: "ok", teks: r.baru
        ? `${form.email.trim().toLowerCase()} ditambahkan. Kirim paket lk-monitoring.json dan pastikan emailnya sudah punya akses ke sheet tim.`
        : `${form.email.trim().toLowerCase()} diperbarui.` });
      setForm(null);
    } catch (e) {
      setInfo({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }

  async function hapus(p: Pengguna) {
    if (!window.confirm(`Hapus ${p.email} (${p.nama_petugas}) dari sheet Akses? Akun ini tidak bisa memakai aplikasi lagi.`)) return;
    setBusy(p.email);
    setInfo(null);
    try {
      const r = await api<Data>(`/api/admin/akses/${encodeURIComponent(p.email)}`, { method: "DELETE" });
      setData((d) => d && { ...d, pengguna: r.pengguna });
      setInfo({ tone: "ok", teks: `${p.email} dihapus dari sheet Akses.` });
    } catch (e) {
      setInfo({ tone: "bad", teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }

  if (terkunci) return <NoAccess onClose={() => router.replace("/today/")} />;
  if (error && !data) return <Notice tone="bad" title="Halaman Admin tidak bisa dimuat">{error}</Notice>;
  if (!data) return <div className={s.loading}><Spinner label="Memuat" /> Membaca sheet Akses…</div>;

  const saya = me?.email?.toLowerCase();
  const adalahAdmin = (p: Pengguna) => p.catatan.toLowerCase() === "admin";
  const q = cari.trim().toLowerCase();
  const daftar = data.pengguna.filter((p) => (!q || `${p.email} ${p.nama_petugas}`.toLowerCase().includes(q))
    && (!peran || (peran === "admin") === adalahAdmin(p)));
  const jumlahAdmin = data.pengguna.filter(adalahAdmin).length;
  const ganti = (f: string) => form && setForm({ ...form, fitur: form.fitur.includes(f) ? form.fitur.filter((x) => x !== f) : [...form.fitur, f] });

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <p className="chips"><span className="chip">Akses aplikasi</span></p>
          <h1>Admin</h1>
          <p className={s.sub}>Kelola siapa saja yang boleh memakai aplikasi. Perubahan langsung ditulis ke sheet Akses.</p>
        </div>
        <div className={s.headAksi}>
          <a className={s.tombolGaris} href="/api/admin/paket" download="lk-monitoring.json">Unduh paket</a>
          <Button onClick={() => { setForm({ ...KOSONG }); setInfo(null); }} disabled={!!form}>Tambah pengguna</Button>
        </div>
      </header>

      <section className={s.kpi} aria-label="Ringkasan pengguna">
        <div><span>Pengguna</span><b>{data.pengguna.length}</b></div>
        <div><span>Admin</span><b>{jumlahAdmin}</b></div>
        {data.fitur.map((f) => (
          <div key={f}><span>{LABEL_FITUR[f] ?? f}</span><b>{data.pengguna.filter((p) => p.fitur.includes(f)).length}</b></div>
        ))}
      </section>

      {info && <Notice tone={info.tone} title={info.tone === "ok" ? "Tersimpan" : "Belum tersimpan"}>{info.teks}</Notice>}

      {form && (
        <section className={s.card} aria-labelledby="h-form">
          <div className={s.cardHead}><h2 id="h-form">{form.email_lama ? `Ubah ${form.email_lama}` : "Tambah pengguna"}</h2></div>
          <div className={s.grid}>
            <label className={s.field}>
              <span>Email Google</span>
              <input type="email" value={form.email} autoFocus placeholder="nama@gmail.com"
                onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </label>
            <label className={s.field}>
              <span>Nama petugas (sama dengan sheet Broadcast)</span>
              <input list="daftar-petugas" value={form.nama_petugas} placeholder="Ketik atau pilih nama"
                onChange={(e) => setForm({ ...form, nama_petugas: e.target.value })} />
              <datalist id="daftar-petugas">{petugas.map((n) => <option key={n} value={n} />)}</datalist>
            </label>
          </div>
          <fieldset className={s.field}>
            <legend>Fitur</legend>
            <div className={s.pilihan}>
              {data.fitur.map((f) => (
                <label key={f}><input type="checkbox" checked={form.fitur.includes(f)} onChange={() => ganti(f)} />{LABEL_FITUR[f] ?? f}</label>
              ))}
              <label><input type="checkbox" checked={form.admin} onChange={(e) => setForm({ ...form, admin: e.target.checked })} />Admin</label>
            </div>
          </fieldset>
          {!form.email_lama && (
            <ol className={s.langkah}>
              <li>Pastikan email ini sudah punya akses edit ke sheet Broadcast, LK, dan LK Eskalasi, serta akses lihat ke sheet Akses.</li>
              <li>Bila aplikasi Google masih mode uji, tambahkan email ini sebagai test user di Google Cloud Console.</li>
              <li>Kirim file paket lk-monitoring.json lewat jalur pribadi (WA/Drive terbatas), bersama install.bat.</li>
            </ol>
          )}
          <div className={s.aksi}>
            <Button loading={busy === "simpan"} disabled={busy !== null || !form.email.trim() || !form.nama_petugas.trim() || !form.fitur.length}
              onClick={() => void simpan()}>
              {form.email_lama ? "Simpan perubahan" : "Tambahkan"}
            </Button>
            <Button variant="secondary" onClick={() => setForm(null)}>Batal</Button>
          </div>
        </section>
      )}

      <LinkLk />

      <section className={s.card} aria-labelledby="h-daftar">
        <div className={s.cardHead}>
          <h2 id="h-daftar">Pengguna</h2>
          <div className={s.saring}>
            <select value={peran} onChange={(e) => setPeran(e.target.value as Peran)} aria-label="Saring peran">
              <option value="">Semua peran</option>
              <option value="admin">Admin</option>
              <option value="pengguna">Pengguna</option>
            </select>
            <input type="search" value={cari} onChange={(e) => setCari(e.target.value)} placeholder="Cari email atau nama" aria-label="Cari pengguna" />
          </div>
        </div>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead><tr><th>Pengguna</th><th>Fitur</th><th>Peran</th><th aria-label="Aksi" /></tr></thead>
            <tbody>
              {daftar.map((p) => {
                const admin = adalahAdmin(p);
                return (
                  <tr key={p.email}>
                    <td>
                      <span className={s.orang}>
                        <span className={`${s.avatar} ${admin ? s.avatarAdmin : ""}`} aria-hidden="true">{inisial(p.nama_petugas, p.email)}</span>
                        <span>
                          <b>{p.nama_petugas || "Tanpa nama"}{p.email.toLowerCase() === saya && <span className={s.anda}>Anda</span>}</b>
                          <small>{p.email}</small>
                        </span>
                      </span>
                    </td>
                    <td>{p.fitur.map((f) => <span key={f} className={`${s.fitur} ${s[`fitur_${f}`] ?? ""}`}>{LABEL_FITUR[f] ?? f}</span>)}</td>
                    <td>{admin ? <span className={s.peranAdmin}>Admin</span> : <span className={s.peran}>Pengguna</span>}</td>
                    <td className={s.rowAksi}>
                      <button type="button" className={s.tombolKecil} disabled={busy !== null}
                        onClick={() => { setForm({ email: p.email, nama_petugas: p.nama_petugas, fitur: p.fitur, admin, email_lama: p.email }); setInfo(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                        Ubah
                      </button>
                      {p.email.toLowerCase() !== saya && (
                        <button type="button" className={`${s.tombolKecil} ${s.bahaya}`} disabled={busy !== null} onClick={() => void hapus(p)}>
                          {busy === p.email ? "Menghapus…" : "Hapus"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!daftar.length && <tr><td colSpan={4} className={s.kosong}>Tidak ada pengguna yang cocok.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
