"""
spam_checker.py
===============
Determines whether an incoming phone number is a spam caller.

Think of this like a multi-layer airport security check:
  Layer 1 = Your own personal no-fly list (manual blocklist)
  Layer 2 = TSA database (Twilio Lookup spam risk score)
  Layer 3 = Third-party intel (Nomorobo API)

Any layer can flag a number as spam. First hit wins.
"""

import os
import logging
import requests
from dotenv import load_dotenv
from requests import RequestException
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

load_dotenv()

logger = logging.getLogger(__name__)

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# --- Layer 1: Your personal blocklist ---
# Add any numbers you KNOW are spam (E.164 format: +1XXXXXXXXXX)
MANUAL_BLOCKLIST: set[str] = {
    "+14016127630",
}

# --- Twilio spam risk threshold (0–100) ---
# 75+ = likely spam. Lower = more aggressive filtering.
TWILIO_SPAM_THRESHOLD = int(os.getenv("SPAM_THRESHOLD", "75"))

# --- Nomorobo API (optional) ---
# Sign up free at nomorobo.com for robocall detection
NOMOROBO_API_KEY = os.getenv("NOMOROBO_API_KEY", "")


def is_spam(phone_number: str) -> bool:
    """
    Main entry point. Returns True if the number is spam.
    Runs all three layers in sequence.
    """
    if not phone_number or phone_number == "Unknown":
        logger.warning("Unknown caller — treating as non-spam to be safe")
        return False

    # Layer 1: Manual blocklist (instant, no API call)
    if _check_manual_blocklist(phone_number):
        logger.info(f"{phone_number} hit manual blocklist")
        return True

    # Layer 2: Twilio Lookup spam risk
    twilio_lookup_result = _check_twilio_lookup(phone_number)
    if twilio_lookup_result is True:
        logger.info(f"{phone_number} flagged by Twilio Lookup")
        return True

    # Layer 3: Nomorobo (if API key is configured)
    nomorobo_result = False
    if NOMOROBO_API_KEY:
        nomorobo_result = _check_nomorobo(phone_number)
    if nomorobo_result is True:
        logger.info(f"{phone_number} flagged by Nomorobo")
        return True

    if twilio_lookup_result is None and nomorobo_result is None:
        logger.warning(
            "Twilio Lookup and Nomorobo unavailable for %s; falling back to manual blocklist only",
            phone_number,
        )

    logger.info(f"{phone_number} passed all spam checks — likely legitimate")
    return False


# ---------------------------------------------------------------------------
# Layer 1: Manual blocklist
# ---------------------------------------------------------------------------
def _check_manual_blocklist(phone_number: str) -> bool:
    return phone_number in MANUAL_BLOCKLIST


# ---------------------------------------------------------------------------
# Layer 2: Twilio Lookup API with spam risk add-on
# Docs: https://www.twilio.com/docs/lookup/v2-api/spam-risk
# Cost: ~$0.01 per lookup (check your Twilio pricing)
# ---------------------------------------------------------------------------
def _check_twilio_lookup(phone_number: str) -> bool | None:
    if not ACCOUNT_SID or not AUTH_TOKEN:
        logger.warning("Twilio creds not set — skipping Lookup check")
        return False

    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        result = client.lookups.v2.phone_numbers(phone_number).fetch(
            fields=["spam_risk"]
        )

        spam_risk = getattr(result, "spam_risk", None) or {}
        score = spam_risk.get("score", 0)
        level = spam_risk.get("level", "none")

        logger.info(f"Twilio Lookup — {phone_number}: score={score}, level={level}")

        return score >= TWILIO_SPAM_THRESHOLD

    except TwilioRestException as exc:
        logger.error(
            "Twilio Lookup failed for %s: code=%s message=%s",
            phone_number,
            exc.code,
            exc.msg,
        )
        return None
    except Exception as exc:
        logger.error(f"Twilio Lookup failed for {phone_number}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Layer 3: Nomorobo (robocall-specific detection)
# Docs: https://api.nomorobo.com
# ---------------------------------------------------------------------------
def _check_nomorobo(phone_number: str) -> bool | None:
    try:
        # Nomorobo expects the number without the leading +1
        clean_number = phone_number.lstrip("+").lstrip("1")

        response = requests.get(
            f"https://api.nomorobo.com/1.0/lookup/{clean_number}",
            headers={"X-API-Key": NOMOROBO_API_KEY},
            timeout=3,
        )

        if response.status_code == 200:
            data = response.json()
            # Nomorobo returns 1 for robocalls and 0 for clean numbers.
            score = data.get("score", 0)
            logger.info(f"Nomorobo — {phone_number}: score={score}")
            return score == 1

    except RequestException as exc:
        logger.error(f"Nomorobo check failed for {phone_number}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Nomorobo check failed for {phone_number}: {exc}")
        return None

    return False


# ---------------------------------------------------------------------------
# Utility: Manually add to blocklist at runtime
# ---------------------------------------------------------------------------
def add_to_blocklist(phone_number: str):
    MANUAL_BLOCKLIST.add(phone_number)
    logger.info(f"Added {phone_number} to runtime blocklist")
