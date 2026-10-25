# HAQ — Testing Report

All results below were run and observed on **25 October 2026** in a Linux build environment (Python 3.13 and 3.10, Node.js 22, headless Chromium). They have **not yet been re-run on the target Windows laptop** — run `test.bat` there to confirm (see the last section).

## Summary

| Check | Command | Result |
|---|---|---|
| Backend tests (Python 3.13) | `cd backend && .venv/bin/python -m pytest -q` | **60 passed** |
| Backend tests (Python 3.10) | same, in a Python 3.10.20 environment | **60 passed** |
| Backend lint | `ruff check app tests` | **All checks passed** |
| Frontend tests | `cd frontend && npm test` | **10 passed** |
| Frontend lint | `npm run lint` (ESLint + React Hooks rules) | **0 problems** |
| Production build | `npm run build` | **Built** (JS 263 KB / 81 KB gzip; CSS 15 KB) |
| Python dependency audit | `pip-audit -r requirements.txt` | **No known vulnerabilities** |
| JS dependency audit | `npm audit` | **0 vulnerabilities** |
| End-to-end browser journey | `python e2e/journey.py` (Playwright, Chromium, 390×844 phone viewport) | **14 / 14 steps passed** |
| Clean-environment setup | fresh copy without venv/node_modules/data → `./setup.sh` → start → `/api/health` → `seed_demo.py` | **Worked**: health `ok`, page served, demo seeded |
| Dev-server proxy | `npx vite` → `GET :5173/api/health` | **Proxied correctly** |

The first e2e run found a real bug: after sending, the "Your claim was sent" confirmation did not appear because two navigations raced. It was fixed in `NewClaim.jsx` (navigate only after the server confirms) and the journey re-run green. Dependency audits initially reported vulnerabilities in Starlette, PyJWT, pypdf, python-multipart, React Router and Vitest; all were upgraded and the full test suite re-run.

## End-to-end journey (real browser)

Each step drives the actual UI against the running server. Screenshots are in `docs/screenshots/`.

| # | Step | Screenshot |
|---|---|---|
| 1 | Landing page loads | `01-landing.png` |
| 2 | Worker registers, reads the dev-mode code, verifies email | `02-worker-home.png` |
| 3 | Worker describes the problem; "saved on this phone only" shown | `03-describe.png` |
| 4 | Uploads TXT + PDF + MP3 together; TXT and PDF text extracted; MP3 honestly marked "not read automatically" | `04-evidence.png` |
| 5 | Fills key details; summary and automatic checks shown | `05-details.png`, `06-summary-checks.png` |
| 6 | Letter prepared, labelled "template (no AI)", edited by the worker | `07-letter.png` |
| 7 | Send disabled until confirmation ticked; only one file shared; claim sent | `08-send.png`, `09-claim-sent.png` |
| 8 | Worker credentials on employer sign-in → clear "worker account" message | `10-wrong-portal.png` |
| 9 | Employer registers + verifies; sees exactly **one** (the shared) file | `11-employer-claim.png` |
| 10 | Employer acknowledges, asks a question; worker replies (status → under review) | — |
| 11 | Employer offers ₹6,000; worker accepts | `12-offer-received.png` |
| 12 | Employer records payment → claim stays "payment pending"; worker confirms → **Resolved** | `13-…`, `14-resolved.png` |
| 13 | Wage calculator (800 × 18 − 8,000 = ₹6,400); Hindi, Tamil and Urdu (right-to-left) screens | `15-wage-calculator.png`, `16-hindi-home.png`, `18-tamil-home.png`, `19-urdu-home.png` |
| 14 | No JavaScript errors; the only HTTP error was the deliberate wrong-portal 403 | — |

## Backend test inventory (60)

**Accounts & sessions (12):** server-assigned roles · duplicate email & weak password · login + wrong portal + identical errors for unknown email/bad password · email verification + resend reports "logged" honestly · code lock-out after 5 attempts · password reset revokes old sessions + same answer for unknown emails · sign-out everywhere · expired token, forged token, and relabelled-role token all rejected · portal enforcement on endpoints · profile update can't change role · unverified employer blocked · login rate limit.

**Claims & evidence (17):** text-only claim → draft → submit (email delivery recorded as "logged", not "sent") · unknowns marked "[not provided]" · letter headings in all 13 languages with the worker's words kept exactly · "another language" kept word-for-word and invalid codes rejected · submit needs confirmation, idempotency key, verified email, employer email · idempotent submit (one event, one notification) · claim locked after sending · input validation (amount, email, date, unknown work record) · linked work record uses deterministic calculation and flags a mismatch · TXT/PDF/DOCX/MP3 together with extraction, amounts, dates, labels E1–E4 and SHA-256 · OCR on a generated PNG (Tesseract) · upload validation (exe, renamed file, empty, oversized, path traversal, no partial files) · duplicate detection + text correction · injection-like text flagged · evidence/history/claims cannot be deleted or altered · export escapes HTML · withdraw draft.

**Employer & authorisation (11):** employer sees only addressed claims and shared evidence; other employer and guessed IDs get 404 · drafts invisible · unverified employer with matching email blocked · worker isolation (view, edit, download, export, list) · employer cannot modify claim/evidence or accept own offer · full resolution flow incl. attachments, idempotent offer, receipt, notifications · partial payment then dispute · reject offer, invalid transitions, zero offer, future payment date · withdrawn claim is read-only · share more after sending but never un-share · employer registering later sees the claim.

