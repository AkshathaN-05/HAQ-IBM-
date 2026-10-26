"""Shared endpoints: health, notifications, authorized file downloads, claim export, dev outbox."""
from __future__ import annotations

import html
import sqlite3

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse

from .claims_service import claim_view, worker_claim
from .db import now_iso
from .deps import AppContext, current_user, get_ctx, require_worker
from .errors import ApiError
from .evidence_files import ocr_available, stt_available

router = APIRouter(prefix="/api", tags=["common"])

# English wording for the printable record (the screens show these in the user's language).
ACTION_LABELS = {
    "ppe": "Give helmet, gloves and safety shoes to every worker", "first_aid": "Keep a first-aid kit and a trained person on site",
    "fix_hazard": "Fix the unsafe place or machine before work continues", "training": "Explain safe working to all workers",
    "injury_care": "Pay for treatment of anyone who was hurt", "inquiry": "Start an inquiry through the Internal Committee or Local Committee",
    "separate": "Keep the people apart (different shift, team or site)", "warning": "Give a written warning to the person responsible",
    "no_retaliation": "Promise in writing: no punishment for complaining", "safe_space": "Provide a safe place to work, toilets and transport",
    "equal_pay": "Give the same pay and benefits as others doing the same work", "fair_shifts": "Share shifts and tasks fairly",
    "review": "Review the decision together with the worker", "apology": "Give a written apology", "stop": "Tell the person, in writing, to stop the threats",
    "protect": "Make sure the worker is safe at work and on the way home", "police": "Help report violence to the police (112)",
    "meeting": "Hold a meeting with the people involved and a supervisor", "rules": "Remind everyone of the workplace rules", "fix": "Fix the problem the worker raised",
}


@router.get("/health")
def health(ctx: AppContext = Depends(get_ctx)):
    db_ok = ctx.db.ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "environment": ctx.settings.app_env,
        "ai": ctx.ai.status(),
        "ocr": "available" if ocr_available() else "not installed",
        "speech_to_text": (f"offline Whisper ({ctx.settings.stt_model})" if ctx.settings.stt_model != "off" and stt_available() else "browser dictation only"),
        "email": ctx.settings.email_mode,
    }


@router.get("/notifications")
def notifications(limit: int = Query(30, ge=1, le=100), user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.connection() as c:
        rows = c.execute("""SELECT n.id, n.type, n.claim_id, n.read_at, n.created_at, cl.reference
                            FROM notifications n LEFT JOIN claims cl ON cl.id = n.claim_id
                            WHERE n.user_id = ? ORDER BY n.created_at DESC LIMIT ?""", (user["id"], limit)).fetchall()
        unread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (user["id"],)).fetchone()[0]
    return {"items": [dict(r) for r in rows], "unread": unread}


