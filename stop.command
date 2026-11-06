#!/bin/bash
# Matikan server LK Monitoring yang berjalan di latar (port 8787). Jendela WhatsApp milik aplikasi ikut tertutup.
PORT="${LKM_PORT:-8787}"
PID="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null)"
if [ -n "$PID" ]; then
  kill $PID 2>/dev/null; sleep 2; kill -9 $PID 2>/dev/null
  echo "LK Monitoring sudah dimatikan."
else
  echo "LK Monitoring tidak sedang berjalan."
fi
sleep 2
