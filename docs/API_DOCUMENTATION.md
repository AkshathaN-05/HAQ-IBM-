# HAQ — API Documentation

Base path: `/api`. All requests and responses are JSON unless noted. Interactive docs are available at **`/api/docs`** when `APP_ENV` is not `production`.

**Authentication:** `Authorization: Bearer <token>` (token from register or login). The server reads the user's role from the database on every request; the token's role claim is never trusted.

**Errors** always look like:

```json
{ "error": { "code": "wrong_portal", "message": "This is a worker account. Please use the worker sign-in page.", "details": {} } }
```

Common codes: `not_signed_in` (401), `session_expired` (401), `invalid_session` (401), `wrong_portal` (403), `email_not_verified` (403), `not_found` (404 — also used when you lack access), `invalid_status` (409), `claim_locked` (409), `validation_error` (422, with `details.fields`), `rate_limited` (429), `database_unavailable` (503).

**Idempotency:** `POST /claims/{id}/submit` requires an `Idempotency-Key` header. Repeating the same key returns the same result without sending twice. Employer offers and payments accept an optional `Idempotency-Key`.

## Accounts — `/api/auth`

| Method & path | Who | Body | Notes |
|---|---|---|---|
| `POST /auth/register/worker` | anyone | `email, password, display_name, phone?, preferred_language?` | Creates a **worker**. Returns `{token, user, verification_email}`; `verification_email` is `logged`, `sent` or `failed` — the real delivery outcome. |
| `POST /auth/register/employer` | anyone | same + `business_name?` | Creates an **employer** (`employer_verification: "unverified"`). |
| `POST /auth/login` | anyone | `email, password, portal` | `portal` must match the account role, otherwise 403 `wrong_portal`. |
| `GET /auth/me` | signed in | — | Current user. |
| `PATCH /auth/me` | signed in | `display_name?, phone?, preferred_language?, business_name?` | Role cannot be changed. |
| `POST /auth/verify-email` | signed in | `code` (6 digits) | 5 attempts per code, 30-minute expiry. |
| `POST /auth/resend-verification` | signed in | — | Rate-limited. |
| `POST /auth/forgot-password` | anyone | `email` | Same response whether or not the account exists. |
| `POST /auth/reset-password` | anyone | `email, code, new_password` | Signs out all existing sessions. |
| `POST /auth/logout-all` | signed in | — | Revokes every token for this user. |

## Wage calculator and work records

| Method & path | Who | Notes |
|---|---|---|
| `POST /wage-calculation` | anyone | `pay_type` (daily/hourly/weekly/monthly/piece/task), `rate`, `units`, `payments_received`. Returns `expected_wages`, `payments_received`, `potential_outstanding`, `excess_payment`, `formula`, `disclaimer`. Decimal arithmetic, 2 dp, half-up. |
| `GET /worker/engagements?limit&offset` | worker | Own records only, each with `calculation`. |
| `POST /worker/engagements` | worker | `employer_name, work_type, pay_type, rate, units, payments_received, start_date?, end_date?, notes?` |
| `PUT /worker/engagements/{id}` | worker | Full update of an own record. |

## Worker claims

| Method & path | Notes |
|---|---|
| `GET /claims?limit&offset` | Own claims, newest first, with unread-update counts. |
| `POST /claims` | `{description, language}` → creates a **draft**. |
| `GET /claims/{id}` | Full worker view: description, fields, evidence (with extracted text, found amounts/dates), checks, calculation, messages, settlements, payments, timeline, latest draft metadata. Marks this claim's notifications read. |
| `PATCH /claims/{id}` | While draft: `description, language, employer_name, employer_email, work_type, start_date, end_date, amount_claimed, requested_outcome, engagement_id, private_notes, complaint_text`. After submission only `private_notes` (else 409 `claim_locked`). |
| `POST /claims/{id}/evidence` | `multipart/form-data` with one `file`. Returns `{id, original_name, kind, size_bytes, sha256, extraction_status: "pending", duplicate_of_existing}`. Extraction runs in the background. Errors: 415 `unsupported_file_type` / `file_content_mismatch`, 413 `file_too_large`, 422 `empty_file`. |
| `PATCH /claims/{id}/evidence/{eid}` | `{extracted_text?}` to correct text; `{shared_with_employer?}` to share. Un-sharing after submission is refused. |
| `POST /claims/{id}/draft` | Builds the complaint letter. Returns `{claim, draft: {text, structured, source: "ai"|"template", provider, model, warnings}}`. |
| `POST /claims/{id}/submit` | Header `Idempotency-Key`. Body `{confirm: true, complaint_text, shared_evidence_ids: []}`. Requires verified email, employer name and email. |
| `POST /claims/{id}/messages` | `{body}` — worker reply. |
| `POST /claims/{id}/withdraw` | `{note?}` |
| `POST /claims/{id}/close` | `{note?}` — worker marks resolved. |
| `POST /claims/{id}/settlements/{sid}/accept` or `/reject` | `{note?}` |
| `POST /claims/{id}/payments/{pid}/confirm` or `/dispute` | `{note?}`. Confirming resolves the claim only when confirmed payments cover the accepted offer (or the claimed amount); otherwise `partially_resolved`. |
| `GET /claims/{id}/export` | Printable HTML record (`text/html`). |

## Employer — `/api/employer` (verified email required)

| Method & path | Notes |
|---|---|
| `GET /employer/claims?filter=all|attention&limit&offset` | Claims sent to this employer's email. |
| `GET /employer/claims/{id}` | Employer view: complaint, worker name/phone, shared files only, messages, offers, payments, post-submission timeline. |
| `POST /employer/claims/{id}/acknowledge` | `submitted → acknowledged` |
| `POST /employer/claims/{id}/messages` | `{kind: response|question|agree|dispute, body}`. `question` sets `info_requested`. |
| `POST /employer/claims/{id}/attachments` | `multipart/form-data` `file`. Visible to the worker. |
| `POST /employer/claims/{id}/settlements` | `{amount, explanation?, expires_on?}`. Replaces any open offer. |
| `POST /employer/claims/{id}/payments` | `{amount, paid_on, reference?, receipt_evidence_id?, settlement_id?}`. Sets `payment_pending`; never resolves the claim on its own. |

## Shared

| Method & path | Notes |
|---|---|
| `GET /health` | Database status, environment, AI provider/model, OCR availability, email mode. |
| `GET /notifications` | `{items, unread}` for the signed-in user. |
| `POST /notifications/read-all` | |
| `GET /evidence/{id}/download` | Authorised download (worker owner; or employer for shared/own files on submitted claims). Sent as an attachment with `nosniff` and a sandbox CSP. |
| `GET /dev/outbox?email=` | **Development + console email only.** Shows the last emails to an address so verification codes can be used without a mail server. Returns 404 otherwise. |
