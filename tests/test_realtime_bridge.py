"""
tests/test_realtime_bridge.py
=============================
Unit tests for the OpenAI Realtime + Twilio Media Streams bridge.

Nine tests covering:
  1. /incoming_realtime returns valid Connect/Stream TwiML
  2. /incoming_realtime rejects invalid Twilio signatures
  3. Bridge captures stream_sid, call_sid, agent from Twilio 'start' event
  4. Bridge forwards Twilio 'media' events to OpenAI append_audio
  5. Bridge forwards OpenAI response.audio.delta to Twilio
  6. Bridge handles barge-in (speech_started → cancel + Twilio clear)
  7. Bridge sets _closed on Twilio 'stop' event
  8. Bridge sets _closed on OpenAI 'error' event
  9. _should_route_to_realtime() respects REALTIME_TRAFFIC_PERCENT

Run:
    python -m pytest tests/test_realtime_bridge.py -v
"""

import asyncio
import json
import os
import time

# Set required env vars BEFORE importing app or bridge modules
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest000000000000000000000000000000")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_auth_token_32chars_padding_xx")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15550000000")
os.environ.setdefault("BASE_URL", "https://example.ngrok.io")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# ===========================================================================
# Test 1 — /incoming_realtime returns <Connect><Stream> TwiML
# ===========================================================================

def test_incoming_realtime_returns_connect_stream_twiml():
    with patch("app._validate_twilio_request", return_value=True), \
         patch("app.is_spam", return_value=True), \
         patch("app.assign_agent", return_value={"name": "Mildred", "voice": "Polly.Joanna"}), \
         patch("app.get_state") as mock_gs, \
         patch("app._launch_callback"):

        mock_state = MagicMock()
        mock_state.agent_key = "mildred"
        mock_gs.return_value = mock_state

        import app as app_module
        client = app_module.app.test_client()
        resp = client.post(
            "/incoming_realtime",
            data={"From": "+15550001111", "CallSid": "CA_rt_test"},
        )

    assert resp.status_code == 200
    body = resp.data.decode()
    assert "<Connect>" in body
    assert "<Stream" in body
    assert "wss://" in body
    assert "/media-stream" in body


# ===========================================================================
# Test 2 — /incoming_realtime rejects invalid Twilio signature
# ===========================================================================

def test_incoming_realtime_signature_validation():
    with patch("app._validate_twilio_request", return_value=False):
        import app as app_module
        client = app_module.app.test_client()
        resp = client.post(
            "/incoming_realtime",
            data={"From": "+15550001111", "CallSid": "CA_sig_test"},
        )

    assert resp.status_code == 403


# ===========================================================================
# Test 3 — Bridge captures stream_sid, call_sid, agent from 'start' event
# ===========================================================================

def test_bridge_captures_stream_sid_from_start_event():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)

    # Patch _start_openai_session so no real network call is made
    with patch.object(bridge, "_start_openai_session", new_callable=AsyncMock):
        bridge._loop_thread.start()

        start_event = {
            "event": "start",
            "streamSid": "MZ_stream_sid",
            "start": {
                "callSid": "CA_call_sid",
                "customParameters": {
                    "agent": "mildred",
                    "call_sid": "CA_call_sid",
                    "spam_score": "90",
                },
            },
        }

        with patch("bridge.realtime_bridge.assign_agent"):
            bridge._handle_twilio_event(start_event)

        # Give the event loop a moment to schedule the patched coroutine
        time.sleep(0.15)

        bridge._loop.call_soon_threadsafe(bridge._loop.stop)
        bridge._loop_thread.join(timeout=2.0)

    assert bridge.stream_sid == "MZ_stream_sid"
    assert bridge.call_sid == "CA_call_sid"
    assert bridge.agent_name == "mildred"


# ===========================================================================
# Test 4 — Bridge forwards Twilio 'media' events to OpenAI append_audio
# ===========================================================================

def test_bridge_forwards_media_to_openai_appends():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)
    bridge.stream_sid = "MZ_test"

    mock_openai = Mock()
    mock_openai.append_audio = AsyncMock()
    bridge._openai = mock_openai

    bridge._loop_thread.start()

    media_event = {
        "event": "media",
        "streamSid": "MZ_test",
        "media": {"payload": "AAEC"},  # sample base64 payload
    }
    bridge._handle_twilio_event(media_event)

    # Allow the coroutine to be scheduled and executed
    time.sleep(0.2)

    bridge._loop.call_soon_threadsafe(bridge._loop.stop)
    bridge._loop_thread.join(timeout=2.0)

    mock_openai.append_audio.assert_called_once_with("AAEC")


