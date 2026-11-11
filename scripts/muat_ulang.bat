@echo off
rem ============================================================
rem  Terapkan perubahan kode (mode source / developer):
rem  1. Matikan semua server LK Monitoring dari folder ini
rem  2. Build ulang tampilan web (web\out)
rem  3. Jalankan server di latar lalu buka browser
rem  Pakai ini setiap habis commit / ubah kode, supaya tidak ada server lama yang tertinggal.
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0.."
set "APP=%CD%"
if not defined LKM_PORT set "LKM_PORT=8787"

echo [1/3] Mematikan server lama...
call "%APP%\scripts\stop.bat"

echo [2/3] Build ulang tampilan web...
pushd "%APP%\web"
call npm run build >"%TEMP%\lkm_build.txt" 2>&1
if errorlevel 1 (
    popd
    type "%TEMP%\lkm_build.txt"
    echo.
    echo Build web gagal. Server tidak dijalankan.
    pause
    exit /b 1
)
popd

echo [3/3] Menjalankan server...
set "PY=%APP%\backend\.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%APP%\.venv\Scripts\pythonw.exe"
start "" /d "%APP%\backend" "%PY%" run.py

for /l %%n in (1,1,40) do (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:%LKM_PORT%/api/health | Out-Null; exit 0 } catch { exit 1 }"
    if not errorlevel 1 goto :buka
    ping -n 2 127.0.0.1 >nul
)
echo Server belum bisa dibuka. Lihat log: %APPDATA%\LKMonitoring\logs\server.log
pause
exit /b 1

:buka
echo Selesai. Refresh browser dengan Ctrl+Shift+R.
start "" "http://127.0.0.1:%LKM_PORT%/"
