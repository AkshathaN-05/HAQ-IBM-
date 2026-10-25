@echo off
REM One-time setup for HAQ on Windows. Needs Python 3.10+ and Node.js 18+.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul || (echo [HAQ] Python 3.10 or newer is required: https://www.python.org/downloads/ & exit /b 1)
where npm >nul 2>nul || (echo [HAQ] Node.js 18 or newer is required: https://nodejs.org/ & exit /b 1)

echo [HAQ] Creating Python environment...
cd backend
if not exist .venv %PY% -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements-dev.txt || exit /b 1
if not exist .env copy .env.example .env >nul

echo [HAQ] Installing and building the web app...
cd ..\frontend
call npm install --no-fund || exit /b 1
call npm run build || exit /b 1
cd ..
echo.
echo [HAQ] Setup finished. Run start.bat to open HAQ.
echo [HAQ] Optional: run demo.bat to create labelled DEMO accounts.
