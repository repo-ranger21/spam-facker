# Spam Call Revenge Bot 🎵

Detects spam callers, calls them back, and traps them in an infinite Rick Roll loop.

## How it works

```
Spam call arrives → Twilio webhook → spam_checker.py → SPAM?
                                                          │
                          ┌───────────────────────────────┘
                          ▼
              Hang up on spammer (our end)
              + Dial spammer back (their end)
                          │
                          ▼
              Spammer answers → /rickroll webhook
                          │
                          ▼
              🎵 Never Gonna Give You Up (loop=∞) 🎵
```

## Prerequisites

- Python 3.10+
- A [Twilio account](https://twilio.com) (~$1/month for a number + per-minute charges)
- [ngrok](https://ngrok.com) for local testing (or deploy to a server)

## Setup

### 1. Install dependencies

```powershell
pip install flask twilio requests python-dotenv
```

### 2. Configure credentials

```powershell
Copy-Item .env.example .env
# Edit .env with your Twilio credentials and BASE_URL
```

### 3. Start the server

```powershell
python app.py
```

### 4. Expose it via ngrok (local dev)

```powershell
ngrok http 5000
```

Copy the `https://` URL ngrok gives you and set it as `BASE_URL` in your `.env`.

### 5. Configure Twilio webhook

1. Go to [Twilio Console → Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Click your number → Voice Configuration
3. Set **"A call comes in"** webhook to: `https://your-ngrok.ngrok.io/incoming`
4. Method: `HTTP POST`
5. Save.

Now call your Twilio number from a phone — you'll hear "Thank you for calling."  
Add that number to `MANUAL_BLOCKLIST` in `spam_checker.py` and call again — Rick Roll trap activates.

## Spam Detection Layers

| Layer | Method | Cost |
|-------|--------|------|
| 1 | Manual blocklist | Free |
| 2 | Twilio Lookup spam score | ~$0.01/call |
| 3 | Nomorobo API | Free tier available |

## Twilio Lookup (Recommended)

Enable the **Spam Risk** add-on in your Twilio account:
https://www.twilio.com/docs/lookup/v2-api/spam-risk

## Legal Note

- This tool is for **defensive, personal use** against numbers that called you first.
- Repeatedly calling back numbers you don't own may violate TCPA in the US.
- Use responsibly — only retaliate against confirmed spam/scam numbers.
- Do **not** deploy this against random numbers or use for harassment.

## Files

```
spam_revenge/
├── app.py            # Flask webhooks (incoming call + rickroll endpoint)
├── spam_checker.py   # 3-layer spam detection logic
├── .env.example      # Config template
├── requirements.txt  # Dependencies
└── README.md         # This file
```
