# LK Monitoring – Revitalisasi SD 2026

Aplikasi web lokal untuk tim monitoring Direktorat SD:

- **WA Blast** – kirim pesan WhatsApp ke fasilitator per sesi dari nomor masing-masing petugas, dengan kuota sesi, batas harian, rekap, dan tampilan chat fasilitator.
- **Tarik Cutoff** – pindahkan data file cutoff (CSV/Excel) ke sheet `WEEK n` di LK Monitoring beserta prioritas sekolah.

Status: **dalam pengembangan (v1)**.

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
scripts/   install.bat, start.bat, dev.bat
legacy/    tarik.py – versi skrip yang sudah dipakai, rujukan untuk porting (Fase 8)
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
