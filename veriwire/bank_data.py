from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from typing import Dict, Optional, Literal


@dataclass
class Payment:
    id: str
    customer_phone: str
    card_last4: str
    payee: str
    amount_cents: int
    currency: str = "USD"
    status: Literal["PENDING", "APPROVED", "CANCELED"] = "PENDING"
    created_at: str = ""

    def to_json(self) -> Dict:
        return asdict(self)


class BankDB:
    def __init__(self) -> None:
        self._payments: Dict[str, Payment] = {
            # realistic demo transactions (short alphanumeric IDs, stored lowercase)
            "09ne482130": Payment(
                id="09ne482130",
                customer_phone="+14155550123",
                card_last4="4242",
                payee="NorthEast Home Title LLC",
                amount_cents=4215000,
                created_at=datetime.now(UTC).isoformat(),
            ),
            "10sf917264": Payment(
                id="10sf917264",
                customer_phone="+14155550123",
                card_last4="1111",
                payee="ACME Escrow LLC",
                amount_cents=970000,
                created_at=datetime.now(UTC).isoformat(),
            ),
            "10ny331842": Payment(
                id="10ny331842",
                customer_phone="+13475550199",
                card_last4="9999",
                payee="Metro Equip Suppliers Inc",
                amount_cents=1289000,
                created_at=datetime.now(UTC).isoformat(),
            ),
        }
        # Backward-compatible aliases to the same records for older/uppercase IDs
        self._payments["WIRE202509NE482130"] = self._payments["09ne482130"]
        self._payments["WIRE202510SF917264"] = self._payments["10sf917264"]
        self._payments["WIRE202510NY331842"] = self._payments["10ny331842"]
        self._payments["09NE482130"] = self._payments["09ne482130"]
        self._payments["10SF917264"] = self._payments["10sf917264"]
        self._payments["10NY331842"] = self._payments["10ny331842"]
        # Demo convenience aliases
        self._payments["pending_wire_id"] = self._payments["10sf917264"]
        self._payments["pending_payment"] = self._payments["10sf917264"]

    def seed(self) -> None:
        # No-op: preloaded with realistic entries above
        return None

    def get_payment(self, pid: str) -> Optional[Payment]:
        return self._payments.get(pid)

    def approve(self, pid: str) -> Payment:
        p = self._require(pid)
        if p.status != "PENDING":
            return p
        p.status = "APPROVED"
        self._payments[p.id] = p
        return p

    def cancel(self, pid: str) -> Payment:
        p = self._require(pid)
        if p.status != "PENDING":
            return p
        p.status = "CANCELED"
        self._payments[p.id] = p
        return p

    def _require(self, pid: str) -> Payment:
        p = self._payments.get(pid)
        if not p:
            raise KeyError(pid)
        return p


DB = BankDB()

