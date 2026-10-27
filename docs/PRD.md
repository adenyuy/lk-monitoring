# PRD – Monitoring Revit SD: WA Blast + Tarik Cutoff

| | |
|---|---|
| **Pemilik** | Tim Monitoring Direktorat SD |
| **Versi** | 1.0 – final untuk mulai development |
| **Tanggal** | 25 Oktober 2026 |
| **Repo** | `github.com/adenyuy/<nama-repo>` (publik) |
| **Dokumen terkait** | [FLOW.md](FLOW.md) alur sistem · [TASKS.md](TASKS.md) daftar tugas · mockup UI: claude.ai/artifact/QdWAM4b4HofcNBq3xvoJUT |

---

## 1. Ringkasan

Aplikasi web lokal untuk tim monitoring dengan dua fitur:

1. **WA Blast** – mengirim pesan WhatsApp ke fasilitator secara otomatis per sesi, dari nomor WA masing-masing petugas, memakai daftar dan isi pesan dari sheet Broadcast. Dilengkapi rekap per sesi/hari dan tampilan chat fasilitator (hanya baca).
2. **Tarik Cutoff** – memindahkan data file cutoff dari aplikasi pelaporan (CSV/Excel) ke sheet WEEK n di LK Monitoring: progres fisik, status submit/reviu, dan prioritas. Hanya untuk pengguna yang diberi akses.

Setiap petugas menjalankan aplikasi di laptopnya sendiri lewat satu shortcut. Aplikasi memperbarui dirinya sendiri dari GitHub setiap kali dibuka.

## 2. Masalah

- Petugas memegang 41–58 fasilitator; mengirim pesan satu per satu (filter sheet, klik nomor, salin, tempel, kirim) lambat.
- Nomor WA pernah diblokir sehari setelah pesan ke-51 dalam satu hari.
- Tidak ada catatan siapa yang sudah dikirimi dan siapa yang membalas, sehingga sulit rekap untuk LK.
- Sheet LK lambat karena data cutoff (±339 ribu baris) dan formula berat di dalamnya.

## 3. Tujuan & Ukuran Keberhasilan

| Tujuan | Ukuran |
|---|---|
| Kirim WA tanpa copy-paste | 1 klik per sesi; tidak ada langkah salin-tempel |
| Nomor tidak diblokir | 0 kejadian blokir selama 2 minggu pemakaian dengan batas default |
| Tidak ada kiriman dobel / terlewat | Setiap fasil di Broadcast tercatat tepat sekali per isi pesan |
| Rekap untuk LK tersedia | Rekap per hari bisa diunduh dalam 1 klik |
| Tarik cutoff cepat | File cutoff penuh selesai ditulis ke WEEK n < 30 detik |
| Mudah dipakai tim | Setup laptop baru < 15 menit tanpa bantuan teknis |

## 4. Pengguna & Akses

| Peran | Siapa | Fitur |
|---|---|---|
| **Petugas** | ±23 petugas monitoring | WA Blast (miliknya sendiri), Riwayat |
| **Pengelola cutoff** | Ditentukan Marvin | Semua fitur Petugas + Tarik Cutoff |
| **Admin** | Marvin | Mengatur daftar akses (di Google Sheet) |

- Identitas pengguna = email akun Google yang login di aplikasi.
- Daftar akses disimpan di **sheet Akses** (Google Sheet milik admin, privat), bukan di repo, karena repo publik.

| email | nama_petugas | fitur |
|---|---|---|
| admin@contoh.id | Nama Petugas | wa_blast, cutoff |
| … | … | wa_blast |

- Email yang tidak ada di sheet Akses → tampil pesan "Akunmu belum terdaftar. Hubungi admin." dan aplikasi berhenti.
- `nama_petugas` di sheet Akses mengisi pilihan nama otomatis (petugas tetap bisa mengonfirmasi di layar setup).

## 5. Cakupan

### Termasuk (v1)
- Setup berurutan: Masuk Google → Konfirmasi nama → Hubungkan WhatsApp → Batas harian.
- WA Blast per sesi dengan kuota, batas harian, jeda acak, anti-dobel, mode coba, berhenti otomatis.
- Layar Hari ini: rel jadwal sesi (klik sesi untuk lihat detail, termasuk sesi yang sudah lewat), panel chat fasil + sekolah binaannya.
- Riwayat per hari + unduh rekap CSV.
- Tarik Cutoff (berbasis akses).
- Instalasi dan pembaruan otomatis dari GitHub.

