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
from twilio.twiml.voice_response import VoiceResponse, Play
from dotenv import load_dotenv
from spam_checker import is_spam

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
    Twilio hits this endpoint the moment a call arrives.
    We check if it's spam, then decide what to do.
    """
    if not _validate_twilio_request():
        logger.warning("Rejected invalid Twilio signature for /incoming")
        return _hangup_twiml_response(status_code=403)

    try:
        caller = request.form.get("From", "Unknown")
        call_sid = request.form.get("CallSid", "")

        logger.info("Incoming call from: %s | SID: %s", caller, call_sid)

        resp = VoiceResponse()

        if is_spam(caller):
            logger.info("SPAM DETECTED: %s - initiating callback trap", caller)

            resp.say("Please hold.", voice="alice")
            resp.pause(length=2)
            _launch_callback(caller)
            resp.hangup()
        else:
            resp.say("Thank you for calling. Connecting you now.", voice="alice")

        return _twiml_response(resp)
    except Exception:
        logger.exception("Internal error while handling /incoming")
        return _hangup_twiml_response()


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
    sid      = request.form.get("CallSid")
    status   = request.form.get("CallStatus")
    duration = request.form.get("CallDuration", "0")
    to       = request.form.get("To")

    logger.info("Call %s to %s ended - Status: %s | Duration: %ss", sid, to, status, duration)

    if status == "completed":
        logger.info("Spammer %s endured %s seconds of Rick Astley", to, duration)

    return Response("", status=204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))  # noqa: S104  # nosec B104
