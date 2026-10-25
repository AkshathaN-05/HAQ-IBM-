"""Accounts: one identity system for both roles. The role is decided by which registration
endpoint is called and is stored server-side; it is never read from a request body."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field

from .db import new_id, now_iso
from .deps import AppContext, audit, client_ip, current_user, get_ctx, public_user
from .errors import ApiError
from .languages import UiLang
from .security import (DUMMY_HASH, hash_code, hash_password, issue_token, new_code,
                       rate_limiter, validate_password_strength, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])

CODE_TTL_MIN = 30
MAX_CODE_ATTEMPTS = 5


class RegisterBase(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\- ]{6,20}$")
    preferred_language: UiLang = "en"


class RegisterWorker(RegisterBase):
    pass


class RegisterEmployer(RegisterBase):
    business_name: str | None = Field(default=None, max_length=150)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    portal: Literal["worker", "employer"]


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=200)


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\- ]{6,20}$")
    preferred_language: UiLang | None = None
    business_name: str | None = Field(default=None, max_length=150)


def _session(ctx: AppContext, user: dict) -> dict:
    token = issue_token(ctx.settings.secret_key, user["id"], user["role"], user["token_version"], ctx.settings.token_ttl_minutes)
    return {"token": token, "user": public_user(user), "expires_in_minutes": ctx.settings.token_ttl_minutes}


def _send_code(ctx: AppContext, c: sqlite3.Connection, user: dict, purpose: str) -> str:
    code = new_code()
    # Invalidate older unused codes for the same purpose.
    c.execute("UPDATE auth_codes SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL", (now_iso(), user["id"], purpose))
    expires = (datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MIN)).isoformat()
    c.execute("INSERT INTO auth_codes(id,user_id,purpose,code_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)",
              (new_id(), user["id"], purpose, hash_code(ctx.settings.secret_key, code), expires, now_iso()))
    return code


def _mail_code(ctx: AppContext, email: str, purpose: str, code: str) -> str:
    if purpose == "verify_email":
        subject, body = "Your HAQ verification code", f"Your HAQ verification code is {code}. It expires in {CODE_TTL_MIN} minutes."
    else:
        subject, body = "Your HAQ password reset code", f"Your HAQ password reset code is {code}. It expires in {CODE_TTL_MIN} minutes. If you did not ask for this, ignore this email."
    return ctx.mailer.send(email, subject, body)


def _use_code(ctx: AppContext, c: sqlite3.Connection, user_id: str, purpose: str, code: str) -> bool:
    row = c.execute("SELECT * FROM auth_codes WHERE user_id=? AND purpose=? AND used_at IS NULL ORDER BY created_at DESC LIMIT 1",
                    (user_id, purpose)).fetchone()
    if row is None or row["expires_at"] < datetime.now(timezone.utc).isoformat() or row["attempts"] >= MAX_CODE_ATTEMPTS:
        return False
    if row["code_hash"] != hash_code(ctx.settings.secret_key, code):
        c.execute("UPDATE auth_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
        return False
    c.execute("UPDATE auth_codes SET used_at = ? WHERE id = ?", (now_iso(), row["id"]))
    return True


def _register(ctx: AppContext, request: Request, body: RegisterBase, role: str, business_name: str | None) -> dict:
    rate_limiter.check(f"register:{client_ip(request)}", 10, 3600)
    validate_password_strength(body.password)
    user = {
        "id": new_id(), "email": body.email.lower(), "password_hash": hash_password(body.password), "role": role,
        "display_name": body.display_name.strip(), "phone": (body.phone or "").strip() or None,
        "business_name": (business_name or "").strip() or None, "preferred_language": body.preferred_language,
        "email_verified_at": None, "employer_verification": "unverified", "token_version": 0, "created_at": now_iso(),
    }
    try:
        with ctx.db.transaction() as c:
            c.execute("""INSERT INTO users(id,email,password_hash,role,display_name,phone,business_name,preferred_language,
                         email_verified_at,employer_verification,token_version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      tuple(user.values()))
            code = _send_code(ctx, c, user, "verify_email")
    except sqlite3.IntegrityError:
        audit(ctx, f"register_{role}", "duplicate_email", ip=client_ip(request))
        raise ApiError(409, "email_taken", "An account with this email already exists. Please sign in instead.")
    delivery = _mail_code(ctx, user["email"], "verify_email", code)
    audit(ctx, f"register_{role}", "ok", user["id"], client_ip(request))
    out = _session(ctx, user)
    out["verification_email"] = delivery
    return out


