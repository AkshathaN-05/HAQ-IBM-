"""Employer portal. Employers see only claims addressed to their verified email address,
and can respond, attach files, offer settlements and record payments — never edit the claim."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field

from . import claim_state, wages
from .claims_service import claim_view, employer_claim
from .db import new_id, now_iso
from .deps import AppContext, add_event, get_ctx, notify, require_verified_employer
from .errors import ApiError
from .routes_worker import receive_upload
from .security import rate_limiter

router = APIRouter(prefix="/api/employer", tags=["employer"])

NEEDS_ATTENTION = ("submitted", "under_review", "disputed", "settlement_accepted")


class MessageIn(BaseModel):
    kind: Literal["response", "question", "agree", "dispute"]
    body: str = Field(min_length=1, max_length=4000)


class SettlementIn(BaseModel):
    amount: str = Field(max_length=20)
    explanation: str = Field(default="", max_length=2000)
    expires_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PaymentIn(BaseModel):
    amount: str = Field(max_length=20)
    paid_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reference: str | None = Field(default=None, max_length=100)
    receipt_evidence_id: str | None = Field(default=None, max_length=40)
    settlement_id: str | None = Field(default=None, max_length=40)


@router.get("/claims")
def inbox(filter: Literal["all", "attention"] = "all", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
          user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    where = "employer_email = ? AND submitted_at IS NOT NULL"
    params: list = [user["email"]]
    if filter == "attention":
        where += f" AND status IN ({','.join('?' * len(NEEDS_ATTENTION))})"
        params += list(NEEDS_ATTENTION)
    with ctx.db.connection() as c:
        rows = c.execute(f"""SELECT cl.id, cl.reference, cl.status, cl.issue_type, cl.amount_claimed, cl.submitted_at, cl.updated_at,
                                    u.display_name AS worker_name,
                                    (SELECT COUNT(*) FROM notifications n WHERE n.claim_id = cl.id AND n.user_id = ? AND n.read_at IS NULL) AS unread
                             FROM claims cl JOIN users u ON u.id = cl.worker_id
                             WHERE {where} ORDER BY cl.updated_at DESC LIMIT ? OFFSET ?""",
                         (user["id"], *params, limit, offset)).fetchall()
        total = c.execute(f"SELECT COUNT(*) FROM claims WHERE {where}", params).fetchone()[0]
    return {"items": [dict(r) for r in rows], "total": total}


@router.get("/claims/{cid}")
def get_claim(cid: str, user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = employer_claim(c, cid, user)
        c.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND claim_id = ? AND read_at IS NULL", (now_iso(), user["id"], cid))
        return claim_view(c, claim, "employer")


@router.post("/claims/{cid}/acknowledge")
def acknowledge(cid: str, user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = employer_claim(c, cid, user)
        nxt = claim_state.check("acknowledge", "employer", claim["status"])
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, "acknowledged")
        notify(c, claim["worker_id"], cid, "acknowledged", f"ack:{cid}")
        return claim_view(c, employer_claim(c, cid, user), "employer")


@router.post("/claims/{cid}/messages", status_code=201)
def message(cid: str, body: MessageIn, user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"msg:{user['id']}", 60, 3600)
    with ctx.db.transaction() as c:
        claim = employer_claim(c, cid, user)
        claim_state.check("employer_message", "employer", claim["status"])
        mid = new_id()
        c.execute("INSERT INTO messages(id,claim_id,author_id,author_role,kind,body,created_at) VALUES (?,?,?,?,?,?,?)",
                  (mid, cid, user["id"], "employer", body.kind, body.body.strip(), now_iso()))
        if body.kind == "question":
            nxt = "info_requested"
        elif claim["status"] == "partially_resolved":
            nxt = claim["status"]
        else:
            nxt = "response_received"
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, f"employer_{body.kind}")
        notify(c, claim["worker_id"], cid, "employer_replied", f"msg:{mid}")
        return claim_view(c, employer_claim(c, cid, user), "employer")


@router.post("/claims/{cid}/attachments", status_code=201)
async def attach(cid: str, request: Request, user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"upload:{user['id']}", 60, 3600)
    with ctx.db.connection() as c:
        claim = employer_claim(c, cid, user)
        if claim["status"] in claim_state.TERMINAL:
            raise ApiError(409, "claim_closed", "This claim is closed.")
    stored = await receive_upload(request, ctx)
    eid = new_id()
    with ctx.db.transaction() as c:
        c.execute("""INSERT INTO evidence(id,claim_id,uploaded_by,party,original_name,kind,mime_type,size_bytes,sha256,storage_name,
                     shared_with_employer,extraction_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (eid, cid, user["id"], "employer", stored.original_name, stored.kind, stored.mime_type, stored.size_bytes,
                   stored.sha256, stored.storage_name, 1, "unsupported", now_iso()))
        c.execute("UPDATE claims SET updated_at = ? WHERE id = ?", (now_iso(), cid))
        add_event(c, cid, user, "employer_attachment", {"file": stored.original_name})
        notify(c, claim["worker_id"], cid, "employer_attachment", f"att:{eid}")
    return {"id": eid, "original_name": stored.original_name, "kind": stored.kind, "size_bytes": stored.size_bytes}


