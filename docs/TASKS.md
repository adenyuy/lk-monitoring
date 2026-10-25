# TASKS – LK Monitoring (WA Blast + Tarik Cutoff)

Kerjakan berurutan per fase. Setiap tugas punya **Selesai jika** sebagai patokan.
Estimasi kasar dalam jam kerja fokus. Rujukan: [PRD.md](PRD.md), [FLOW.md](FLOW.md), mockup UI.

---

## Struktur repo target

```
lk-monitoring/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI: mount /api + file statis web/out
│   │   ├── config.py          # ID sheet, jadwal sesi, kuota, port, path data
│   │   ├── paths.py           # %APPDATA%\LKMonitoring\...
│   │   ├── db.py              # SQLite + migrasi sederhana
│   │   ├── google_auth.py     # OAuth, email pengguna
│   │   ├── sheets.py          # Broadcast, LK, Akses
│   │   ├── access.py          # cek fitur per email
│   │   ├── schedule.py        # sesi aktif, kuota efektif
│   │   ├── send_queue.py      # antrean, anti-dobel
│   │   ├── sender.py          # loop kirim (thread), stop, mode coba
│   │   ├── events.py          # SSE broadcaster
│   │   ├── cutoff.py          # port dari tarik.py
│   │   ├── wa/
│   │   │   ├── browser.py     # Playwright persistent context
│   │   │   ├── selectors.py   # SEMUA selektor WhatsApp Web di sini
│   │   │   ├── actions.py     # buka chat, kirim, cek terkirim, baca chat
│   │   │   └── status.py      # login / QR / logout
│   │   └── routers/           # me, settings, wa, today, sessions, fasil, history, cutoff, events
│   ├── tests/                 # pytest: schedule, queue, cutoff, parser
│   └── requirements.txt
├── web/                       # Next.js (App Router, TS), output: 'export'
│   ├── app/
│   │   ├── setup/             # 4 langkah
│   │   ├── (app)/today/
│   │   ├── (app)/history/
│   │   ├── (app)/cutoff/
│   │   └── (app)/settings/
│   ├── components/
│   ├── lib/api.ts             # fetch + SSE client
│   └── styles/tokens.css
├── scripts/
│   ├── install.bat
│   ├── start.bat
│   └── dev.bat                # jalankan backend + next dev untuk developer
├── docs/                      # PRD.md, FLOW.md, TASKS.md, CARA_PAKAI.md
├── .github/workflows/release.yml
├── .gitignore
└── README.md
```

---

## Fase 0 – Persiapan repo (± 2 jam)

- [ ] **0.1 Buat repo publik** `adenyuy/lk-monitoring`, branch `main`, lalu buat `stable` dari `main`.
  Selesai jika: kedua branch ada di GitHub.
- [x] **0.2 `.gitignore`**: `credentials.json`, `token*.json`, `*.db`, `chrome-profile/`, `web/.next/`, `web/out/` (di `main`), `node_modules/`, `__pycache__/`, `.venv/`, `data/`, `*.csv`, `*.xlsx`.
  Selesai jika: `git status` bersih setelah menjalankan app lokal.
- [x] **0.3 Pindahkan dokumen** `PRD.md`, `FLOW.md`, `TASKS.md` ke `docs/`.
- [x] **0.4 Kerangka backend**: venv, `requirements.txt` (fastapi, uvicorn, gspread, google-auth, google-auth-oauthlib, pandas, openpyxl, playwright, python-multipart, sse-starlette).
  Selesai jika: `uvicorn app.main:app --port 8787` menampilkan `{"ok": true}` di `/api/health`.
- [x] **0.5 Kerangka web**: `npx create-next-app@latest web --ts --app --eslint`, `next.config` → `output: 'export'`, `images.unoptimized`.
  Selesai jika: `npm run build` menghasilkan `web/out/index.html`.
- [x] **0.6 Backend menyajikan `web/out`** di `/` (fallback ke `index.html` per route).
  Selesai jika: `http://localhost:8787` menampilkan halaman Next hasil build.
- [x] **0.7 `scripts/dev.bat`**: jalankan uvicorn (reload) + `next dev` dengan proxy `/api` ke 8787.

