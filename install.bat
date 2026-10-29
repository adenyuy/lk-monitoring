@echo off
rem ============================================================
rem  Instal LK Monitoring (sekali saja per laptop)
rem  - Memasang Git, Python 3.12, dan Google Chrome bila belum ada (lewat winget)
rem  - Mengunduh aplikasi ke %LOCALAPPDATA%\LKMonitoring\app
rem  - Membuat shortcut "LK Monitoring" di Desktop
rem ============================================================
setlocal EnableExtensions
title Instal LK Monitoring
set "REPO=https://github.com/adenyuy/lk-monitoring.git"
set "APP=%LOCALAPPDATA%\LKMonitoring\app"

echo.
echo  Instal LK Monitoring
echo  ====================
echo.

echo [1/6] Memeriksa Git...
call :cari_git
if not defined GIT (
    echo       Git belum ada, memasang lewat winget...
    winget install --id Git.Git -e --scope user --silent --accept-package-agreements --accept-source-agreements
    call :cari_git
)
if not defined GIT goto :gagal_git
echo       OK

echo [2/6] Memeriksa Python 3.12...
call :cari_python
if not defined PY (
    echo       Python belum ada, memasang lewat winget...
    winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
    call :cari_python
)
if not defined PY goto :gagal_python
echo       OK

echo [3/6] Memeriksa Google Chrome...
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if not defined CHROME (
    echo       Chrome belum ada, memasang lewat winget...
    winget install --id Google.Chrome -e --silent --accept-package-agreements --accept-source-agreements
)
echo       OK

echo [4/6] Mengunduh aplikasi...
if exist "%APP%\.git" (
    "%GIT%" -C "%APP%" fetch --depth 1 -q origin release
    "%GIT%" -C "%APP%" reset -q --hard origin/release
) else (
    if not exist "%LOCALAPPDATA%\LKMonitoring" mkdir "%LOCALAPPDATA%\LKMonitoring"
    "%GIT%" clone -q --depth 1 -b release "%REPO%" "%APP%"
)
if not exist "%APP%\start.bat" goto :gagal_unduh
echo       OK

echo [5/6] Memasang paket Python (beberapa menit)...
if not exist "%APP%\.venv\Scripts\python.exe" "%PY%" -m venv "%APP%\.venv"
"%APP%\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
"%APP%\.venv\Scripts\python.exe" -m pip install -q -r "%APP%\backend\requirements.txt"
if errorlevel 1 goto :gagal_pip
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%APP%\backend\requirements.txt" SHA256') do if not defined HASH set "HASH=%%h"
> "%APP%\.venv\req.sha" echo %HASH%
echo       OK

echo [6/6] Membuat shortcut di Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\LK Monitoring.lnk');" ^
  "$s.TargetPath='%APP%\start.bat'; $s.WorkingDirectory='%APP%'; $s.WindowStyle=7;" ^
  "$s.IconLocation='%SystemRoot%\System32\shell32.dll,13'; $s.Description='LK Monitoring'; $s.Save()"
echo       OK

echo.
echo  Selesai. Aplikasi akan dibuka di browser.
echo  Selanjutnya cukup klik dua kali "LK Monitoring" di Desktop.
echo.
call "%APP%\start.bat"
exit /b 0

rem ---------- fungsi ----------

:cari_git
set "GIT="
for /f "delims=" %%i in ('where git 2^>nul') do if not defined GIT set "GIT=%%i"
if not defined GIT if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
exit /b 0

:cari_python
set "PY="
for /f "delims=" %%i in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
exit /b 0

:gagal_git
echo.
echo  Git belum terpasang. Pasang dari https://git-scm.com/download/win lalu jalankan file ini lagi.
goto :akhir
:gagal_python
echo.
echo  Python 3.12 belum terpasang. Pasang dari https://www.python.org/downloads/ (centang "Add to PATH"),
echo  lalu jalankan file ini lagi.
goto :akhir
:gagal_unduh
echo.
echo  Aplikasi gagal diunduh. Periksa koneksi internet lalu jalankan file ini lagi.
goto :akhir
:gagal_pip
echo.
echo  Paket Python gagal dipasang. Periksa koneksi internet lalu jalankan file ini lagi.
goto :akhir
:akhir
echo.
pause
exit /b 1
