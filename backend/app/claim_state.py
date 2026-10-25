"""Claim status state machine. Only these transitions are possible, and each action is
restricted to one role. Clients never set a status directly."""
from __future__ import annotations

from .errors import ApiError

STATUSES = [
    "draft", "submitted", "acknowledged", "under_review", "info_requested", "response_received",
    "settlement_offered", "settlement_accepted", "payment_pending", "partially_resolved",
    "resolved", "disputed", "withdrawn",
]
OPEN_AFTER_SUBMIT = {"submitted", "acknowledged", "under_review", "info_requested", "response_received",
                     "settlement_offered", "settlement_accepted", "payment_pending", "partially_resolved", "disputed"}
TERMINAL = {"resolved", "withdrawn"}

# action -> (role, allowed current statuses, next status or None if computed by caller)
TRANSITIONS: dict[str, tuple[str, set[str], str | None]] = {
    "submit":            ("worker",   {"draft"}, "submitted"),
    "withdraw":          ("worker",   {"draft"} | OPEN_AFTER_SUBMIT, "withdrawn"),
    "worker_reply":      ("worker",   OPEN_AFTER_SUBMIT, None),  # info_requested -> under_review, else unchanged
    "close_resolved":    ("worker",   OPEN_AFTER_SUBMIT, "resolved"),
    "accept_settlement": ("worker",   {"settlement_offered"}, "settlement_accepted"),
    "reject_settlement": ("worker",   {"settlement_offered"}, "disputed"),
    "confirm_payment":   ("worker",   {"payment_pending"}, None),  # resolved or partially_resolved
    "dispute_payment":   ("worker",   {"payment_pending"}, "disputed"),
    "acknowledge":       ("employer", {"submitted"}, "acknowledged"),
    "employer_message":  ("employer", {"submitted", "acknowledged", "under_review", "info_requested", "response_received", "disputed", "partially_resolved"}, None),
    "offer_settlement":  ("employer", {"submitted", "acknowledged", "under_review", "info_requested", "response_received", "disputed", "settlement_offered"}, "settlement_offered"),
    "record_payment":   ("employer", {"submitted", "acknowledged", "under_review", "info_requested", "response_received", "settlement_offered", "settlement_accepted", "partially_resolved", "disputed", "payment_pending"}, "payment_pending"),
}


def check(action: str, role: str, current: str) -> str | None:
    spec = TRANSITIONS.get(action)
    if spec is None:
        raise ApiError(400, "unknown_action", "Unknown action.")
    needed_role, allowed, nxt = spec
    if role != needed_role:
        raise ApiError(403, "forbidden", "You are not allowed to do this on this claim.")
    if current not in allowed:
        raise ApiError(409, "invalid_status", f"This can't be done while the claim is '{current.replace('_', ' ')}'.",
                       {"status": current, "action": action})
    return nxt
