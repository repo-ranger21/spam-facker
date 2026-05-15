"""
bridge/realtime_bridge.py
=========================
Bidirectional WebSocket bridge: Twilio Media Streams ↔ OpenAI Realtime API.

Implements Phases 1-6 of the Realtime migration:
  Phase 1 — Accept Twilio WS, log all events
  Phase 2 — Connect OpenAI Realtime, play agent intro
  Phase 3 — Bidirectional μ-law audio forwarding
  Phase 4 — Barge-in / interruption (input_audio_buffer.speech_started)
  Phase 5 — Per-turn case-file injection (session.update after response.done)
  Phase 6 — Structured logging, cleanup hooks, latency measurement

Threading model
---------------
Flask gthread worker thread (the Twilio thread):
  - Calls bridge.run()
  - Reads Twilio messages synchronously via twilio_ws.receive()
  - Dispatches async work to the asyncio loop via run_coroutine_threadsafe()
  - Calls bridge.cleanup() in the finally block

Asyncio loop thread (one daemon thread per call):
  - Created fresh for each bridge instance
  - Runs asyncio.run_forever() for the call lifetime
  - Handles all OpenAI WebSocket I/O
  - Calls twilio_ws.send() directly (thread-safe in flask-sock)

Shared mutable state (guarded by _state_lock):
  - _response_in_progress: bool — written from asyncio loop, read from both sides

Audio format invariant:
  Twilio → Bridge: base64-encoded g711_ulaw, 20ms frames
  Bridge → OpenAI: same — no transcoding
  OpenAI → Bridge: base64-encoded g711_ulaw
  Bridge → Twilio: same — no transcoding
"""

import asyncio
import json
import logging
import threading
import time

from agents import AGENTS, AGENT_TO_REALTIME_VOICE, REALTIME_VOICE_RULES
from bridge.openai_client import RealtimeClient
from conversation import add_exchange, assign_agent, get_state

log = logging.getLogger(__name__)


