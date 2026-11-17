#!/bin/bash
# ============================================================
#  Instal LK Monitoring di Mac (sekali saja per laptop)
#  - Memeriksa Git (Command Line Tools), Python 3.10+, dan Google Chrome
#  - Mengunduh aplikasi ke ~/Library/Application Support/LKMonitoring/app
#  - Membuat "LK Monitoring.command" di Desktop
#
#  Cara paling mudah (tanpa peringatan Gatekeeper): buka Terminal lalu tempel
#    curl -fsSL https://raw.githubusercontent.com/adenyuy/lk-monitoring/release/install.command | bash
# ============================================================
set -u
REPO="https://github.com/adenyuy/lk-monitoring.git"
BASE="$HOME/Library/Application Support/LKMonitoring"
APP="$BASE/app"
PY_URL="https://www.python.org/ftp/python/3.12.8/python-3.12.8-macos11.pkg"

gagal() { echo; echo "  $1"; echo; read -r -p "  Tekan Enter untuk menutup..." _ </dev/tty 2>/dev/null || true; exit 1; }

echo
echo "  Instal LK Monitoring"
echo "  ===================="
echo

echo "[1/6] Memeriksa Git..."
if ! xcode-select -p >/dev/null 2>&1 || ! git --version >/dev/null 2>&1; then
  echo "      Git belum ada. Jendela pemasangan Command Line Tools akan muncul: klik Install."
  xcode-select --install >/dev/null 2>&1 || true
  gagal "Setelah pemasangan Command Line Tools selesai, jalankan pemasang ini lagi."
fi
echo "      OK"

echo "[2/6] Memeriksa Python 3.10 atau lebih baru..."
PY=""
for c in python3.13 python3.12 python3.11 python3.10 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  echo "      Python belum ada. Mengunduh pemasang Python 3.12..."
  curl -fsSL -o /tmp/lkm-python.pkg "$PY_URL" && open /tmp/lkm-python.pkg
  gagal "Selesaikan pemasangan Python (klik Continue sampai Close), lalu jalankan pemasang ini lagi."
fi
echo "      OK ($("$PY" --version))"

echo "[3/6] Memeriksa Google Chrome..."
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "$HOME/Applications/Google Chrome.app" ]; then
  open "https://www.google.com/chrome/"
  gagal "Google Chrome belum ada. Pasang Chrome dari halaman yang baru terbuka, lalu jalankan pemasang ini lagi."
fi
echo "      OK"

echo "[4/6] Mengunduh aplikasi..."
mkdir -p "$BASE"
if [ -d "$APP/.git" ]; then
  git -C "$APP" fetch --depth 1 -q origin release && git -C "$APP" reset -q --hard origin/release
else
  git clone -q --depth 1 -b release "$REPO" "$APP" || gagal "Aplikasi gagal diunduh. Periksa koneksi internet lalu coba lagi."
fi
[ -f "$APP/start.command" ] || gagal "Aplikasi gagal diunduh. Periksa koneksi internet lalu coba lagi."
chmod +x "$APP"/*.command
echo "      OK"

echo "[5/6] Memasang paket Python (beberapa menit)..."
[ -x "$APP/.venv/bin/python" ] || "$PY" -m venv "$APP/.venv" || gagal "Gagal membuat lingkungan Python."
"$APP/.venv/bin/python" -m pip install -q --upgrade pip
"$APP/.venv/bin/python" -m pip install -q -r "$APP/backend/requirements.txt" || gagal "Paket Python gagal dipasang. Periksa koneksi internet lalu coba lagi."
shasum -a 256 "$APP/backend/requirements.txt" | cut -d' ' -f1 > "$APP/.venv/req.sha"
echo "      OK"

echo "[6/6] Membuat pintasan di Desktop..."
PINTAS="$HOME/Desktop/LK Monitoring.command"
cat > "$PINTAS" <<EOF
#!/bin/bash
exec "$APP/start.command"
EOF
chmod +x "$PINTAS"
xattr -d com.apple.quarantine "$PINTAS" "$APP"/*.command >/dev/null 2>&1 || true
echo "      OK"

echo
echo "  Selesai. Aplikasi akan dibuka di browser."
echo "  Selanjutnya cukup klik dua kali \"LK Monitoring\" di Desktop."
echo
exec "$APP/start.command"