# ===========================================================================
# Test 5 — Bridge forwards OpenAI response.audio.delta to Twilio
# ===========================================================================

def test_bridge_forwards_openai_audio_to_twilio():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)
    bridge.stream_sid = "MZ_test"
    bridge.call_sid = "CA_test"
    bridge.agent_name = "mildred"

    async def run():
        event = {"type": "response.audio.delta", "delta": "AUDIODATA64"}
        await bridge._handle_openai_event(event)

    asyncio.run(run())

    mock_ws.send.assert_called_once()
    payload = json.loads(mock_ws.send.call_args[0][0])
    assert payload["event"] == "media"
    assert payload["streamSid"] == "MZ_test"
    assert payload["media"]["payload"] == "AUDIODATA64"


# ===========================================================================
# Test 6 — Bridge handles barge-in: cancel_response + Twilio clear
# ===========================================================================

def test_bridge_handles_barge_in():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)
    bridge.stream_sid = "MZ_test"
    bridge.call_sid = "CA_test"
    bridge.agent_name = "mildred"
    bridge._response_in_progress = True

    mock_openai = Mock()
    mock_openai.cancel_response = AsyncMock()
    bridge._openai = mock_openai

    async def run():
        event = {"type": "input_audio_buffer.speech_started"}
        await bridge._handle_openai_event(event)

    asyncio.run(run())

    # OpenAI cancel must be called
    mock_openai.cancel_response.assert_called_once()

    # Twilio must receive a 'clear' event
    send_calls = mock_ws.send.call_args_list
    assert len(send_calls) >= 1
    payloads = [json.loads(c[0][0]) for c in send_calls]
    clear_events = [p for p in payloads if p.get("event") == "clear"]
    assert len(clear_events) == 1, f"Expected 1 clear event, got {len(clear_events)}"

    # _response_in_progress must be reset
    with bridge._state_lock:
        assert not bridge._response_in_progress


# ===========================================================================
# Test 7 — Bridge sets _closed on Twilio 'stop' event
# ===========================================================================

def test_bridge_cleanup_on_twilio_close():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)
    bridge.stream_sid = "MZ_test"
    bridge.call_sid = "CA_test"

    bridge._handle_twilio_event({"event": "stop", "streamSid": "MZ_test"})

    assert bridge._closed.is_set()


# ===========================================================================
# Test 8 — Bridge sets _closed on OpenAI 'error' event
# ===========================================================================

def test_bridge_cleanup_on_openai_error():
    from bridge.realtime_bridge import RealtimeBridge

    mock_ws = Mock()
    bridge = RealtimeBridge(mock_ws)
    bridge.stream_sid = "MZ_test"
    bridge.call_sid = "CA_test"
    bridge.agent_name = "mildred"

    error_event = {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": "test error"},
    }

    async def run():
        await bridge._handle_openai_event(error_event)

    asyncio.run(run())

    assert bridge._closed.is_set()


# ===========================================================================
# Test 9 — _should_route_to_realtime() respects REALTIME_TRAFFIC_PERCENT
# ===========================================================================

def test_routing_respects_traffic_percent():
    import app as app_module

    # With ENABLE_REALTIME=false, nothing should route regardless of percent
    with patch.dict(os.environ, {"ENABLE_REALTIME": "false", "REALTIME_TRAFFIC_PERCENT": "100"}):
        results = [app_module._should_route_to_realtime() for _ in range(20)]
    assert not any(results), "Should not route when ENABLE_REALTIME=false"

    # With ENABLE_REALTIME=true and 50% traffic, expect ~half to route
    with patch.dict(os.environ, {"ENABLE_REALTIME": "true", "REALTIME_TRAFFIC_PERCENT": "50"}):
        results = [app_module._should_route_to_realtime() for _ in range(1000)]
    routed_count = sum(results)
    assert 380 <= routed_count <= 620, (
        f"Expected ~500/1000 with 50% traffic, got {routed_count}"
    )

    # With ENABLE_REALTIME=true and 0% traffic, nothing should route
    with patch.dict(os.environ, {"ENABLE_REALTIME": "true", "REALTIME_TRAFFIC_PERCENT": "0"}):
        results = [app_module._should_route_to_realtime() for _ in range(20)]
    assert not any(results), "Should not route when REALTIME_TRAFFIC_PERCENT=0"
