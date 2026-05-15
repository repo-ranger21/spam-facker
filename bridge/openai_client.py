"""
bridge/openai_client.py
=======================
Async wrapper around the OpenAI Realtime WebSocket API.

Encapsulates connection lifecycle, session configuration, and audio
streaming. Designed to run inside a dedicated asyncio event loop owned
by RealtimeBridge — never share a client across bridges.

Audio format invariant:
  Input:  g711_ulaw (8kHz mono μ-law, 20ms frames, base64-encoded)
  Output: g711_ulaw — same. Zero transcoding in the bridge.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator

import websockets

log = logging.getLogger(__name__)


class RealtimeClient:
    """
    Wraps wss://api.openai.com/v1/realtime WebSocket connection.

    Lifecycle:
        client = RealtimeClient()
        await client.connect()
        await client.update_session(instructions=..., voice=...)
        await client.create_response()          # trigger intro
        async for event in client.events():     # read server events
            ...
        await client.close()
    """

    URL = "wss://api.openai.com/v1/realtime"
    MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")

    def __init__(self) -> None:
        self._ws = None

    async def connect(self) -> None:
        """
        Open the WebSocket connection and authenticate.
        Raises immediately if OPENAI_API_KEY is missing or the handshake fails.
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        url = f"{self.URL}?model={self.MODEL}"
        self._ws = await websockets.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        )
        log.debug("RealtimeClient: connected to %s", url)

    async def update_session(
        self,
        *,
        instructions: str,
        voice: str | None = None,
    ) -> None:
        """
        Send session.update to configure voice, audio formats, VAD, and
        the persona instructions.

        voice cannot be changed after the first audio is sent — pass
        voice=None on subsequent updates to leave it unchanged.
        """
        session: dict = {
            "modalities": ["audio", "text"],
            "instructions": instructions,
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 700,
            },
            "temperature": 0.9,
        }
        if voice is not None:
            session["voice"] = voice

        await self._send({"type": "session.update", "session": session})

    async def append_audio(self, base64_mulaw: str) -> None:
        """Forward a base64-encoded μ-law audio chunk to the input buffer."""
        await self._send(
            {"type": "input_audio_buffer.append", "audio": base64_mulaw}
        )

    async def create_response(self) -> None:
        """
        Ask the model to generate a response immediately.
        Use for the intro line; subsequent responses are VAD-triggered.
        """
        await self._send({"type": "response.create"})

    async def cancel_response(self) -> None:
        """Interrupt an in-progress response (barge-in path)."""
        await self._send({"type": "response.cancel"})

    async def events(self) -> AsyncIterator[dict]:
        """
        Async generator that yields parsed JSON events from the server.
        Terminates when the WebSocket closes.
        """
        async for raw in self._ws:
            yield json.loads(raw)

    async def close(self) -> None:
        """Close the WebSocket connection gracefully."""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            finally:
                self._ws = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send(self, payload: dict) -> None:
        if self._ws is None:
            raise RuntimeError("RealtimeClient: not connected — call connect() first")
        await self._ws.send(json.dumps(payload))
