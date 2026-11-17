@echo off
rem Matikan SEMUA server LK Monitoring dari folder ini (termasuk server kedua yang tidak memegang port),
rem beserta proses anaknya. Jendela WhatsApp milik aplikasi ikut tertutup.
setlocal
set "APP=%~dp0.."
for %%i in ("%APP%") do set "APP=%%~fi"
powershell -NoProfile -Command ^
  "$app = $env:APP.ToLower();" ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($app) -and $_.CommandLine -match 'run\.py' };" ^
  "if ($p) { $p | ForEach-Object { taskkill /PID $_.ProcessId /T /F *> $null }; Write-Host ('LK Monitoring sudah dimatikan (' + @($p).Count + ' proses).') } else { Write-Host 'LK Monitoring tidak sedang berjalan.' }"
ping -n 3 127.0.0.1 >nul
