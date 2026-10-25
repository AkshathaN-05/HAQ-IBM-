"""Password hashing, session tokens, one-time codes and rate limiting."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt

from .errors import ApiError

# --- Passwords (scrypt from the standard library) -------------------------------------------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# A hash used to keep sign-in timing similar when the email does not exist.
DUMMY_HASH = hash_password(secrets.token_hex(8))


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ApiError(422, "weak_password", "Password must be at least 8 characters.")
    if len(password) > 200:
        raise ApiError(422, "weak_password", "Password is too long.")
    if password.isdigit() or password.isalpha():
        raise ApiError(422, "weak_password", "Use a mix of letters and numbers.")


# --- Session tokens (JWT, HS256) ------------------------------------------------------------

def issue_token(secret: str, user_id: str, role: str, token_version: int, ttl_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,  # informational only; the server always re-reads the role from the database
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "iss": "haq",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(secret: str, token: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], issuer="haq",
                          options={"require": ["exp", "iat", "sub", "iss"]})
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "session_expired", "Your session has expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise ApiError(401, "invalid_session", "Please sign in again.")


# --- One-time codes ---------------------------------------------------------------------------

def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(secret: str, code: str) -> str:
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()


# --- Rate limiting (in-memory, per process) -------------------------------------------------

class RateLimiter:
    """Sliding-window limiter. Good enough for a single-process deployment; use a shared
    store (e.g. Redis) when running several instances."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.enabled = True

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise ApiError(429, "rate_limited", "Too many attempts. Please wait a few minutes and try again.")
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()
