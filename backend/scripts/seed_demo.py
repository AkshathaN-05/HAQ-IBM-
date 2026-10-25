"""Create clearly-labelled DEMO accounts and one DEMO claim for presentations.

Usage (from the backend folder):  python scripts/seed_demo.py
Safe to run more than once: it does nothing if the demo accounts already exist.
Refuses to run when APP_ENV=production.

Every demo record is labelled "DEMO" so it cannot be mistaken for a real claim.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security import rate_limiter  # noqa: E402

WORKER = {"email": "demo.worker@haq.example", "password": "DemoWorker123", "display_name": "Asha",
          "phone": "9000000001", "preferred_language": "en"}
EMPLOYER = {"email": "demo.employer@haq.example", "password": "DemoEmployer123", "display_name": "Ravi Kumar",
            "business_name": "Kumar Builders", "preferred_language": "en"}


def main() -> None:
    settings = load_settings()
    if settings.app_env == "production":
        sys.exit("Refusing to create demo data in production.")
    app = create_app(settings)
    rate_limiter.enabled = False
    c = TestClient(app)
    db = app.state.ctx.db
    with db.connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (WORKER["email"],)).fetchone():
            print("Demo data already exists. Nothing to do.")
            return

    def register(role, body):
        r = c.post(f"/api/auth/register/{role}", json=body)
        r.raise_for_status()
        token = r.json()["token"]
        with db.connection() as conn:  # demo accounts are marked verified directly
            conn.execute("UPDATE users SET email_verified_at = created_at WHERE email = ?", (body["email"],))
        return {"Authorization": f"Bearer {token}"}

    w = register("worker", WORKER)
    register("employer", EMPLOYER)

    eng = c.post("/api/worker/engagements", headers=w, json={
        "employer_name": "Kumar Builders", "work_type": "Construction helper", "pay_type": "daily",
        "rate": "800", "units": "18", "payments_received": "8000",
        "start_date": "2026-09-01", "end_date": "2026-09-20", "notes": "DEMO record"}).json()

    claim = c.post("/api/claims", headers=w, json={"language": "en", "description":
        "I worked 18 days as a helper at the Kumar Builders site from 1 to 20 September. "
        "We agreed Rs 800 per day. I was paid Rs 8000 on 5 September and nothing after that."}).json()
    cid = claim["id"]
    c.patch(f"/api/claims/{cid}", headers=w, json={
        "employer_name": "Kumar Builders", "employer_email": EMPLOYER["email"], "work_type": "Construction helper",
        "start_date": "2026-09-01", "end_date": "2026-09-20", "amount_claimed": "6400",
        "requested_outcome": "Please pay the remaining wages of Rs 6400.", "engagement_id": eng["id"]})
    files = [
        ("demo-whatsapp-chat.txt", "[DEMO] Ravi (05/09/2026): Paid Rs 8000 today by UPI. Will pay the rest after the slab work.\n"
                                   "Asha (21/09/2026): Sir, the remaining Rs 6400 is still pending.".encode()),
        ("demo-attendance.txt", "[DEMO] Attendance September 2026 — Asha\nDays present: 18\nRate: Rs 800/day".encode()),
    ]
    ev_ids = []
    for name, data in files:
        r = c.post(f"/api/claims/{cid}/evidence", headers=w, files={"file": (name, data, "text/plain")})
        r.raise_for_status()
        ev_ids.append(r.json()["id"])
    d = c.post(f"/api/claims/{cid}/draft", headers=w).json()
    print("DEMO claim drafted with:", d["draft"]["provider"])
    print("\nDemo accounts (DEMO data only):")
    print(f"  Worker   — {WORKER['email']} / {WORKER['password']}")
    print(f"  Employer — {EMPLOYER['email']} / {EMPLOYER['password']}")
    print("The demo claim is saved as a DRAFT so you can show the review-and-send step live.")


if __name__ == "__main__":
    main()
