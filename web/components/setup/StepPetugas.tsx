"use client";

import { useEffect, useMemo, useState } from "react";
import { api, post } from "@/lib/api";
import type { Me, Petugas } from "@/lib/types";
import { Button, Notice, Spinner } from "@/components/ui";
import s from "./setup.module.css";

const norm = (x: string) => x.replace(/\*/g, "").replace(/\s+/g, " ").trim().toLowerCase();

export function StepPetugas({
  me,
  onBack,
  onNext,
}: {
  me: Me;
  onBack: () => void;
  onNext: (petugas: Petugas) => void;
}) {
  const [list, setList] = useState<Petugas[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<string | null>(me.settings.nama_petugas ?? me.access?.nama_petugas ?? null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    api<{ petugas: Petugas[] }>("/api/petugas")
      .then((d) => setList(d.petugas))
      .catch((e) => setLoadError(e.message));
  }, []);

  const dariAkses = me.access?.nama_petugas ?? "";
  // Nama akunmu (dari sheet Akses) selalu di paling atas, sisanya urut abjad.
  const shown = useMemo(() => {
    const filtered = (list ?? []).filter((p) => norm(p.nama).includes(norm(query)));
    const mine = filtered.filter((p) => dariAkses && norm(p.nama) === norm(dariAkses));
    return [...mine, ...filtered.filter((p) => !mine.includes(p))];
  }, [list, query, dariAkses]);
  const selected = list?.find((p) => picked && norm(p.nama) === norm(picked)) ?? null;
  const beda = selected && dariAkses && norm(selected.nama) !== norm(dariAkses);

  async function save() {
    if (!selected) return;
    setSaving(true);
    setSaveError(null);
    try {
      await post("/api/settings", { nama_petugas: selected.nama });
      onNext(selected);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h1 className={s.title}>Pilih nama petugas</h1>
      <p className={s.desc}>
        Sesuai kolom Nama Petugas di sheet Broadcast. Hanya fasilitator dengan nama ini yang akan dikirimi pesan dari
        nomor WhatsApp-mu.
      </p>

      {loadError && <Notice tone="bad" title="Daftar petugas tidak bisa dimuat">{loadError}</Notice>}

      {!list && !loadError && (
        <div className={s.waiting}>
          <Spinner label="Memuat" />
          <span>Membaca sheet Broadcast…</span>
        </div>
      )}

      {list && (
        <>
          <label className={s.srOnly} htmlFor="cari">Cari nama petugas</label>
          <input id="cari" className={s.search} type="search" placeholder="Cari nama" value={query}
            onChange={(e) => setQuery(e.target.value)} autoComplete="off" />
          <ul className={s.list} role="radiogroup" aria-label="Nama petugas">
            {shown.map((p) => {
              const on = !!selected && norm(selected.nama) === norm(p.nama);
              return (
                <li key={p.nama}>
                  <button type="button" role="radio" aria-checked={on} className={s.option}
                    onClick={() => setPicked(p.nama)}>
                    <span className={s.radio} aria-hidden="true" />
                    <span className={s.optionName}>{p.nama}</span>
                    {dariAkses && norm(p.nama) === norm(dariAkses) && <span className={s.badge}>Akunmu</span>}
                    <span className={s.count}>{p.jumlah_fasil} fasilitator</span>
                  </button>
                </li>
              );
            })}
            {shown.length === 0 && <li className={s.empty}>Tidak ada nama yang cocok dengan &ldquo;{query}&rdquo;.</li>}
          </ul>
        </>
      )}

      {beda && (
        <Notice tone="warn" title="Nama berbeda dengan data akses">
          Akunmu terdaftar sebagai <b>{dariAkses}</b>. Pastikan kamu memang mengirim untuk {selected?.nama}.
        </Notice>
      )}
      {saveError && <Notice tone="bad" title="Belum tersimpan">{saveError}</Notice>}

      <div className={s.actions}>
        <Button disabled={!selected} loading={saving} onClick={save}>
          {selected ? `Lanjut sebagai ${selected.nama}` : "Pilih nama dulu"}
        </Button>
        <Button variant="ghost" onClick={onBack}>Kembali</Button>
      </div>
    </>
  );
}
