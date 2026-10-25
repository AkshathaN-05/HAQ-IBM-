#!/usr/bin/env bash
# One-time setup for macOS/Linux. Needs Python 3.10+ and Node.js 18+.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
(cd frontend && npm install --no-fund && npm run build)
echo "Setup finished. Start with: cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000"
