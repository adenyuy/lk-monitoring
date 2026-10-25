# Alur Sistem – LK Monitoring

Pelengkap [PRD.md](PRD.md) dan [TASKS.md](TASKS.md). Diagram memakai Mermaid (tampil di GitHub, atau di VS Code dengan ekstensi *Markdown Preview Mermaid Support*).

---

## 1. Arsitektur

```mermaid
flowchart LR
    subgraph GitHub["GitHub (repo publik)"]
        MAIN["main"] -- "merge setelah dites" --> STABLE["stable"]
        STABLE -- "GitHub Actions:<br/>build Next.js" --> REL["release<br/>(Python + web/out)"]
    end

    subgraph Google["Google Sheets"]
        BC["Broadcast"]
        LK["LK WEEK n"]
        AK["Akses (privat, admin)"]
    end

    subgraph Laptop["Laptop petugas"]
        START["start.bat"] -- "git pull release" --> REL
        START --> API["Python FastAPI :8787<br/>UI statis + /api"]
        UI["Browser<br/>localhost:8787"] <-- "HTTP + SSE" --> API
        API <--> DB[("%APPDATA%\\LKMonitoring<br/>data.db, token, profil Chrome")]
        API --> PW["Playwright<br/>Chrome profil khusus"]
    end

    API -- "baca" --> BC
    API -- "baca / tulis (cutoff)" --> LK
    API -- "baca" --> AK
    PW -- "WhatsApp Web" --> WA(("WhatsApp<br/>nomor petugas"))
    WA --> F["Fasilitator"]
    FILE["File cutoff<br/>CSV / Excel"] -. "dipilih pengguna" .-> API
```

- Tidak ada server pusat; setiap laptop menjalankan app sendiri.
- Tim hanya butuh **Git + Python + Chrome**. Node.js hanya dipakai developer dan GitHub Actions.
- Data pengguna di luar folder repo, sehingga update tidak menyentuhnya.

---

## 2. Siklus Rilis

```mermaid
flowchart LR
    A["Kerja di main"] --> B["Tes lokal<br/>(dev.bat, mode coba)"]
    B --> C["Merge main → stable"]
    C --> D["Actions: npm build,<br/>push ke release, tag versi"]
    D --> E["Laptop tim dapat versi baru<br/>saat start.bat dibuka"]
```

---

## 3. Instalasi & Membuka App

```mermaid
flowchart TD
    subgraph Sekali["Sekali per laptop: install.bat"]
        I1{"Git & Python ada?"} -- Tidak --> I2["winget install (scope user)"] --> I3
        I1 -- Ya --> I3["git clone -b release"]
        I3 --> I4["venv + pip install"] --> I5["Shortcut Desktop 'LK Monitoring'"]
    end

    subgraph Harian["Setiap dibuka: start.bat"]
        S1{"Online?"} -- Ya --> S2["git fetch + reset ke origin/release"] --> S3
        S1 -- Tidak --> S3{"requirements.txt berubah?"}
        S3 -- Ya --> S4["pip install"] --> S5
        S3 -- Tidak --> S5{"App sudah jalan<br/>(port 8787)?"}
        S5 -- Ya --> S7["Buka browser saja"]
        S5 -- Tidak --> S6["Jalankan FastAPI"] --> S7
    end
```

---

## 4. Setup di Dalam App (sekali, bisa diulang dari Pengaturan)

```mermaid
flowchart TD
    A["Buka app"] --> B{"credentials.json ada?"}
    B -- Tidak --> B1["Pilih file credentials.json<br/>(dari admin)"] --> C
    B -- Ya --> C{"Sudah login Google?"}
    C -- Tidak --> C1["Masuk dengan Google"] --> D
    C -- Ya --> D{"Email ada di sheet Akses?"}
    D -- Tidak --> X["Akunmu belum terdaftar.<br/>Hubungi admin."]
    D -- Ya --> E["Konfirmasi nama petugas"]
    E --> F["Hubungkan WhatsApp (scan QR)"]
    F --> G["Atur batas harian<br/>(peringatan > 40 dan > 50)"]
    G --> H["Layar Hari ini"]
```

---

## 5. Layar Hari ini

```mermaid
flowchart TD
    A["Hari ini"] --> B["Judul kondisi + ringkasan<br/>+ rel jadwal 10.00–22.00"]
    B --> C{"Klik blok sesi"}
    C -- "Sesi lewat" --> D["Daftar terkirim + status"]
    C -- "Sesi berjalan" --> E["Tombol 'Kirim N pesan'<br/>+ mode coba"]
    C -- "Sesi mendatang" --> F["Urutan yang akan dikirimi"]
    D --> G["Klik fasil → panel chat:<br/>sekolah binaan + pesan + balasan"]
    E --> G
    F --> G
    E --> H["Proses kirim (alur 6)"]
```

Judul kondisi:

