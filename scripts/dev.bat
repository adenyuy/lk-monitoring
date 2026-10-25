@echo off
rem Mode developer: backend (auto-reload) di :8787 + Next.js dev server di :3000.
rem Buka http://localhost:3000 untuk develop tampilan.
setlocal
cd /d "%~dp0.."

if not exist backend\.venv (
    echo Membuat virtualenv backend...
    py -3 -m venv backend\.venv || python -m venv backend\.venv
    backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
)
if not exist web\node_modules (
    echo Menginstal paket web...
    pushd web & call npm install & popd
)

start "LKM backend" cmd /k "cd /d %CD%\backend && .venv\Scripts\python run.py --reload"
set NEXT_PUBLIC_API_BASE=http://127.0.0.1:8787
cd web
call npm run dev
