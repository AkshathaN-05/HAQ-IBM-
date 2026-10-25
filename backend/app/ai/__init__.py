"""Complaint drafting.

The AI's job is limited on purpose: it writes only the short *narrative* paragraph of the
complaint in plain, neutral language. Everything else — reference, parties, amounts and the
wage calculation, the evidence index, the disclaimer — is assembled by deterministic code.
AI output is validated; if it contains amounts or dates that are not in the worker's own
information, or is not valid JSON, it is rejected and the template narrative is used instead.
"""
from .drafting import ClaimFacts, DraftResult, build_provider, draft_complaint  # noqa: F401
