"""
Spam Call Revenge Bot
=====================
Uses Twilio to detect spam calls, call them back, and trap them
in an infinite Rick Roll loop.
...
"""

import atexit
import logging
import os
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, send_from_directory, stream_with_context
from flask_sock import Sock
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Gather, Play, Stream, VoiceResponse
from werkzeug.utils import secure_filename

from conversation import (
    PendingReplyRegistry,
    StreamingRegistry,
    add_exchange,
    assign_agent,
    elapsed_seconds,
    end_call,
    get_stall_tactic,
    get_state,
    should_escalate,
)
from llm import generate_response
from record_util import RECORDINGS_DIR, make_mp4
from spam_checker import is_spam
from tts import FillerMissingError, cleanup_old_files, get_filler_url, stream_tts, synthesize

load_dotenv()

app = Flask(__name__)
sock = Sock(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

XML_MIMETYPE = "text/xml"
NOT_FOUND_BODY = "Not found"


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_gather(action: str) -> Gather:
    """Return a standard Gather verb pointed at the given action URL."""
    return Gather(
        input="speech",
        action=action,
        method="POST",
        speech_timeout=2,
        speech_model="phone_call",
        enhanced=True,
        language="en-US",
        action_on_empty_result=True,
    )


def _generate_and_synthesize(
    call_sid: str,
    speech_result: str,
    seq: int,
) -> str | None:
    """
    Background task: LLM generation + TTS synthesis → audio URL.
    Runs in ThreadPoolExecutor. Must not raise; returns None on failure.
    """
    t0 = time.monotonic()
    state = get_state(call_sid)
    if not state:
        logger.warning(
            "respond.generation_started: state missing",
            extra={"call_sid": call_sid, "agent": "unknown", "seq": seq},
        )
        return None

    agent = state.agent
    logger.info(
        "respond.generation_started",
        extra={"call_sid": call_sid, "agent": agent["name"], "seq": seq},
    )

    try:
        escalate = should_escalate(call_sid)
        history = state.history
        reply = generate_response(
            agent=agent,
            history=history,
            user_speech=speech_result,
            escalate=escalate,
            state=state,
        )
        add_exchange(call_sid, speech_result, reply)

        gen_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "respond.generation_complete",
            extra={
                "call_sid": call_sid,
                "agent": agent["name"],
                "seq": seq,
                "duration_ms": gen_ms,
            },
        )

        if ENABLE_STREAMING_TTS:
            voice_id = agent.get("elevenlabs_voice_id", "")
            token = _streaming_registry.register(reply, voice_id)
            return f"{BASE_URL}/audio/stream/{token}.mp3"

        voice_id = agent.get("elevenlabs_voice_id")
        if voice_id:
            tts_path = synthesize(reply, voice_id, call_sid)
            if tts_path:
                return f"{BASE_URL}/audio/tts/{Path(tts_path).name}"
        return None

    except Exception:
        logger.exception(
            "Background generation failed",
            extra={"call_sid": call_sid, "agent": agent.get("name", "?"), "seq": seq},
        )
        return None


def _prewarm_tts(
    text: str,
    voice_id: str,
    call_sid: str,
) -> None:
    """Pre-generate TTS in a background thread."""
    if not get_state(call_sid):
        logger.info("TTS prewarm skipped; call %s already ended", call_sid)
        return

    try:
        synthesize(text, voice_id, call_sid)
    except Exception:
        logger.exception("[%s] TTS prewarm failed", call_sid)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


