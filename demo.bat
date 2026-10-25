@echo off
REM Creates clearly labelled DEMO accounts and a DEMO draft claim (development only).
cd /d "%~dp0backend"
.venv\Scripts\python scripts\seed_demo.py
