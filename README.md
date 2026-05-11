# SpamFacker

SpamFacker is a two-part anti-spam platform:

- Frontend: a static landing page served from Cloudflare Pages
- Backend: a Flask webhook service deployed to Render or Railway for Twilio call handling and spam checks

## Architecture Diagram

```text
Cloudflare Pages (index.html)
    |
    v
User lands on marketing site

Twilio Incoming Voice Webhook
    |
    v
Render/Railway Flask App (app.py)
    |
    +--> spam_checker.py
    |      |- Manual blocklist
    |      |- Twilio Lookup spam_risk
    |      '- Nomorobo lookup
    |
    +--> /incoming returns TwiML
    +--> Callback via Twilio REST API
    +--> /rickroll serves TwiML with audio playback
    '--> /audio/snippet.mp3 serves static audio when present
```

## Repository Layout

```text
spam-facker/
├── app.py
├── spam_checker.py
├── requirements.txt
├── .env.example
├── Procfile
├── index.html
├── _headers
├── README.md
└── static/
    ├── .gitkeep
    └── snippet.mp3 (gitignored; upload separately)
```

## Environment Variables

| Name | Required | Description |
| ---- | -------- | ----------- |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio Account SID used for Lookup and outbound callback requests |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio Auth Token used for REST calls and webhook signature validation |
| `TWILIO_PHONE_NUMBER` | Yes | Twilio phone number in E.164 format used as the caller ID for callbacks |
| `BASE_URL` | Yes | Public HTTPS base URL for the deployed Flask app; must exactly match the Twilio webhook URL and must not end with `/` |
| `RICK_ROLL_URL` | No | Public audio URL to play during the callback; defaults to `${BASE_URL}/audio/snippet.mp3` |
| `SPAM_THRESHOLD` | No | Minimum Twilio spam score required to treat a call as spam; default is `75` |
| `NOMOROBO_API_KEY` | No | Optional Nomorobo API key for robocall lookups |
| `PORT` | No | Runtime port injected by the host platform; defaults to `5000` locally |

## Backend Deploy Steps

### Render or Railway

1. Connect the repository to Render or Railway.
2. Let the platform auto-detect Python.
3. Confirm the start command comes from [Procfile](Procfile): `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`.
4. Add the environment variables from [.env.example](.env.example) in the platform dashboard.
5. Set your Twilio voice webhooks to `${BASE_URL}/incoming` and `${BASE_URL}/rickroll` through the same public host.
6. Deploy and verify `${BASE_URL}/health` returns `{"status": "ok"}`.

## Cloudflare Pages Deploy Steps

1. Connect the repository to Cloudflare Pages.
2. Set the build command to none.
3. Set the output directory to `/`.
4. Ensure [_headers](_headers) is included in the deployment output.
5. If you later add any frontend environment variables, configure them in the Cloudflare dashboard.

## Local Development

1. Install the pinned backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

1. Create a local env file:

```powershell
Copy-Item .env.example .env
```

1. Run the Flask server:

```powershell
python app.py
```

1. If testing locally with Twilio, expose the app via ngrok and set `BASE_URL` to the public HTTPS URL.

## Audio Upload After Deploy

The backend expects `static/snippet.mp3` to exist if you rely on the default audio route.

### Render shell example

1. Open the service shell from the Render dashboard.
2. Upload or copy your audio file into the service filesystem at `static/snippet.mp3`.

### SCP example

```bash
scp ./snippet.mp3 user@your-server:/opt/render/project/src/static/snippet.mp3
```

If you prefer not to manage server-side audio files, set `RICK_ROLL_URL` to a separate public HTTPS-hosted MP3 instead.

## Spam Detection Layers

| Layer | Method | Behavior |
| ----- | ------ | -------- |
| 1 | Manual blocklist | Immediate local block decision |
| 2 | Twilio Lookup `spam_risk` | Score-based spam detection |
| 3 | Nomorobo API | Optional robocall lookup with a 3 second timeout |

If Twilio Lookup and Nomorobo are both unavailable, SpamFacker logs a warning and falls back to the manual blocklist only.

## Twilio Webhook Notes

- `BASE_URL` must exactly match the deployed webhook host configured in Twilio.
- Do not include a trailing slash in `BASE_URL`.
- `/incoming` and `/rickroll` validate the Twilio request signature before processing.
- `/incoming` and `/rickroll` always return TwiML, even on internal errors, to avoid 5xx retry loops.

## Legal Notice

- Use SpamFacker only for defensive handling of inbound calls you receive.
- Telecom, call recording, and automated callback laws vary by jurisdiction.
- You are responsible for confirming Twilio usage, recording consent, and local legal compliance before deployment.
- Do not use this project to harass random numbers or initiate unsolicited campaigns.