@router.post("/register/worker", status_code=201)
def register_worker(body: RegisterWorker, request: Request, ctx: AppContext = Depends(get_ctx)):
    return _register(ctx, request, body, "worker", None)


@router.post("/register/employer", status_code=201)
def register_employer(body: RegisterEmployer, request: Request, ctx: AppContext = Depends(get_ctx)):
    return _register(ctx, request, body, "employer", body.business_name)


@router.post("/login")
def login(body: LoginIn, request: Request, ctx: AppContext = Depends(get_ctx)):
    ip = client_ip(request)
    rate_limiter.check(f"login:{ip}", 20, 900)
    rate_limiter.check(f"login-email:{body.email.lower()}", 10, 900)
    with ctx.db.connection() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
    if row is None:
        verify_password(body.password, DUMMY_HASH)  # keep timing similar
        audit(ctx, "login", "unknown_email", ip=ip)
        raise ApiError(401, "bad_credentials", "Email or password is not correct.")
    user = dict(row)
    if not verify_password(body.password, user["password_hash"]):
        audit(ctx, "login", "bad_password", user["id"], ip)
        raise ApiError(401, "bad_credentials", "Email or password is not correct.")
    if user["role"] != body.portal:
        audit(ctx, "login", "wrong_portal", user["id"], ip)
        other = "worker" if user["role"] == "worker" else "employer"
        raise ApiError(403, "wrong_portal",
                       f"This is a {other} account. Please use the {other} sign-in page.", {"account_role": user["role"]})
    audit(ctx, "login", "ok", user["id"], ip)
    return _session(ctx, user)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user)}


@router.patch("/me")
def update_me(body: ProfileIn, user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    fields = body.model_dump(exclude_unset=True)
    if "business_name" in fields and user["role"] != "employer":
        fields.pop("business_name")
    if not fields:
        return {"user": public_user(user)}
    sets = ", ".join(f"{k} = ?" for k in fields)
    with ctx.db.transaction() as c:
        c.execute(f"UPDATE users SET {sets} WHERE id = ?", (*fields.values(), user["id"]))
        row = c.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {"user": public_user(dict(row))}


@router.post("/verify-email")
def verify_email(body: CodeIn, request: Request, user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"verify:{user['id']}", 10, 900)
    if user["email_verified_at"]:
        return {"user": public_user(user)}
    with ctx.db.transaction() as c:
        ok = _use_code(ctx, c, user["id"], "verify_email", body.code)
        if ok:
            c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (now_iso(), user["id"]))
        row = c.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    audit(ctx, "verify_email", "ok" if ok else "bad_code", user["id"], client_ip(request))
    if not ok:
        raise ApiError(400, "bad_code", "That code is wrong or has expired. You can ask for a new code.")
    return {"user": public_user(dict(row))}


@router.post("/resend-verification")
def resend_verification(request: Request, user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"resend:{user['id']}", 3, 900)
    if user["email_verified_at"]:
        return {"status": "already_verified"}
    with ctx.db.transaction() as c:
        code = _send_code(ctx, c, user, "verify_email")
    return {"status": _mail_code(ctx, user["email"], "verify_email", code)}


@router.post("/forgot-password")
def forgot_password(body: EmailIn, request: Request, ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"forgot:{client_ip(request)}", 5, 900)
    with ctx.db.connection() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
    if row is not None:
        with ctx.db.transaction() as c:
            code = _send_code(ctx, c, dict(row), "reset_password")
        _mail_code(ctx, row["email"], "reset_password", code)
    audit(ctx, "forgot_password", "requested", row["id"] if row else None, client_ip(request))
    # Same answer whether or not the account exists, so emails can't be discovered.
    return {"status": "If an account exists for this email, a reset code has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, ctx: AppContext = Depends(get_ctx)):
    rate_limiter.check(f"reset:{client_ip(request)}", 10, 900)
    validate_password_strength(body.new_password)
    with ctx.db.transaction() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
        ok = row is not None and _use_code(ctx, c, row["id"], "reset_password", body.code)
        if ok:
            # Changing token_version signs out every existing session.
            c.execute("UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
                      (hash_password(body.new_password), row["id"]))
    audit(ctx, "reset_password", "ok" if ok else "bad_code", row["id"] if row else None, client_ip(request))
    if not ok:
        raise ApiError(400, "bad_code", "That code is wrong or has expired.")
    return {"status": "Password changed. Please sign in with your new password."}


@router.post("/logout-all")
def logout_all(request: Request, user: dict = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.transaction() as c:
        c.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (user["id"],))
    audit(ctx, "logout_all", "ok", user["id"], client_ip(request))
    return {"status": "Signed out on all devices."}
