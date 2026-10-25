"""Deterministic wage arithmetic. No AI is ever used for money calculations."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .errors import ApiError

PAY_TYPES = ("daily", "hourly", "weekly", "monthly", "piece", "task")
UNIT_LABELS = {
    "daily": "days", "hourly": "hours", "weekly": "weeks",
    "monthly": "months", "piece": "pieces", "task": "tasks",
}
MAX_RATE = Decimal("10000000")      # ₹1 crore per unit is far beyond any real informal wage
MAX_UNITS = Decimal("100000")
MAX_PAYMENT = Decimal("1000000000")
CENT = Decimal("0.01")


def to_money(value, field: str, *, maximum: Decimal = MAX_PAYMENT, allow_zero: bool = True) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ApiError(422, "invalid_amount", f"{field} is required.", {"field": field})
    if isinstance(value, float):
        value = repr(value)
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        raise ApiError(422, "invalid_amount", f"{field} must be a number.", {"field": field})
    if not d.is_finite():
        raise ApiError(422, "invalid_amount", f"{field} must be a number.", {"field": field})
    if d < 0:
        raise ApiError(422, "invalid_amount", f"{field} cannot be negative.", {"field": field})
    if d == 0 and not allow_zero:
        raise ApiError(422, "invalid_amount", f"{field} must be more than zero.", {"field": field})
    if d > maximum:
        raise ApiError(422, "invalid_amount", f"{field} looks too large. Please check it.", {"field": field})
    return d


def money_str(d: Decimal) -> str:
    return str(d.quantize(CENT, rounding=ROUND_HALF_UP))


def calculate(pay_type: str, rate, units, payments_received) -> dict:
    if pay_type not in PAY_TYPES:
        raise ApiError(422, "invalid_pay_type", "Choose how you were paid.", {"field": "pay_type"})
    r = to_money(rate, "rate", maximum=MAX_RATE, allow_zero=False)
    u = to_money(units, "units", maximum=MAX_UNITS, allow_zero=False)
    p = to_money(payments_received, "payments_received")
    expected = (r * u).quantize(CENT, rounding=ROUND_HALF_UP)
    paid = p.quantize(CENT, rounding=ROUND_HALF_UP)
    outstanding = max(expected - paid, Decimal("0"))
    excess = max(paid - expected, Decimal("0"))
    units_s = format(u.normalize(), "f")
    return {
        "pay_type": pay_type,
        "rate": money_str(r),
        "units": units_s,
        "unit_label": UNIT_LABELS[pay_type],
        "expected_wages": money_str(expected),
        "payments_received": money_str(paid),
        "potential_outstanding": money_str(outstanding),
        "excess_payment": money_str(excess),
        "formula": f"{money_str(r)} × {units_s} {UNIT_LABELS[pay_type]} = {money_str(expected)}; "
                   f"{money_str(expected)} − {money_str(paid)} paid",
        "disclaimer": "This is an arithmetic estimate based only on the numbers you entered. It is not a legal finding.",
    }