## Fase 1 – Fondasi backend (± 6 jam)

- [x] **1.1 `paths.py`**: buat `%APPDATA%\LKMonitoring\` + subfolder saat start.
- [x] **1.2 `config.py`**: ID Broadcast, ID LK, nama tab, jadwal sesi `[("10:00","13:59",10), …]`, jeda 45–120, port 8787, `ACCESS_SHEET_ID` dibaca dari `settings` (bukan hardcode).
- [x] **1.3 `db.py`**: buat tabel `settings`, `sends`, `chat_status`, `cutoff_runs` (skema di PRD §9). Fungsi kecil `get_setting/set_setting`.
  Selesai jika: test membuat & membaca setiap tabel lulus.
- [x] **1.4 `google_auth.py`**: alur OAuth installed app (scope `openid`, `email`, `spreadsheets`), simpan `token.json`, refresh otomatis, login ulang jika refresh gagal. Ambil email dari ID token.
  Selesai jika: `/api/me` mengembalikan email setelah login.
- [x] **1.5 Unggah credentials**: endpoint `POST /api/setup/credentials` (file) → salin ke folder data; `/api/me` mengembalikan `needsCredentials: true` bila belum ada.
- [x] **1.6 `sheets.py` – Broadcast**: baca `Broadcast!A:E`, normalisasi nama petugas (buang `*`, trim, casefold), ambil nomor dari `wa.me/…`, kembalikan list `{nama_fasil, nomor, pesan, hash}`.
  Selesai jika: untuk "Sari Petugas" terbaca 49 baris, "Budi Petugas" tidak ikut.
- [x] **1.7 `sheets.py` – LK**: baca `WEEK n!B3:O` (hanya kolom perlu), kelompokkan sekolah per nomor fasil (9 digit terakhir) + petugas. Cache 10 menit.
- [x] **1.8 `sheets.py` + `access.py` – Akses**: baca sheet Akses → `{email: {nama_petugas, fitur[]}}`. Email tidak terdaftar → 403 dengan pesan jelas.
- [x] **1.9 Router `me`, `settings`, `petugas`.**

## Fase 2 – Fondasi web (± 5 jam)

- [x] **2.1 Token desain** dari mockup di `styles/tokens.css`:
  `--bg #F6F7F9`, `--surface #FFFFFF`, `--ink #172033`, `--muted #5B6474`, `--line #E4E7EC`, `--primary #2346A0`, `--primary-soft #F5F7FD`, `--ok #1E5E3C / #E9F5EE`, `--warn #7A4900 / #FFF4DE`, `--bad #A6282B / #FCECEC`; font IBM Plex Sans 400/500/600; radius 8 (kontrol) / 10–12 (panel).
- [x] **2.2 Komponen dasar**: `Button` (primary/secondary/ghost/danger), `Chip` (status), `Panel`, `Stepper`, `Toggle`, `Table`, `EmptyState`, `ErrorBanner`.
- [x] **2.3 `lib/api.ts`**: wrapper fetch dengan penanganan error (pesan dari backend tampil apa adanya) + `useEvents()` untuk SSE.
- [x] **2.4 Layout app**: header (logo, menu Hari ini / Riwayat / Tarik Cutoff*, nomor WA, nama, tombol batas harian), footer versi. *Menu Cutoff hanya bila `me.fitur` memuat `cutoff`.
- [x] **2.5 Penjaga rute**: belum setup → `/setup`; sudah → `/today`.

## Fase 3 – Setup berurutan (± 5 jam)

- [x] **3.1 Langkah 0 (bila perlu)**: pilih file `credentials.json`.
- [x] **3.2 Masuk Google**: tombol → `POST /api/auth/login` (backend membuka browser OAuth) → polling `/api/me` sampai login. Tampilkan pesan bila email tidak terdaftar di Akses.
- [x] **3.3 Konfirmasi nama**: daftar dari `/api/petugas`, terpilih otomatis dari Akses, tampil jumlah fasil.
- [x] **3.4 Hubungkan WhatsApp**: `POST /api/wa/connect` → Chrome terbuka; layar menunggu status `logged_in` lewat SSE; tampil nomor tersamar.
- [x] **3.5 Batas harian**: stepper ±5 (10–70), peringatan 3 tingkat, estimasi hari; simpan.
  Selesai jika: seluruh alur bisa dilalui ulang dari Pengaturan tanpa kehilangan data.

