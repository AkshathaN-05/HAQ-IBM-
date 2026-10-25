"""Rule-based evidence consistency checks.

These are prompts for the worker to review, never verdicts. No finding means "fraud";
no score is produced; evidence is never altered or hidden because of a finding."""
from __future__ import annotations

from decimal import Decimal

from .evidence_files import find_amounts, find_dates, looks_like_instructions

MATCHES = "information_matches"
POSSIBLE = "possible_inconsistency"
REVIEW = "needs_manual_review"
UNVERIFIABLE = "unable_to_verify"
FAILED = "extraction_failed"


def run_checks(claim: dict, evidence: list[dict], calculation: dict | None) -> list[dict]:
    findings: list[dict] = []
    labels = {e["id"]: f"E{i}" for i, e in enumerate(evidence, 1)}

    def add(cls, message, ids):
        findings.append({"classification": cls, "message": message,
                         "evidence": [{"id": i, "label": labels.get(i, "?")} for i in ids]})

    # Duplicate uploads (same SHA-256)
    by_hash: dict[str, list[str]] = {}
    for e in evidence:
        by_hash.setdefault(e["sha256"], []).append(e["id"])
    for ids in by_hash.values():
        if len(ids) > 1:
            add(REVIEW, "The same file was uploaded more than once. You may want to keep only one copy shared.", ids)

    # Extraction status
    for e in evidence:
        if e["extraction_status"] == "failed":
            add(FAILED, "Text could not be read from this file. It is still attached; you can type what it shows.", [e["id"]])
        elif e["extraction_status"] == "unsupported":
            add(UNVERIFIABLE, e.get("extraction_error") or "This file type cannot be read automatically. It is still attached.", [e["id"]])
        if e["kind"] == "image":
            add(UNVERIFIABLE, "Screenshots and photos cannot show where or when they were taken. Add context if you can (who sent it, which app).", [e["id"]])
        if looks_like_instructions(e.get("extracted_text") or ""):
            add(REVIEW, "This file contains text that looks like instructions to a computer. It was treated as plain text only.", [e["id"]])

    # Amount claimed vs wage calculation
    claimed = claim.get("amount_claimed")
    if claimed and calculation:
        outstanding = Decimal(calculation["potential_outstanding"])
        if Decimal(claimed) == outstanding:
            add(MATCHES, f"The amount you are asking for (₹{claimed}) matches the wage calculation.", [])
        else:
            add(POSSIBLE, f"The amount you are asking for (₹{claimed}) is different from the wage calculation (₹{calculation['potential_outstanding']}). Please check which is right.", [])

    # Amount claimed or payments mentioned in evidence
    texted = [e for e in evidence if e.get("extracted_text")]
    if claimed and texted:
        claimed_s = f"{Decimal(claimed):.2f}"
        hits = [e["id"] for e in texted if claimed_s in find_amounts(e["extracted_text"])]
        if hits:
            add(MATCHES, f"₹{claimed} also appears in your evidence.", hits)
    if calculation and texted:
        paid = f"{Decimal(calculation['payments_received']):.2f}"
        if Decimal(paid) > 0:
            mentioning = [e["id"] for e in texted if find_amounts(e["extracted_text"])]
            hits = [e["id"] for e in texted if paid in find_amounts(e["extracted_text"])]
            if hits:
                add(MATCHES, f"The payment total you entered (₹{paid}) appears in your evidence.", hits)
            elif mentioning:
                add(POSSIBLE, f"Your evidence mentions amounts, but none equal the payment total you entered (₹{paid}). Payments may be split across several receipts — please check.", mentioning)

    # Dates in evidence outside the claim period
    start, end = claim.get("start_date"), claim.get("end_date")
    if start and end and start > end:
        add(POSSIBLE, "The start date is after the end date.", [])
    if start or end:
        for e in texted:
            outside = [d for d in find_dates(e["extracted_text"]) if (start and d < start) or (end and d > end)]
            if outside:
                add(POSSIBLE, f"This file mentions date(s) outside the period you gave ({', '.join(outside[:3])}). This may be fine — please check.", [e["id"]])
    return findings
