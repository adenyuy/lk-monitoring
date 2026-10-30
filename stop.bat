@echo off
rem Matikan server LK Monitoring yang berjalan di latar (port 8787).
rem Jendela WhatsApp milik aplikasi ikut tertutup.
if not defined LKM_PORT set "LKM_PORT=8787"
powershell -NoProfile -Command ^
  "$p = Get-NetTCPConnection -LocalPort %LKM_PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "if ($p) { $p | ForEach-Object { Stop-Process -Id $_ -Force }; Write-Host 'LK Monitoring sudah dimatikan.' } else { Write-Host 'LK Monitoring tidak sedang berjalan.' }"
ping -n 4 127.0.0.1 >nul
