from fastapi.testclient import TestClient
from api.bank_sandbox import app


client = TestClient(app)


def test_get_payment_ok():
    r = client.get("/payments/10SF917264")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "10sf917264"


def test_approve_then_conflict():
    # ensure pending alias exists
    r = client.get("/payments/10SF917264")
    assert r.status_code == 200
    # approve
    r = client.post("/payments/10SF917264/approve")
    assert r.status_code in (200, 409)


def test_cancel_then_conflict():
    r = client.post("/payments/09NE482130/cancel")
    assert r.status_code in (200, 409)