## Fase 4 – Mesin WhatsApp (± 10 jam, bagian paling berisiko)

- [x] **4.1 `wa/browser.py`**: Playwright `launch_persistent_context(user_data_dir=chrome-profile, channel="chrome", headless=False)`; satu instance untuk seluruh app; tutup rapi saat app berhenti.
- [x] **4.2 `wa/status.py`**: deteksi `qr` / `loading` / `logged_in` / `logged_out`; ambil nomor akun yang login.
- [x] **4.3 `wa/selectors.py`**: kumpulkan semua selektor (kotak pesan, tombol kirim, ikon status pesan, popup nomor tidak valid, daftar pesan masuk). Beri komentar tanggal dicek.
- [x] **4.4 `actions.open_chat(nomor, teks)`**: buka `https://web.whatsapp.com/send?phone=<nomor>&text=<urlencoded>`, tunggu kotak pesan berisi teks atau popup "nomor tidak valid" (timeout 30 dtk).
- [x] **4.5 `actions.send()`**: tekan Enter/tombol kirim, tunggu pesan terakhir keluar berstatus bukan jam (≤ 30 dtk). Kembalikan `terkirim` / `gagal(alasan)`.
- [x] **4.6 `actions.read_chat(nomor)`**: ambil status pesan keluar terakhir (terkirim/dibaca) + teks & jam pesan masuk setelahnya.
- [x] **4.7 Uji manual dengan mode coba** ke nomor sendiri / rekan (bukan fasil).
  Selesai jika: 3 percobaan berturut-turut membuka chat dan mengisi teks dengan benar; 1 kirim nyata ke nomor sendiri terdeteksi "terkirim".

## Fase 5 – Penjadwal & pengiriman (± 8 jam)

- [x] **5.1 `schedule.py`**: `sesi_aktif(now)`, `kuota_efektif(...)`, `judul_hari_ini(...)`, cek akhir pekan. Unit test untuk batas jam (13.59/14.00, 22.00, Sabtu).
- [x] **5.2 `send_queue.py`**: gabungkan Broadcast + `sends` → status per fasil; anti-dobel (`nomor + hash`); deteksi nomor dobel; urutan = urutan sheet.
  Selesai jika: test "pesan berubah → masuk antrean lagi" dan "nomor dobel → dilewati" lulus.
- [x] **5.3 `sender.py`**: thread kirim; untuk tiap fasil: validasi → open_chat → send/coba → catat `sends` → SSE → jeda acak; patuhi Stop, 2 gagal beruntun, logout.
- [x] **5.4 Router `send/start`, `send/stop`, `events`.** Tolak start bila di luar sesi / kuota 0 / sudah berjalan (pesan error jelas).
- [x] **5.5 Pembaruan status chat**: job tiap 15 menit + saat app dibuka → `read_chat` untuk kiriman 7 hari terakhir yang belum "Dibalas"; dijalankan hanya saat tidak sedang mengirim.

## Fase 6 – Layar Hari ini (± 8 jam)

- [x] **6.1 `/api/today` + `/api/sessions/{n}`** (judul, ringkasan, blok, baris detail).
- [x] **6.2 Rel jadwal**: grid `4fr 2fr 3fr 2fr 1fr`, blok sebagai `<button>`, penanda jam sekarang (update tiap menit), label jam 10.00–22.00, scroll horizontal di layar sempit.
- [x] **6.3 Panel detail sesi**: tiga keadaan (lewat / berjalan / mendatang) + kontrol kirim, mode coba, progres SSE, hitung mundur, Stop.
- [x] **6.4 Panel chat**: `/api/fasil/{nomor}` → status, tabel sekolah binaan (NPSN, progres, chip prioritas), gelembung pesan, tombol "Buka di WhatsApp Web" (fokuskan chat di jendela Chrome app).
- [x] **6.5 Keadaan kosong & error**: Broadcast kosong untuk petugas, WA logout (banner + tombol scan ulang), sheet tidak bisa dibaca.

## Fase 7 – Riwayat (± 4 jam)

