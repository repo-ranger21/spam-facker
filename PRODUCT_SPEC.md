# SpamFacker — Product Spec v1.0
## "Annoy & Destroy" — Profitable, Legal Edition

---

## I. Product Summary

SpamFacker is a **Spite-Tech SaaS** that deploys AI voice agents against inbound spam callers.
When a spam call hits your number, SpamFacker intercepts it, assigns a randomized AI persona,
and wastes the scammer's time for as long as possible — autonomously.

**Core value prop:** Turn 1-minute scams into 45-minute psychological labyrinths.
**Slogan:** *Because "Go Away" doesn't work, but "Infinite Hold" does.*

---

## II. How It Works (User Flow)

1. User signs up, gets a **SpamFacker honeypot number** (or forwards their real number)
2. Spam call arrives → SpamFacker intercepts via Twilio webhook
3. Spam score checked (Twilio Lookup + Nomorobo)
4. RNG assigns one of 5 AI agents to handle the call
5. LLM drives the conversation — tangents, confusion, delays — in real time
6. Call is recorded and logged to the user's dashboard
7. Duration contributed to leaderboard + credits

---

## III. The Vengeance Roster

| Agent     | Archetype        | Core Tactic                                                              |
|-----------|------------------|--------------------------------------------------------------------------|
| Mildred   | Sweet Grandma    | Verbal Labyrinth — polite, deaf, perpetually searching for her "card"    |
| Gary      | Angry Foreman    | Decibel Destroyer — background construction, yells at coworkers          |
| Timmy     | Slow Processor   | Eternal Why — 3-sec delays, interprets all tech terms literally          |
| Shanika   | Firecracker      | Volume Wall — aggressive interruptions, extended personal rants           |
| Bruce     | Grumpy Veteran   | Short Fuse — impatient, threatens his "son the Senator" every 30 seconds |

Each agent has:
- A base persona prompt (LLM system message)
- An escalation prompt that fires after 5 minutes on the line
- A library of fallback tangents (lost glasses, bad connection, wrong number confusion)

---

## IV. Technical Stack

### Core
- **Twilio Voice** — inbound webhook, outbound TTS, call recording
- **Python / Flask** — webhook handler, agent router
- **OpenAI / Claude API** — real-time LLM conversation per agent persona
- **Twilio Lookup + Nomorobo** — spam detection (3-layer)
- **PostgreSQL** — call logs, user accounts, leaderboard data
- **Cloudflare Pages** — frontend dashboard

### Key Features
- **RNG Agent Selection** — random on each call, weighted by user preference
- **Escalation Loop** — intensity increases at 5-min, 10-min, 15-min marks
- **Bad Connection Gaslight** — artificial 2-sec latency injection mid-call
- **Obnoxious DTMF Response** — replies to "Press 1" prompts with fax/busy tones
- **Grandpa's Long Story** — LLM-triggered tangent mode for maximum derailment
- **Honeypot Number** — publishable decoy number that attracts inbound spam

### Recording & Consent Compliance
- All calls recorded with verbal notice at call start ("This call may be recorded")
- Single-party consent baseline (caller already recording you = consent established)
- Dashboard recordings marked by jurisdiction for enterprise compliance tier

---

## V. Monetization — "Schadenfreude" Subscription Model

### Free Tier
- 10 spam intercepts/month
- 3 agents (Mildred, Timmy, Gary)
- Basic call log (duration, agent used)

### Chaos Tier — $9/mo
- Unlimited intercepts
- All 5 agents + escalation mode
- Full call recordings in dashboard
- Personal leaderboard stats

### Schadenfreude Tier — $19/mo
- Everything in Chaos
- Live listen-in dashboard (your own calls only)
- "Bounty for Tears" credits — earn $0.10 account credit per 10 minutes wasted
- Monthly "Hall of Shame" digest — your top calls ranked by duration

### Vengeance-as-a-Service (VaaS) — $99/mo per seat (Enterprise)
- Reroutes corporate spam lines to a "Confused HR Director" bot
- Dedicated agent customization (company name, industry-specific confusion)
- Multi-user dashboard
- Jurisdiction-aware recording compliance flags
- SLA + priority support

---

## VI. Leaderboard — "The Salt Mines"

Public leaderboard (anonymized by default) tracking:

- Total Scammer Minutes Wasted (global + personal)
- Longest Single Call
- Most Calls Intercepted This Week
- Agent Win Rate (which agent keeps them on longest)
- "Comeback of the Week" — staff-picked highlight clip (user-consented submissions)

---

## VII. Deployment Plan (Lucius Engine Framework)

### Phase 1 — MVP (Month 1–2)
- Flask + Twilio webhook live
- Mildred + Timmy agents (simplest LLM personas)
- Manual spam list + Twilio Lookup
- Basic dashboard (React, call log only)
- Free tier only

### Phase 2 — Monetization (Month 3–4)
- Stripe integration
- All 5 agents + escalation loop
- Chaos tier live
- Leaderboard (Salt Mines) v1

### Phase 3 — Scale (Month 5–6)
- Schadenfreude tier + live listen dashboard
- VaaS enterprise onboarding
- Honeypot number publishing
- Public Hall of Shame (opt-in submissions)

---

## VIII. Competitive Moat

| Competitor          | Gap SpamFacker Fills                              |
|---------------------|---------------------------------------------------|
| Jolly Roger Phone   | No LLM — pre-recorded only, no escalation         |
| Nomorobo            | Block-only, no time-wasting, no entertainment     |
| YouMail             | Corporate/clean, no Spite-Tech angle              |
| RoboKiller          | Close competitor — moat is agent depth + VaaS     |

SpamFacker's differentiation: **LLM-driven improvisation + entertainment layer + VaaS B2B**.
RoboKiller blocks. SpamFacker *punishes*.