ACCOUNT_SID = _require_env("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = _require_env("TWILIO_AUTH_TOKEN")
MY_TWILIO_NUMBER = _require_env("TWILIO_PHONE_NUMBER")
BASE_URL = _require_env("BASE_URL").rstrip("/")
RICK_ROLL_URL = os.getenv(
    "RICK_ROLL_URL",
    f"{BASE_URL}/audio/snippet.mp3",
)
CREATOR_STRIKE_ENABLED = os.getenv("CREATOR_STRIKE_ENABLED", "false").lower() == "true"
CREATOR_STRIKE_STRIPE_URL = os.getenv("CREATOR_STRIKE_STRIPE_URL", "")

client = Client(ACCOUNT_SID, AUTH_TOKEN)
request_validator = RequestValidator(AUTH_TOKEN)
STATIC_DIR = Path(app.root_path) / "static"

# ---------------------------------------------------------------------------
# Feature flags — flip to "true" in .env once each phase is smoke-tested
# ---------------------------------------------------------------------------
ENABLE_FILLERS = os.getenv("ENABLE_FILLERS", "false").lower() == "true"
ENABLE_STREAMING_TTS = os.getenv("ENABLE_STREAMING_TTS", "false").lower() == "true"
# ENABLE_REALTIME, REALTIME_TRAFFIC_PERCENT, REALTIME_FALLBACK_TO_LEGACY
# are read at call time via os.getenv() inside _should_route_to_realtime()

# ---------------------------------------------------------------------------
# Async LLM + TTS infrastructure
# ---------------------------------------------------------------------------
_thread_pool = ThreadPoolExecutor(max_workers=8)
_pending_registry = PendingReplyRegistry()
_streaming_registry = StreamingRegistry()

# ---------------------------------------------------------------------------
# Realtime bridge registry — tracks all in-flight bridges for atexit cleanup
# ---------------------------------------------------------------------------
_bridge_registry: dict[str, "RealtimeBridge"] = {}
_bridge_registry_lock = threading.Lock()

# call_sid → {"mp3": str, "mp4": str | None}
_recordings: dict[str, dict] = {}
_recordings_lock = threading.Lock()

# Caller cascade tracking: scammer number -> count of agent callbacks already placed
_caller_log: dict[str, int] = {}
_caller_log_lock = threading.Lock()
CALLBACK_CAP = 3          # total agent callbacks after the initial song
CALLBACK_DELAY_SEC = 60   # delay after each call ends before the next callback


def _shutdown_thread_pool() -> None:
    _thread_pool.shutdown(wait=False)


def _shutdown_bridges() -> None:
    """Gracefully close all in-flight realtime bridges on process shutdown."""
    with _bridge_registry_lock:
        bridges = list(_bridge_registry.values())
    for bridge in bridges:
        try:
            bridge.cleanup()
        except Exception:
            pass


atexit.register(_shutdown_thread_pool)
atexit.register(_shutdown_bridges)


def _should_route_to_realtime() -> bool:
    """Return True if this spam call should be routed to the realtime bridge."""
    if os.getenv("ENABLE_REALTIME", "false").lower() != "true":
        return False
    pct = int(os.getenv("REALTIME_TRAFFIC_PERCENT", "0"))
    if pct <= 0:
        return False
    return random.randint(1, 100) <= pct


def _ws_host() -> str:
    """Extract public hostname from BASE_URL for WebSocket URL construction."""
    return urlparse(BASE_URL).netloc


def _realtime_twiml(call_sid: str, caller: str) -> Response:
    """
    Build TwiML to connect a spam call to the realtime bridge.
    Assigns an agent, builds <Connect><Stream>, and launches the Rick Roll
    callback in background (same as legacy path).
    """
    # Import here to avoid circular import at module level
    from bridge.realtime_bridge import RealtimeBridge  # noqa: F401 (ensures bridge module loaded)

    agent = assign_agent(call_sid)
    state = get_state(call_sid)
    agent_key = state.agent_key if state else "mildred"

    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f"wss://{_ws_host()}/media-stream")
    stream.parameter(name="agent", value=agent_key)
    stream.parameter(name="call_sid", value=call_sid)
    connect.append(stream)
    response.append(connect)

    logger.info(
        "Routing call %s to realtime bridge | agent=%s", call_sid, agent_key
    )

    threading.Thread(
        target=_launch_callback,
        args=(caller,),
        daemon=True,
    ).start()

    return _twiml_response(response)


def _build_request_url() -> str:
    if request.args:
        query_string = urlencode(request.args, doseq=True)
        return f"{BASE_URL}{request.path}?{query_string}"
    return f"{BASE_URL}{request.path}"


