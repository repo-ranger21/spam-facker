"""
APP_ADDITIONS.py
================
Paste these routes into app.py AFTER the existing /status route.
Also add the imports and the updated /incoming handler below.

Step 1: Add to requirements.txt
  openai==1.30.1

Step 2: Add to .env.example and Render environment:
  OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

Step 3: Add these imports to the TOP of app.py (after existing imports):
  from conversation import assign_agent, get_state, add_exchange, should_escalate, end_call, get_stall_tactic, elapsed_seconds
  from llm import generate_response, generate_stall

Step 4: REPLACE the existing /incoming route with the one below.

Step 5: ADD the /respond and updated /status routes below.
"""

# ─────────────────────────────────────────────────────────────
# REPLACE existing /incoming with this version
# ─────────────────────────────────────────────────────────────

@app.route("/incoming", methods=["POST"])
def incoming_call():
    """
    Entry point for all inbound calls.
    Spam → assign agent → intro → start Gather loop.
    Legit → polite hold message.
    """
    caller   = request.form.get("From", "Unknown")
    call_sid = request.form.get("CallSid", "")

    logger.info(f"Incoming call from: {caller} | SID: {call_sid}")

    # Twilio signature validation
    validator = RequestValidator(AUTH_TOKEN)
    url       = f"{BASE_URL}/incoming"
    if not validator.validate(url, request.form, request.headers.get("X-Twilio-Signature", "")):
        logger.warning(f"Invalid Twilio signature from {caller}")
        return Response("Forbidden", status=403)

    resp = VoiceResponse()

    if is_spam(caller):
        logger.info(f"SPAM DETECTED: {caller} — deploying agent")

        # Assign agent and get their intro line
        agent = assign_agent(call_sid)

        # Greet the spammer in character, then open the Gather loop
        gather = Gather(
            input="speech",
            action=f"{BASE_URL}/respond",
            method="POST",
            speech_timeout="auto",
            speech_model="phone_call",
            enhanced=True,
            language="en-US",
        )
        gather.say(agent["intro"], voice=agent["voice"])
        resp.append(gather)

        # If they say nothing at all, loop back
        resp.redirect(f"{BASE_URL}/respond", method="POST")

    else:
        resp.say("Thank you for calling. Please hold.", voice="Polly.Joanna")

    return Response(str(resp), mimetype="text/xml")


# ─────────────────────────────────────────────────────────────
# ADD this new /respond route — the conversation loop engine
# ─────────────────────────────────────────────────────────────

@app.route("/respond", methods=["POST"])
def respond():
    """
    The conversation loop.
    Every time the spammer speaks, Twilio hits this endpoint.
    We: get their speech → run LLM → speak reply → listen again.

    This loop runs indefinitely until the caller hangs up.
    Each iteration = one exchange (them speaking + agent replying).
    """
    call_sid    = request.form.get("CallSid", "")
    caller      = request.form.get("From", "Unknown")
    speech_result = request.form.get("SpeechResult", "").strip()
    confidence  = float(request.form.get("Confidence", "0"))

    resp = VoiceResponse()

    # Get or create call state
    state = get_state(call_sid)
    if not state:
        # Edge case: state lost (e.g. worker restart) — reassign gracefully
        logger.warning(f"[{call_sid}] No state found — reassigning agent")
        agent = assign_agent(call_sid)
    else:
        agent = state["agent"]

    # Handle empty or low-confidence STT
    if not speech_result or confidence < 0.3:
        logger.info(f"[{call_sid}] Low/empty STT (confidence={confidence:.2f}) — using stall")
        reply = get_stall_tactic(call_sid)
    else:
        logger.info(f"[{call_sid}] Spammer said: '{speech_result[:80]}'")

        # Check for escalation trigger
        escalate = should_escalate(call_sid)

        # Generate LLM response
        history = state["history"] if state else []
        reply   = generate_response(
            agent=agent,
            history=history,
            user_speech=speech_result,
            escalate=escalate,
        )

        # Store the exchange
        add_exchange(call_sid, speech_result, reply)

    # Log elapsed time for leaderboard data
    elapsed = elapsed_seconds(call_sid)
    logger.info(f"[{call_sid}] Agent reply ({elapsed}s elapsed): {reply[:80]}")

    # Speak the reply and listen for the next input
    gather = Gather(
        input="speech",
        action=f"{BASE_URL}/respond",
        method="POST",
        speech_timeout="auto",
        speech_model="phone_call",
        enhanced=True,
        language="en-US",
    )
    gather.say(reply, voice=agent["voice"])
    resp.append(gather)

    # If silence — loop back to /respond which triggers a stall
    resp.redirect(f"{BASE_URL}/respond", method="POST")

    return Response(str(resp), mimetype="text/xml")


# ─────────────────────────────────────────────────────────────
# REPLACE existing /status route with this version
# (adds end_call cleanup and leaderboard logging)
# ─────────────────────────────────────────────────────────────

@app.route("/status", methods=["POST"])
def call_status():
    sid      = request.form.get("CallSid", "")
    status   = request.form.get("CallStatus", "")
    duration = request.form.get("CallDuration", "0")
    to       = request.form.get("To", "Unknown")

    logger.info(f"Call {sid} to {to} | Status: {status} | Duration: {duration}s")

    if status == "completed":
        logger.info(
            f"LEADERBOARD: Spammer {to} endured {duration}s. "
            f"Scammer minutes wasted: {int(duration) // 60}m {int(duration) % 60}s"
        )
        end_call(sid)   # Clean up in-memory state

    return Response("", status=204)


# ─────────────────────────────────────────────────────────────
# ADD this import at the top of app.py with other Twilio imports
# ─────────────────────────────────────────────────────────────
# from twilio.twiml.voice_response import VoiceResponse, Play, Gather
# (replace existing VoiceResponse, Play import line)
