"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, post } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import type { Petugas } from "@/lib/types";
import { Button, Chip, Notice, Spinner } from "@/components/ui";
import { NoAccess } from "@/components/app/NoAccess";
import s from "./admin.module.css";

type Pengguna = { baris: number; email: string; nama_petugas: string; fitur: string[]; catatan: string };
type Data = { pengguna: Pengguna[]; fitur: string[] };
type Form = { email: string; nama_petugas: string; fitur: string[]; admin: boolean; email_lama: string };

const LABEL_FITUR: Record<string, string> = { wa_blast: "Blast & LK", cutoff: "Tarik Cutoff" };
const KOSONG: Form = { email: "", nama_petugas: "", fitur: ["wa_blast"], admin: false, email_lama: "" };

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
  const q = cari.trim().toLowerCase();
  const daftar = data.pengguna.filter((p) => !q || `${p.email} ${p.nama_petugas}`.toLowerCase().includes(q));
  const ganti = (f: string) => form && setForm({ ...form, fitur: form.fitur.includes(f) ? form.fitur.filter((x) => x !== f) : [...form.fitur, f] });

  return (
    <div className={s.page}>
      <header className={s.head}>
        <div>
          <h1>Admin</h1>
          <p>Kelola siapa saja yang boleh memakai aplikasi. Perubahan langsung ditulis ke sheet Akses.</p>
        </div>
        <div className={s.headAksi}>
          <a className={s.paket} href="/api/admin/paket" download="lk-monitoring.json">Unduh paket lk-monitoring.json</a>
          <Button onClick={() => { setForm({ ...KOSONG }); setInfo(null); }} disabled={!!form}>Tambah pengguna</Button>
        </div>
      </header>

      {info && <Notice tone={info.tone} title={info.tone === "ok" ? "Tersimpan" : "Belum tersimpan"}>{info.teks}</Notice>}

      {form && (
        <section className={s.card} aria-labelledby="h-form">
          <h2 id="h-form">{form.email_lama ? `Ubah ${form.email_lama}` : "Tambah pengguna"}</h2>
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
            <div className={s.checks}>
              {data.fitur.map((f) => (
                <label key={f}><input type="checkbox" checked={form.fitur.includes(f)} onChange={() => ganti(f)} />{LABEL_FITUR[f] ?? f}</label>
              ))}
              <label><input type="checkbox" checked={form.admin} onChange={(e) => setForm({ ...form, admin: e.target.checked })} />Admin (boleh membuka halaman ini)</label>
            </div>
          </fieldset>
          <div className={s.aksi}>
            <Button loading={busy === "simpan"} disabled={busy !== null || !form.email.trim() || !form.nama_petugas.trim() || !form.fitur.length}
              onClick={() => void simpan()}>
              {form.email_lama ? "Simpan perubahan" : "Tambahkan"}
            </Button>
            <Button variant="secondary" onClick={() => setForm(null)}>Batal</Button>
          </div>
          {!form.email_lama && (
            <ul className={s.langkah}>
              <li>Pastikan email ini sudah punya akses edit ke sheet Broadcast, LK, dan LK Eskalasi, serta akses lihat ke sheet Akses.</li>
              <li>Bila aplikasi Google masih mode uji, tambahkan email ini sebagai test user di Google Cloud Console.</li>
              <li>Kirim file paket lk-monitoring.json lewat jalur pribadi (WA/Drive terbatas), bersama install.bat.</li>
            </ul>
          )}
        </section>
      )}

      <section className={s.card} aria-labelledby="h-daftar">
        <div className={s.cardHead}>
          <h2 id="h-daftar">Pengguna <span>{data.pengguna.length}</span></h2>
          <input type="search" className={s.cari} value={cari} onChange={(e) => setCari(e.target.value)} placeholder="Cari email atau nama" aria-label="Cari pengguna" />
        </div>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead><tr><th>Nama petugas</th><th>Email</th><th>Fitur</th><th>Peran</th><th aria-label="Aksi" /></tr></thead>
            <tbody>
              {daftar.map((p) => {
                const admin = p.catatan.toLowerCase() === "admin";
                return (
                  <tr key={p.email}>
                    <td><b>{p.nama_petugas || "–"}</b>{p.email.toLowerCase() === saya && <span className={s.anda}>Anda</span>}</td>
                    <td>{p.email}</td>
                    <td>{p.fitur.map((f) => <span key={f} className={s.fitur}>{LABEL_FITUR[f] ?? f}</span>)}</td>
                    <td><Chip tone={admin ? "info" : "muted"}>{admin ? "Admin" : "Pengguna"}</Chip></td>
                    <td className={s.rowAksi}>
                      <button type="button" className={s.linkBtn} disabled={busy !== null}
                        onClick={() => { setForm({ email: p.email, nama_petugas: p.nama_petugas, fitur: p.fitur, admin, email_lama: p.email }); setInfo(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                        Ubah
                      </button>
                      {p.email.toLowerCase() !== saya && (
                        <button type="button" className={`${s.linkBtn} ${s.bahaya}`} disabled={busy !== null} onClick={() => void hapus(p)}>
                          {busy === p.email ? "Menghapus…" : "Hapus"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