@router.post("/claims/{cid}/settlements", status_code=201)
def offer(cid: str, body: SettlementIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
          user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    amount = wages.money_str(wages.to_money(body.amount, "amount", allow_zero=False))
    if body.expires_on and body.expires_on < date.today().isoformat():
        raise ApiError(422, "invalid_date", "The offer expiry date is in the past.", {"field": "expires_on"})
    with ctx.db.transaction() as c:
        claim = employer_claim(c, cid, user)
        if idempotency_key:
            existing = c.execute("SELECT id FROM settlements WHERE request_key = ?", (f"{cid}:{idempotency_key}",)).fetchone()
            if existing:
                return claim_view(c, claim, "employer")
        nxt = claim_state.check("offer_settlement", "employer", claim["status"])
        c.execute("UPDATE settlements SET status = 'superseded' WHERE claim_id = ? AND status = 'offered'", (cid,))
        sid = new_id()
        c.execute("""INSERT INTO settlements(id,claim_id,offered_by,amount,currency,explanation,expires_on,status,request_key,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (sid, cid, user["id"], amount, "INR", body.explanation.strip(), body.expires_on, "offered",
                   f"{cid}:{idempotency_key}" if idempotency_key else None, now_iso()))
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, "settlement_offered", {"amount": amount})
        notify(c, claim["worker_id"], cid, "settlement_offered", f"offer:{sid}")
        return claim_view(c, employer_claim(c, cid, user), "employer")


@router.post("/claims/{cid}/payments", status_code=201)
def record_payment(cid: str, body: PaymentIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
                   user: dict = Depends(require_verified_employer), ctx: AppContext = Depends(get_ctx)):
    amount = wages.money_str(wages.to_money(body.amount, "amount", allow_zero=False))
    try:
        paid_on = date.fromisoformat(body.paid_on)
    except ValueError:
        raise ApiError(422, "invalid_date", "Please enter a real payment date.", {"field": "paid_on"})
    if paid_on > date.today():
        raise ApiError(422, "invalid_date", "The payment date cannot be in the future.", {"field": "paid_on"})
    with ctx.db.transaction() as c:
        claim = employer_claim(c, cid, user)
        if idempotency_key:
            if c.execute("SELECT 1 FROM payments WHERE request_key = ?", (f"{cid}:{idempotency_key}",)).fetchone():
                return claim_view(c, claim, "employer")
        nxt = claim_state.check("record_payment", "employer", claim["status"])
        if body.receipt_evidence_id:
            ok = c.execute("SELECT 1 FROM evidence WHERE id = ? AND claim_id = ? AND party = 'employer' AND uploaded_by = ?",
                           (body.receipt_evidence_id, cid, user["id"])).fetchone()
            if not ok:
                raise ApiError(422, "unknown_receipt", "The receipt file was not found on this claim.")
        if body.settlement_id:
            ok = c.execute("SELECT 1 FROM settlements WHERE id = ? AND claim_id = ?", (body.settlement_id, cid)).fetchone()
            if not ok:
                raise ApiError(422, "unknown_settlement", "Settlement not found on this claim.")
        pid = new_id()
        c.execute("""INSERT INTO payments(id,claim_id,settlement_id,recorded_by,amount,currency,paid_on,reference,receipt_evidence_id,
                     worker_confirmation,request_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid, cid, body.settlement_id, user["id"], amount, "INR", body.paid_on, (body.reference or "").strip() or None,
                   body.receipt_evidence_id, "pending", f"{cid}:{idempotency_key}" if idempotency_key else None, now_iso()))
        # The claim waits for the worker to confirm; an employer's statement alone never resolves it.
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, "payment_recorded_by_employer", {"amount": amount, "paid_on": body.paid_on})
        notify(c, claim["worker_id"], cid, "payment_recorded", f"pay:{pid}")
        return claim_view(c, employer_claim(c, cid, user), "employer")
