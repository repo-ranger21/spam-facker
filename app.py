"""
Spam Call Revenge Bot
=====================
Uses Twilio to detect spam calls, call them back, and trap them
in an infinite Rick Roll loop.

Think of this like a bouncer at a club:
- Incoming call = someone knocking at the door
- Spam check = bouncer checking the guest list
- Callback + Rick Roll = if you're on the NO list, you get escorted
  into a room and Rick Astley never lets you leave.

Setup:
    pip install flask twilio requests python-dotenv

Run:
    python app.py

Expose locally with ngrok:
    ngrok http 5000
    Then set your Twilio webhook to: https://<your-ngrok>.ngrok.io/incoming
"""

import os
import logging
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, Response, jsonify, request, send_from_directory
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Play, Gather
from dotenv import load_dotenv
from spam_checker import is_spam
from conversation import assign_agent, get_state, add_exchange, \
    should_escalate, end_call, get_stall_tactic, elapsed_seconds
from llm import generate_response, generate_stall

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")

# --- Twilio credentials (set in .env) ---
ACCOUNT_SID = _require_env("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = _require_env("TWILIO_AUTH_TOKEN")
MY_TWILIO_NUMBER = _require_env("TWILIO_PHONE_NUMBER")
# BASE_URL must exactly match the webhook URL configured in Twilio and must not end with a trailing slash.
BASE_URL = _require_env("BASE_URL").rstrip("/")

# Rick Roll audio URL - publicly hosted MP3.
# You can replace this with any audio file URL you host (e.g. Cloudflare R2, S3).
RICK_ROLL_URL = os.getenv("RICK_ROLL_URL", f"{BASE_URL}/audio/snippet.mp3")

client = Client(ACCOUNT_SID, AUTH_TOKEN)
request_validator = RequestValidator(AUTH_TOKEN)
STATIC_DIR = Path(app.root_path) / "static"


def _build_request_url() -> str:
    if request.args:
        return f"{BASE_URL}{request.path}?{urlencode(request.args, doseq=True)}"
    return f"{BASE_URL}{request.path}"


def _hangup_twiml_response(status_code: int = 200) -> Response:
    resp = VoiceResponse()
    resp.hangup()
    return Response(str(resp), status=status_code, mimetype="text/xml")


def _twiml_response(response: VoiceResponse, status_code: int = 200) -> Response:
    return Response(str(response), status=status_code, mimetype="text/xml")


def _validate_twilio_request() -> bool:
    signature = request.headers.get("X-Twilio-Signature", "")
    return request_validator.validate(_build_request_url(), request.form, signature)


@app.after_request
def add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Twilio-Signature"
    return response


# ---------------------------------------------------------------------------
# Static audio endpoint used by Twilio <Play>
# ---------------------------------------------------------------------------
@app.route("/audio/snippet.mp3", methods=["GET"])
def audio_snippet():
    snippet_path = STATIC_DIR / "snippet.mp3"
    if not snippet_path.is_file():
        logger.error("Audio snippet missing at %s", snippet_path)
        return jsonify({"error": "snippet.mp3 not found"}), 404
    return send_from_directory("static", "snippet.mp3", mimetype="audio/mpeg")


@app.route("/health", methods=["GET"])
def health() -> Response:
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Webhook: Twilio calls this when YOUR number receives an incoming call
# ---------------------------------------------------------------------------
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
        logger.warning(f"[{call_sid}] State lost — reassigning agent")
        agent = assign_agent(call_sid)
        state = get_state(call_sid)
    else:
        agent = state["agent"]

    # Voice consistency guard — never fall back to Twilio default
    voice = agent.get("voice", "Polly.Kendra")

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
    gather.say(reply, voice=voice)
    resp.append(gather)

    # If silence — loop back to /respond which triggers a stall
    resp.redirect(f"{BASE_URL}/respond", method="POST")

    return Response(str(resp), mimetype="text/xml")


# ---------------------------------------------------------------------------
# Webhook: Twilio calls this when the OUTBOUND callback connects
# ---------------------------------------------------------------------------
@app.route("/rickroll", methods=["POST"])
def rickroll():
    """
    This is the trap room.
    Once the spammer answers our callback, this endpoint plays
    Rick Astley on an infinite loop.

    The <Play loop="0"> instruction is like a broken record —
    "0" means loop forever in Twilio's TwiML spec.
    """
    if not _validate_twilio_request():
        logger.warning("Rejected invalid Twilio signature for /rickroll")
        return _hangup_twiml_response(status_code=403)

    try:
        caller = request.form.get("To", "Unknown")
        logger.info("Spammer %s answered callback - Rick Roll engaged", caller)

        resp = VoiceResponse()
        resp.say("We've been expecting you.", voice="alice")
        resp.append(Play(RICK_ROLL_URL, loop=0))

        return _twiml_response(resp)
    except Exception:
        logger.exception("Internal error while handling /rickroll")
        return _hangup_twiml_response()


# ---------------------------------------------------------------------------
# Internal: Launch the outbound callback to the spammer's number
# ---------------------------------------------------------------------------
def _launch_callback(spam_number: str):
    """
    Dials the spammer back using Twilio's REST API.
    When they answer, Twilio hits /rickroll and the loop begins.
    """
    try:
        call = client.calls.create(
            to=spam_number,
            from_=MY_TWILIO_NUMBER,
            url=f"{BASE_URL}/rickroll",
            status_callback=f"{BASE_URL}/status",
            status_callback_event=["completed"],
        )
        logger.info("Callback launched - SID: %s", call.sid)
    except TwilioRestException as exc:
        logger.error(
            "Twilio callback failed for %s - code=%s message=%s",
            spam_number,
            exc.code,
            exc.msg,
        )
    except Exception:
        logger.exception("Unexpected error while launching callback to %s", spam_number)


# ---------------------------------------------------------------------------
# Optional: Status callback for logging call completion
# ---------------------------------------------------------------------------
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))  # noqa: S104  # nosec B104
