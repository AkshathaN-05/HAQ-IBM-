import uuid

from conftest import full_draft, make_party, submit


def upload(party, url, name, data):
    return party.post(url, files={"file": (name, data, "application/octet-stream")})


def submitted_claim(worker, employer, share_first=True):
    cid = full_draft(worker, employer.user["email"])
    e1 = upload(worker, f"/api/claims/{cid}/evidence", "shared.txt", b"Paid Rs 8000").json()["id"]
    e2 = upload(worker, f"/api/claims/{cid}/evidence", "private.txt", b"my private note").json()["id"]
    worker.post(f"/api/claims/{cid}/draft")
    r = submit(worker, cid, shared=[e1] if share_first else [])
    assert r.status_code == 200, r.text
    return cid, e1, e2


def test_employer_sees_only_addressed_claims_and_shared_evidence(client, app, worker, employer):
    cid, shared, private = submitted_claim(worker, employer)
    inbox = employer.get("/api/employer/claims").json()
    assert inbox["total"] == 1 and inbox["items"][0]["id"] == cid
    view = employer.get(f"/api/employer/claims/{cid}").json()
    assert [e["id"] for e in view["evidence"]] == [shared]
    assert "private_notes" not in view and "description" not in view and "checks" not in view
    assert "extracted_text" not in view["evidence"][0]
    assert all(t["type"] not in ("draft_created", "evidence_added", "complaint_drafted") for t in view["timeline"])
    assert employer.get(f"/api/evidence/{shared}/download").status_code == 200
    assert employer.get(f"/api/evidence/{private}/download").status_code == 404
    # Another employer sees nothing and cannot guess IDs
    other = make_party(client, app, "employer")
    assert other.get("/api/employer/claims").json()["total"] == 0
    assert other.get(f"/api/employer/claims/{cid}").status_code == 404
    assert other.get(f"/api/evidence/{shared}/download").status_code == 404
    assert other.get(f"/api/evidence/{uuid.uuid4()}/download").status_code == 404


def test_drafts_are_invisible_to_employer(client, app, worker, employer):
    cid = full_draft(worker, employer.user["email"])
    assert employer.get("/api/employer/claims").json()["total"] == 0
    assert employer.get(f"/api/employer/claims/{cid}").status_code == 404


def test_unverified_employer_with_matching_email_sees_nothing(client, app, worker):
    emp = make_party(client, app, "employer", email="boss@example.com", verify=False)
    cid = full_draft(worker, "boss@example.com")
    submit(worker, cid)
    assert emp.get(f"/api/employer/claims/{cid}").status_code == 403


def test_worker_isolation(client, app, worker, employer):
    cid, shared, _ = submitted_claim(worker, employer)
    other = make_party(client, app, "worker")
    assert other.get(f"/api/claims/{cid}").status_code == 404
    assert other.patch(f"/api/claims/{cid}", json={"private_notes": "x"}).status_code == 404
    assert other.get(f"/api/evidence/{shared}/download").status_code == 404
    assert other.get(f"/api/claims/{cid}/export").status_code == 404
    assert other.get("/api/claims").json()["total"] == 0


def test_employer_cannot_modify_claim_or_evidence(client, app, worker, employer):
    cid, shared, _ = submitted_claim(worker, employer)
    assert employer.patch(f"/api/claims/{cid}", json={"amount_claimed": "1"}).status_code == 403
    assert employer.patch(f"/api/claims/{cid}/evidence/{shared}", json={"extracted_text": "x"}).status_code == 403
    assert employer.post(f"/api/claims/{cid}/close", json={}).status_code == 403
    # Employer cannot accept their own offer or confirm their own payment
    employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "6000"})
    sid = employer.get(f"/api/employer/claims/{cid}").json()["settlements"][0]["id"]
    assert employer.post(f"/api/claims/{cid}/settlements/{sid}/accept", json={}).status_code == 403