def _hangup_twiml_response(status_code: int = 200) -> Response:
    response = VoiceResponse()
    response.hangup()
    return Response(
        str(response),
        status=status_code,
        mimetype=XML_MIMETYPE,
    )


def _twiml_response(
    response: VoiceResponse,
    status_code: int = 200,
) -> Response:
    return Response(
        str(response),
        status=status_code,
        mimetype=XML_MIMETYPE,
    )


def _validate_twilio_request() -> bool:
    signature = request.headers.get("X-Twilio-Signature", "")
    return request_validator.validate(
        _build_request_url(),
        request.form,
        signature,
    )


_CORS_ALLOWED_PATHS = {"/health", "/audio/snippet.mp3"}


@app.after_request
def add_cors_headers(response: Response) -> Response:
    if (
        request.path in _CORS_ALLOWED_PATHS
        or request.path.startswith("/audio/tts/")
        or request.path.startswith("/audio/fillers/")
        or request.path.startswith("/audio/stream/")
    ):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/audio/snippet.mp3", methods=["GET"])
def audio_snippet():
    snippet_path = STATIC_DIR / "snippet.mp3"
    if not snippet_path.is_file():
        logger.error("Audio snippet missing at %s", snippet_path)
        return jsonify({"error": "snippet.mp3 not found"}), 404
    return send_from_directory(
        str(STATIC_DIR),
        "snippet.mp3",
        mimetype="audio/mpeg",
    )


@app.route("/health", methods=["GET"])
def health() -> Response:
    return jsonify({"status": "ok"})


@app.route("/audio/tts/<filename>", methods=["GET"])
def serve_tts(filename: str) -> Response:
    """Serve ElevenLabs-generated TTS files."""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return Response(NOT_FOUND_BODY, status=404)

    tts_dir = (STATIC_DIR / "tts").resolve()
    candidate = (tts_dir / safe_filename).resolve()

    try:
        candidate.relative_to(tts_dir)
    except ValueError:
        logger.warning("Path traversal attempt blocked: %s", filename)
        return Response(NOT_FOUND_BODY, status=404)

    if not candidate.exists():
        return Response(NOT_FOUND_BODY, status=404)

    return send_from_directory(
        str(tts_dir),
        safe_filename,
        mimetype="audio/mpeg",
    )


@app.route("/incoming", methods=["POST"])
def incoming_call() -> Response:
    if not _validate_twilio_request():
        caller = request.form.get("From", "Unknown")
        logger.warning(
            "Invalid Twilio signature for /incoming from %s",
            caller,
        )
        return Response("Forbidden", status=403)

    caller = request.form.get("From", "Unknown")
    call_sid = request.form.get("CallSid", "")

    logger.info("Incoming call from: %s | SID: %s", caller, call_sid)

    response = VoiceResponse()

    if is_spam(caller):
        with _caller_log_lock:
            first_time = caller not in _caller_log
            if first_time:
                _caller_log[caller] = 0

        if first_time:
            logger.info("FIRST CONTACT: %s; playing song on infinite loop", caller)
            response.play(RICK_ROLL_URL, loop=0)
            # Song loops until they hang up. The /status 'completed' event then
            # kicks off the agent callback cascade.
            return _twiml_response(response)

        # Returning caller (voluntary redial): deploy a live agent. No song,
        # no callback spawn here — the cascade is driven entirely by /status.
        logger.info("RETURNING CALLER: %s; deploying agent", caller)
        if _should_route_to_realtime():
            return _realtime_twiml(call_sid, caller)

        agent = assign_agent(call_sid)
        gather = Gather(
            input="speech",
            action=f"{BASE_URL}/respond",
            method="POST",
            speech_timeout=2,
            speech_model="phone_call",
            enhanced=True,
            language="en-US",
            action_on_empty_result=True,
        )
        voice_id = agent.get("elevenlabs_voice_id")
        tts_path = (
            synthesize(agent["intro"], voice_id, call_sid)
            if voice_id
            else None
        )
        if tts_path:
            gather.play(f"{BASE_URL}/audio/tts/{Path(tts_path).name}")
        else:
            gather.say(agent["intro"], voice=agent["voice"])
        response.append(gather)
        response.redirect(f"{BASE_URL}/respond", method="POST")
    else:
        response.say(
            "Thank you for calling. Please hold.",
            voice="Polly.Joanna",
        )

    return _twiml_response(response)


