"""Request context, authentication dependencies and shared helpers."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Request

from .ai.providers import BaseProvider
from .config import Settings
from .db import Database, new_id, now_iso
from .errors import ApiError
from .mailer import Mailer
from .security import decode_token

log = logging.getLogger("haq")


@dataclass
class AppContext:
    settings: Settings
    db: Database
    mailer: Mailer
    ai: BaseProvider


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def current_user(request: Request, ctx: AppContext = Depends(get_ctx)) -> dict:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise ApiError(401, "not_signed_in", "Please sign in.")
    claims = decode_token(ctx.settings.secret_key, header[7:].strip())
    try:
        with ctx.db.connection() as c:
            row = c.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
    except sqlite3.Error:
        raise ApiError(503, "database_unavailable", "The service is temporarily unavailable. Please try again shortly.")
    if row is None or row["token_version"] != claims.get("ver"):
        raise ApiError(401, "invalid_session", "Please sign in again.")
    return dict(row)


def require_worker(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "worker":
        raise ApiError(403, "wrong_portal", "This page is for workers. You are signed in with an employer account.")
    return user


def require_employer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "employer":
        raise ApiError(403, "wrong_portal", "This page is for employers. You are signed in with a worker account.")
    return user


def require_verified_employer(user: dict = Depends(require_employer)) -> dict:
    if not user["email_verified_at"]:
        raise ApiError(403, "email_not_verified", "Please verify your email address first. Claims are only shown to verified email owners.")
    return user


def public_user(u: dict) -> dict:
    return {
        "id": u["id"], "email": u["email"], "role": u["role"], "display_name": u["display_name"],
        "phone": u.get("phone"), "business_name": u.get("business_name"),
        "preferred_language": u["preferred_language"], "email_verified": bool(u["email_verified_at"]),
        "employer_verification": u["employer_verification"] if u["role"] == "employer" else None,
    }


# --- History, notifications, audit ---------------------------------------------------------

def add_event(c: sqlite3.Connection, claim_id: str, actor: dict | None, type_: str, detail: dict | None = None) -> None:
    c.execute(
        "INSERT INTO claim_events(id, claim_id, actor_id, actor_role, type, detail, created_at) VALUES (?,?,?,?,?,?,?)",
        (new_id(), claim_id, actor["id"] if actor else None, actor["role"] if actor else "system", type_,
         json.dumps(detail, ensure_ascii=False) if detail else None, now_iso()),
    )


def notify(c: sqlite3.Connection, user_id: str | None, claim_id: str, type_: str, dedupe_key: str) -> None:
    if not user_id:
        return
    c.execute(
        "INSERT OR IGNORE INTO notifications(id, user_id, claim_id, type, dedupe_key, created_at) VALUES (?,?,?,?,?,?)",
        (new_id(), user_id, claim_id, type_, dedupe_key, now_iso()),
    )


def audit(ctx: AppContext, action: str, outcome: str, user_id: str | None = None, ip: str | None = None, detail: str | None = None) -> None:
    try:
        with ctx.db.connection() as c:
            c.execute("INSERT INTO audit_log(id, user_id, action, outcome, ip, detail, created_at) VALUES (?,?,?,?,?,?,?)",
                      (new_id(), user_id, action, outcome, ip, detail, now_iso()))
    except sqlite3.Error:
        log.warning("Could not write audit event %s", action)
