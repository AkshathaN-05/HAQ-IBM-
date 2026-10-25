@echo off
REM Runs backend tests, frontend tests, lint and a production build.
cd /d "%~dp0backend"
.venv\Scripts\python -m pytest -q || exit /b 1
.venv\Scripts\python -m ruff check app tests || exit /b 1
cd ..\frontend
call npm run lint || exit /b 1
call npm test || exit /b 1
call npm run build || exit /b 1
echo [HAQ] All checks passed.