@app.route("/respond", methods=["POST"])
def respond() -> Response:
    """Continue the spammer conversation loop."""
    if not _validate_twilio_request():
        logger.warning("Invalid Twilio signature for /respond")
        return _hangup_twiml_response(status_code=403)

    call_sid = request.form.get("CallSid", "")
    speech_result = request.form.get("SpeechResult", "").strip()
    confidence = _safe_float(request.form.get("Confidence", "0"))

    state = get_state(call_sid)
    if not state:
        logger.warning("[%s] State lost; reassigning agent", call_sid)
        agent = assign_agent(call_sid)
        state = get_state(call_sid)
    else:
        agent = state.agent

    voice = agent.get("voice", "Polly.Kendra")
    seq = state.turn_count if state else 0

    # --- Low-confidence / empty STT: stall synchronously (both paths) ---
    if not speech_result or confidence < 0.3:
        logger.info(
            "[%s] Low or empty STT (confidence=%.2f); using stall",
            call_sid,
            confidence,
        )
        reply = get_stall_tactic(call_sid)
        gather = _build_gather(f"{BASE_URL}/respond")
        voice_id = agent.get("elevenlabs_voice_id")
        tts_path = synthesize(reply, voice_id, call_sid) if voice_id else None
        response = VoiceResponse()
        if tts_path:
            gather.play(f"{BASE_URL}/audio/tts/{Path(tts_path).name}")
        else:
            gather.say(reply, voice=voice)
        response.append(gather)
        response.redirect(f"{BASE_URL}/respond", method="POST")
        return _twiml_response(response)

    # --- Real speech input ---
    if ENABLE_FILLERS:
        # Async path: kick off LLM+TTS in background, play filler immediately
        future = _thread_pool.submit(
            _generate_and_synthesize, call_sid, speech_result, seq
        )
        _pending_registry.start(call_sid, seq, future)
        logger.info(
            "respond.filler_dispatched",
            extra={"call_sid": call_sid, "agent": agent["name"], "seq": seq},
        )

        response = VoiceResponse()
        try:
            filler_url = get_filler_url(agent["name"], BASE_URL)
            response.play(filler_url)
        except FillerMissingError:
            response.say("One moment please.", voice=voice)

        continue_url = (
            f"{BASE_URL}/respond_continue"
            f"?{urlencode({'call_sid': call_sid, 'seq': seq})}"
        )
        response.redirect(continue_url, method="POST")
        return _twiml_response(response)

    # Legacy synchronous path (ENABLE_FILLERS=false)
    logger.info("[%s] Spammer said: %r", call_sid, speech_result[:80])
    escalate = should_escalate(call_sid)
    history = state.history if state else []
    reply = generate_response(
        agent=agent,
        history=history,
        user_speech=speech_result,
        escalate=escalate,
        state=state,
    )
    add_exchange(call_sid, speech_result, reply)

    stall = get_stall_tactic(call_sid)
    threading.Thread(
        target=_prewarm_tts,
        args=(stall, agent.get("elevenlabs_voice_id", ""), call_sid),
        daemon=True,
    ).start()

    elapsed = elapsed_seconds(call_sid)
    logger.info(
        "[%s] Agent reply (%ss elapsed): %s",
        call_sid,
        elapsed,
        reply[:80],
    )

    gather = _build_gather(f"{BASE_URL}/respond")
    voice_id = agent.get("elevenlabs_voice_id")
    tts_path = synthesize(reply, voice_id, call_sid) if voice_id else None

    response = VoiceResponse()
    if tts_path:
        gather.play(f"{BASE_URL}/audio/tts/{Path(tts_path).name}")
    else:
        gather.say(reply, voice=voice)
    response.append(gather)
    response.redirect(f"{BASE_URL}/respond", method="POST")
    return _twiml_response(response)


