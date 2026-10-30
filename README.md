# LK Monitoring – Revitalisasi SD 2026

Aplikasi web lokal untuk tim monitoring Direktorat SD:

- **WA Blast** – kirim pesan WhatsApp ke fasilitator per sesi dari nomor masing-masing petugas, dengan kuota sesi, batas harian, rekap, dan tampilan chat fasilitator.
- **Tarik Cutoff** – pindahkan data file cutoff (CSV/Excel) ke sheet `WEEK n` di LK Monitoring beserta prioritas sekolah.

Status: **v1 siap pilot**. Panduan untuk tim: [docs/CARA_PAKAI.md](docs/CARA_PAKAI.md).

## Rilis ke tim

1. Gabungkan `main` ke `stable` lalu push: `git checkout stable && git merge main && git push && git checkout main`.
2. GitHub Actions ([.github/workflows/release.yml](.github/workflows/release.yml)) menjalankan tes, build tampilan, lalu memperbarui branch `release` + tag `vYYYY.MM.DD-N`.
3. Laptop tim otomatis memperbarui diri saat membuka **LK Monitoring** (`start.bat` menarik branch `release`).

Teman baru: kirim `scripts/install.bat` + `credentials.json`, daftarkan emailnya di Google Cloud (Audience → Test users) dan di sheet Akses.

## Dokumen

| Dokumen | Isi |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Kebutuhan produk, aturan bisnis, arsitektur, API |
| [docs/FLOW.md](docs/FLOW.md) | Diagram alur sistem |
| [docs/TASKS.md](docs/TASKS.md) | Daftar tugas per fase |

## Struktur

```
backend/   Python FastAPI: API, Google Sheets, WhatsApp Web (Playwright), tarik cutoff
web/       Next.js (static export) untuk tampilan
scripts/   install.bat (sekali), start.bat (buka + perbarui), stop.bat, dev.bat (developer)
docs/      PRD, alur, tugas
```

## Branch

| Branch | Isi |
|---|---|
| `main` | Pengembangan |
| `stable` | Versi yang sudah dites |
| `release` | Dibuat otomatis oleh GitHub Actions dari `stable` (dipakai laptop tim) |

## Keamanan

Repo ini publik. Jangan pernah commit `credentials.json`, `token.json`, file cutoff, atau data pengguna. Semua data pengguna disimpan di `%APPDATA%\LKMonitoring\` di luar folder repo.
