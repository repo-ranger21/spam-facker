# SpamFacker

SpamFacker is a Flask + Twilio voice app that detects likely spam callers and keeps them talking to AI personas instead of to you. The current codebase is centered on inbound call handling: Twilio sends an incoming call to the app, the app scores the caller, and spam calls get routed into a voice conversation loop powered by OpenAI and optional ElevenLabs TTS.

The repo also includes a static landing page for Cloudflare Pages and an experimental callback/Rickroll path in the backend, but the shipped inbound flow is the main implementation.

## Current Behavior

```text
Inbound call -> /incoming
               |
               +-> spam_checker.py
               |    1) manual blocklist
               |    2) Twilio Lookup spam_risk
               |    3) Nomorobo (optional)
               |
               +-> not spam: polite hold message
               |
               +-> spam: assign agent -> intro line -> /respond loop
                                            |
                                            +-> llm.py generates reply
                                            +-> tts.py optionally renders MP3 with ElevenLabs
                                            +-> Twilio Gather listens again
```

Important implementation detail: the current inbound path does not automatically launch the outbound callback trap. The callback helper and `/rickroll` route exist in the code, but they are not wired into `/incoming` today.

## Features

- Three-layer spam detection with graceful fallback when paid lookups are unavailable.
- Five character agents defined in [agents.py](agents.py), each with a persona, intro line, escalation prompt, and fallback tactics.
- Real-time reply generation through OpenAI in [llm.py](llm.py).
- Optional ElevenLabs voice playback with local MP3 caching in [tts.py](tts.py).
- Twilio webhook signature validation for the main voice routes.
- In-memory per-call state tracking in [conversation.py](conversation.py).
- Static site assets in [index.html](index.html) and [_headers](_headers).

## AI Agents

Five personas ship with the app:

| Agent | Voice | Style |
| ----- | ----- | ----- |
| Mildred | Polly.Joanna | Sweet grandmother who mishears everything and never finds the right card |
| Gary | Polly.Matthew | Construction foreman yelling over a chaotic job site |
| Timmy | Polly.Justin | Literal, methodical caller who asks endless clarifying questions |
| Shanika | Polly.Kendra | High-energy interrupter who turns every call into a tangent |
| Bruce | Polly.Russell | Suspicious retiree with a short fuse and constant authority threats |

Escalation kicks in after turn 10, which pushes the persona into a more time-wasting second mode.

## Project Layout

```text
spam-facker/
|-- app.py
|-- agents.py
|-- conversation.py
|-- llm.py
|-- spam_checker.py
|-- tts.py
|-- requirements.txt
|-- .env.example
|-- Procfile
|-- index.html
|-- _headers
|-- PRODUCT_SPEC.md
|-- APP_ADDITIONS.py
`-- static/
    |-- .gitkeep
    `-- tts/
```

## Requirements

- Python 3.11+ recommended.
- A Twilio account with a voice-capable phone number.
- An OpenAI API key.
- An ElevenLabs API key if you want generated audio instead of falling back to Twilio/Polly voices.
- Optional Nomorobo API key for the third spam-check layer.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `.env`, then run the app:

```powershell
python app.py
```

Health check:

```text
GET http://localhost:5000/health
```

To test against real Twilio webhooks locally, expose the app with ngrok or a similar tunnel:

```powershell
ngrok http 5000
```

Set `BASE_URL` to the public HTTPS URL from your tunnel, with no trailing slash.

## Environment Variables

The canonical template lives in [.env.example](.env.example).

| Variable | Required | Notes |
| -------- | -------- | ----- |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account SID used for Lookup and REST API access |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth token used for request validation and API calls |
| `TWILIO_PHONE_NUMBER` | Yes | Voice-capable Twilio number in E.164 format |
| `BASE_URL` | Yes | Public HTTPS base URL for webhook construction; no trailing slash |
| `OPENAI_API_KEY` | Yes | Used by [llm.py](llm.py) for response generation |
| `ELEVENLABS_API_KEY` | Yes for ElevenLabs mode, optional otherwise | If missing, the app logs an error and falls back to Twilio `say()` |
| `RICK_ROLL_URL` | No | Optional public MP3 URL used by the `/rickroll` route |
| `SPAM_THRESHOLD` | No | Twilio spam score threshold, default `75` |
| `NOMOROBO_API_KEY` | No | Enables the Nomorobo lookup layer |
| `PORT` | No | Defaults to `5000` locally |

## Twilio Configuration

Configure your Twilio number with these webhook targets:

- Voice webhook: `POST {BASE_URL}/incoming`
- If you use outbound callback experiments, status callback: `POST {BASE_URL}/status`

Operational notes:

- `BASE_URL` must exactly match the URL Twilio signs against.
- `/incoming` performs a signature check before handling the request.
- `/rickroll` also validates Twilio signatures.
- `/respond` currently processes the request without its own explicit signature guard, so if you want stricter webhook hardening, that route is the first place to tighten.

## Deployment

### Render or Railway

1. Create a new web service from this repository.
2. Use the dependencies from [requirements.txt](requirements.txt).
3. Use the start command from [Procfile](Procfile): `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. Add the environment variables from [.env.example](.env.example).
5. Set your Twilio number's voice webhook to `{BASE_URL}/incoming`.
6. Verify `{BASE_URL}/health` returns `{"status": "ok"}`.

### Cloudflare Pages

The repository root also contains a static marketing page.

1. Connect the repository to Cloudflare Pages.
2. Use no build command.
3. Set the output directory to the repository root.
4. Make sure [_headers](_headers) is published with the static site.

## State and Scaling

Call state lives in process memory inside [conversation.py](conversation.py). That is fine for local development and small single-instance deployments, but it has clear limits:

- Active call state is lost on process restart.
- Multi-instance deployments need shared state such as Redis.
- The current [Procfile](Procfile) uses two Gunicorn workers, which may be acceptable for hobby use but is not a robust scaling strategy for long-lived voice sessions.

## Endpoints

| Route | Method | Purpose |
| ----- | ------ | ------- |
| `/health` | GET | Basic health check |
| `/audio/snippet.mp3` | GET | Serves the callback audio file if present |
| `/audio/tts/<filename>` | GET | Serves generated ElevenLabs audio files |
| `/incoming` | POST | Main Twilio inbound voice webhook |
| `/respond` | POST | Conversation loop for speech input |
| `/rickroll` | POST | Outbound callback trap route |
| `/status` | POST | Status callback for completion logging and cleanup |

## Known Gaps

- The product vision in [PRODUCT_SPEC.md](PRODUCT_SPEC.md) is much larger than the current implementation.
- There is no persistent database, dashboard, authentication layer, or billing flow in this repo.
- The outbound callback helper exists but is not part of the active inbound flow.
- Audio for `/audio/snippet.mp3` is not included in the repository.

## Troubleshooting

- `403` from Twilio webhook routes usually means `BASE_URL` does not exactly match the public URL Twilio is calling.
- If replies come back in Twilio voices instead of ElevenLabs audio, check `ELEVENLABS_API_KEY` and the logs from [tts.py](tts.py).
- If every caller is treated as legitimate, verify Twilio Lookup access, your spam threshold, and whether the number is present in the manual blocklist in [spam_checker.py](spam_checker.py).
- If call state seems to disappear mid-call, inspect worker count and process restarts first.

## Legal and Operational Use

- Use this project only on calls that reach numbers you control.
- Verify local laws around call recording, automated callbacks, and telecom abuse before deploying.
- Do not use the project for harassment, unsolicited campaigns, or retaliatory calling outside lawful defensive use.