| Kondisi | Judul | Tombol kirim |
|---|---|---|
| Di dalam sesi, ada kuota | Sesi 2 sedang berjalan, sampai 15.59 | Kirim N pesan |
| Kuota sesi habis | Kuota sesi 2 habis, sesi 3 mulai 16.00 | Nonaktif |
| Batas harian tercapai / lewat 22.00 | Pengiriman hari ini selesai | Nonaktif |
| Sebelum 10.00 | Sesi 1 mulai 10.00 | Nonaktif |
| Sabtu/Minggu (tidak diizinkan) | Akhir pekan, kirim dimatikan | Nonaktif |

---

## 6. Proses Kirim Satu Sesi

```mermaid
flowchart TD
    S["Kirim N pesan"] --> Q["Ambil antrean: milik petugas,<br/>belum terkirim (nomor + hash pesan),<br/>urut sesuai sheet"]
    Q --> K{"Kuota efektif > 0<br/>dan antrean ada?"}
    K -- Tidak --> END["Selesai sesi → ringkasan"]
    K -- Ya --> STOP{"Stop ditekan?"}
    STOP -- Ya --> END
    STOP -- Tidak --> V{"Nomor & pesan valid,<br/>tidak dobel?"}
    V -- Tidak --> SKIP["Catat Dilewati + alasan"] --> K
    V -- Ya --> OPEN["Buka chat:<br/>web.whatsapp.com/send?phone=…&text=…"]
    OPEN --> CHK{"Halaman siap?"}
    CHK -- "Logout / minta QR" --> HALT["BERHENTI TOTAL<br/>minta scan ulang"]
    CHK -- "Nomor tidak terdaftar" --> FAIL["Catat Gagal"]
    CHK -- Ya --> MODE{"Mode coba?"}
    MODE -- Ya --> TRY["Catat Dicoba<br/>(tidak mengurangi kuota)"] --> WAIT
    MODE -- Tidak --> SEND["Tekan kirim"]
    SEND --> CONF{"Status bukan 'jam'<br/>dalam 30 dtk?"}
    CONF -- Ya --> OK["Catat Terkirim"] --> WAIT
    CONF -- Tidak --> FAIL
    FAIL --> FC{"2 gagal beruntun?"}
    FC -- Ya --> HALT2["BERHENTI TOTAL<br/>tampilkan penyebab"]
    FC -- Tidak --> WAIT["Jeda acak 45–120 dtk<br/>(SSE: hitung mundur)"] --> K
```

---

## 7. Status Fasilitator

```mermaid
stateDiagram-v2
    [*] --> Menunggu: muncul di Broadcast
    Menunggu --> Terkirim: berhasil dikirim
    Menunggu --> Gagal: gagal kirim
    Menunggu --> Dilewati: data tidak valid / dobel
    Menunggu --> Dicoba: mode coba
    Dicoba --> Menunggu
    Gagal --> Menunggu: dicoba lagi di sesi berikutnya
    Terkirim --> Dibaca: centang biru
    Terkirim --> Dibalas: ada pesan masuk
    Dibaca --> Dibalas: ada pesan masuk
    Terkirim --> Menunggu: isi pesan di Broadcast berubah
    Dibaca --> Menunggu: isi pesan di Broadcast berubah
    Dibalas --> Menunggu: isi pesan di Broadcast berubah
```

Pembaruan Dibaca/Dibalas: saat app dibuka dan tiap 15 menit (untuk kiriman 7 hari terakhir), hanya saat tidak sedang mengirim.

---

## 8. Tarik Cutoff (pengguna dengan fitur `cutoff`)

```mermaid
flowchart TD
    A["Menu Tarik Cutoff"] --> B["Pilih file cutoff (CSV/XLSX)<br/>mode Harian / Mingguan, week n"]
    B --> C["Pratinjau:<br/>baris file, sekolah, jumlah per prioritas, contoh"]
    C --> D{"Sheet WEEK n ada?"}
    D -- Tidak --> X["Buat dulu sheet WEEK n di LK"]
    D -- Ya --> E["Tulis ke WEEK n"]
    E --> F{"Mode"}
    F -- Harian --> G["M, N, O + Prioritas H"]
    F -- Mingguan --> H["J, K, L"]
    G --> I["Format persen + note waktu update<br/>+ catat riwayat lokal"]
    H --> I
```

Pemetaan prioritas: P1 belum submit · P2 sudah submit, progres < 50% · P3 sudah submit, ≥ 50%, belum reviu · Selesai.

---

## 9. Pergantian Hari

```mermaid
flowchart LR
    A["Tanggal berganti"] --> B["Hitungan harian & kuota sesi = 0"]
    A --> C["Riwayat kemarin tetap tersimpan"]
    A --> D["Antrean lanjut dari yang belum terkirim"]
    E["Broadcast diperbarui<br/>(pesan berubah)"] --> F["Fasil terkait masuk antrean lagi"]
```
