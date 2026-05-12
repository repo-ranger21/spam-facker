# SpamFacker

SpamFacker is an anti-spam voice platform that deploys AI personas to waste spam callers' time. When a spam call hits your Twilio number, an LLM-powered character answers in real time, keeps the spammer engaged through an infinite conversation loop, and logs every second of their wasted time.

- **Frontend**: static marketing page served from Cloudflare Pages
- **Backend**: Flask webhook service deployed on Render or Railway, wired to Twilio voice webhooks

---

## How It Works

```text
Inbound call → /incoming (Twilio webhook)
                    |
              spam_checker.py (3-layer detection)
                    |
          ┌─── Spam ──────────────────────────────────────┐
          │                                               │
     assign random AI agent (agents.py)           "Thank you for calling.
          │                                         Please hold."
     agent speaks intro line
          │
     Gather loop: caller speaks → /respond
          │
     llm.py → OpenAI gpt-4o-mini → in-character reply
          │
     Twilio speaks reply → Gather again → repeat forever
          │
     /status webhook logs duration on call end
```

**Spam detection layers** (first hit wins):

| Layer | Method | Notes |
| ----- | ------ | ----- |
| 1 | Manual blocklist | Instant, no API cost |
| 2 | Twilio Lookup `spam_risk` | Score-based, ~$0.01/lookup |
| 3 | Nomorobo API | Robocall-specific, optional |

If Twilio Lookup and Nomorobo are both unavailable, the app falls back to the manual blocklist only and logs a warning.

---

## AI Voice Agents

Five distinct characters are randomly assigned to each spam call. Every agent has a unique system prompt, voice, intro line, escalation prompt (injected after turn 10), and a set of stall tactics for low-confidence STT input.

| Agent | Voice | Persona |
| ----- | ----- | ------- |
| **Mildred** | Polly.Joanna | Sweet 79-year-old grandmother — hard of hearing, perpetually searching for her glasses and "the plastic card" |
| **Gary** | Polly.Matthew | Construction foreman on a loud job site — can't hear over the jackhammers, always yelling at Danny |
| **Timmy** | Polly.Justin | Methodical literal thinker — asks what "compromised" means, wants every word spelled out |
| **Shanika** | Polly.Kendra | Force of nature — cuts them off, goes on tangents about cousin DeShawn, always mid-something |
| **Bruce** | Polly.Russell | Suspicious retiree who threatens to call his son the Senator every three exchanges |

Each agent's escalation prompt shifts the character into a second gear: Mildred thinks this is her doctor's office; Gary needs to dictate a formal complaint but can't find a working pen; Timmy starts re-reading his notes from the beginning because he got step one wrong.

---

## Repository Layout

```text
spam-facker/
├── app.py              # Flask app, all Twilio webhook routes
├── agents.py           # Five AI agent definitions (system prompts, voices, tactics)
├── conversation.py     # In-memory call state (per-call history, turn count, escalation)
├── llm.py              # OpenAI gpt-4o-mini conversation engine
├── spam_checker.py     # 3-layer spam detection logic
├── requirements.txt
├── .env.example
├── Procfile            # gunicorn start command for Render/Railway
├── index.html          # Cloudflare Pages marketing site
├── _headers            # Cloudflare Pages headers config
├── APP_ADDITIONS.py    # Reference copy of the routes added to app.py
└── static/
    ├── .gitkeep
    └── snippet.mp3     # gitignored — upload separately if using local audio
```

---

## Environment Variables

| Name | Required | Description |
| ---- | -------- | ----------- |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio Account SID — used for Lookup and outbound callbacks |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio Auth Token — used for REST calls and webhook signature validation |
| `TWILIO_PHONE_NUMBER` | Yes | Your Twilio number in E.164 format, used as caller ID for outbound calls |
| `BASE_URL` | Yes | Public HTTPS base URL of the deployed Flask app — must exactly match the Twilio webhook URL, no trailing slash |
| `OPENAI_API_KEY` | Yes | OpenAI API key for gpt-4o-mini voice agent responses |
| `RICK_ROLL_URL` | No | Public audio URL to play during callbacks — defaults to `${BASE_URL}/audio/snippet.mp3` |
| `SPAM_THRESHOLD` | No | Minimum Twilio spam score (0–100) to treat a call as spam — default `75` |
| `NOMOROBO_API_KEY` | No | Nomorobo API key for robocall lookups |
| `PORT` | No | Runtime port injected by the host platform — defaults to `5000` locally |

---

## API Endpoints

| Endpoint | Method | Purpose |
| -------- | ------ | ------- |
| `GET /health` | GET | Health check — returns `{"status": "ok"}` |
| `/incoming` | POST | Twilio webhook — entry point for all inbound calls |
| `/respond` | POST | Twilio webhook — LLM conversation loop (called on every speech input) |
| `/rickroll` | POST | Twilio webhook — plays audio loop to caller on outbound callback |
| `/status` | POST | Twilio status callback — logs duration, cleans up call state |
| `/audio/snippet.mp3` | GET | Serves `static/snippet.mp3` if present |

---

## Deploy

### Render or Railway

1. Connect the repository.
2. Let the platform auto-detect Python.
3. Confirm the start command from [Procfile](Procfile): `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. Add all required environment variables from [.env.example](.env.example) in the platform dashboard.
5. Set your Twilio voice webhook for your number to `${BASE_URL}/incoming`.
6. Deploy and verify `${BASE_URL}/health` returns `{"status": "ok"}`.

> **Single-worker note**: `conversation.py` stores call state in memory. The Procfile sets 2 workers, which is fine for personal use — a call will always hit the same worker in practice on free-tier Render. For multi-worker production deployments, swap the `_calls` dict in `conversation.py` for Redis.

### Cloudflare Pages (marketing site)

1. Connect the repository to Cloudflare Pages.
2. Set the build command to none.
3. Set the output directory to `/`.
4. Ensure [_headers](_headers) is included in the deployment output.

---

## Local Development

```powershell
# Install dependencies
python -m pip install -r requirements.txt

# Set up environment
Copy-Item .env.example .env
# Fill in your real values in .env

# Run the Flask dev server
python app.py
```

To receive real Twilio webhooks locally, expose the server with ngrok and set `BASE_URL` to the public HTTPS URL ngrok provides.

```bash
ngrok http 5000
# Then set BASE_URL=https://<your-ngrok-id>.ngrok.io in .env
```

---

## Audio File

The backend serves `static/snippet.mp3` for the Rick Roll callback loop. That file is gitignored — you need to add it after deploying.

**Option A — serve from the app:**

Upload `snippet.mp3` to `static/snippet.mp3` on the server after deploy (Render shell, SCP, etc.). Leave `RICK_ROLL_URL` unset; it defaults to `${BASE_URL}/audio/snippet.mp3`.

**Option B — external host:**

Host the MP3 on Cloudflare R2, S3, or any public HTTPS URL. Set `RICK_ROLL_URL` to that URL. No file upload needed.

---

## Twilio Webhook Notes

- `BASE_URL` must exactly match the host configured in Twilio — including protocol, no trailing slash.
- `/incoming` and `/respond` validate the Twilio request signature before processing.
- All routes return valid TwiML even on internal errors to avoid 5xx retry loops.
- `/status` should be set as the status callback on any outbound calls if you want leaderboard logging.

---

## Legal Notice

- Use SpamFacker only for defensive handling of inbound calls you receive.
- Telecom, call recording, and automated callback laws vary by jurisdiction.
- You are responsible for confirming Twilio usage, recording consent, and local legal compliance before deployment.
- Do not use this project to harass random numbers or initiate unsolicited campaigns.
