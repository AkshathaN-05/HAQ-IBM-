# HAQ — Deployment Guide

## 1. Run locally on Windows (tested path: setup + start)

Prerequisites: **Python 3.10+** (python.org; tick "Add python.exe to PATH") and **Node.js 18+** (nodejs.org).

```bat
cd %USERPROFILE%\Documents\HAQ
setup.bat
start.bat
```

`start.bat` opens http://localhost:8000. Stop the server with `Ctrl+C` in its window.

Optional: `demo.bat` creates two clearly labelled DEMO accounts and a DEMO draft claim.

### macOS / Linux

```bash
./setup.sh
cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000
```

### Developing the frontend with hot reload

Terminal 1: `start.bat` (API on :8000). Terminal 2: `cd frontend && npm run dev`, then open http://localhost:5173. Vite forwards `/api` to port 8000.

## 2. Database and migrations

- The database is a single SQLite file at `backend/data/haq.sqlite3` (or `$HAQ_DATA_DIR/haq.sqlite3`).
- Migrations in `backend/migrations/NNN_*.sql` are applied **automatically at start-up**, each in a transaction, and recorded in `schema_migrations`. Re-running is safe.
- Back up by stopping the server and copying the whole `data` folder (database **and** `private_files`).
- Never delete `data/` on a machine with real claims.

## 3. Turn on IBM Granite

### Option A — IBM Granite on your own laptop with Ollama (no cloud account)

```bat
ollama pull granite3.3:2b
ollama list
```

In `backend\.env`:

```
AI_PROVIDER=ollama
OLLAMA_MODEL=granite3.3:2b      (use the exact name shown by `ollama list`)
```

Restart `start.bat`. Check http://localhost:8000/api/health — `"ai": {"provider": "ollama-granite", ...}`. Then prepare a letter: the note should say "Written with help from IBM Granite (local)".

### Option B — IBM Granite on IBM watsonx.ai

1. In IBM Cloud, create a watsonx.ai project and associate a Watson Machine Learning service.
2. Create an IBM Cloud API key (Manage → Access (IAM) → API keys).
3. Copy the project ID (project → Manage → General).
4. In `backend\.env`:

```
AI_PROVIDER=watsonx
WATSONX_URL=https://us-south.ml.cloud.ibm.com   (your project's region)
WATSONX_APIKEY=<your key — never commit this>
WATSONX_PROJECT_ID=<your project id>
WATSONX_MODEL_ID=<a Granite instruct model listed in your project>
```

Restart and check `/api/health`. If the key or model is wrong, the app keeps working with the template and shows a warning; the server log says why (e.g. "IBM Cloud IAM rejected the API key").

## 4. Production settings

```
APP_ENV=production
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
EMAIL_MODE=smtp
SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=... SMTP_FROM=...
HAQ_DATA_DIR=<a persistent, backed-up, encrypted volume>
```

In production the API docs (`/api/docs`) and the dev outbox are disabled, and the app refuses to start without `SECRET_KEY`. Put HTTPS in front (a reverse proxy or the platform's TLS).

## 5. IBM Cloud Code Engine (prepared, not yet deployed)

The `Dockerfile` builds the frontend, installs Tesseract (English, Hindi, Kannada) and runs as a non-root user on port 8080.

```bash
ibmcloud login --sso
ibmcloud target -r us-south -g Default
ibmcloud ce project create --name haq
ibmcloud ce secret create --name haq-secrets --from-env-file backend/.env.production
ibmcloud ce application create --name haq --build-source . --build-strategy dockerfile \
    --env-from-secret haq-secrets --port 8080 --min-scale 1 --max-scale 1
```

These commands follow the Code Engine CLI as documented at the time of writing; confirm the flags with `ibmcloud ce application create --help`.

**Important:** Code Engine containers have no permanent disk. SQLite and uploaded files would be lost on restart. Before a real deployment, either mount persistent storage or move the database to a managed service (e.g. IBM Cloud Databases for PostgreSQL / Db2) and files to IBM Cloud Object Storage. Keep `--max-scale 1` while using SQLite and the in-memory rate limiter.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `setup.bat` says Python is required | Install Python 3.10+ and tick "Add to PATH", then open a new terminal. |
| `'npm' is not recognized` | Install Node.js LTS and open a new terminal. |
| Browser shows "Could not reach HAQ" | `start.bat` is not running, or something else uses port 8000 (`netstat -ano | findstr :8000`). |
| Port 8000 busy | Edit `start.bat` to use `--port 8001` and open that port. |
| No verification email | Expected in development: the code is shown in the yellow DEV box under "Confirm your email". |
| Images say "OCR (Tesseract) is not installed" | Install Tesseract for Windows and add it to PATH, or type the text with "Check the text we found". |
| Letter says "no AI was used" | `AI_PROVIDER` is `local`, or the AI provider failed — read the warning and `/api/health`. |
| Voice typing button missing | The browser has no speech recognition; use Chrome or Edge. |
| `database is locked` | Only one server should use a data folder at a time. |
| Start over with an empty database | Stop the server and rename `backend\data` (don't delete it if it holds real claims). |
