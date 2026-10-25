"""Worker portal: claims, evidence, complaint drafting, submission, responses, work records."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field

from . import claim_state, wages
from .ai import ClaimFacts, draft_complaint
from .ai.drafting import EvidenceFact
from .claims_service import claim_view, engagement_calc, new_reference, worker_claim
from .db import new_id, now_iso
from .deps import AppContext, add_event, get_ctx, notify, require_worker
from .errors import ApiError
from .languages import ClaimLang
from .evidence_files import (ExtractionUnsupported, extract_text, find_amounts, find_dates,
                             store_upload)
from .security import rate_limiter

log = logging.getLogger("haq.worker")
router = APIRouter(prefix="/api", tags=["worker"])

DateStr = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


IssueType = Literal["wages", "safety", "harassment", "discrimination", "threats", "coworkers", "other"]


class ClaimCreate(BaseModel):
    description: str = Field(default="", max_length=8000)
    language: ClaimLang = "en"
    issue_type: IssueType = "wages"


class ClaimUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=8000)
    language: ClaimLang | None = None
    issue_type: IssueType | None = None
    employer_name: str | None = Field(default=None, max_length=150)
    employer_email: EmailStr | None = None
    work_type: str | None = Field(default=None, max_length=150)
    start_date: str | None = DateStr
    end_date: str | None = DateStr
    amount_claimed: str | None = Field(default=None, max_length=20)
    requested_outcome: str | None = Field(default=None, max_length=1000)
    engagement_id: str | None = Field(default=None, max_length=40)
    private_notes: str | None = Field(default=None, max_length=4000)
    complaint_text: str | None = Field(default=None, max_length=20000)


class SubmitIn(BaseModel):
    confirm: bool
    complaint_text: str = Field(min_length=20, max_length=20000)
    shared_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class EvidenceUpdate(BaseModel):
    extracted_text: str | None = Field(default=None, max_length=20000)
    shared_with_employer: bool | None = None


class TextIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class EngagementIn(BaseModel):
    employer_name: str = Field(min_length=1, max_length=150)
    work_type: str = Field(min_length=1, max_length=150)
    pay_type: Literal["daily", "hourly", "weekly", "monthly", "piece", "task"]
    rate: str = Field(max_length=20)
    units: str = Field(max_length=20)
    payments_received: str = Field(default="0", max_length=20)
    start_date: str | None = DateStr
    end_date: str | None = DateStr
    notes: str | None = Field(default=None, max_length=2000)


class WageIn(BaseModel):
    pay_type: Literal["daily", "hourly", "weekly", "monthly", "piece", "task"] = "daily"
    rate: str = Field(max_length=20)
    units: str = Field(max_length=20)
    payments_received: str = Field(default="0", max_length=20)


def _check_dates(start: str | None, end: str | None) -> None:
    for name, v in (("start_date", start), ("end_date", end)):
        if v:
            try:
                d = date.fromisoformat(v)
            except ValueError:
                raise ApiError(422, "invalid_date", "Please enter a real date.", {"field": name})
            if d.year < 1990 or d > date.today().replace(year=date.today().year + 1):
                raise ApiError(422, "invalid_date", "This date looks wrong. Please check it.", {"field": name})


# --- Wage calculator & work records --------------------------------------------------------

@router.post("/wage-calculation")
def wage_calculation(body: WageIn, request: Request):
    rate_limiter.check(f"wage:{request.client.host if request.client else '?'}", 120, 60)
    return wages.calculate(body.pay_type, body.rate, body.units, body.payments_received)


def _engagement_out(row: dict) -> dict:
    out = dict(row)
    out.pop("worker_id", None)
    try:
        out["calculation"] = wages.calculate(row["pay_type"], row["rate"], row["units"], row["payments_received"])
    except ApiError:
        out["calculation"] = None
    return out


@router.get("/worker/engagements")
def list_engagements(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                     user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.connection() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM engagements WHERE worker_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                           (user["id"], limit, offset))]
        total = c.execute("SELECT COUNT(*) FROM engagements WHERE worker_id = ?", (user["id"],)).fetchone()[0]
    return {"items": [_engagement_out(r) for r in rows], "total": total}


def _validated_engagement(body: EngagementIn) -> dict:
    _check_dates(body.start_date, body.end_date)
    calc = wages.calculate(body.pay_type, body.rate, body.units, body.payments_received)  # validates numbers
    d = body.model_dump()
    d["rate"], d["units"], d["payments_received"] = calc["rate"], calc["units"], calc["payments_received"]
    return d


@router.post("/worker/engagements", status_code=201)
def create_engagement(body: EngagementIn, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    d = _validated_engagement(body)
    eid, now = new_id(), now_iso()
    with ctx.db.transaction() as c:
        c.execute("""INSERT INTO engagements(id,worker_id,employer_name,work_type,pay_type,rate,units,payments_received,
                     start_date,end_date,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (eid, user["id"], d["employer_name"].strip(), d["work_type"].strip(), d["pay_type"], d["rate"], d["units"],
                   d["payments_received"], d["start_date"], d["end_date"], d["notes"], now, now))
        row = c.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
    return _engagement_out(dict(row))