- [ ] **7.1 `/api/history`** (daftar hari) dan `/api/history/{tanggal}` (ringkasan sesi + baris).
- [ ] **7.2 Layar Riwayat**: daftar hari kiri, ringkasan 5 sesi, tabel + saring status.
- [ ] **7.3 CSV rekap**: satu baris per sekolah (gabung `sends` × sekolah binaan LK), UTF-8 dengan BOM agar rapi di Excel.

## Fase 8 – Tarik Cutoff (± 5 jam)

- [ ] **8.1 `cutoff.py`**: pindahkan fungsi dari `tarik.py` (`baca_cutoff`, `olah`, `ke_capaian`, `prioritas`, penulisan batch + format persen + note). Pertahankan test dari data contoh (kasus 13.12, koma desimal, Laporan 50% kosong).
- [ ] **8.2 `POST /api/cutoff/preview`** (multipart file + mode + week) → ringkasan & contoh, file disimpan sementara.
- [ ] **8.3 `POST /api/cutoff/write`** → tulis ke `WEEK n`, simpan `cutoff_runs`. Cek akses `cutoff` di kedua endpoint.
- [ ] **8.4 Layar Tarik Cutoff**: pilih file, mode, week → pratinjau (jumlah per prioritas, contoh) → "Tulis ke WEEK n" → hasil + riwayat.
  Selesai jika: file cutoff penuh tertulis ke file copy LK < 30 detik dan hasilnya sama dengan `tarik.py`.

## Fase 9 – Distribusi (± 5 jam)

- [ ] **9.1 `.github/workflows/release.yml`**: on push `stable` → setup Node → `npm ci && npm run build` di `web/` → salin `backend/`, `web/out/`, `scripts/`, `docs/CARA_PAKAI.md` → force-push ke branch `release` + tag versi (`vYYYY.MM.DD-N`).
- [ ] **9.2 `install.bat`**: cek/instal Git & Python 3.12 (winget, `--scope user`), `git clone -b release`, `python -m venv`, `pip install -r`, `python -m playwright install-deps` tidak perlu (pakai Chrome), buat shortcut Desktop ke `start.bat`.
- [ ] **9.3 `start.bat`**: `git fetch` + `git reset --hard origin/release` (lewati bila offline), `pip install -r` bila hash `requirements.txt` berubah, jalankan uvicorn tanpa jendela console tambahan, buka `http://localhost:8787`, cegah dua instance (cek port).
- [ ] **9.4 `CARA_PAKAI.md`** untuk tim (install, setup, kirim per sesi, riwayat, tips anti-ban, kontak admin).
- [ ] **9.5 Sheet Akses** dibuat + isi email tim; email tim didaftarkan di Google Cloud → Audience → Test users.

## Fase 10 – Uji & rilis (± 4 jam + pilot)

- [ ] **10.1 Uji lokal penuh** di laptop Marvin: setup dari nol, mode coba 5 fasil, kirim nyata 3 fasil, Riwayat & CSV, Tarik Cutoff ke file copy.
- [ ] **10.2 Uji laptop bersih** (tanpa Python/Git): `install.bat` → app jalan < 15 menit.
- [ ] **10.3 Pilot** 1–2 petugas selama 2 hari; catat masalah di GitHub Issues.
- [ ] **10.4 Rilis tim**: merge ke `stable`, kirim `install.bat` + `credentials.json` + CARA_PAKAI.

---

## Sebelum mulai ngoding (non-kode)

- [ ] Bersihkan LK asli: kosongkan isi CUTOFF (sheet tetap ada), hapus sheet W1 & Copy of Template, hapus isi kolom Helper 1–3 jika tidak dipakai.
- [ ] Konfirmasi ke tim: definisi prioritas baru & rencana update Broadcast besok pagi.
- [ ] Tentukan nama repo dan lokasi sheet Akses (PRD §13).

## Urutan kerja yang disarankan untuk hari pertama

1. Fase 0 lengkap.
2. 1.1–1.6 (bisa membaca Broadcast).
3. 4.1–4.4 + 4.7 mode coba (membuktikan bagian paling berisiko lebih awal).
4. Baru lanjut UI (Fase 2–3).
