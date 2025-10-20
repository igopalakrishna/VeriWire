VeriWire — Voice Agent for High‑Risk Wire Confirmation 

Executive Summary
VeriWire is a voice-enabled AI agent that confirms or stops high‑risk wire transfers in a short phone call. It performs human liveness, verifies the transaction ID, collects two security factors (card last‑4 and spoken phone digits), reads amount and payee from an API, and then executes approve/cancel. It short‑circuits on already approved/canceled payments and escalates to a fraud specialist when appropriate.

Why Voice
- Urgent decisions and universal access via phone
- Barge‑in friendly, low‑friction identity checks
- Works well for outbound “please confirm now” scenarios

System Architecture
- Telephony/STT/TTS: Twilio Media Streams ↔ Deepgram Agent Converse (STT nova‑3, TTS aura). Low‑latency, telephony‑tuned speech stack.
- Voice bridge: `main.py` WebSocket server (ws://localhost:5000) relays audio and handles Agent messages and tool responses.
- Agent policy: OpenAI gpt‑4o‑mini orchestrated via `config.json` (tools, safety rules, no internal narration).
- Orchestration/state: LangGraph in `veriwire/graph.py` (liveness → ID → 2‑factor → decision); per‑call session key (`veriwire/session.py`) prevents collisions.
- Bank tools/API: `veriwire/bank_tools.py` calls `api/bank_sandbox.py` (FastAPI) for get/approve/cancel/freeze/schedule and verification helpers.
- Auditability: SQLite event logging in `veriwire/storage.py` (start/function_call/stop).

Security & Policy Highlights
- Dynamic liveness phrase prevents recorded prompts.
- Two‑factor verification (must both match):
  - Last‑4 of card (digits or spoken numbers)
  - Spoken phone digits; normalized and compared to stored phone
- Readback policy: Always fetch with `get_payment_summary` before speaking amount/payee; never invent.
- Status short‑circuit: If `status != PENDING`, agent immediately says “already {STATUS}” and offers a specialist.
- Prompts are concise and do not narrate internal processing or tools.

Run the Demo Locally
1) Sandbox API (port 8000):
```bash
uv run uvicorn api.bank_sandbox:app --port 8000 --reload
```
2) Voice bridge (port 5000):
```bash
DEEPGRAM_API_KEY=your_key uv run python main.py
```
3) Telephony: point Twilio Media Streams to your ngrok wss → ws://localhost:5000

Demo Script (1–2 minutes)
- Liveness: agent says a phrase (e.g., “blue cedar 37”); repeat it.
- ID: say “10 s f 9 1 7 2 6 4” (→ `10sf917264`).
- Last‑4: say “one one one one” (→ 1111).
- Phone digits: say “four one five five five five zero one two three” (→ 415‑555‑0123).
- Agent speaks: “$9,700.00 USD to ACME Escrow LLC”, then asks approve/cancel.
- Repeat call for same ID to show “already CANCELED/APPROVED” short‑circuit.

Edge Cases to Try
- Unknown ID: 404 → agent asks to repeat ID.
- Noisy ID (e.g., “10sf‑917 264”) → normalization.
- Conflicts: approve after cancel (409) → agent explains.
- Escalation: failed verification or deepfake spike triggers freeze/specialist.

Testing
```bash
uv run pytest -q
```
Coverage includes: in‑memory data transitions (`veriwire/bank_data.py`), FastAPI endpoints (`api/bank_sandbox.py`), ID normalization (`veriwire/bank_tools.py`), and SQLite logging (`veriwire/storage.py`).

Technology Choices (Justifications)
- OpenAI gpt‑4o‑mini: cost‑efficient, fast tool-calling, solid reasoning for dialog control.
- Deepgram STT/TTS: excellent telephony performance and low latency.
- LangGraph: explicit, testable, and extensible conversation orchestration.
- FastAPI: simple, typed demo API with TestClient support.
- SQLite: lightweight, easy to inspect audit trail.

Repository Structure
- `main.py` — voice bridge WebSocket server
- `config.json` — agent policy, tools, STT/TTS, greeting
- `api/bank_sandbox.py` — mock bank API (get/approve/cancel/freeze/schedule)
- `veriwire/bank_tools.py` — tool-call implementations (incl. verify_last4/verify_phone)
- `veriwire/graph.py` — LangGraph orchestration (liveness → ID → verify → act)
- `veriwire/bank_data.py` — in‑memory payment records (IDs, last‑4, phone)
- `veriwire/storage.py` — SQLite event logging
- `veriwire/session.py` — per‑call in‑memory session store
- `tests/` — unit tests for data, tools, API, storage

Evaluation Plan
- KPIs: time‑to‑decision, verification success rate, tool-call success/404/409, escalation rate.
- Method: read logs from SQLite/events; add counters/metrics as next step.

Next Steps (toward production)
- Persistent data store for payments; structured audit/reporting tables.
- Deterministic deepfake test mode; ANI validation and phone reputation scoring.
- Agent‑compatible DTMF path (safe injection format) and better barge‑in tunes.
- Observability: SLIs, tracing (OpenTelemetry), dashboards.
- CI, containerization, and deploy scripts.

AI Assistant Usage Disclosure
I used an AI coding assistant inside my IDE to scaffold modules, refactor to a package (`veriwire/`), add tests, fix lints, and speed up boilerplate. I validated changes with pytest, the local sandbox, and live calls; I also tightened prompts to remove internal narration and force tool‑backed readouts.

Contact
If you’d like me to extend this demo (e.g., outbound initiation, real bank API, richer verifications), I can adapt the LangGraph flow and sandbox quickly.