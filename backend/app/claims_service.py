"""Loading claims with authorization, and building the views each role may see."""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone

from . import wages
from .checks import run_checks
from .errors import ApiError

NOT_FOUND = ApiError(404, "not_found", "This claim was not found, or you do not have access to it.")


def new_reference() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "HAQ-" + datetime.now(timezone.utc).strftime("%y%m") + "-" + "".join(secrets.choice(alphabet) for _ in range(6))


def worker_claim(c: sqlite3.Connection, claim_id: str, worker: dict) -> dict:
    row = c.execute("SELECT * FROM claims WHERE id = ? AND worker_id = ?", (claim_id, worker["id"])).fetchone()
    if row is None:
        raise NOT_FOUND  # same response whether it doesn't exist or belongs to someone else
    return dict(row)


def employer_claim(c: sqlite3.Connection, claim_id: str, employer: dict) -> dict:
    row = c.execute(
        "SELECT * FROM claims WHERE id = ? AND employer_email = ? AND submitted_at IS NOT NULL",
        (claim_id, employer["email"]),
    ).fetchone()
    if row is None:
        raise NOT_FOUND
    return dict(row)


def engagement_calc(c: sqlite3.Connection, claim: dict) -> dict | None:
    if not claim.get("engagement_id"):
        return None
    e = c.execute("SELECT * FROM engagements WHERE id = ? AND worker_id = ?", (claim["engagement_id"], claim["worker_id"])).fetchone()
    if e is None:
        return None
    try:
        return wages.calculate(e["pay_type"], e["rate"], e["units"], e["payments_received"])
    except ApiError:
        return None


def _evidence_public(e: dict, include_text: bool) -> dict:
    out = {k: e[k] for k in ("id", "party", "original_name", "kind", "mime_type", "size_bytes", "sha256",
                               "shared_with_employer", "extraction_status", "created_at")}
    out["shared_with_employer"] = bool(out["shared_with_employer"])
    if include_text:
        out.update({
            "extracted_text": e["extracted_text"], "extracted_text_edited": bool(e["extracted_text_edited"]),
            "extraction_error": e["extraction_error"],
            "found_amounts": json.loads(e["found_amounts"] or "[]"), "found_dates": json.loads(e["found_dates"] or "[]"),
        })
    return out


def claim_view(c: sqlite3.Connection, claim: dict, role: str) -> dict:
    cid = claim["id"]
    worker = c.execute("SELECT display_name, phone, email FROM users WHERE id = ?", (claim["worker_id"],)).fetchone()
    base_fields = ("id", "reference", "status", "language", "employer_name", "work_type", "start_date", "end_date",
                   "amount_claimed", "requested_outcome", "complaint_text", "complaint_provider", "submitted_at",
                   "created_at", "updated_at")
    view = {k: claim[k] for k in base_fields}
    view["worker"] = {"display_name": worker["display_name"], "phone": worker["phone"]}

    if role == "worker":
        view.update({k: claim[k] for k in ("description", "employer_email", "engagement_id", "private_notes")})
        ev_rows = [dict(r) for r in c.execute("SELECT * FROM evidence WHERE claim_id = ? ORDER BY created_at", (cid,))]
    else:
        # Employers see the submitted complaint, shared worker files and their own files only.
        ev_rows = [dict(r) for r in c.execute(
            "SELECT * FROM evidence WHERE claim_id = ? AND (party = 'employer' OR shared_with_employer = 1) ORDER BY created_at", (cid,))]

    worker_ev = [e for e in ev_rows if e["party"] == "worker"]
    view["evidence"] = [dict(_evidence_public(e, include_text=(role == "worker")), label=f"E{i}") for i, e in enumerate(worker_ev, 1)]
    view["employer_attachments"] = [_evidence_public(e, include_text=False) for e in ev_rows if e["party"] == "employer"]
    view["messages"] = [dict(r) for r in c.execute(
        "SELECT id, author_role, kind, body, created_at FROM messages WHERE claim_id = ? ORDER BY created_at", (cid,))]
    view["settlements"] = [dict(r) for r in c.execute(
        "SELECT id, amount, currency, explanation, expires_on, status, decided_at, decision_note, created_at FROM settlements WHERE claim_id = ? ORDER BY created_at", (cid,))]
    view["payments"] = [dict(r) for r in c.execute(
        "SELECT id, settlement_id, amount, currency, paid_on, reference, receipt_evidence_id, worker_confirmation, worker_note, created_at FROM payments WHERE claim_id = ? ORDER BY created_at", (cid,))]
    events = []
    for r in c.execute("SELECT actor_role, type, detail, created_at FROM claim_events WHERE claim_id = ? ORDER BY created_at, rowid", (cid,)):
        d = dict(r)
        d["detail"] = json.loads(d["detail"]) if d["detail"] else None
        if role == "employer" and d["type"] in ("draft_created", "evidence_added", "complaint_drafted", "complaint_edited", "details_updated", "extraction_finished"):
            continue  # pre-submission history is the worker's private working
        events.append(d)
    view["timeline"] = events

    if role == "worker":
        calc = engagement_calc(c, claim)
        view["calculation"] = calc
        view["checks"] = run_checks(claim, worker_ev, calc)
        latest = c.execute("SELECT structured, source, provider, model, version FROM complaint_versions WHERE claim_id = ? ORDER BY version DESC LIMIT 1", (cid,)).fetchone()
        view["latest_draft"] = ({"structured": json.loads(latest["structured"]) if latest["structured"] else None,
                                 "source": latest["source"], "provider": latest["provider"], "model": latest["model"],
                                 "version": latest["version"]} if latest else None)
        emp = c.execute("SELECT employer_verification FROM users WHERE email = ? AND role = 'employer'", (claim["employer_email"] or "",)).fetchone() if claim["employer_email"] else None
        view["employer_account"] = {"registered": emp is not None, "verification": emp["employer_verification"] if emp else None}
    return view
