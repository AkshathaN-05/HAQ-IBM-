# HAQ — Security Notes

## What is in place (and tested)

| Area | Control | Where | Test |
|---|---|---|---|
| Identity | One account system for both roles; role set by the registration endpoint and stored in the DB; any `role` in a request body is ignored | `routes_auth.py` | `test_register_worker_and_employer_roles_are_server_assigned`, `test_profile_update_cannot_change_role` |
| Role escalation | Role is re-read from the DB on every request; a token whose role claim is edited (even with a valid signature) gains nothing | `deps.py` | `test_expired_and_tampered_tokens` |
| Wrong portal | Login checks the requested portal against the stored role (403 with a clear message); every endpoint checks role | `routes_auth.py`, `deps.py` | `test_login_and_wrong_portal`, `test_portal_enforcement_on_endpoints` |
| Passwords | scrypt (N=2^14, r=8, p=1) with random salt; min 8 chars, letters + numbers; constant-time compare; dummy hash for unknown emails | `security.py` | `test_duplicate_email_and_weak_password` |
| Sessions | HS256 JWT with expiry, issuer and `token_version`; sign-out-everywhere and password reset revoke all tokens | `security.py` | `test_logout_all_invalidates_tokens`, `test_password_reset_signs_out_old_sessions` |
| Codes | 6-digit codes stored as HMAC hashes, 30-min expiry, 5 attempts, older codes invalidated | `routes_auth.py` | `test_verification_code_locks_after_too_many_attempts` |
| Account discovery | Forgot-password gives the same answer for any email; login gives the same error for unknown email and bad password | `routes_auth.py` | `test_password_reset_signs_out_old_sessions`, `test_login_and_wrong_portal` |
| Rate limits | Register, login (per IP and per email), verify, resend, forgot/reset, uploads, drafting, messages, wage calculator | `security.py` | `test_rate_limit_on_login` |
| Data isolation | Worker queries always filter by owner; employer queries by verified email + submitted; 404 for anything not yours | `claims_service.py`, `routes_common.py` | `test_worker_isolation`, `test_employer_sees_only_addressed_claims_and_shared_evidence` |
| Employer limits | Cannot edit claims, complaint or evidence; cannot accept own offer or confirm own payment; payment never auto-resolves | `claim_state.py`, routes | `test_employer_cannot_modify_claim_or_evidence`, `test_full_resolution_flow` |
| Uploads | Extension allow-list, magic-byte check, size limits (checked while streaming and via Content-Length), empty-file check, random storage names, original name never used as a path, partial files cleaned up, max 30 files per claim | `evidence_files.py` | `test_upload_validation` |
| Downloads | Authorisation on every request, `Content-Disposition: attachment`, `nosniff`, sandbox CSP, `no-store` | `routes_common.py` | `test_employer_sees_only...`, `test_worker_isolation` |
| Evidence integrity | SHA-256 recorded; DB triggers block deleting evidence, claims and history and changing original file metadata | `migrations/001_initial.sql` | `test_evidence_and_history_cannot_be_deleted` |
| AI safety | Evidence wrapped as data; model output must be JSON and may not contain amounts/dates/evidence labels that aren't in the worker's own data; safe fallback; arithmetic never done by AI | `ai/drafting.py` | `test_ai_invented_amount_is_rejected_and_template_used`, `test_ai_invented_date_and_evidence_label_rejected`, `test_prompt_wraps_evidence_as_data` |
| Prompt-injection signal | Evidence containing instruction-like text is flagged for review | `evidence_files.py`, `checks.py` | `test_injection_text_in_evidence_is_flagged` |
| Secrets | Read from environment / `.env` (git-ignored); production refuses to start without a ≥32-char `SECRET_KEY`; watsonx API key stays on the server; no secrets in the frontend | `config.py` | `test_production_requires_secret_key` |
| Output encoding | React escapes UI text; the HTML export escapes every value and sets a strict CSP | `routes_common.py` | `test_export_is_escaped` |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (mic only for self), `Cache-Control: no-store` on API | `main.py` | `test_security_headers` |
| Errors | Unhandled errors return a generic message; details go to the server log by exception type only | `errors.py` | `test_errors_have_consistent_shape` |
| Emails | Never contain claim details — only codes or "sign in to read it" | `routes_worker.py`, `routes_auth.py` | — |
| Dependencies | `pip-audit` and `npm audit` run on 25 Oct 2026: **no known vulnerabilities** after upgrading FastAPI/Starlette, PyJWT, pypdf, python-multipart, React Router and Vitest | — | see TESTING_REPORT.md |
| Bob | `.bobignore` excludes `.env` and `backend/data/` so IBM Bob does not read secrets or private evidence | `.bobignore` | — |

## Known gaps (be honest about these in a presentation)

- **No malware scanning.** Files are validated strictly and never executed or served inline, but they are not virus-scanned. Add ClamAV or a cloud scanning service before real use.
- **Rate limiting is in-memory**, so it resets on restart and is per process. Use a shared store (e.g. Redis) for multi-instance deployments.
- **The session token is in `sessionStorage`.** That is cleared when the tab closes and never sent automatically (no CSRF), but a successful XSS could read it. An HttpOnly cookie + CSRF token design would be stronger.
- **Files are not encrypted at rest** by the app. Rely on disk encryption or move to encrypted object storage (e.g. IBM Cloud Object Storage with server-side encryption).
- **Employer identity is not verified.** `employer_verification` exists but there is no process that sets it to `verified`. Email ownership is the only proof today.
- **Retention/deletion policy** is not implemented: claims and evidence are kept indefinitely (deletion is deliberately blocked to preserve the dispute record). A data-protection review (India's DPDP Act) is needed before real use.
- **Single SQLite file.** Fine for a pilot; use a managed database for production.