@router.post("/notifications/read-all")
def read_all(user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.connection() as c:
        c.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", (now_iso(), user["id"]))
    return {"unread": 0}


def _authorized_evidence(c: sqlite3.Connection, evidence_id: str, user: dict) -> sqlite3.Row:
    ev = c.execute("SELECT e.*, cl.worker_id, cl.employer_email, cl.submitted_at FROM evidence e JOIN claims cl ON cl.id = e.claim_id WHERE e.id = ?",
                   (evidence_id,)).fetchone()
    denied = ApiError(404, "not_found", "File not found, or you do not have access to it.")
    if ev is None:
        raise denied
    if user["role"] == "worker":
        if ev["worker_id"] != user["id"]:
            raise denied
    else:
        if not user["email_verified_at"] or ev["employer_email"] != user["email"] or not ev["submitted_at"]:
            raise denied
        if not (ev["party"] == "employer" or ev["shared_with_employer"]):
            raise denied
    return ev


@router.get("/evidence/{evidence_id}/download")
def download(evidence_id: str, user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.connection() as c:
        ev = _authorized_evidence(c, evidence_id, user)
    path = ctx.settings.storage_dir / ev["storage_name"]
    if not path.is_file():
        raise ApiError(410, "file_missing", "The stored file is missing. Please contact support.")
    # Served as an attachment with a fixed type so browsers never run it inline as a page.
    return FileResponse(path, media_type=ev["mime_type"], filename=ev["original_name"],
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
                                 "Content-Security-Policy": "default-src 'none'; sandbox"})


STATUS_TEXT = {
    "draft": "Draft", "submitted": "Sent to employer", "acknowledged": "Employer has seen it", "under_review": "Under review",
    "info_requested": "Employer asked a question", "response_received": "Employer replied", "settlement_offered": "Offer received",
    "settlement_accepted": "Offer accepted", "payment_pending": "Payment recorded — waiting for your confirmation",
    "partially_resolved": "Partly paid", "resolved": "Resolved", "disputed": "Disputed", "withdrawn": "Withdrawn",
}


@router.get("/claims/{cid}/export", response_class=HTMLResponse)
def export_claim(cid: str, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    """A printable record of the claim (print to PDF from the browser)."""
    with ctx.db.connection() as c:
        v = claim_view(c, worker_claim(c, cid, user), "worker")
    e = html.escape
    rows = []
    rows.append(f"<h1>HAQ claim record — {e(v['reference'])}</h1>")
    rows.append(f"<p><b>Status:</b> {e(STATUS_TEXT.get(v['status'], v['status']))}<br><b>Created:</b> {e(v['created_at'])}"
                f"<br><b>Sent:</b> {e(v['submitted_at'] or 'not sent')}<br><b>Exported:</b> {e(now_iso())}</p>")
    rows.append("<h2>Complaint</h2><pre>" + e(v["complaint_text"] or "(no complaint drafted yet)") + "</pre>")
    rows.append("<h2>Evidence</h2><table><tr><th>#</th><th>File</th><th>Type</th><th>Shared</th><th>SHA-256</th></tr>")
    for ev in v["evidence"]:
        rows.append(f"<tr><td>{e(ev['label'])}</td><td>{e(ev['original_name'])}</td><td>{e(ev['kind'])}</td>"
                    f"<td>{'yes' if ev['shared_with_employer'] else 'no'}</td><td><code>{e(ev['sha256'][:16])}…</code></td></tr>")
    rows.append("</table>")
    if v["messages"]:
        rows.append("<h2>Messages</h2>")
        for m in v["messages"]:
            rows.append(f"<p><b>{e(m['author_role'].title())}</b> ({e(m['kind'])}, {e(m['created_at'])}):<br>{e(m['body'])}</p>")
    if v["settlements"]:
        rows.append("<h2>Settlement offers</h2><ul>")
        for s in v["settlements"]:
            rows.append(f"<li>₹{e(s['amount'])} — {e(s['status'])} ({e(s['created_at'])}) {e(s['explanation'] or '')}</li>")
        rows.append("</ul>")
    if v.get("action_plans"):
        rows.append("<h2>Action plans</h2><ul>")
        for ap in v["action_plans"]:
            acts = [ACTION_LABELS.get(k, k) for k in ap["actions"]] + ([ap["custom_action"]] if ap["custom_action"] else [])
            who = " ".join(x for x in (ap["contact_name"], ap["contact_phone"]) if x)
            rows.append(f"<li>{e('; '.join(acts))} — {e(ap['status'])}"
                        f"{(' — handled by ' + e(who)) if who else ''}{(' — by ' + e(ap['due_on'])) if ap['due_on'] else ''}"
                        f" — worker: {e(ap['worker_confirmation'])} ({e(ap['created_at'])})</li>")
        rows.append("</ul>")
    if v["payments"]:
        rows.append("<h2>Payments recorded</h2><ul>")
        for p in v["payments"]:
            rows.append(f"<li>₹{e(p['amount'])} on {e(p['paid_on'])}, ref {e(p['reference'] or '—')} — worker: {e(p['worker_confirmation'])}</li>")
        rows.append("</ul>")
    rows.append("<h2>History</h2><ul>")
    for t in v["timeline"]:
        rows.append(f"<li>{e(t['created_at'])} — {e(t['actor_role'])}: {e(t['type'].replace('_', ' '))}</li>")
    rows.append("</ul><p><i>This record was produced by HAQ from the information in the app. It is not a legal finding.</i></p>")
    page = ("<!doctype html><html><head><meta charset='utf-8'><title>HAQ claim record</title><style>"
            "body{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;color:#1d2a20}"
            "pre{white-space:pre-wrap;background:#f7f3e8;padding:1rem;border-radius:8px}table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid #ccc;padding:4px 6px;text-align:left;font-size:14px}</style></head><body>"
            + "".join(rows) + "</body></html>")
    return HTMLResponse(page, headers={"Cache-Control": "private, no-store",
                                       "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/dev/outbox")
def dev_outbox(email: str = Query(..., max_length=200), ctx: AppContext = Depends(get_ctx)):
    """Development only: shows emails that would have been sent, so codes can be used without a mail server."""
    if not ctx.settings.is_dev or ctx.settings.email_mode != "console":
        raise ApiError(404, "not_found", "Not found.")
    with ctx.db.connection() as c:
        rows = c.execute("SELECT subject, body, created_at FROM email_outbox WHERE to_email = ? COLLATE NOCASE ORDER BY created_at DESC LIMIT 5",
                         (email,)).fetchall()
    return {"items": [dict(r) for r in rows], "note": "Development mode only. In production, emails are sent by SMTP."}
