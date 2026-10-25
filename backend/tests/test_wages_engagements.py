from app import wages


def test_brief_example(client):
    r = client.post("/api/wage-calculation", json={"pay_type": "daily", "rate": "800", "units": "18", "payments_received": "8000"})
    assert r.status_code == 200
    d = r.json()
    assert d["expected_wages"] == "14400.00"
    assert d["potential_outstanding"] == "6400.00"
    assert d["excess_payment"] == "0.00"
    assert "not a legal finding" in d["disclaimer"]


def test_excess_payment_and_rounding():
    d = wages.calculate("hourly", "87.335", "10.5", "1000")
    assert d["expected_wages"] == "917.02"  # 917.0175 -> half-up to 2dp
    assert d["excess_payment"] == "82.98"
    assert d["potential_outstanding"] == "0.00"
    assert wages.calculate("piece", "2.5", "100", "0")["expected_wages"] == "250.00"
    assert wages.calculate("monthly", "15,000", "3", "30000")["potential_outstanding"] == "15000.00"
    assert wages.calculate("daily", "500", "100", "0")["units"] == "100"


def test_invalid_inputs(client):
    for body, code in [
        ({"pay_type": "daily", "rate": "-1", "units": "1"}, "invalid_amount"),
        ({"pay_type": "daily", "rate": "abc", "units": "1"}, "invalid_amount"),
        ({"pay_type": "daily", "rate": "800", "units": "0"}, "invalid_amount"),
        ({"pay_type": "daily", "rate": "99999999999", "units": "1"}, "invalid_amount"),
        ({"pay_type": "daily", "rate": "NaN", "units": "1"}, "invalid_amount"),
    ]:
        r = client.post("/api/wage-calculation", json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["code"] == code
    r = client.post("/api/wage-calculation", json={"pay_type": "yearly", "rate": "1", "units": "1"})
    assert r.status_code == 422


def test_engagements_crud_and_isolation(client, app, worker):
    from conftest import make_party
    body = {"employer_name": "Mehta family", "work_type": "Cook", "pay_type": "monthly", "rate": "9000", "units": "2",
            "payments_received": "12000", "start_date": "2026-07-01", "end_date": "2026-08-31"}
    r = worker.post("/api/worker/engagements", json=body)
    assert r.status_code == 201
    e = r.json()
    assert e["calculation"]["potential_outstanding"] == "6000.00"
    r = worker.put(f"/api/worker/engagements/{e['id']}", json={**body, "payments_received": "18000"})
    assert r.json()["calculation"]["potential_outstanding"] == "0.00"
    assert worker.get("/api/worker/engagements").json()["total"] == 1
    other = make_party(client, app, "worker")
    assert other.get("/api/worker/engagements").json()["total"] == 0
    assert other.put(f"/api/worker/engagements/{e['id']}", json=body).status_code == 404
    bad = worker.post("/api/worker/engagements", json={**body, "start_date": "2026-02-30"})
    assert bad.status_code == 422
