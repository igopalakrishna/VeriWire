import requests

BASE = "http://127.0.0.1:8000"


def _normalize_pid(payment_id: str) -> str:
    cleaned = "".join(ch for ch in payment_id if ch.isalnum())
    return cleaned.lower()


def _require_pid(payment_id: str) -> str:
    if not payment_id:
        raise ValueError("payment_id is required")
    return _normalize_pid(payment_id)


def get_payment_summary(payment_id: str):
    pid = _require_pid(payment_id)
    r = requests.get(f"{BASE}/payments/{pid}", timeout=5)
    r.raise_for_status()
    p = r.json()
    dollars = p["amount_cents"] / 100.0
    return {
        "id": p["id"],
        "payee": p["payee"],
        "amount_readable": f"${dollars:,.2f} {p['currency']}",
        "status": p["status"],
        # for verification-only; do not read full PII aloud
        "card_last4": p.get("card_last4", ""),
        "customer_phone": p.get("customer_phone", ""),
    }


def approve_wire(payment_id: str):
    pid = _require_pid(payment_id)
    r = requests.post(f"{BASE}/payments/{pid}/approve", timeout=5)
    r.raise_for_status()
    return r.json()


def cancel_wire(payment_id: str):
    pid = _require_pid(payment_id)
    r = requests.post(f"{BASE}/payments/{pid}/cancel", timeout=5)
    r.raise_for_status()
    return r.json()


def freeze_payee(payee: str):
    r = requests.post(f"{BASE}/freeze_payee", params={"payee": payee}, timeout=5)
    r.raise_for_status()
    return r.json()


def schedule_fraud_specialist(customer_phone: str):
    r = requests.post(
        f"{BASE}/schedule_specialist", params={"phone": customer_phone}, timeout=5
    )
    r.raise_for_status()
    return r.json()


FUNCTION_MAP = {
    "get_payment_summary": get_payment_summary,
    "approve_wire": approve_wire,
    "cancel_wire": cancel_wire,
    "freeze_payee": freeze_payee,
    "schedule_fraud_specialist": schedule_fraud_specialist,
}


def _normalize_phone_digits(val: str) -> str:
    digs = "".join(ch for ch in val if ch.isdigit())
    return digs[-10:] if len(digs) >= 10 else digs


def verify_last4(payment_id: str, last4: str):
    pid = _require_pid(payment_id)
    r = requests.get(f"{BASE}/payments/{pid}", timeout=5)
    r.raise_for_status()
    p = r.json()
    provided = "".join(ch for ch in last4 if ch.isdigit())
    match = (len(provided) == 4 and provided == p.get("card_last4", ""))
    return {"ok": True, "match": match}


def verify_phone(payment_id: str, phone_digits: str):
    pid = _require_pid(payment_id)
    r = requests.get(f"{BASE}/payments/{pid}", timeout=5)
    r.raise_for_status()
    p = r.json()
    expected = _normalize_phone_digits(p.get("customer_phone", ""))
    provided = _normalize_phone_digits(phone_digits)
    match = False
    if expected and provided:
        match = (provided == expected) or (len(provided) >= 7 and expected.endswith(provided)) or (provided == ("1" + expected))
    return {"ok": True, "match": match, "expected_len": len(expected)}


# Register verification helpers for the agent to call explicitly
FUNCTION_MAP.update({
    "verify_last4": verify_last4,
    "verify_phone": verify_phone,
})


