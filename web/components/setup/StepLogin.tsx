"use client";

import { useRef, useState } from "react";
import { post, upload } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { Me } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./setup.module.css";

function initials(email: string) {
  return email.slice(0, 2).toUpperCase();
}

export function StepLogin({ me, reload, onNext }: { me: Me; reload: () => Promise<Me | null>; onNext: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const waiting = me.login.status === "running" && !me.logged_in;
  usePolling(reload, 1500, waiting);

  async function pickCredentials(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await upload("/api/setup/credentials", file);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function login() {
    setBusy(true);
    setError(null);
    try {
      await post("/api/auth/login");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function switchAccount() {
    setBusy(true);
    try {
      await post("/api/auth/logout");
      await post("/api/auth/login");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  // 0. file paket (credentials + alamat sheet) belum dipasang
  if (me.needs_credentials) {
    return (
      <>
        <h1 className={s.title}>Pasang file akses aplikasi</h1>
        <p className={s.desc}>
          Sebelum masuk, aplikasi perlu file <b>lk-monitoring.json</b> dari admin. File ini berisi izin aplikasi dan
          alamat sheet tim, cukup dipasang sekali di laptop ini.
        </p>
        <ul className={s.points}>
          {[
            "Minta file lk-monitoring.json ke admin tim monitoring. Jangan dibagikan ke orang lain.",
            "Simpan di laptop ini, misalnya di folder Downloads.",
            "Tekan tombol di bawah lalu pilih file tersebut.",
          ].map((t) => (
            <li key={t}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
              {t}
            </li>
          ))}
        </ul>
        {error && <Notice tone="bad" title="File tidak bisa dipakai">{error}</Notice>}
        <div className={s.actions}>
          <input ref={fileRef} id="cred" type="file" accept=".json,application/json" className={s.srOnly}
            onChange={(e) => pickCredentials(e.target.files?.[0])} />
          <Button loading={busy} onClick={() => fileRef.current?.click()}>Pilih lk-monitoring.json</Button>
        </div>
      </>
    );
  }

  // 3. sudah login tapi email belum terdaftar / sheet Akses bermasalah
  if (me.logged_in && me.access_error) {
    return (
      <>
        <h1 className={s.title}>Akun belum bisa dipakai</h1>
        <div className={s.account}>
          <span className={s.avatar} aria-hidden="true">{initials(me.email ?? "?")}</span>
          <div>
            <div style={{ fontWeight: 500 }}>{me.email}</div>
            <div className={s.fine}>Akun Google yang sedang masuk</div>
          </div>
        </div>
        <Notice tone="bad" title="Akses ditolak">{me.access_error}</Notice>
        <div className={s.actions}>
          <Button variant="secondary" loading={busy} onClick={switchAccount}>Masuk dengan akun lain</Button>
          <Button variant="ghost" onClick={reload}>Cek lagi</Button>
        </div>
      </>
    );
  }

  // 4. siap
  if (me.logged_in && me.access) {
    return (
      <>
        <h1 className={s.title}>Masuk sebagai {me.access.nama_petugas || me.email}</h1>
        <div className={s.account}>
          <span className={s.avatar} aria-hidden="true">{initials(me.email ?? "?")}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500 }}>{me.email}</div>
            <div className={s.fine}>
              Fitur: {me.access.fitur.map((f) => (f === "wa_blast" ? "WA Blast" : "Tarik Cutoff")).join(", ")}
            </div>
          </div>
        </div>
        <div className={s.actions}>
          <Button onClick={onNext}>Lanjut</Button>
          <Button variant="ghost" loading={busy} onClick={switchAccount}>Ganti akun</Button>
        </div>
      </>
    );
  }

  // 1–2. belum login / sedang menunggu login di browser
  return (
    <>
      <h1 className={s.title}>Masuk dengan akun Google</h1>
      <p className={s.desc}>
        Dipakai untuk membaca daftar fasilitator dan isi pesan dari sheet Broadcast tim. Aplikasi tidak mengubah isi
        sheet tersebut.
      </p>
      <ul className={s.points}>
        {[
          "Tab baru terbuka untuk memilih akun Google.",
          "Pakai akun yang didaftarkan admin di sheet Akses.",
          "Izinkan akses Google Sheets dan alamat email, lalu kembali ke halaman ini.",
        ].map((t) => (
          <li key={t}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
            {t}
          </li>
        ))}
      </ul>
      {(error || me.login.status === "error") && (
        <Notice tone="bad" title="Login belum berhasil">{error || me.login.error}</Notice>
      )}
      {waiting ? (
        <div className={s.waiting}>
          <Spinner label="Menunggu login" />
          <span>Selesaikan login di tab browser yang baru terbuka. Halaman ini lanjut otomatis.</span>
        </div>
      ) : (
        <div className={s.actions}>
          <Button loading={busy} onClick={login}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#fff" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3zM12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22zM6.4 14a6 6 0 0 1 0-3.9V7.5H3.1a10 10 0 0 0 0 9zM12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.5L6.4 10C7.2 7.7 9.4 5.9 12 5.9z" />
            </svg>
            Masuk dengan Google
          </Button>
        </div>
      )}
      <p className={s.fine}>
        Muncul tulisan &ldquo;Google hasn&rsquo;t verified this app&rdquo;? Pilih <b>Continue</b>. Ini aplikasi internal tim.
      </p>
    </>
  );
}
