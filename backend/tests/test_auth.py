from datetime import datetime, timedelta, timezone

import jwt

from conftest import latest_code, make_party


def test_register_worker_and_employer_roles_are_server_assigned(client, app):
    # A "role" field in the body is ignored: the endpoint decides the role.
    r = client.post("/api/auth/register/worker", json={"email": "w1@example.com", "password": "Passw0rd!", "display_name": "W", "role": "employer"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "worker"
    r = client.post("/api/auth/register/employer", json={"email": "e1@example.com", "password": "Passw0rd!", "display_name": "E"})
    assert r.json()["user"]["role"] == "employer"
    assert r.json()["user"]["employer_verification"] == "unverified"


def test_duplicate_email_and_weak_password(client):
    body = {"email": "dup@example.com", "password": "Passw0rd!", "display_name": "D"}
    assert client.post("/api/auth/register/worker", json=body).status_code == 201
    r = client.post("/api/auth/register/employer", json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    r = client.post("/api/auth/register/worker", json={**body, "email": "w2@example.com", "password": "abcdefgh"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "weak_password"


def test_login_and_wrong_portal(client, app):
    make_party(client, app, "worker", email="asha@example.com")
    ok = client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": "Passw0rd!", "portal": "worker"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "worker"
    wrong = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "Passw0rd!", "portal": "employer"})
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "wrong_portal"
    assert "worker account" in wrong.json()["error"]["message"]
    bad = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope12345", "portal": "worker"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Passw0rd!", "portal": "worker"})
    assert unknown.status_code == 401 and unknown.json()["error"]["code"] == bad.json()["error"]["code"]


def test_email_verification_flow(client, app):
    p = make_party(client, app, "worker", email="v@example.com", verify=False)
    assert p.user["email_verified"] is False
    bad = p.post("/api/auth/verify-email", json={"code": "000000" if latest_code(app, "v@example.com") != "000000" else "111111"})
    assert bad.status_code == 400
    r = p.post("/api/auth/resend-verification")
    assert r.json()["status"] == "logged"  # honest: console mode logs, does not claim "sent"
    r = p.post("/api/auth/verify-email", json={"code": latest_code(app, "v@example.com")})
    assert r.status_code == 200 and r.json()["user"]["email_verified"] is True


def test_verification_code_locks_after_too_many_attempts(client, app):
    p = make_party(client, app, "worker", email="lock@example.com", verify=False)
    code = latest_code(app, "lock@example.com")
    wrong = "999999" if code != "999999" else "888888"
    for _ in range(5):
        p.post("/api/auth/verify-email", json={"code": wrong})
    assert p.post("/api/auth/verify-email", json={"code": code}).status_code == 400


def test_password_reset_signs_out_old_sessions(client, app):
    p = make_party(client, app, "worker", email="reset@example.com")
    assert p.get("/api/auth/me").status_code == 200
    r = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    # Same answer for unknown emails (no account discovery)
    r2 = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert r2.json() == r.json()
    code = latest_code(app, "reset@example.com")
    r = client.post("/api/auth/reset-password", json={"email": "reset@example.com", "code": code, "new_password": "NewPassw0rd"})
    assert r.status_code == 200
    assert p.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewPassw0rd", "portal": "worker"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"email": "reset@example.com", "code": code, "new_password": "Another1x"}).status_code == 400


def test_logout_all_invalidates_tokens(client, app):
    p = make_party(client, app, "employer")
    assert p.post("/api/auth/logout-all").status_code == 200
    assert p.get("/api/auth/me").status_code == 401


def test_expired_and_tampered_tokens(client, app, settings):
    p = make_party(client, app, "worker")
    claims = jwt.decode(p.token, settings.secret_key, algorithms=["HS256"], issuer="haq")
    expired = jwt.encode({**claims, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, settings.secret_key, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_expired"
    # Role escalation attempt: forge a token claiming employer role with the wrong key
    forged = jwt.encode({**claims, "role": "employer"}, "attacker-key-" + "y" * 40, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    # Even a validly-signed token's role claim is ignored: the role comes from the database.
    relabelled = jwt.encode({**claims, "role": "employer"}, settings.secret_key, algorithm="HS256")
    r = client.get("/api/employer/claims", headers={"Authorization": f"Bearer {relabelled}"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal"
    assert client.get("/api/auth/me").status_code == 401


def test_portal_enforcement_on_endpoints(client, app, worker, employer):
    assert worker.get("/api/employer/claims").json()["error"]["code"] == "wrong_portal"
    assert employer.get("/api/claims").json()["error"]["code"] == "wrong_portal"
    assert employer.post("/api/claims", json={"description": "x"}).status_code == 403


def test_profile_update_cannot_change_role(client, app, worker):
    r = worker.patch("/api/auth/me", json={"preferred_language": "kn", "role": "employer", "business_name": "X"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "worker"
    assert r.json()["user"]["preferred_language"] == "kn"
    assert r.json()["user"]["business_name"] is None


def test_unverified_employer_cannot_view_claims(client, app):
    p = make_party(client, app, "employer", verify=False)
    r = p.get("/api/employer/claims")
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"


def test_rate_limit_on_login(client, app):
    from app.security import rate_limiter
    rate_limiter.enabled = True
    rate_limiter.reset()
    codes = [client.post("/api/auth/login", json={"email": "rl@example.com", "password": "x", "portal": "worker"}).status_code for _ in range(12)]
    assert 429 in codes
    rate_limiter.enabled = False