class RealtimeBridge:
    """
    One instance per active call. Constructed and owned by the /media-stream
    flask-sock route handler.

    Usage:
        bridge = RealtimeBridge(ws)
        try:
            bridge.run()
        except Exception:
            log.exception("media_stream.fatal")
        finally:
            bridge.cleanup()
    """

    def __init__(self, twilio_ws) -> None:
        self.twilio_ws = twilio_ws
        self.stream_sid: str | None = None
        self.agent_name: str | None = None
        self.call_sid: str | None = None

        # Asyncio infrastructure — one loop per bridge
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_async_loop,
            daemon=True,
            name="realtime-asyncio",
        )
        self._openai: RealtimeClient | None = None
        self._closed = threading.Event()

        # Shared mutable state — all writes must hold _state_lock
        self._state_lock = threading.Lock()
        self._response_in_progress = False

        # Session context — written once on start, read-only thereafter
        self._base_instructions: str = ""
        self._voice: str = "alloy"

        # Latency tracking (asyncio thread only)
        self._speech_stopped_at: float = 0.0
        self._first_audio_delta_at: float | None = None
        self._intro_played: bool = False

        # Turn tracking
        self._turn_count: int = 0
        self._started_at: float = time.monotonic()

        # Transcript accumulation (asyncio thread only)
        self._pending_agent_text: str = ""
        self._pending_caller_text: str = ""

    # ------------------------------------------------------------------
    # Public API — called from the Twilio (gthread) thread
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Block until Twilio closes the connection or a fatal error occurs.
        Must be called from the flask-sock route handler (the Twilio thread).
        Starts the asyncio loop thread, then reads Twilio messages.
        """
        self._loop_thread.start()

        log.info(
            "realtime.connected",
            extra={
                "call_sid": self.call_sid or "?",
                "stream_sid": self.stream_sid or "?",
                "agent": self.agent_name or "?",
            },
        )

        try:
            while not self._closed.is_set():
                try:
                    msg = self.twilio_ws.receive(timeout=30)
                except Exception as exc:
                    log.info(
                        "realtime.twilio_ws_closed: %s",
                        type(exc).__name__,
                        extra={"call_sid": self.call_sid or "?"},
                    )
                    break

                if msg is None:
                    # receive() timeout — check _closed and loop again
                    continue

                try:
                    event = json.loads(msg)
                    self._handle_twilio_event(event)
                except json.JSONDecodeError as exc:
                    log.warning(
                        "realtime.bad_json: %s",
                        exc,
                        extra={"call_sid": self.call_sid or "?"},
                    )
        finally:
            self._closed.set()
            log.info(
                "realtime.twilio_dropped",
                extra={
                    "call_sid": self.call_sid or "?",
                    "stream_sid": self.stream_sid or "?",
                    "turn_count": self._turn_count,
                },
            )

    def cleanup(self) -> None:
        """
        Idempotent cleanup — always called from the Twilio thread's finally block.
        Closes the OpenAI WebSocket, stops the asyncio loop, joins the loop thread.
        """
        self._closed.set()

        # Close OpenAI WS from within the event loop
        if self._openai is not None and self._loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self._openai.close(), self._loop
                )
                fut.result(timeout=3.0)
            except Exception:
                pass

        # Stop the event loop and wait for the thread to exit
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)

        duration_sec = round(time.monotonic() - self._started_at, 1)
        log.info(
            "realtime.closed",
            extra={
                "call_sid": self.call_sid or "?",
                "stream_sid": self.stream_sid or "?",
                "agent": self.agent_name or "?",
                "total_duration_sec": duration_sec,
                "turn_count": self._turn_count,
            },
        )

    # ------------------------------------------------------------------
    # Asyncio loop thread
    # ------------------------------------------------------------------

    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()

    # ------------------------------------------------------------------
    # Twilio event dispatch — called from the Twilio thread
    # ------------------------------------------------------------------

    def _handle_twilio_event(self, event: dict) -> None:
        kind = event.get("event")

        if kind == "connected":
            log.debug(
                "realtime.twilio_protocol_connected",
                extra={"call_sid": self.call_sid or "?"},
            )

        elif kind == "start":
            self._on_twilio_start(event)

        elif kind == "media":
            # Forward audio to OpenAI — only after OpenAI session is up
            if self._openai is not None and self.stream_sid is not None:
                asyncio.run_coroutine_threadsafe(
                    self._openai.append_audio(event["media"]["payload"]),
                    self._loop,
                )

        elif kind == "stop":
            log.info(
                "realtime.twilio_stop",
                extra={
                    "stream_sid": self.stream_sid,
                    "call_sid": self.call_sid,
                },
            )
            self._closed.set()

        elif kind == "mark":
            log.debug(
                "realtime.mark: %s",
                event.get("mark", {}).get("name"),
            )

        else:
            log.debug(
                "realtime.unknown_twilio_event: %s",
                kind,
                extra={"call_sid": self.call_sid or "?"},
            )

    def _on_twilio_start(self, event: dict) -> None:
        """
        Process the Twilio 'start' event: extract stream/call/agent identifiers,
        then kick off the OpenAI session on the asyncio loop.
        """
        self.stream_sid = event.get("streamSid")
        start_data = event.get("start", {})
        params = start_data.get("customParameters", {})
        self.agent_name = params.get("agent", "mildred").lower()
        # Prefer call_sid from customParameters; fall back to start.callSid
        self.call_sid = params.get("call_sid") or start_data.get("callSid", "")

        log.info(
            "realtime.start",
            extra={
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "agent": self.agent_name,
            },
        )

        agent = AGENTS.get(self.agent_name, AGENTS["mildred"])
        self._voice = AGENT_TO_REALTIME_VOICE.get(self.agent_name, "alloy")
        self._base_instructions = agent["system_prompt"] + REALTIME_VOICE_RULES

        # Ensure call state exists in conversation registry
        if self.call_sid:
            assign_agent(self.call_sid, preferred=self.agent_name)

        asyncio.run_coroutine_threadsafe(
            self._start_openai_session(), self._loop
        )

    # ------------------------------------------------------------------
    # OpenAI session lifecycle — runs in the asyncio loop thread
    # ------------------------------------------------------------------

    async def _start_openai_session(self) -> None:
        """
        Connect to OpenAI Realtime, configure the session, then trigger
        the agent's intro line.
        """
        t0 = time.monotonic()
        try:
            self._openai = RealtimeClient()
            await self._openai.connect()

            connect_ms = int((time.monotonic() - t0) * 1000)
            log.info(
                "realtime.openai_connected",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "connect_ms": connect_ms,
                },
            )

            await self._openai.update_session(
                instructions=self._base_instructions,
                voice=self._voice,
            )
            log.info(
                "realtime.session_updated",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                },
            )

            # Trigger the agent's opening line immediately
            await self._openai.create_response()

            # Start listening for OpenAI events
            asyncio.create_task(self._read_openai_events())

        except Exception:
            log.exception(
                "realtime.connect_failed",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                },
            )
            self._closed.set()

    async def _read_openai_events(self) -> None:
        """
        Async task — reads the OpenAI event stream for the full call duration.
        Terminates when the stream closes or _closed is set.
        """
        try:
            async for event in self._openai.events():
                if self._closed.is_set():
                    break
                await self._handle_openai_event(event)
        except Exception:
            log.exception(
                "realtime.openai_dropped",
                extra={
                    "call_sid": self.call_sid,
                    "turn_count": self._turn_count,
                },
            )
            # Clear any Twilio audio buffer so the caller doesn't hear stale audio
            self._send_to_twilio({"event": "clear", "streamSid": self.stream_sid})
            log.info(
                "realtime.openai_error",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "event": {"type": "connection_lost"},
                },
            )
            self._closed.set()

    async def _handle_openai_event(self, event: dict) -> None:
        """Dispatch a single OpenAI Realtime event."""
        kind = event.get("type")

        if kind == "session.created":
            log.debug("realtime.session_created", extra={"call_sid": self.call_sid})

        elif kind == "session.updated":
            log.debug("realtime.session_updated_ack", extra={"call_sid": self.call_sid})

        elif kind == "response.created":
            with self._state_lock:
                self._response_in_progress = True
                self._first_audio_delta_at = None
                self._pending_agent_text = ""

        elif kind == "response.audio.delta":
            # First audio chunk — record latency reference point
            if self._first_audio_delta_at is None:
                self._first_audio_delta_at = time.monotonic()
            # Forward audio immediately — no buffering
            self._send_to_twilio(
                {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": event["delta"]},
                }
            )

        elif kind == "response.audio.done":
            response_id = event.get("response_id", "")
            self._send_to_twilio(
                {
                    "event": "mark",
                    "streamSid": self.stream_sid,
                    "mark": {"name": f"resp_{response_id}_done"},
                }
            )
            if not self._intro_played:
                self._intro_played = True
                log.info(
                    "realtime.intro_played",
                    extra={
                        "call_sid": self.call_sid,
                        "stream_sid": self.stream_sid,
                        "agent": self.agent_name,
                    },
                )

        elif kind == "response.audio_transcript.delta":
            self._pending_agent_text += event.get("delta", "")

        elif kind == "response.audio_transcript.done":
            transcript = event.get("transcript") or self._pending_agent_text
            log.info(
                "realtime.agent_said",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "text": transcript,
                },
            )
            self._pending_agent_text = transcript

        elif kind == "response.done":
            response_data = event.get("response", {})
            status = response_data.get("status", "")

            with self._state_lock:
                self._response_in_progress = False

            # Cancelled = barge-in; log it but skip turn accounting
            if status == "cancelled":
                log.info(
                    "realtime.response_cancelled [INTERRUPTED]",
                    extra={"call_sid": self.call_sid},
                )
                return

            # Compute turn latency
            if self._speech_stopped_at and self._first_audio_delta_at:
                latency_ms = int(
                    (self._first_audio_delta_at - self._speech_stopped_at) * 1000
                )
            else:
                latency_ms = -1

            self._turn_count += 1
            log.info(
                "realtime.turn_complete",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "caller_text": self._pending_caller_text,
                    "agent_text": self._pending_agent_text,
                    "turn_latency_ms": latency_ms,
                    "turn_count": self._turn_count,
                },
            )

            # Update the conversation case file
            if self.call_sid and self._pending_caller_text and self._pending_agent_text:
                add_exchange(
                    self.call_sid,
                    self._pending_caller_text,
                    self._pending_agent_text,
                )
            self._pending_caller_text = ""

            # Phase 5 — refresh persona instructions with current case-file
            await self._refresh_session_instructions()

        elif kind == "input_audio_buffer.speech_started":
            # Barge-in: caller spoke while agent was mid-sentence
            with self._state_lock:
                active = self._response_in_progress

            if active:
                await self._openai.cancel_response()
                self._send_to_twilio(
                    {"event": "clear", "streamSid": self.stream_sid}
                )
                with self._state_lock:
                    self._response_in_progress = False
                log.info(
                    "realtime.barge_in",
                    extra={
                        "call_sid": self.call_sid,
                        "stream_sid": self.stream_sid,
                        "agent": self.agent_name,
                    },
                )

            # Reset latency reference points for the new turn
            self._first_audio_delta_at = None
            self._speech_stopped_at = 0.0

        elif kind == "input_audio_buffer.speech_stopped":
            self._speech_stopped_at = time.monotonic()

        elif kind == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            self._pending_caller_text = transcript
            log.info(
                "realtime.caller_said",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "text": transcript,
                },
            )

        elif kind == "error":
            log.error(
                "realtime.openai_error",
                extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "agent": self.agent_name,
                    "event": event,
                },
            )
            self._closed.set()

        else:
            log.debug(
                "realtime.unhandled_openai_event: %s",
                kind,
                extra={"call_sid": self.call_sid or "?"},
            )

    async def _refresh_session_instructions(self) -> None:
        """
        Phase 5 — After each completed response, inject the latest case-file
        state into the session instructions so the agent uses current tactics.

        voice is omitted — it cannot change after audio has started.
        """
        if not self.call_sid or self._openai is None:
            return

        state = get_state(self.call_sid)
        if state is None:
            return

        addendum = (
            "\n\nTACTICAL CONTEXT (use this for your next reply):\n"
            f"- Scam pattern observed: {state.scam_type or 'unknown'}\n"
            f"- Caller has asked for: {', '.join(state.asked_for) or 'nothing yet'}\n"
            f"- Your recent tactics: {state.tactics_used[-3:]}\n"
            f"- AVOID repeating: {state.tactics_used[-1] if state.tactics_used else 'n/a'}\n"
        )

        try:
            await self._openai.update_session(
                instructions=self._base_instructions + addendum,
                voice=None,  # voice cannot change mid-session
            )
        except Exception:
            log.warning(
                "realtime.session_refresh_failed",
                extra={"call_sid": self.call_sid},
            )

    # ------------------------------------------------------------------
    # Thread-safe Twilio send — called from the asyncio loop thread
    # ------------------------------------------------------------------

    def _send_to_twilio(self, payload: dict) -> None:
        """
        Send a JSON event to Twilio. twilio_ws.send() is thread-safe in
        flask-sock (simple-websocket). Sets _closed on any send failure.
        """
        if self._closed.is_set():
            return
        try:
            self.twilio_ws.send(json.dumps(payload))
        except Exception as exc:
            log.warning(
                "realtime.twilio_send_failed",
                extra={"err": str(exc), "call_sid": self.call_sid},
            )
            self._closed.set()