@app.route("/respond_continue", methods=["POST"])
def respond_continue() -> Response:
    """Block (up to 4 s) for the background LLM+TTS result, then respond."""
    if not _validate_twilio_request():
        logger.warning("Invalid Twilio signature for /respond_continue")
        return _hangup_twiml_response(status_code=403)

    call_sid = request.form.get("CallSid", "")
    seq = _safe_int(request.args.get("seq", "0"))

    state = get_state(call_sid)
    agent = state.agent if state else {}
    voice = agent.get("voice", "Polly.Kendra")
    agent_name = agent.get("name", "unknown")

    logger.info(
        "respond_continue.awaiting",
        extra={"call_sid": call_sid, "agent": agent_name, "seq": seq},
    )

    result_url = _pending_registry.await_result(call_sid, seq, timeout_sec=4.0)

    response = VoiceResponse()
    gather = _build_gather(f"{BASE_URL}/respond")

    if result_url:
        logger.info(
            "respond_continue.served",
            extra={"call_sid": call_sid, "agent": agent_name, "seq": seq},
        )
        gather.play(result_url)
    else:
        logger.warning(
            "respond_continue.timed_out",
            extra={"call_sid": call_sid, "agent": agent_name, "seq": seq},
        )
        gather.say(
            "I'm sorry, the line is a bit fuzzy, could you say that again?",
            voice=voice,
        )

    response.append(gather)
    response.redirect(f"{BASE_URL}/respond", method="POST")
    return _twiml_response(response)


