from typing import TypedDict, Optional, Literal, Dict

from langgraph.graph import StateGraph, END

from veriwire.dfdetect import DeepfakeDetector
from veriwire.bank_tools import (
    get_payment_summary,
    approve_wire,
    cancel_wire,
    freeze_payee,
    schedule_fraud_specialist,
)


class S(TypedDict, total=False):
    user_text: str
    say: str
    verified: bool
    phrase: str
    payment_id: str
    customer_phone: str
    card_last4: str
    phone_verified: bool
    target_phone_digits: str
    intent: Optional[Literal["approve", "cancel", "escalate", "unknown"]]
    df_flag: bool
    summary: Optional[Dict]
    _df: DeepfakeDetector


def make_phrase() -> str:
    import random

    return f"{random.choice(['blue','silver','green','orange','violet'])} {random.choice(['cedar','harbor','atlas','falcon','delta'])} {random.randint(10,99)}"


def _extract_digits_spoken(text: str) -> str:
    mapping = {
        "zero": "0", "oh": "0", "o": "0",
        "one": "1", "two": "2", "three": "3", "four": "4", "for": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    }
    tokens = text.lower().replace("-", " ").split()
    digits = []
    for tok in tokens:
        if tok.isdigit():
            digits.extend(list(tok))
            continue
        if tok in mapping:
            digits.append(mapping[tok])
    return "".join(digits)


def verify_human(state: S) -> S:
    if not state.get("phrase"):
        state["phrase"] = make_phrase()
        state["say"] = f"Please say exactly: '{state['phrase']}'"
        return state

    ok = all(tok in state.get("user_text", "").lower() for tok in state["phrase"].lower().split())
    if ok:
        state["verified"] = True
        state["say"] = ""
    else:
        state["phrase"] = make_phrase()
        state["say"] = f"Let's try again. Please say: '{state['phrase']}'"
    return state


def dfcheck(state: S) -> S:
    det = state.get("_df") or DeepfakeDetector()
    suspicious, score = det.is_suspicious()
    state["_df"] = det
    state["df_flag"] = bool(suspicious)
    return state


def explain(state: S) -> S:
    if state.get("summary") is None:
        state["summary"] = get_payment_summary(state["payment_id"])
    payee = state["summary"]["payee"]
    amt = state["summary"]["amount_readable"]
    # copy verification fields locally
    state["card_last4"] = state["summary"].get("card_last4", "")
    state["customer_phone"] = state["summary"].get("customer_phone", "")
    # normalize phone to last 10 digits target
    # Stored phone comes formatted (+1, dashes). Normalize by stripping non-digits.
    digits_phone = "".join(ch for ch in state["customer_phone"] if ch.isdigit()) or ""
    state["target_phone_digits"] = digits_phone[-10:] if len(digits_phone) >= 10 else digits_phone
    # If payment is already not pending, short-circuit
    status = (state["summary"].get("status") or "").upper()
    if status and status != "PENDING":
        state["say"] = f"This payment is already {status}. If you need help, I can connect you to a specialist."
        return state

    state["say"] = "Before we proceed, please confirm the last four digits of the card used on this payment."
    return state


def understand(state: S) -> S:
    text = state.get("user_text", "").lower().strip()
    # If we don't have last-4 yet, try to capture it first (only digits)
    if not state.get("verified") and state.get("card_last4"):
        digits = _extract_digits_spoken(text)
        if len(digits) == 4 and digits == state["card_last4"]:
            state["verified"] = True
            state["say"] = "Thanks. Now please say the phone number you are calling from."
            return state
        else:
            state["say"] = "I didn't get that. Please say just the last four digits."
            return state

    # After last-4, confirm phone number matches
    if state.get("verified") and not state.get("phone_verified"):
        expected = state.get("target_phone_digits", "")
        provided = _extract_digits_spoken(text)
        # Accept match if full last-10 provided, or if they provide a suffix of at least 7 digits matching the expected tail
        if expected and provided and (provided == expected or (len(provided) >= 7 and expected.endswith(provided)) or (provided == ("1" + expected))):
            state["phone_verified"] = True
            state["say"] = "Thanks. Do you approve or cancel this payment?"
            return state
        else:
            state["say"] = "I didn't catch that. Please say the phone digits, for example 'four one five…'"
            return state

    if text == "1" or "approve" in text:
        state["intent"] = "approve"
    elif text == "2" or "cancel" in text or "decline" in text:
        state["intent"] = "cancel"
    else:
        state["intent"] = "unknown"
        state["say"] = "Please say approve or cancel."
    return state


def act(state: S) -> S:
    pid = state["payment_id"]
    phone = state["customer_phone"]
    summary = state.get("summary") or {}

    if state.get("df_flag"):
        try:
            freeze_payee(summary.get("payee", "Unknown"))
        finally:
            schedule_fraud_specialist(phone)
        state["say"] = "I'm detecting an issue with this line. Transferring you to a fraud specialist now."
        return state

    if state.get("intent") == "approve":
        res = approve_wire(pid)
        state["say"] = f"Approved. Confirmation {res['id']}. Goodbye."
    elif state.get("intent") == "cancel":
        res = cancel_wire(pid)
        state["say"] = f"Canceled. Ticket {res['id']}. Goodbye."
    return state


g = StateGraph(S)
g.add_node("VerifyHuman", verify_human)
g.add_node("DFCheck", dfcheck)
g.add_node("Explain", explain)
g.add_node("Understand", understand)
g.add_node("Act", act)
g.set_entry_point("VerifyHuman")
g.add_edge("VerifyHuman", "DFCheck")
g.add_conditional_edges(
    "DFCheck",
    lambda s: "Explain" if s.get("verified") else "VerifyHuman",
    {"Explain": "Explain", "VerifyHuman": "VerifyHuman"},
)
g.add_edge("Explain", "Understand")
g.add_conditional_edges(
    "Understand",
    lambda s: "Act" if s.get("intent") in {"approve", "cancel"} else "Explain",
    {"Act": "Act", "Explain": "Explain"},
)
g.add_edge("Act", END)
graph_app = g.compile()


