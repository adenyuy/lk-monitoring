@echo off
rem ============================================================
rem  Buka LK Monitoring
rem  1. Bila server sudah jalan: langsung buka browser
rem  2. Perbarui aplikasi dari branch release (dilewati bila offline)
rem  3. Pasang ulang paket Python bila requirements.txt berubah
rem  4. Jalankan server di latar (tanpa jendela) lalu buka browser
rem ============================================================
setlocal EnableExtensions

rem File ini ikut diperbarui oleh git. Jalankan salinannya dari folder TEMP supaya
rem cmd tidak membaca file yang sedang berubah.
if /i not "%~1"=="--salinan" (
    copy /y "%~f0" "%TEMP%\lkm_start.bat" >nul
    "%TEMP%\lkm_start.bat" --salinan "%~dp0"
    exit /b
)

set "APP=%~2"
if "%APP:~-1%"=="\" set "APP=%APP:~0,-1%"
cd /d "%APP%"
title LK Monitoring
if not defined LKM_PORT set "LKM_PORT=8787"
set "URL=http://127.0.0.1:%LKM_PORT%/"

call :hidup
if not errorlevel 1 (
    if not defined LKM_TANPA_BROWSER start "" "%URL%"
    exit /b 0
)

echo Memeriksa pembaruan...
set "GIT="
for /f "delims=" %%i in ('where git 2^>nul') do if not defined GIT set "GIT=%%i"
if not defined GIT if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if defined GIT if exist ".git" (
    "%GIT%" fetch --depth 1 -q origin release 2>nul && "%GIT%" reset -q --hard origin/release
)

set "HASH="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "backend\requirements.txt" SHA256') do if not defined HASH set "HASH=%%h"
set "LAMA="
if exist ".venv\req.sha" set /p LAMA=<".venv\req.sha"
if not "%HASH%"=="%LAMA%" (
    echo Memasang paket baru...
    ".venv\Scripts\python.exe" -m pip install -q -r "backend\requirements.txt" && > ".venv\req.sha" echo %HASH%
)

echo Menjalankan aplikasi...
start "" /d "%APP%\backend" "%APP%\.venv\Scripts\pythonw.exe" run.py

rem Tunggu sampai server siap (maks 40 detik)
for /l %%n in (1,1,40) do (
    call :hidup
    if not errorlevel 1 goto :buka
    ping -n 2 127.0.0.1 >nul
)
echo.
echo Aplikasi belum bisa dibuka. Lihat log: %APPDATA%\LKMonitoring\logs\server.log
pause
exit /b 1

:buka
if not defined LKM_TANPA_BROWSER start "" "%URL%"
exit /b 0

:hidup
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:%LKM_PORT%/api/health | Out-Null; exit 0 } catch { exit 1 }"
exit /b %errorlevel%
