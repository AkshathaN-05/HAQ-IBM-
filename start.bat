@echo off
REM Starts HAQ (API + web app) on http://localhost:8000
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (echo [HAQ] Run setup.bat first. & exit /b 1)
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