@router.put("/worker/engagements/{eid}")
def update_engagement(eid: str, body: EngagementIn, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    d = _validated_engagement(body)
    with ctx.db.transaction() as c:
        cur = c.execute("""UPDATE engagements SET employer_name=?, work_type=?, pay_type=?, rate=?, units=?, payments_received=?,
                           start_date=?, end_date=?, notes=?, updated_at=? WHERE id=? AND worker_id=?""",
                        (d["employer_name"].strip(), d["work_type"].strip(), d["pay_type"], d["rate"], d["units"], d["payments_received"],
                         d["start_date"], d["end_date"], d["notes"], now_iso(), eid, user["id"]))
        if cur.rowcount == 0:
            raise ApiError(404, "not_found", "Work record not found.")
        row = c.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
    return _engagement_out(dict(row))


# --- Claims ----------------------------------------------------------------------------------

@router.get("/claims")
def list_claims(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.connection() as c:
        rows = c.execute("""SELECT cl.id, cl.reference, cl.status, cl.issue_type, cl.employer_name, cl.amount_claimed, cl.created_at, cl.updated_at,
                                   cl.submitted_at, substr(cl.description, 1, 140) AS preview,
                                   (SELECT COUNT(*) FROM notifications n WHERE n.claim_id = cl.id AND n.user_id = ? AND n.read_at IS NULL) AS unread
                            FROM claims cl WHERE worker_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                         (user["id"], user["id"], limit, offset)).fetchall()
        total = c.execute("SELECT COUNT(*) FROM claims WHERE worker_id = ?", (user["id"],)).fetchone()[0]
    return {"items": [dict(r) for r in rows], "total": total}


@router.post("/claims", status_code=201)
def create_claim(body: ClaimCreate, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    cid, now = new_id(), now_iso()
    with ctx.db.transaction() as c:
        c.execute("""INSERT INTO claims(id, reference, worker_id, status, language, issue_type, description, created_at, updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?)""", (cid, new_reference(), user["id"], "draft", body.language, body.issue_type, body.description.strip(), now, now))
        add_event(c, cid, user, "draft_created")
        claim = worker_claim(c, cid, user)
        return claim_view(c, claim, "worker")


@router.get("/claims/{cid}")
def get_claim(cid: str, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        c.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND claim_id = ? AND read_at IS NULL", (now_iso(), user["id"], cid))
        return claim_view(c, claim, "worker")


@router.patch("/claims/{cid}")
def update_claim(cid: str, body: ClaimUpdate, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    fields = body.model_dump(exclude_unset=True)
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        if claim["status"] != "draft":
            # After submission only private notes can change; the sent complaint stays as sent.
            if set(fields) - {"private_notes"}:
                raise ApiError(409, "claim_locked", "This claim has been sent, so its details can no longer be changed. You can add a reply instead.")
        _check_dates(fields.get("start_date", claim["start_date"]), fields.get("end_date", claim["end_date"]))
        if fields.get("amount_claimed") not in (None, ""):
            fields["amount_claimed"] = wages.money_str(wages.to_money(fields["amount_claimed"], "amount_claimed", allow_zero=False))
        elif "amount_claimed" in fields:
            fields["amount_claimed"] = None
        if fields.get("employer_email"):
            fields["employer_email"] = str(fields["employer_email"]).lower()
        if fields.get("engagement_id"):
            ok = c.execute("SELECT 1 FROM engagements WHERE id = ? AND worker_id = ?", (fields["engagement_id"], user["id"])).fetchone()
            if not ok:
                raise ApiError(404, "not_found", "Work record not found.")
        elif "engagement_id" in fields:
            fields["engagement_id"] = None
        for k in ("employer_name", "work_type", "requested_outcome", "description", "private_notes"):
            if isinstance(fields.get(k), str):
                fields[k] = fields[k].strip() or (None if k != "description" else "")
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            c.execute(f"UPDATE claims SET {sets}, updated_at = ? WHERE id = ?", (*fields.values(), now_iso(), cid))
            if "complaint_text" in fields and fields["complaint_text"]:
                v = (c.execute("SELECT COALESCE(MAX(version), 0) FROM complaint_versions WHERE claim_id = ?", (cid,)).fetchone()[0]) + 1
                c.execute("INSERT INTO complaint_versions(id,claim_id,version,source,provider,model,text,structured,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                          (new_id(), cid, v, "worker", "worker", None, fields["complaint_text"], None, now_iso()))
                add_event(c, cid, user, "complaint_edited", {"version": v})
            elif set(fields) - {"private_notes"}:
                add_event(c, cid, user, "details_updated", {"fields": sorted(set(fields) - {"private_notes"})})
        return claim_view(c, worker_claim(c, cid, user), "worker")


# --- Evidence --------------------------------------------------------------------------------

def process_evidence(ctx: AppContext, evidence_id: str) -> None:
    """Background job: extract text, amounts and dates. Failures are recorded, never hidden."""
    with ctx.db.connection() as c:
        row = c.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
    if row is None:
        return
    path = ctx.settings.storage_dir / row["storage_name"]
    ext = row["storage_name"].rsplit(".", 1)[-1]
    status, text, error = "done", None, None
    try:
        text = extract_text(path, ext, ctx.settings.ocr_languages, ctx.settings.stt_model)
    except ExtractionUnsupported as e:
        status, error = "unsupported", str(e)
    except Exception as e:  # corrupt files etc.
        status, error = "failed", "The file could not be read. It may be damaged or password-protected."
        log.info("Extraction failed for %s: %s", evidence_id, type(e).__name__)
    amounts = find_amounts(text) if text else []
    dates_ = find_dates(text) if text else []
    with ctx.db.transaction() as c:
        c.execute("""UPDATE evidence SET extraction_status=?, extracted_text=?, extraction_error=?, found_amounts=?, found_dates=?
                     WHERE id = ? AND extracted_text_edited = 0""",
                  (status, text, error, json.dumps(amounts), json.dumps(dates_), evidence_id))
        if row["party"] == "worker":
            add_event(c, row["claim_id"], None, "extraction_finished", {"file": row["original_name"], "status": status})


async def receive_upload(request: Request, ctx: AppContext):
    """Parse a single-file multipart upload, rejecting oversized bodies before reading them."""
    limit = max(ctx.settings.max_upload_mb, ctx.settings.max_media_upload_mb) * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 1024 * 1024:
        raise ApiError(413, "file_too_large", f"This file is larger than {limit // (1024 * 1024)} MB.")
    try:
        form = await request.form(max_files=1, max_fields=5)
    except Exception:
        raise ApiError(400, "bad_upload", "The upload did not arrive completely. Please try again.")
    upload = form.get("file")
    if upload is None or not hasattr(upload, "file"):
        raise ApiError(422, "no_file", "Please choose a file to upload.")
    try:
        return await run_in_threadpool(
            store_upload, upload.file, upload.filename or "file", ctx.settings.storage_dir,
            ctx.settings.max_upload_mb * 1024 * 1024, ctx.settings.max_media_upload_mb * 1024 * 1024)
    finally:
        await upload.close()


@router.post("/claims/{cid}/evidence", status_code=201)
async def upload_evidence(cid: str, request: Request, background: BackgroundTasks,
                          user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"upload:{user['id']}", 60, 3600)
    with ctx.db.connection() as c:
        claim = worker_claim(c, cid, user)
        if claim["status"] in claim_state.TERMINAL:
            raise ApiError(409, "claim_closed", "This claim is closed.")
        count = c.execute("SELECT COUNT(*) FROM evidence WHERE claim_id = ? AND party = 'worker'", (cid,)).fetchone()[0]
        if count >= 30:
            raise ApiError(409, "too_many_files", "A claim can have at most 30 files.")
    stored = await receive_upload(request, ctx)
    eid = new_id()
    with ctx.db.transaction() as c:
        c.execute("""INSERT INTO evidence(id,claim_id,uploaded_by,party,original_name,kind,mime_type,size_bytes,sha256,storage_name,
                     shared_with_employer,extraction_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (eid, cid, user["id"], "worker", stored.original_name, stored.kind, stored.mime_type, stored.size_bytes,
                   stored.sha256, stored.storage_name, 0, "pending", now_iso()))
        c.execute("UPDATE claims SET updated_at = ? WHERE id = ?", (now_iso(), cid))
        add_event(c, cid, user, "evidence_added", {"file": stored.original_name, "kind": stored.kind})
        dup = c.execute("SELECT COUNT(*) FROM evidence WHERE claim_id = ? AND sha256 = ? AND id != ?", (cid, stored.sha256, eid)).fetchone()[0]
    background.add_task(process_evidence, ctx, eid)
    return {"id": eid, "original_name": stored.original_name, "kind": stored.kind, "size_bytes": stored.size_bytes,
            "sha256": stored.sha256, "extraction_status": "pending", "duplicate_of_existing": dup > 0}


@router.patch("/claims/{cid}/evidence/{eid}")
def update_evidence(cid: str, eid: str, body: EvidenceUpdate, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        ev = c.execute("SELECT * FROM evidence WHERE id = ? AND claim_id = ? AND party = 'worker'", (eid, cid)).fetchone()
        if ev is None:
            raise ApiError(404, "not_found", "File not found.")
        if body.extracted_text is not None:
            text = body.extracted_text.strip()
            c.execute("""UPDATE evidence SET extracted_text = ?, extracted_text_edited = 1, found_amounts = ?, found_dates = ?,
                         extraction_status = CASE WHEN ? != '' THEN 'done' ELSE extraction_status END WHERE id = ?""",
                      (text, json.dumps(find_amounts(text)), json.dumps(find_dates(text)), text, eid))
            add_event(c, cid, user, "evidence_text_corrected", {"file": ev["original_name"]})
        if body.shared_with_employer is not None and bool(ev["shared_with_employer"]) != body.shared_with_employer:
            if claim["status"] != "draft" and not body.shared_with_employer:
                raise ApiError(409, "already_shared", "This file was already shared with the employer and cannot be un-shared.")
            c.execute("UPDATE evidence SET shared_with_employer = ? WHERE id = ?", (int(body.shared_with_employer), eid))
            if claim["status"] != "draft":
                add_event(c, cid, user, "evidence_shared", {"file": ev["original_name"]})
                emp = c.execute("SELECT id FROM users WHERE email = ? AND role = 'employer'", (claim["employer_email"],)).fetchone()
                notify(c, emp["id"] if emp else None, cid, "evidence_shared", f"evshare:{eid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")


# --- Drafting & submission -------------------------------------------------------------------

def build_facts(c, claim: dict, user: dict) -> ClaimFacts:
    ev_rows = [dict(r) for r in c.execute("SELECT * FROM evidence WHERE claim_id = ? AND party = 'worker' ORDER BY created_at", (claim["id"],))]
    evidence = [EvidenceFact(id=e["id"], label=f"E{i}", name=e["original_name"], kind=e["kind"],
                             status=e["extraction_status"], text=e["extracted_text"] or "") for i, e in enumerate(ev_rows, 1)]
    return ClaimFacts(
        reference=claim["reference"], language=claim["language"], worker_name=user["display_name"],
        worker_contact=user.get("phone") or "", description=claim["description"] or "", issue_type=claim["issue_type"],
        employer_name=claim["employer_name"], work_type=claim["work_type"], start_date=claim["start_date"],
        end_date=claim["end_date"], amount_claimed=claim["amount_claimed"], requested_outcome=claim["requested_outcome"],
        calculation=engagement_calc(c, claim), evidence=evidence)


@router.post("/claims/{cid}/draft")
def generate_draft(cid: str, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"draft:{user['id']}", 20, 3600)
    with ctx.db.connection() as c:
        claim = worker_claim(c, cid, user)
        if claim["status"] != "draft":
            raise ApiError(409, "claim_locked", "This claim has already been sent.")
        if len((claim["description"] or "").strip()) < 10:
            raise ApiError(422, "description_too_short", "Please tell us a little more about what happened first.")
        pending = c.execute("SELECT COUNT(*) FROM evidence WHERE claim_id = ? AND extraction_status = 'pending'", (cid,)).fetchone()[0]
        facts = build_facts(c, claim, user)
    result = draft_complaint(ctx.ai, facts)  # may call the AI provider (slow) — outside any DB transaction
    if pending:
        result.warnings.append("Some files were still being read, so their contents were not used. You can generate the draft again in a moment.")
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        if claim["status"] != "draft":
            raise ApiError(409, "claim_locked", "This claim has already been sent.")
        v = (c.execute("SELECT COALESCE(MAX(version), 0) FROM complaint_versions WHERE claim_id = ?", (cid,)).fetchone()[0]) + 1
        c.execute("INSERT INTO complaint_versions(id,claim_id,version,source,provider,model,text,structured,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  (new_id(), cid, v, result.source, result.provider, result.model, result.text,
                   json.dumps(result.structured, ensure_ascii=False), now_iso()))
        c.execute("UPDATE claims SET complaint_text = ?, complaint_provider = ?, updated_at = ? WHERE id = ?",
                  (result.text, result.provider, now_iso(), cid))
        add_event(c, cid, user, "complaint_drafted", {"version": v, "source": result.source, "provider": result.provider})
        view = claim_view(c, worker_claim(c, cid, user), "worker")
    return {"claim": view, "draft": {"text": result.text, "structured": result.structured, "source": result.source,
                                     "provider": result.provider, "model": result.model, "warnings": result.warnings}}


@router.post("/claims/{cid}/submit")
def submit_claim(cid: str, body: SubmitIn, idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
                 user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    if not body.confirm:
        raise ApiError(422, "confirmation_required", "Please confirm that you have read the complaint and want to send it.")
    if not user["email_verified_at"]:
        raise ApiError(403, "email_not_verified", "Please verify your email address before sending a claim.")
    send_email_to = None
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        if claim["status"] != "draft":
            if claim["submit_key"] == idempotency_key:
                return claim_view(c, claim, "worker")  # safe retry: already done
            raise ApiError(409, "already_submitted", "This claim has already been sent.")
        claim_state.check("submit", "worker", claim["status"])
        if not claim["employer_email"]:
            raise ApiError(422, "employer_email_required", "Please add the employer's email address so HAQ can deliver the claim.")
        if not claim["employer_name"]:
            raise ApiError(422, "employer_name_required", "Please add the employer's name.")
        own_ids = {r["id"] for r in c.execute("SELECT id FROM evidence WHERE claim_id = ? AND party = 'worker'", (cid,))}
        unknown = set(body.shared_evidence_ids) - own_ids
        if unknown:
            raise ApiError(422, "unknown_evidence", "Some selected files do not belong to this claim.")
        c.execute("UPDATE evidence SET shared_with_employer = 0 WHERE claim_id = ? AND party = 'worker'", (cid,))
        for eid in body.shared_evidence_ids:
            c.execute("UPDATE evidence SET shared_with_employer = 1 WHERE id = ?", (eid,))
        now = now_iso()
        text = body.complaint_text.strip()
        if text != (claim["complaint_text"] or "").strip():
            v = (c.execute("SELECT COALESCE(MAX(version), 0) FROM complaint_versions WHERE claim_id = ?", (cid,)).fetchone()[0]) + 1
            c.execute("INSERT INTO complaint_versions(id,claim_id,version,source,provider,model,text,structured,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (new_id(), cid, v, "worker", "worker", None, text, None, now))
        c.execute("UPDATE claims SET status = 'submitted', complaint_text = ?, submitted_at = ?, submit_key = ?, updated_at = ? WHERE id = ?",
                  (text, now, idempotency_key, now, cid))
        add_event(c, cid, user, "submitted", {"shared_files": len(body.shared_evidence_ids), "to": claim["employer_name"]})
        emp = c.execute("SELECT id FROM users WHERE email = ? AND role = 'employer'", (claim["employer_email"],)).fetchone()
        notify(c, emp["id"] if emp else None, cid, "new_claim", f"submitted:{cid}")
        send_email_to = claim["employer_email"]
    # Email contains no claim details — only a prompt to sign in.
    status = ctx.mailer.send(send_email_to, "You have a new message on HAQ",
                             "A worker has sent you a workplace claim through HAQ. Sign in to the HAQ employer portal "
                             "(or create an employer account with this email address) to read and respond to it.")
    with ctx.db.transaction() as c:
        add_event(c, cid, None, "employer_notified_by_email", {"delivery": status})
        return claim_view(c, worker_claim(c, cid, user), "worker")


# --- After submission: worker actions ---------------------------------------------------------

def _employer_id(c, claim) -> str | None:
    r = c.execute("SELECT id FROM users WHERE email = ? AND role = 'employer'", (claim["employer_email"] or "",)).fetchone()
    return r["id"] if r else None


@router.post("/claims/{cid}/messages", status_code=201)
def worker_reply(cid: str, body: TextIn, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"msg:{user['id']}", 60, 3600)
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        claim_state.check("worker_reply", "worker", claim["status"])
        mid = new_id()
        c.execute("INSERT INTO messages(id,claim_id,author_id,author_role,kind,body,created_at) VALUES (?,?,?,?,?,?,?)",
                  (mid, cid, user["id"], "worker", "reply", body.body.strip(), now_iso()))
        new_status = "under_review" if claim["status"] == "info_requested" else claim["status"]
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_iso(), cid))
        add_event(c, cid, user, "worker_replied")
        notify(c, _employer_id(c, claim), cid, "worker_replied", f"msg:{mid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")


@router.post("/claims/{cid}/withdraw")
def withdraw(cid: str, body: NoteIn, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        nxt = claim_state.check("withdraw", "worker", claim["status"])
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, "withdrawn", {"note": body.note} if body.note else None)
        if claim["submitted_at"]:
            notify(c, _employer_id(c, claim), cid, "withdrawn", f"withdrawn:{cid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")


@router.post("/claims/{cid}/close")
def close_resolved(cid: str, body: NoteIn, user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        nxt = claim_state.check("close_resolved", "worker", claim["status"])
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, "closed_as_resolved_by_worker", {"note": body.note} if body.note else None)
        notify(c, _employer_id(c, claim), cid, "resolved", f"resolved:{cid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")


@router.post("/claims/{cid}/settlements/{sid}/{decision}")
def decide_settlement(cid: str, sid: str, decision: Literal["accept", "reject"], body: NoteIn,
                      user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        nxt = claim_state.check(f"{decision}_settlement", "worker", claim["status"])
        s = c.execute("SELECT * FROM settlements WHERE id = ? AND claim_id = ?", (sid, cid)).fetchone()
        if s is None:
            raise ApiError(404, "not_found", "Offer not found.")
        if s["status"] != "offered":
            raise ApiError(409, "offer_not_open", "This offer is no longer open.")
        if decision == "accept" and s["expires_on"] and s["expires_on"] < date.today().isoformat():
            raise ApiError(409, "offer_expired", "This offer has expired. You can ask the employer for a new one.")
        c.execute("UPDATE settlements SET status = ?, decided_at = ?, decision_note = ? WHERE id = ?",
                  ("accepted" if decision == "accept" else "rejected", now_iso(), body.note, sid))
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, f"settlement_{decision}ed", {"amount": s["amount"]})
        notify(c, _employer_id(c, claim), cid, f"settlement_{decision}ed", f"settle-{decision}:{sid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")


@router.post("/claims/{cid}/payments/{pid}/{decision}")
def decide_payment(cid: str, pid: str, decision: Literal["confirm", "dispute"], body: NoteIn,
                   user: dict = Depends(require_worker), ctx: AppContext = Depends(get_ctx)):
    from decimal import Decimal
    with ctx.db.transaction() as c:
        claim = worker_claim(c, cid, user)
        nxt = claim_state.check(f"{decision}_payment", "worker", claim["status"])
        p = c.execute("SELECT * FROM payments WHERE id = ? AND claim_id = ?", (pid, cid)).fetchone()
        if p is None:
            raise ApiError(404, "not_found", "Payment record not found.")
        if p["worker_confirmation"] != "pending":
            raise ApiError(409, "already_decided", "You have already responded to this payment record.")
        c.execute("UPDATE payments SET worker_confirmation = ?, worker_note = ? WHERE id = ?",
                  ("confirmed" if decision == "confirm" else "disputed", body.note, pid))
        if decision == "confirm":
            still_pending = c.execute("SELECT COUNT(*) FROM payments WHERE claim_id = ? AND worker_confirmation = 'pending'", (cid,)).fetchone()[0]
            confirmed = sum((Decimal(r["amount"]) for r in c.execute("SELECT amount FROM payments WHERE claim_id = ? AND worker_confirmation = 'confirmed'", (cid,))), Decimal("0"))
            acc = c.execute("SELECT amount FROM settlements WHERE claim_id = ? AND status = 'accepted' ORDER BY decided_at DESC LIMIT 1", (cid,)).fetchone()
            target = Decimal(acc["amount"]) if acc else (Decimal(claim["amount_claimed"]) if claim["amount_claimed"] else None)
            if still_pending:
                nxt = "payment_pending"
            elif target is not None and confirmed >= target:
                nxt = "resolved"
            else:
                nxt = "partially_resolved"
        c.execute("UPDATE claims SET status = ?, updated_at = ? WHERE id = ?", (nxt, now_iso(), cid))
        add_event(c, cid, user, f"payment_{decision}ed", {"amount": p["amount"]})
        notify(c, _employer_id(c, claim), cid, f"payment_{decision}ed", f"pay-{decision}:{pid}")
        return claim_view(c, worker_claim(c, cid, user), "worker")