### Tidak termasuk (v1)
- Pengisian LK otomatis dari balasan fasil (direncanakan v2).
- WhatsApp Cloud API / server terpusat / dashboard online tim.
- Mengubah isi sheet Broadcast.
- Membalas chat dari aplikasi (membalas tetap di WhatsApp Web).

## 6. Sumber Data

| Data | Lokasi | Akses aplikasi |
|---|---|---|
| Broadcast | Spreadsheet "Tempalete kirim pesan Dashboard Tim 1", ID `ID_SHEET_BROADCAST`, tab `Broadcast` | Baca |
| LK Monitoring | Spreadsheet "Master LK Komunikasi Para Petugas - Revit SD 2026", ID `ID_SHEET_LK`, tab `WEEK n` | Baca (WA Blast), baca + tulis (Cutoff) |
| Akses | Spreadsheet milik admin (ID diisi di konfigurasi) | Baca |
| Cutoff | File CSV/Excel dari aplikasi pelaporan, dipilih pengguna | Baca lokal |

### Broadcast
| Kolom | Dipakai untuk |
|---|---|
| `Nama Fasil` | Nama fasil di antrean |
| `Nomor HP` | Link `https://wa.me/62…` → diambil angkanya |
| `Pesan` | Isi pesan yang dikirim apa adanya |
| `Nama Petugas` | Filter. Buang `*` dan spasi, cocokkan **persis** (tanpa beda huruf besar/kecil). "Dimas Sari Petugas" ≠ "Sari Petugas". |

Kolom `TEMPLATE PESAN 1/2/3` tidak dipakai.

### LK WEEK n (struktur yang dipakai)
| Kolom | Isi |
|---|---|
| B | Petugas |
| C | NPSN |
| D | Nama Sekolah |
| F | Fasilitator |
| G | No Fasil |
| H | Prioritas (ditulis Tarik Cutoff harian) |
| J, K, L | Progress fisik, Status submit, Status reviu – baseline (Tarik Cutoff mingguan) |
| M, N, O | Progress fisik, Status submit, Status reviu – harian (Tarik Cutoff harian) |

Data mulai baris 3. Sekolah binaan fasil di panel chat = baris LK dengan nomor fasil yang sama (9 digit terakhir) dan petugas yang sama.

### File cutoff
Kolom berdasarkan posisi: A NPSN, C Jenis Laporan, E Capaian (%), F Sudah Submit, G Sudah Review. Semua nilai dibaca sebagai teks (mencegah "13.12" berubah jadi tanggal).

## 7. Aturan Bisnis

### 7.1 Prioritas (Tarik Cutoff)
| Prioritas | Kondisi |
|---|---|
| Prioritas 1 | Belum submit laporan 50% (berapa pun progresnya) |
| Prioritas 2 | Sudah submit, progres fisik < 50% |
| Prioritas 3 | Sudah submit, progres ≥ 50%, belum direviu |
| Selesai | Sudah submit, progres ≥ 50%, sudah direviu |

- Progres = capaian tertinggi dari baris "Laporan Mingguan". Nilai yang terbaca sebagai tanggal (contoh 2026-12-13) dikembalikan menjadi 13.12.
- Submit/reviu diambil dari baris "Laporan 50%". Baris tidak ada atau kosong → "Tidak".
- Progres ditulis sebagai persen (22.39 → 0.2239 berformat `0.00%`).

### 7.2 Sesi & kuota (WA Blast)
| Sesi | Aktif | Kuota |
|---|---|---|
| 1 | 10.00 – 13.59 | 10 |
| 2 | 14.00 – 15.59 | 10 |
| 3 | 16.00 – 18.59 | 15 |
| 4 | 19.00 – 20.59 | 15 |
| 5 | 21.00 – 22.00 | 10 |

- Kuota efektif = `min(kuota sesi − terkirim sesi ini, batas harian − terkirim hari ini, sisa antrean)`.
- Sesi yang terlewat tidak dipindah ke sesi berikutnya.
- Sabtu/Minggu: tidak bisa kirim, kecuali pengguna menyalakan "Izinkan kirim akhir pekan".
- Jadwal & kuota disimpan di konfigurasi repo agar bisa diubah lewat update.

