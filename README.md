VeriWire - Banking Payment Confirmation Voice Agent

Run sandbox API (terminal 1):

```bash
uv run uvicorn bank_sandbox:app --port 8000 --reload
```

Run voice bridge (terminal 2):

```bash
DEEPGRAM_API_KEY=your_key uv run python main.py
```

Notes:
- The voice bridge listens on ws://localhost:5000 for Twilio Media Streams (compatible with your existing ngrok setup).
- Configure your Twilio webhook to point to the above.
- On call start, VeriWire speaks a dynamic liveness phrase and expects an exact repeat.
- Say "approve"/"cancel" or press 1/2 to proceed.

