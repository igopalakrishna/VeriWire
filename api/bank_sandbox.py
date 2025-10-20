from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
from datetime import datetime
import uvicorn
import uuid
from contextlib import asynccontextmanager

from veriwire.bank_data import DB, Payment


def _seed() -> None:
    DB.seed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed()
    yield


app = FastAPI(title="VeriWire Bank Sandbox", lifespan=lifespan)


@app.get("/payments/{pid}")
def get_payment(pid: str):
    p = DB.get_payment(pid)
    if not p:
        raise HTTPException(404)
    return p.to_json()


@app.post("/payments/{pid}/approve")
def approve_payment(pid: str):
    try:
        p = DB.approve(pid)
    except KeyError:
        raise HTTPException(404)
    if p.status != "APPROVED":
        # Not transitioned because it wasn't PENDING
        raise HTTPException(409, f"already {p.status}")
    return {"ok": True, "id": p.id, "status": p.status}


@app.post("/payments/{pid}/cancel")
def cancel_payment(pid: str):
    try:
        p = DB.cancel(pid)
    except KeyError:
        raise HTTPException(404)
    if p.status != "CANCELED":
        # Not transitioned because it wasn't PENDING
        raise HTTPException(409, f"already {p.status}")
    return {"ok": True, "id": p.id, "status": p.status}


@app.post("/freeze_payee")
def freeze_payee(payee: str):
    return {"ok": True, "payee": payee, "ticket_id": f"TKT-{uuid.uuid4().hex[:8]}"}


@app.post("/schedule_specialist")
def schedule_specialist(phone: str):
    return {"ok": True, "scheduled_at": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    uvicorn.run("api.bank_sandbox:app", host="0.0.0.0", port=8000, reload=True)