**AI & reliability (16):** watsonx call shape (IAM token, `/ml/v1/text/chat`, Granite model ID, project ID, prompt-injection guard text) with token caching — **using a mocked HTTP transport** · invented amount rejected → template fallback · invented date / non-existent evidence label / non-JSON rejected · watsonx 401 and timeout handled · watsonx needs credentials · Ollama Granite call shape + "model not installed" message (mocked) · evidence wrapped as data · production needs `SECRET_KEY` · invalid env values · invalid AI provider · migrations idempotent · database unavailable → 503 + degraded health · consistent error shape · security headers · dev outbox hidden outside development · empty `.env` values fall back to defaults.

**Wages & work records (4):** brief example (₹6,400) · excess payment and half-up rounding · invalid inputs · work-record CRUD and isolation.

## Frontend test inventory (10)

Translation with variables and English fallback · every language only uses known keys · all 13 languages cover the main screens and every claim status, Urdu is right-to-left · API client sends bearer token and parses errors · network failure becomes a friendly message · Indian rupee formatting · checks shown without fraud language · wrong-portal message shown and no session started · worker registration never sends a role · wage calculator shows server result and disclaimer.

## Feature checklist

✅ implemented and tested · 🟡 implemented, tested only with mocks or partially · ⬜ not implemented

| Feature | Status | Evidence |
|---|---|---|
| Worker + employer registration, one identity system, server-assigned roles | ✅ | test_auth.py, e2e 2/9 |
| Email verification, resend, password reset, sign out everywhere | ✅ | test_auth.py |
| Real email delivery (SMTP) | 🟡 | Code path exists; not tested against a mail server |
| Wrong-portal handling | ✅ | test_auth.py, e2e 8 |
| Guided 6-step claim flow | ✅ | e2e 3–7 |
| Voice typing (browser speech recognition) | 🟡 | Implemented; cannot be automated in headless Chrome — test manually in Chrome with a microphone |
| Local draft on the device + delete control + leave warning | ✅ | e2e 3 (indicator) |
| Multi-file mixed evidence, progress, retry, size/type/content validation | ✅ | test_claims.py, e2e 4 |
| Text extraction: TXT, PDF text, DOCX | ✅ | test_mixed_evidence_types_and_extraction |
| OCR for images | 🟡 | Tested where Tesseract is installed; on a laptop without Tesseract the app says OCR is unavailable |
| OCR for scanned PDFs | ⬜ | Reported as "no text layer" |
| Audio/video transcription on the server | ⬜ | Stored and labelled "not transcribed" |
| Worker can correct extracted text | ✅ | test_duplicate_detection_and_text_correction |
| Rule-based checks (5 classifications) | ✅ | test_claims.py |
| Complaint letter headings in 13 languages; any other language kept word-for-word | ✅ | test_claims.py, e2e 6 |
| Complaint narrative by IBM Granite via watsonx.ai | 🟡 | Implemented; tested with mocked HTTP only (no credentials available) |
| Complaint narrative by IBM Granite via Ollama | 🟡 | Implemented; tested with mocked HTTP only |
| AI output validation and fallback | ✅ | test_ai_and_reliability.py |
| Translation of the letter for the employer | ⬜ | Not implemented |
| Explicit confirmation + idempotent submission | ✅ | test_submit_is_idempotent, e2e 7 |
| Choose which files to share; share more later | ✅ | test_employer_and_authz.py, e2e 7/9 |
| Employer inbox, acknowledge, reply, question, attachments | ✅ | test_full_resolution_flow, e2e 9–10 |
| Settlement offers with expiry, accept/reject | ✅ | test_employer_and_authz.py, e2e 11 |
| Payments with receipt; worker confirm/dispute; partial resolution | ✅ | test_full_resolution_flow, test_partial_payment_and_dispute, e2e 12 |
| State machine enforced on the server | ✅ | test_reject_offer_and_invalid_transitions |
| Timeline, in-app notifications (de-duplicated), audit log | ✅ | test_submit_is_idempotent, test_full_resolution_flow |
| Email notifications for claim updates | ⬜ | Only the initial "you have a claim" invite email |
| Printable claim record | ✅ | test_export_is_escaped |
| Wage calculator (6 pay types) + work records | ✅ | test_wages_engagements.py, e2e 13 |
| UI in 13 Indian languages (Urdu right-to-left) | ✅ / 🟡 | English + Hindi complete; 11 others cover main worker screens and statuses; native review needed; e2e screenshots 16, 18, 19 |
| Demo data clearly labelled | ✅ | seed_demo.py (all names prefixed "DEMO") |
| Container image for IBM Cloud Code Engine | 🟡 | Dockerfile written; **not built or deployed** (no Docker or IBM Cloud access here) |

## Re-running on your Windows laptop

```
setup.bat      (one time)
test.bat       backend tests + lint, frontend lint + tests + build
start.bat      then open http://localhost:8000
```

Expect `test_ocr_on_image_if_tesseract_installed` to be **skipped** on Windows unless Tesseract is installed — that is correct behaviour, not a failure. The Playwright journey needs `pip install playwright` and `python -m playwright install chromium`, then `python e2e\journey.py` while `start.bat` is running.