### 7.3 Batas harian
- Diatur tiap pengguna, default **40**, rentang 10–70.
- 41–50: peringatan kuning "Mendekati batas aman".
- > 50: peringatan merah "Nomor tim pernah diblokir sehari setelah pesan ke-51".

### 7.4 Pengiriman
- Jeda acak 45–120 detik antar pesan.
- Terkirim = pesan muncul di chat dengan status bukan "menunggu" (ikon jam) dalam 30 detik.
- **Anti-dobel:** kunci = `nomor + sha1(isi pesan)`. Status Terkirim dengan kunci sama → tidak dikirim lagi. Isi pesan berubah di Broadcast → masuk antrean lagi.
- Nomor muncul di 2 baris dengan pesan sama → baris kedua "Dilewati – nomor dobel".
- **Berhenti total** jika: WA Web logout / meminta QR, 2 gagal beruntun, halaman tidak merespons 60 detik. Alasan ditampilkan.
- Nomor tidak terdaftar di WhatsApp → "Gagal", lanjut ke berikutnya (dihitung untuk aturan 2 gagal beruntun).
- Stop → berhenti setelah pesan yang sedang diproses selesai.
- Mode coba → buka chat dan isi pesan tanpa menekan kirim; dicatat status "Dicoba"; tidak mengurangi kuota.

### 7.5 Status chat
| Status | Arti |
|---|---|
| Menunggu | Belum dikirim |
| Terkirim | Centang satu/dua abu |
| Dibaca | Centang biru, belum ada balasan |
| Dibalas | Ada pesan masuk dari fasil setelah pesan kita |
| Gagal | Gagal kirim, alasan dicatat |
| Dilewati | Data tidak valid / dobel |
| Dicoba | Mode coba |

Status Dibaca/Dibalas diperbarui saat aplikasi dibuka dan setiap 15 menit, untuk kiriman 7 hari terakhir.

### 7.6 Pergantian hari
- Riwayat tersimpan dan tetap bisa dilihat.
- Hitungan harian & kuota sesi kembali ke nol.
- Antrean melanjutkan fasil yang belum terkirim.

## 8. Fitur

