# Using IBM Bob on HAQ — guided sessions

## Read this first (honesty note)

HAQ's code in this folder was written and tested by Claude (an AI assistant made by Anthropic) on 25 October 2026, **not by IBM Bob**. IBM Bob had not been used on this project when it was handed over.

So that your report can truthfully say how IBM Bob helped, **use Bob for real on this project** with the sessions below, keep what it produces, and record it in `IBM_BOB_USAGE.md`. Only claim in your report what Bob actually did in these sessions.

`.bobignore` already excludes `.env` and `backend/data/` so Bob never reads secrets or private evidence.

Bob's documented modes: **Ask** (read-only explanations), **Plan** (a plan without code), **Code** (reads, writes and tests), **Advanced** (Code + MCP tools), **Orchestrator** (switches modes for multi-step work), plus **code review** (`/review` or the Review Panel) and **Bob Shell** in the terminal.

## Setup (5 minutes)

1. Open IBM Bob → **File → Open Folder** → `Documents\HAQ`.
2. Open a terminal in Bob and run `setup.bat` (first time only), then `test.bat`. Note the result in the log.
3. Keep `start.bat` running in a second terminal while you work.

## Session 1 — Understand the system (Ask mode) · ~15 min

Paste each prompt, read the answer, and note anything Bob explained that helped you.

1. `Explain the architecture of this repository. How does a request from the React app reach the database, and where is authorisation enforced?`
2. `Walk me through backend/app/claim_state.py. Which actions can an employer take, and why can't an employer resolve a claim on their own?`
3. `Explain how backend/app/ai/drafting.py stops the AI from inventing money amounts. What happens if the model's answer is rejected?`
4. `In backend/app/evidence_files.py, how is an uploaded file validated before it is stored? What attacks does this protect against?`

**Record:** which explanation was most useful, and anything Bob got wrong.

## Session 2 — Code review (/review) · ~15 min

1. Run `/review` (or the Review Panel) on `backend/app/routes_worker.py` and `backend/app/routes_employer.py`.
2. Ask: `Review backend/app/security.py and backend/app/routes_auth.py for security weaknesses. Rank findings by severity.`

**Record:** each finding, whether you agree, and whether you fixed it. If you fix something, run `test.bat` afterwards and record the result.

## Session 3 — Add tests with Bob (Code mode) · ~20 min

Pick one (all are real gaps listed in KNOWN_LIMITATIONS.md / TESTING_REPORT.md):

- `Add a pytest test in backend/tests that checks an expired settlement offer cannot be accepted (see decide_settlement in routes_worker.py). Run the tests.`
- `Add a Vitest test for frontend/src/pages/NewClaim.jsx that checks the Send button stays disabled until the confirmation checkbox is ticked.`
- `Add a pytest test that a worker cannot share an evidence file from another worker's claim when submitting.`

Accept the change only if `test.bat` still passes. **Record:** the test name, file, and pass/fail.

## Session 4 — Plan an improvement (Plan mode) · ~15 min

Ask for a plan (no code) for one item, and save Bob's plan into the log:

- `Plan how to move uploaded evidence from the local private_files folder to IBM Cloud Object Storage, keeping downloads authorised and files private. List files to change, edge cases and tests.`
- `Plan how to add server-side speech-to-text for uploaded voice notes using IBM Watson Speech to Text, in Indian languages, with a safe fallback.`
- `Plan replacing SQLite with IBM Db2 or PostgreSQL. Which SQL in backend/migrations and backend/app needs to change?`

## Session 5 (optional) — Implement a small improvement (Code mode)

Examples: translate the remaining screens in `frontend/src/i18n_more.js` for one language you know (then ask a native speaker to check them), or show file sizes in the employer view. Run `test.bat` and record the result.

## After the sessions

Fill in `IBM_BOB_USAGE.md` and commit it to the repository.