@app.route("/audio/stream/<token>.mp3", methods=["GET"])
def audio_stream(token: str) -> Response:
    """Serve streaming TTS audio for a single-use token (Phase 2)."""
    spec = _streaming_registry.pop(token)
    if spec is None:
        abort(404)
    return Response(
        stream_with_context(stream_tts(spec.text, spec.voice_id)),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/audio/fillers/<agent_slug>/<filename>", methods=["GET"])
def serve_filler(agent_slug: str, filename: str) -> Response:
    """Serve pre-rendered filler audio files (Phase 1)."""
    safe_slug = secure_filename(agent_slug)
    safe_file = secure_filename(filename)
    if not safe_slug or not safe_file:
        return Response(NOT_FOUND_BODY, status=404)

    fillers_dir = (STATIC_DIR / "tts" / "fillers").resolve()
    agent_dir = fillers_dir / safe_slug
    candidate = (agent_dir / safe_file).resolve()

    try:
        candidate.relative_to(fillers_dir)
    except ValueError:
        logger.warning(
            "Path traversal attempt for filler: %s/%s", agent_slug, filename
        )
        return Response(NOT_FOUND_BODY, status=404)

    if not candidate.exists():
        return Response(NOT_FOUND_BODY, status=404)

    return send_from_directory(str(agent_dir), safe_file, mimetype="audio/mpeg")


@app.route("/rickroll", methods=["POST"])
def rickroll() -> Response:
    """Trap room for the outbound callback."""
    if not _validate_twilio_request():
        logger.warning("Rejected invalid Twilio signature for /rickroll")
        return _hangup_twiml_response(status_code=403)

    try:
        caller = request.form.get("To", "Unknown")
        logger.info("Spammer %s answered callback; Rick Roll engaged", caller)

        response = VoiceResponse()
        response.say("We've been expecting you.", voice="alice")
        response.append(Play(RICK_ROLL_URL, loop=0))
        return _twiml_response(response)
    except Exception:
        logger.exception("Internal error while handling /rickroll")
        return _hangup_twiml_response()


def _launch_callback(spam_number: str) -> None:
    """Dial the spammer back using Twilio's REST API."""
    try:
        create_kwargs: dict = dict(
            to=spam_number,
            from_=MY_TWILIO_NUMBER,
            url=f"{BASE_URL}/rickroll",
            status_callback=f"{BASE_URL}/status",
            status_callback_event=["completed"],
        )
        if CREATOR_STRIKE_ENABLED:
            create_kwargs["record"] = True
            create_kwargs["recording_status_callback"] = f"{BASE_URL}/recording_ready"
        call = client.calls.create(**create_kwargs)
        logger.info("Callback launched; SID: %s", call.sid)
    except TwilioRestException as exc:
        logger.exception(
            "Twilio callback failed for %s; code=%s message=%s",
            spam_number,
            exc.code,
            exc.msg,
        )
    except Exception:
        logger.exception(
            "Unexpected error while launching callback to %s",
            spam_number,
        )


def _launch_agent_callback(spam_number: str) -> None:
    """Dial the spammer back and route them straight into a live agent."""
    try:
        call = client.calls.create(
            to=spam_number,
            from_=MY_TWILIO_NUMBER,
            url=f"{BASE_URL}/agent_callback",
            status_callback=f"{BASE_URL}/status",
            status_callback_event=["completed"],
        )
        logger.info("Agent callback launched to %s; SID: %s", spam_number, call.sid)
    except TwilioRestException as exc:
        logger.exception(
            "Agent callback failed for %s; code=%s message=%s",
            spam_number, exc.code, exc.msg,
        )
    except Exception:
        logger.exception("Unexpected error launching agent callback to %s", spam_number)


@app.route("/agent_callback", methods=["POST"])
def agent_callback() -> Response:
    """Outbound callback answered by the spammer — deploy a live agent."""
    if not _validate_twilio_request():
        logger.warning("Invalid Twilio signature for /agent_callback")
        return _hangup_twiml_response(status_code=403)

    call_sid = request.form.get("CallSid", "")
    logger.info("Agent callback answered | SID: %s", call_sid)

    agent = assign_agent(call_sid)
    response = VoiceResponse()
    gather = _build_gather(f"{BASE_URL}/respond")
    voice_id = agent.get("elevenlabs_voice_id")
    tts_path = synthesize(agent["intro"], voice_id, call_sid) if voice_id else None
    if tts_path:
        gather.play(f"{BASE_URL}/audio/tts/{Path(tts_path).name}")
    else:
        gather.say(agent["intro"], voice=agent["voice"])
    response.append(gather)
    response.redirect(f"{BASE_URL}/respond", method="POST")
    return _twiml_response(response)


@app.route("/incoming_realtime", methods=["POST"])
def incoming_realtime() -> Response:
    """
    Direct realtime entry point. Point a Twilio number's Voice webhook here
    to bypass the legacy Gather/Say flow entirely.

    For gradual rollout, leave Twilio pointing at /incoming and control
    traffic via ENABLE_REALTIME + REALTIME_TRAFFIC_PERCENT env vars instead.
    """
    if not _validate_twilio_request():
        caller = request.form.get("From", "Unknown")
        logger.warning(
            "Invalid Twilio signature for /incoming_realtime from %s", caller
        )
        abort(403)

    caller = request.form.get("From", "Unknown")
    call_sid = request.form.get("CallSid", "")

    logger.info("Incoming realtime call from: %s | SID: %s", caller, call_sid)

    if not is_spam(caller):
        response = VoiceResponse()
        response.say(
            "Thank you for calling. Please hold.",
            voice="Polly.Joanna",
        )
        return _twiml_response(response)

    return _realtime_twiml(call_sid, caller)


@sock.route("/media-stream")
def media_stream(ws) -> None:
    """
    Twilio Media Streams WebSocket endpoint.
    One persistent connection per active call for the full call duration.
    Each connection gets its own RealtimeBridge with its own asyncio loop.
    """
    # Import here so tests can patch before the module-level import resolves
    from bridge.realtime_bridge import RealtimeBridge

    bridge = RealtimeBridge(ws)
    bridge_id = str(id(bridge))

    with _bridge_registry_lock:
        _bridge_registry[bridge_id] = bridge

    try:
        bridge.run()
    except Exception:
        logger.exception(
            "media_stream.fatal",
            extra={"bridge_id": bridge_id, "call_sid": bridge.call_sid or "?"},
        )
    finally:
        bridge.cleanup()
        with _bridge_registry_lock:
            _bridge_registry.pop(bridge_id, None)


@app.route("/status", methods=["POST"])
def call_status() -> Response:
    if not _validate_twilio_request():
        logger.warning("Invalid Twilio signature for /status")
        return Response("Forbidden", status=403)

    sid = request.form.get("CallSid", "")
    status = request.form.get("CallStatus", "")
    duration = request.form.get("CallDuration", "0")
    to = request.form.get("To", "Unknown")
    duration_seconds = _safe_int(duration)
    direction = request.form.get("Direction", "")
    scammer = request.form.get("From", "") if direction == "inbound" \
        else request.form.get("To", "")

    logger.info(
        "Call %s to %s | Status: %s | Duration: %ss",
        sid,
        to,
        status,
        duration,
    )

    if status == "completed":
        logger.info(
            (
                "LEADERBOARD: Spammer %s endured %ss. "
                "Scammer minutes wasted: %sm %ss"
            ),
            to,
            duration,
            duration_seconds // 60,
            duration_seconds % 60,
        )
        # --- Agent callback cascade (capped) ---
        do_schedule = False
        next_n = 0
        with _caller_log_lock:
            fired = _caller_log.get(scammer)
            if fired is not None and fired < CALLBACK_CAP:
                _caller_log[scammer] = fired + 1
                next_n = fired + 1
                do_schedule = True
        if do_schedule:
            logger.info(
                "Scheduling agent callback %d/%d to %s in %ds",
                next_n, CALLBACK_CAP, scammer, CALLBACK_DELAY_SEC,
            )
            threading.Timer(
                CALLBACK_DELAY_SEC, _launch_agent_callback, args=(scammer,)
            ).start()
        _pending_registry.cleanup(sid)
        _streaming_registry.cleanup_expired()
        end_call(sid)
        cleanup_old_files()

    return Response("", status=204)


@app.route("/recording_ready", methods=["POST"])
def recording_ready() -> Response:
    """Twilio recording status callback — triggered when a call recording is ready."""
    if not _validate_twilio_request():
        logger.warning("Invalid Twilio signature for /recording_ready")
        return Response("Forbidden", status=403)

    status = request.form.get("RecordingStatus", "")
    call_sid = request.form.get("CallSid", "")
    recording_url = request.form.get("RecordingUrl", "")

    if status != "completed" or not recording_url:
        return Response("", status=204)

    logger.info("Recording ready for call %s — generating MP4", call_sid)

    def _generate(sid: str, url: str) -> None:
        try:
            mp3_path, mp4_path = make_mp4(url, sid, ACCOUNT_SID, AUTH_TOKEN)
            with _recordings_lock:
                _recordings[sid] = {"mp3": mp3_path, "mp4": mp4_path}
            logger.info("Creator Strike media ready for %s", sid)
        except Exception:
            logger.exception("MP4 generation failed for call %s", sid)
            with _recordings_lock:
                _recordings[sid] = {"mp3": None, "mp4": None}

    threading.Thread(target=_generate, args=(call_sid, recording_url), daemon=True).start()
    return Response("", status=204)


@app.route("/api/download/<call_id>", methods=["GET"])
def download_recording(call_id: str) -> Response:
    """Serve the MP3 or MP4 for a Creator Strike call recording.

    Query params:
        format=mp3  (default) — raw audio
        format=mp4  — branded vertical video
    """
    fmt = request.args.get("format", "mp3").lower()
    if fmt not in ("mp3", "mp4"):
        return Response("Invalid format. Use mp3 or mp4.", status=400)

    with _recordings_lock:
        entry = _recordings.get(call_id)

    if not entry:
        return Response("Recording not found.", status=404)

    file_path = entry.get(fmt)
    if not file_path or not Path(file_path).exists():
        if fmt == "mp4" and entry.get("mp3"):
            return Response("MP4 is still being generated. Try again shortly.", status=202)
        return Response("File not available.", status=404)

    mimetype = "audio/mpeg" if fmt == "mp3" else "video/mp4"
    return send_from_directory(
        str(RECORDINGS_DIR),
        Path(file_path).name,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"spamfacker_{call_id}.{fmt}",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))  # noqa: S104
