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
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Play
from dotenv import load_dotenv
from spam_checker import is_spam

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Twilio credentials (set in .env) ---
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
MY_TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")   # Your Twilio number, e.g. +14015550100

# Rick Roll audio URL - publicly hosted MP3.
# You can replace this with any audio file URL you host (e.g. Cloudflare R2, S3).
RICK_ROLL_URL = os.getenv(
    "RICK_ROLL_URL",
    "https://ia803108.us.archive.org/21/items/NeverGonnaGiveYouUp/jocofullinterview__comp.mp3"
)

client = Client(ACCOUNT_SID, AUTH_TOKEN)


# ---------------------------------------------------------------------------
# Webhook: Twilio calls this when YOUR number receives an incoming call
# ---------------------------------------------------------------------------
@app.route("/incoming", methods=["POST"])
def incoming_call():
    """
    Twilio hits this endpoint the moment a call arrives.
    We check if it's spam, then decide what to do.
    """
    caller   = request.form.get("From", "Unknown")
    call_sid = request.form.get("CallSid", "")

    logger.info(f"Incoming call from: {caller} | SID: {call_sid}")

    resp = VoiceResponse()

    if is_spam(caller):
        logger.info(f"SPAM DETECTED: {caller} — initiating callback trap")

        # Tell the spammer to hold (they usually hang up fast; this buys time)
        resp.say("Please hold.", voice="alice")
        resp.pause(length=2)

        # Fire the callback in the background — trap is set
        _launch_callback(caller)

        # Hang up our end; the REAL punishment starts on their callback
        resp.hangup()
    else:
        # Legitimate call — ring through normally (or handle however you like)
        resp.say("Thank you for calling. Connecting you now.", voice="alice")
        # TODO: add <Dial> here if you want to forward to a real number

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
    caller = request.form.get("To", "Unknown")
    logger.info(f"Spammer {caller} answered callback — Rick Roll engaged 🎵")

    resp = VoiceResponse()
    resp.say("We've been expecting you.", voice="alice")

    # loop=0 means infinite loop — they're stuck until THEY hang up
    resp.append(Play(RICK_ROLL_URL, loop=0))

    return Response(str(resp), mimetype="text/xml")


# ---------------------------------------------------------------------------
# Internal: Launch the outbound callback to the spammer's number
# ---------------------------------------------------------------------------
def _launch_callback(spam_number: str):
    """
    Dials the spammer back using Twilio's REST API.
    When they answer, Twilio hits /rickroll and the loop begins.
    """
    base_url = os.getenv("BASE_URL")  # e.g. https://abc123.ngrok.io

    try:
        call = client.calls.create(
            to=spam_number,
            from_=MY_TWILIO_NUMBER,
            url=f"{base_url}/rickroll",   # Twilio fetches TwiML from here on connect
            status_callback=f"{base_url}/status",
            status_callback_event=["completed"],
        )
        logger.info(f"Callback launched → SID: {call.sid}")
    except Exception as e:
        logger.error(f"Failed to launch callback to {spam_number}: {e}")


# ---------------------------------------------------------------------------
# Optional: Status callback for logging call completion
# ---------------------------------------------------------------------------
@app.route("/status", methods=["POST"])
def call_status():
    sid      = request.form.get("CallSid")
    status   = request.form.get("CallStatus")
    duration = request.form.get("CallDuration", "0")
    to       = request.form.get("To")

    logger.info(f"Call {sid} to {to} ended — Status: {status} | Duration: {duration}s")

    if status == "completed":
        logger.info(f"Spammer {to} endured {duration} seconds of Rick Astley 🏆")

    return Response("", status=204)


if __name__ == "__main__":
    # Use debug=False in production
    app.run(host="0.0.0.0", port=5000, debug=True)
