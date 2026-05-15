# SpamFacker Latency Sprint — Smoke Test Procedure

Step-by-step manual verification using a real Twilio number and ngrok.  
Run this before flipping any feature flag to `true` in production.

---

## Prerequisites

```powershell
# Install dependencies (if not already)
pip install -r requirements.txt

# Activate virtual environment (Windows)
.\.venv\Scripts\Activate.ps1
```

---

## Phase 0 — Baseline (all flags OFF)

1. Start the dev server:
   ```powershell
   $env:ENABLE_FILLERS="false"
   $env:ENABLE_STREAMING_TTS="false"
   $env:ENABLE_TOKEN_CAP="false"
   python app.py
   ```
2. In a second terminal, start ngrok:
   ```powershell
   ngrok http 5000
   ```
3. Copy the `https://…ngrok.io` forwarding URL and set it as `BASE_URL` in `.env`.
4. Set your Twilio number's Voice webhook to `{BASE_URL}/incoming` (HTTP POST).
5. Call the Twilio number from a real phone. Confirm:
   - [ ] Intro plays (ElevenLabs or Polly fallback)
   - [ ] Each turn: caller speaks, agent replies, loop continues
   - [ ] `/status` webhook receives `CallStatus=completed` after hangup

---

## Phase 1 — Filler audio (`ENABLE_FILLERS=true`)

### Step 1 — Pre-render fillers

```powershell
python -m scripts.generate_fillers
```

Expected output: `generated=40 skipped=0 failed=0`  
Check that files exist under `static/tts/fillers/{agent_slug}/00.mp3` etc.

Re-run to confirm idempotency (should show `skipped=40`):
```powershell
python -m scripts.generate_fillers
```

### Step 2 — Enable and test

```powershell
$env:ENABLE_FILLERS="true"
python app.py
```

Call the Twilio number. Confirm for each turn:
- [ ] A filler phrase plays immediately (< 200 ms after speech ends)
- [ ] The real agent response follows ~1-2 s later
- [ ] No double-speak or TwiML errors in the Twilio debugger
- [ ] `/respond_continue` appears in the Twilio call log
- [ ] Timeout path: if you kill the server mid-call and restart, the "line is fuzzy" fallback fires

### Step 3 — Check logs

Look for these structured log entries:
```
respond.filler_dispatched   {"call_sid": "CA…", "agent": "Mildred", "seq": 0}
respond.generation_started  {"call_sid": "CA…", "agent": "Mildred", "seq": 0}
respond.generation_complete {"call_sid": "CA…", "duration_ms": 1234}
respond_continue.served     {"call_sid": "CA…", "seq": 0}
```

---

## Phase 2 — Streaming TTS (`ENABLE_STREAMING_TTS=true`)

> Requires Phase 1 to be working.

```powershell
$env:ENABLE_FILLERS="true"
$env:ENABLE_STREAMING_TTS="true"
python app.py
```

Call and confirm:
- [ ] Audio begins playing before full synthesis completes (noticeably faster start)
- [ ] `/audio/stream/{token}.mp3` appears in the Twilio call log (HTTP 200)
- [ ] A second GET to the same token URL returns 404 (single-use confirmed)
- [ ] No buffering errors in ngrok logs (`X-Accel-Buffering: no` header present)

---

## Phase 3 — Token cap (`ENABLE_TOKEN_CAP=true`)

```powershell
$env:ENABLE_TOKEN_CAP="true"
python app.py
```

Call and confirm:
- [ ] Agent responses are noticeably shorter (≤ 2 sentences)
- [ ] Agent does not repeat phrases from earlier in the call
- [ ] LLM latency is slightly lower (check `duration_ms` in logs vs baseline)
- [ ] No regressions in response quality

---

## Rollback

To disable any phase instantly, flip its flag back to `false` and restart:

```powershell
$env:ENABLE_FILLERS="false"
# or
$env:ENABLE_STREAMING_TTS="false"
# or
$env:ENABLE_TOKEN_CAP="false"
python app.py
```

No database migrations, no file deletions required.
