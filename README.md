# VeriWire — Voice Agent for High-Risk Wire Confirmation

> **Voice-first approvals with human liveness, multi-factor identity, and real-time tool-calling.**

[![Status](https://img.shields.io/badge/status-POC-blue.svg)](#) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#) [![FastAPI](https://img.shields.io/badge/FastAPI-API-green.svg)](#) [![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-8A2BE2.svg)](#)

## Executive Summary

**VeriWire** is a voice-enabled AI agent that confirms or stops **high-risk wire transfers** in a short phone call. It performs **3-step identity verification**, **human liveness**, fetches the **amount & payee** from an API, and executes **approve/cancel** with audit logs. It short-circuits previously decided payments and escalates suspicious cases to a fraud specialist.

**Identity flow (before any disclosure):**

1. **Phone on file** → caller speaks their phone number; system verifies it exists.
2. **Card last‑4** → caller speaks the last four digits; must match phone record.
3. **Customer‑ID last‑4** → caller speaks last four; must match phone+card.
   Only then: **liveness phrase → deepfake risk check → read‑back → approve/cancel**.

---

## Why Voice (and why now)

* **Urgent decisions**: customers can confirm or stop a transfer immediately over the phone.
* **Universal access**: no apps or links needed; works on any handset.
* **Barge-in friendly**: short prompts, interruption-tolerant design reduce friction.
* **Trusted outbound**: ideal for “please confirm now” scenarios.

---

## System Architecture

* **Telephony / STT / TTS**: Twilio Media Streams ↔ Deepgram (STT: nova-2/3, TTS: aura). Low-latency, telephony-tuned.
* **Voice bridge**: `main.py` WebSocket server relays audio to the agent and handles tool responses.
* **Agent policy**: OpenAI `gpt-4o-mini` via `config.json` for concise prompts, tool schemas, and safety rules.
* **Orchestration & state**: **LangGraph** in `veriwire/graph.py`:

  ```
  CollectPhone → CheckPhone → CollectCard → CheckCard → CollectID → CheckID
         → VerifyHuman (liveness) → DFCheck → Explain (read-back) → UnderstandIntent → Act
  ```

  Per-call sessions (`veriwire/session.py`) isolate concurrent calls.
* **Bank tools & API**: `veriwire/bank_tools.py` calls the mock bank **FastAPI** (`api/bank_sandbox.py`) for:

  * `get_payment_summary`, `approve_wire`, `cancel_wire`
  * `customer_exists`, `verify_card_last4`, `verify_id_last4`, `default_payment`
  * `freeze_payee`, `schedule_specialist`
* **Auditability**: SQLite event logging in `veriwire/storage.py` (prompts, user turns, tool calls, DF scores, decisions).

---

## Security & Policy Highlights

* **3-factor identity** before any transaction details:

  * **Phone on file** (spoken digits normalized to E.164)
  * **Card last‑4**
  * **Customer‑ID last‑4**
    Each allows **max 3 tries**; on failure → **escalate** (no disclosure).
* **Human liveness**: dynamic phrase (e.g., “blue cedar 39”) thwarts recorded prompts.
* **Deepfake risk stub**: continuous risk scoring; on spike → **freeze payee** + **schedule specialist**.
* **Read-back policy**: Always fetch via `get_payment_summary`; never invent details.
* **PII guardrails**: Never speak full numbers; only **last‑4** or masked (e.g., `•••• 1234`).
* **Idempotency & short-circuit**: If `status != PENDING`, say “already {STATUS}”, offer specialist, and end.

---

## Quick Start (Local Demo)

### 0) Prerequisites

* Python 3.10+
* Accounts/keys: **Deepgram**, **OpenAI**, (optional) **Twilio** for real calls
* `uv` or `pip`, and `ngrok` for public WSS during live tests

### 1) Create and fill `.env`

```bash
cp .env.example .env
# add DEEPGRAM_API_KEY=... and OPENAI_API_KEY=...
```

### 2) Sandbox API (port 8000)

```bash
uv run uvicorn api.bank_sandbox:app --host 0.0.0.0 --port 8000 --reload
```

### 3) Voice bridge (port 5000)

```bash
uv run python main.py
# or: DEEPGRAM_API_KEY=... OPENAI_API_KEY=... uv run python main.py
```

### 4) Telephony

* Point **Twilio Media Streams** to your public WSS (e.g., `wss://<ngrok-id>.ngrok.io/ws`) which forwards to `ws://localhost:5000`.
* Trigger an **outbound call** to your device or call the Twilio number that streams audio to the bridge.

> **No Twilio?** You can still run the full agent locally and feed audio via a WebSocket test client.

---

## Demo Script (≈ 2 minutes)

1. **Collect phone**: “Please say your phone number.” (speak digits)
2. **Collect card last‑4**: “Say last four digits of your card.”
3. **Collect ID last‑4**: “Say last four digits of your customer ID.”
4. **Liveness**: “Please say exactly: ‘blue cedar 37’.”
5. **Read-back**: “This is to confirm **$9,700.00 USD** to **ACME Escrow LLC**.”
6. **Decision**: “Do you **approve** or **cancel**? You can press **1** to approve, **2** to cancel.”
7. **Repeat call** with same payment to show “already **CANCELED/APPROVED**” short-circuit.

---

## Edge Cases to Try

* **Unknown phone** → 3 tries → escalate (no disclosure)
* **Wrong card last‑4** twice → third correct → proceed
* **Wrong ID last‑4** thrice → escalate
* **Ambiguous intent** (“okay”, “maybe”) → clarify → “approve or cancel?”
* **DTMF override**: say “approve” while pressing `2` → **cancel** wins
* **Already decided**: approve twice (409) → “already APPROVED”
* **Deepfake spike** (lower threshold to force) → **freeze + specialist**
* **Silence timeout**: no speech for N seconds → prompt once, then end

---

## Tests

```bash
uv run pytest -q
```

**Coverage includes:**

* In-memory data & identities (`veriwire/bank_data.py`)
* FastAPI endpoints (`api/bank_sandbox.py`)
* Tool clients & normalization (`veriwire/bank_tools.py`)
* Graph transitions & retries (`veriwire/graph.py`)
* SQLite event logging (`veriwire/storage.py`)

Add integration tests for:

* **3-factor identity** success/fail paths
* **Idempotent approve/cancel** (404/409 handling)
* **DTMF priority** over speech intent
* **Deepfake escalation** gates tool calls

---

## Technology Choices (and why)

* **OpenAI `gpt-4o-mini`** — low latency, strong function-calling, affordable for dialog control.
* **Deepgram STT/TTS** — robust telephony accuracy + fast turn-taking/barge-in.
* **LangGraph** — explicit, testable state machine; easy to extend.
* **FastAPI** — typed, fast mock of bank endpoints with built-in TestClient.
* **SQLite** — lightweight audit trail; trivial to swap for Postgres.

---

## Configuration

* **`config.json`** — LLM model, system prompt, tool schemas, STT/TTS params
* **Environment** (`.env`)

  * `DEEPGRAM_API_KEY=...`
  * `OPENAI_API_KEY=...`
  * Optional Twilio settings if you wire outbound dialing

---

## Repository Structure

```
.
├─ main.py                   # Voice bridge (WS server) + Deepgram agent I/O
├─ config.json               # Agent policy, tools, STT/TTS, copy
├─ api/
│  └─ bank_sandbox.py        # Mock bank API (get/approve/cancel/freeze/schedule + identity helpers)
├─ veriwire/
│  ├─ bank_tools.py          # Tool-call implementations & FUNCTION_MAP
│  ├─ bank_data.py           # In-memory customers/payments & seeding
│  ├─ graph.py               # LangGraph orchestration (identity → liveness → decision)
│  ├─ session.py             # Per-call in-memory session store
│  ├─ storage.py             # SQLite event logging (sessions & events)
│  └─ dfdetect.py            # Deepfake risk stub (randomized score spikes)
└─ tests/                    # Unit tests for API, tools, graph, storage
```

---

## Evaluation Plan

* **Task success**: % calls with correct approve/cancel
* **Time-to-decision**: median seconds from greeting → decision
* **Identity verification**: pass rates per step; average retries; escalation rate
* **Tool reliability**: 2xx vs 4xx/5xx; idempotent behavior
* **Trust & safety**: DF spike handling; zero PII leakage in logs

---

## Roadmap (toward production)

* Persistent store for payments & identity; structured audit schema
* Deterministic deepfake test mode + real detector integration
* Caller reputation/ANI validation; branded calling integration
* Observability (OpenTelemetry), SLIs/SLOs, dashboards
* DTMF config flags; richer interruption controls
* CI, containers, IaC, staging deployments

---

## AI Assistant Usage Disclosure

An AI coding assistant was used for scaffolding, refactors, and boilerplate. All logic, prompts, and tests were reviewed and validated locally (pytest + sandbox) and with live call trials. Prompts avoid internal narration and enforce tool-backed readouts and PII policy.

---

## License

This project is provided for interview and educational purposes. Please adapt the license for your organization’s needs.

---

**Questions / Feedback?** Open an issue or ping me in the PR — happy to walk through the architecture and tradeoffs.