### F1. Instalasi & pembaruan
| | Kriteria |
|---|---|
| F1.1 | `install.bat` (sekali): pasang Git & Python via winget bila belum ada, clone repo ke `%USERPROFILE%\lk-monitoring`, pasang library, buat shortcut Desktop "LK Monitoring". |
| F1.2 | `start.bat` (shortcut): ambil versi terbaru dari branch `release` (dilewati bila offline), pasang library baru bila `requirements.txt` berubah, jalankan server, buka browser ke `http://localhost:8787`. |
| F1.3 | Data pengguna disimpan di `%APPDATA%\LKMonitoring\` (di luar folder repo) sehingga update tidak pernah menyentuhnya. |
| F1.4 | `credentials.json` (OAuth client) tidak ada di repo. Saat pertama dijalankan, app meminta pengguna memilih file `credentials.json` (dibagikan admin lewat Drive) lalu menyalinnya ke folder data. |
| F1.5 | Versi aplikasi tampil di footer (tag/commit) untuk memudahkan laporan masalah. |

### F2. Setup berurutan (sesuai mockup)
| | Kriteria |
|---|---|
| F2.1 | Masuk Google (OAuth, scope: `openid email spreadsheets`). Email dicek ke sheet Akses. |
| F2.2 | Konfirmasi nama petugas: terisi dari sheet Akses; daftar nama dari Broadcast + jumlah fasil. |
| F2.3 | Hubungkan WhatsApp: membuka Chrome profil khusus app di WhatsApp Web, layar menunggu sampai login terdeteksi, lalu menampilkan nomor tersamar. |
| F2.4 | Batas harian: stepper ±5, peringatan sesuai 7.3, estimasi jumlah hari. |
| F2.5 | Setup hanya muncul sekali; bisa diulang dari menu pengaturan. |

### F3. Hari ini
| | Kriteria |
|---|---|
| F3.1 | Judul menyebut kondisi: "Sesi 2 sedang berjalan, sampai 15.59" / "Kuota sesi 2 habis, sesi 3 mulai 16.00" / "Pengiriman hari ini selesai" / "Akhir pekan, kirim dimatikan". |
| F3.2 | Ringkasan: terkirim hari ini / batas, dibalas, belum dikirim / total. |
| F3.3 | Rel jadwal 10.00–22.00: blok sesi selebar durasinya, status, progres, penanda jam sekarang. Blok bisa diklik. |
| F3.4 | Detail sesi terpilih: sesi lewat → daftar terkirim + status; sesi berjalan → tombol "Kirim N pesan", mode coba, progres, hitung mundur, Stop; sesi mendatang → urutan yang akan dikirimi. |
| F3.5 | Panel chat: nama fasil, status, tabel sekolah binaan (nama, NPSN, progres, prioritas dari LK), gelembung pesan keluar & balasan terakhir, tombol "Buka di WhatsApp Web". |

### F4. Riwayat
| | Kriteria |
|---|---|
| F4.1 | Daftar hari kirim (terbaru di atas) dengan total terkirim & dibalas. |
| F4.2 | Ringkasan per sesi untuk hari terpilih. |
| F4.3 | Tabel: jam, sesi, fasil, jumlah sekolah, status, balasan terakhir. Bisa disaring per status. |
| F4.4 | "Unduh rekap (CSV)": satu baris per sekolah (NPSN, sekolah, fasil, nomor, sesi, jam, status, balasan terakhir) agar mudah dipakai mengisi LK. |

### F5. Pengaturan
Nama petugas, batas harian, izinkan akhir pekan, scan ulang QR WhatsApp, muat ulang data Broadcast, keluar dari akun Google.

### F6. Tarik Cutoff (hanya pengguna dengan fitur `cutoff`)
| | Kriteria |
|---|---|
| F6.1 | Menu "Tarik Cutoff" hanya tampil untuk pengguna berakses. |
| F6.2 | Form: pilih file (CSV/XLSX), mode (Harian M–O + H / Mingguan J–L), nomor week (sheet `WEEK n` harus ada). |
| F6.3 | Pratinjau sebelum menulis: jumlah baris file, jumlah sekolah, jumlah per prioritas, contoh 3 sekolah. |
| F6.4 | Tombol "Tulis ke WEEK n" → menulis kolom terkait + format persen + catatan waktu update di header (note). |
| F6.5 | Riwayat tarik cutoff (lokal): waktu, file, mode, week, jumlah sekolah. |
| F6.6 | Logika identik dengan `tarik.py` yang sudah diuji (±8 detik untuk 11.381 sekolah). |

## 9. Arsitektur

```
Laptop petugas
├── start.bat ──► Python (FastAPI, port 8787)
│                 ├── melayani UI Next.js (hasil static export)
│                 ├── /api/*  → Google Sheets (gspread), data lokal (SQLite)
│                 ├── Worker WhatsApp (Playwright + Chrome profil khusus)
│                 └── Tarik Cutoff (pandas)
└── Browser ──► http://localhost:8787
```

| Lapisan | Teknologi | Catatan |
|---|---|---|
| UI | **Next.js** (App Router, TypeScript), `output: 'export'` | Dibangun jadi file statis; tim tidak perlu Node.js |
| Styling | CSS Modules / Tailwind dengan token dari mockup | IBM Plex Sans, aksen `#2346A0` |
| API & server lokal | **Python 3.12, FastAPI, Uvicorn** | Satu proses melayani UI + API |
| WhatsApp | **Playwright (Python)**, `channel="chrome"`, persistent context | Memakai Chrome yang terpasang, tidak perlu unduh browser |
| Google | `google-auth-oauthlib`, `gspread` | OAuth installed app |
| Data lokal | SQLite (`%APPDATA%\LKMonitoring\data.db`) | Log kirim, status chat, pengaturan, riwayat cutoff |
| Pembaruan UI realtime | Server-Sent Events `/api/events` | Progres kirim, status WA |
| Distribusi | GitHub (publik) + GitHub Actions | Build Next → branch `release` |

### Branch
| Branch | Isi | Siapa memakai |
|---|---|---|
| `main` | Pengembangan harian | Developer |
| `stable` | Versi yang sudah dites | Merge manual dari `main` |
| `release` | Dibuat otomatis oleh GitHub Actions dari `stable`: kode Python + hasil build Next (`web/out`) | `start.bat` di laptop tim |

### Data lokal (`%APPDATA%\LKMonitoring\`)
```
credentials.json      OAuth client (dari admin)
token.json            login Google pengguna
chrome-profile/       login WhatsApp Web
data.db               SQLite
logs/app.log          log teknis (rotasi 5 × 1 MB)
```

### Skema SQLite (ringkas)
```sql
settings(key TEXT PRIMARY KEY, value TEXT)
sends(id INTEGER PK, tanggal TEXT, waktu TEXT, sesi INT, nama_fasil TEXT, nomor TEXT,
      hash_pesan TEXT, status TEXT, keterangan TEXT, coba INT)
chat_status(nomor TEXT PK, status TEXT, balasan_terakhir TEXT, waktu_balasan TEXT, dicek TEXT)
cutoff_runs(id INTEGER PK, waktu TEXT, file TEXT, mode TEXT, week TEXT, sekolah INT, ringkasan TEXT)
```

### API
| Method | Path | Fungsi |
|---|---|---|
| GET | `/api/me` | Email, nama petugas, fitur, status setup |
| POST | `/api/auth/login` · `/api/auth/logout` | Login/keluar Google |
| GET/POST | `/api/settings` | Batas harian, akhir pekan, nama petugas |
| GET | `/api/petugas` | Daftar nama + jumlah fasil dari Broadcast |
| GET | `/api/wa/status` · POST `/api/wa/connect` | Status & buka WhatsApp Web |
| GET | `/api/today` | Judul, ringkasan, blok sesi |
| GET | `/api/sessions/{n}` | Detail sesi hari ini |
| POST | `/api/send/start` (`{coba}`) · `/api/send/stop` | Mulai / hentikan kirim |
| GET | `/api/fasil/{nomor}` | Sekolah binaan + chat terakhir |
| GET | `/api/history` · `/api/history/{tanggal}` · `/api/history/{tanggal}.csv` | Riwayat & rekap |
| POST | `/api/cutoff/preview` · `/api/cutoff/write` | Tarik Cutoff (cek akses) |
| GET | `/api/events` | SSE: progres kirim, status WA |

## 10. Kebutuhan Non-Fungsional
- Windows 10/11, Google Chrome terpasang.
- Server hanya mendengar di `127.0.0.1` (tidak bisa diakses dari jaringan).
- Tidak ada rahasia di repo publik: `credentials.json`, token, ID sheet Akses disimpan lokal/konfigurasi pengguna. ID sheet Broadcast & LK boleh di repo (akses tetap dibatasi Google).
- Bahasa antarmuka Indonesia; copy mengikuti mockup.
- Responsif sampai lebar 1024 px (laptop); tidak ditargetkan untuk HP.
- Aplikasi tetap bisa dibuka offline untuk melihat Riwayat.
- Waktu memakai zona Asia/Jakarta.

## 11. Risiko
| Risiko | Mitigasi |
|---|---|
| Nomor diblokir WhatsApp | Batas harian default 40, kuota sesi, jeda acak, peringatan; koordinator mengingatkan tim |
| Tampilan WhatsApp Web berubah → selektor rusak | Selektor dikumpulkan di satu file; mode coba untuk cek cepat; update lewat `release` |
| Update rusak sampai ke tim | Hanya `stable` yang dirilis; tes mode coba sebelum merge |
| Sheet LK lambat | Bersihkan LK (kosongkan CUTOFF, hapus W1 & Copy of Template); baca hanya kolom yang perlu |
| Login Google kedaluwarsa tiap 7 hari (app OAuth mode Testing) | App mendeteksi dan membuka login ulang otomatis; email tim didaftarkan sebagai test user |

## 12. Keputusan
| Topik | Keputusan |
|---|---|
| Model | Web lokal per laptop, nomor WA masing-masing |
| Frontend / backend | Next.js (static export) + Python FastAPI |
| Repo | Publik, akun `adenyuy`, branch `main` / `stable` / `release` |
| Log | Lokal (SQLite) |
| Batas harian | Per pengguna, default 40 |
| Cek di Aplikasi Revit sebelum kirim | Dilewati |
| Akhir pekan | Pengaturan per pengguna, default mati |
| Fitur cutoff | Berdasarkan sheet Akses |
| Pengisian LK dari balasan | Ditunda ke v2 |

## 13. Pertanyaan Terbuka
1. Nama repo (usulan: `lk-monitoring`).
2. Lokasi sheet Akses: file baru milik admin, atau tab baru di file Broadcast? (usulan: file baru, privat).
3. Kirim di akhir pekan: kebijakan tim?
4. Jika Broadcast nanti memuat beberapa jenis blast (mis. progres ≥ 50% belum submit), apakah perlu memilih tab sumber? (v1: hanya tab `Broadcast`).