def test_full_resolution_flow(client, app, worker, employer):
    cid, _, _ = submitted_claim(worker, employer)
    r = employer.post(f"/api/employer/claims/{cid}/acknowledge")
    assert r.json()["status"] == "acknowledged"
    r = employer.post(f"/api/employer/claims/{cid}/messages", json={"kind": "question", "body": "Which dates were you absent?"})
    assert r.json()["status"] == "info_requested"
    r = worker.post(f"/api/claims/{cid}/messages", json={"body": "I was not absent on any day."})
    assert r.json()["status"] == "under_review"
    att = upload(employer, f"/api/employer/claims/{cid}/attachments", "register.pdf", b"%PDF-1.4\n%%EOF")
    assert att.status_code == 201
    w = worker.get(f"/api/claims/{cid}").json()
    assert w["employer_attachments"][0]["original_name"] == "register.pdf"
    assert worker.get(f"/api/evidence/{att.json()['id']}/download").status_code == 200
    key = uuid.uuid4().hex
    r = employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "6400", "explanation": "Full amount"}, headers={"Idempotency-Key": key})
    assert r.json()["status"] == "settlement_offered"
    employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "6400"}, headers={"Idempotency-Key": key})
    assert len(employer.get(f"/api/employer/claims/{cid}").json()["settlements"]) == 1
    sid = worker.get(f"/api/claims/{cid}").json()["settlements"][0]["id"]
    r = worker.post(f"/api/claims/{cid}/settlements/{sid}/accept", json={"note": "OK"})
    assert r.json()["status"] == "settlement_accepted"
    rec = upload(employer, f"/api/employer/claims/{cid}/attachments", "upi.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).json()["id"]
    r = employer.post(f"/api/employer/claims/{cid}/payments", json={"amount": "6400", "paid_on": "2026-10-01", "reference": "UPI123", "receipt_evidence_id": rec, "settlement_id": sid})
    assert r.status_code == 201
    assert r.json()["status"] == "payment_pending"  # employer's word alone does not resolve the claim
    pid = r.json()["payments"][0]["id"]
    r = worker.post(f"/api/claims/{cid}/payments/{pid}/confirm", json={})
    assert r.json()["status"] == "resolved"
    assert worker.post(f"/api/claims/{cid}/payments/{pid}/confirm", json={}).status_code == 409
    # Notifications reached the worker for each meaningful event
    types = {n["type"] for n in worker.get("/api/notifications").json()["items"]}
    assert {"acknowledged", "employer_replied", "settlement_offered", "payment_recorded"} <= types


def test_partial_payment_and_dispute(client, app, worker, employer):
    cid, _, _ = submitted_claim(worker, employer)
    r = employer.post(f"/api/employer/claims/{cid}/payments", json={"amount": "3000", "paid_on": "2026-10-01"})
    pid = r.json()["payments"][0]["id"]
    r = worker.post(f"/api/claims/{cid}/payments/{pid}/confirm", json={})
    assert r.json()["status"] == "partially_resolved"  # 3000 of 6400 claimed
    r = employer.post(f"/api/employer/claims/{cid}/payments", json={"amount": "3400", "paid_on": "2026-10-02"})
    pid2 = [p for p in r.json()["payments"] if p["id"] != pid][0]["id"]
    r = worker.post(f"/api/claims/{cid}/payments/{pid2}/dispute", json={"note": "I only got 2000"})
    assert r.json()["status"] == "disputed"


def test_reject_offer_and_invalid_transitions(client, app, worker, employer):
    cid, _, _ = submitted_claim(worker, employer)
    sid_missing = str(uuid.uuid4())
    assert worker.post(f"/api/claims/{cid}/settlements/{sid_missing}/accept", json={}).status_code == 409  # not in settlement_offered
    employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "2000"})
    sid = worker.get(f"/api/claims/{cid}").json()["settlements"][0]["id"]
    r = worker.post(f"/api/claims/{cid}/settlements/{sid}/reject", json={"note": "Too low"})
    assert r.json()["status"] == "disputed"
    assert employer.post(f"/api/employer/claims/{cid}/acknowledge").status_code == 409
    r = employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "5000"})
    assert r.json()["status"] == "settlement_offered"
    statuses = [s["status"] for s in r.json()["settlements"]]
    assert statuses == ["rejected", "offered"]
    bad = employer.post(f"/api/employer/claims/{cid}/settlements", json={"amount": "0"})
    assert bad.status_code == 422
    assert employer.post(f"/api/employer/claims/{cid}/payments", json={"amount": "10", "paid_on": "2999-01-01"}).status_code == 422


def test_withdrawn_claim_is_closed(client, app, worker, employer):
    cid, _, _ = submitted_claim(worker, employer)
    assert worker.post(f"/api/claims/{cid}/withdraw", json={}).json()["status"] == "withdrawn"
    assert employer.post(f"/api/employer/claims/{cid}/messages", json={"kind": "response", "body": "x"}).status_code == 409
    assert employer.get(f"/api/employer/claims/{cid}").json()["status"] == "withdrawn"


def test_share_more_evidence_after_submit_but_not_unshare(client, app, worker, employer):
    cid, shared, private = submitted_claim(worker, employer)
    r = worker.patch(f"/api/claims/{cid}/evidence/{private}", json={"shared_with_employer": True})
    assert r.status_code == 200
    assert employer.get(f"/api/evidence/{private}/download").status_code == 200
    r = worker.patch(f"/api/claims/{cid}/evidence/{shared}", json={"shared_with_employer": False})
    assert r.status_code == 409


def test_employer_registering_later_sees_claim(client, app, worker):
    cid = full_draft(worker, "later@example.com")
    submit(worker, cid)
    emp = make_party(client, app, "employer", email="later@example.com")
    assert emp.get("/api/employer/claims").json()["total"] == 1
