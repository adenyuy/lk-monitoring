#!/bin/bash
# ============================================================
#  Buka LK Monitoring (Mac)
#  1. Bila server sudah jalan: langsung buka browser
#  2. Perbarui aplikasi dari branch release (dilewati bila offline)
#  3. Pasang ulang paket Python bila requirements.txt berubah
#  4. Jalankan server di latar lalu buka browser
# ============================================================
set -u

# File ini ikut diperbarui oleh git. Jalankan salinannya supaya bash tidak membaca file yang sedang berubah.
if [ "${1:-}" != "--salinan" ]; then
  APP="$(cd "$(dirname "$0")" && pwd)"
  cp "$0" /tmp/lkm_start.command && chmod +x /tmp/lkm_start.command
  exec /tmp/lkm_start.command --salinan "$APP"
fi
APP="$2"
cd "$APP" || exit 1
PORT="${LKM_PORT:-8787}"
URL="http://127.0.0.1:$PORT/"
LOG="$HOME/Library/Application Support/LKMonitoring/logs"

hidup() { curl -fs -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; }
buka() { [ -n "${LKM_TANPA_BROWSER:-}" ] || open "$URL"; }

if hidup; then buka; exit 0; fi

echo "Memeriksa pembaruan..."
if [ -d .git ]; then
  git fetch --depth 1 -q origin release 2>/dev/null && git reset -q --hard origin/release
  chmod +x ./*.command 2>/dev/null
fi

HASH="$(shasum -a 256 backend/requirements.txt | cut -d' ' -f1)"
LAMA="$(cat .venv/req.sha 2>/dev/null || true)"
if [ "$HASH" != "$LAMA" ]; then
  echo "Memasang paket baru..."
  .venv/bin/python -m pip install -q -r backend/requirements.txt && echo "$HASH" > .venv/req.sha
fi

echo "Menjalankan aplikasi..."
mkdir -p "$LOG"
(cd backend && nohup ../.venv/bin/python run.py >> "$LOG/server.log" 2>&1 &)

# Tunggu sampai server siap (maks 40 detik)
for _ in $(seq 1 40); do
  if hidup; then
    buka
    echo "LK Monitoring sudah berjalan. Jendela ini boleh ditutup."
    exit 0
  fi
  sleep 1
done
echo
echo "Aplikasi belum bisa dibuka. Lihat log: $LOG/server.log"
read -r -p "Tekan Enter untuk menutup..." _ </dev/tty 2>/dev/null || true
exit 1
