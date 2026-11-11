#!/bin/bash
# Matikan SEMUA server LK Monitoring dari folder ini (termasuk server kedua yang tidak memegang port).
# Jendela WhatsApp milik aplikasi ikut tertutup.
APP="$(cd "$(dirname "$0")/.." && pwd)"
PID="$(pgrep -f "$APP.*run\.py|run\.py.*$APP" 2>/dev/null)"
PORT="${LKM_PORT:-8787}"
PID="$PID $(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null)"
PID="$(echo $PID | xargs)"
if [ -n "$PID" ]; then
  for p in $PID; do pkill -P "$p" 2>/dev/null; done
  kill $PID 2>/dev/null; sleep 2; kill -9 $PID 2>/dev/null
  echo "LK Monitoring sudah dimatikan."
else
  echo "LK Monitoring tidak sedang berjalan."
fi
sleep 2
