"""
tts.py
======
ElevenLabs TTS engine for SpamFacker.

Converts agent text responses to MP3 audio files served via Twilio <Play>.
Think of this as a voice actor booth - the LLM writes the line,
ElevenLabs performs it, Twilio plays it to the caller.

Flow:
  LLM reply text -> ElevenLabs API -> MP3 bytes -> saved to static/tts/
  -> Flask serves at /audio/tts/<filename> -> Twilio <Play> plays it
"""

import os
import hashlib
import logging
import random
import threading
from pathlib import Path
from typing import Iterator

import requests
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

logger = logging.getLogger(__name__)

TTS_DIR = Path("static/tts")
TTS_DIR.mkdir(parents=True, exist_ok=True)
FILLERS_DIR = Path("static/tts/fillers")
_cleanup_lock = threading.Lock()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Model: eleven_turbo_v2 - fastest, lowest latency, good quality
# Swap to eleven_multilingual_v2 for higher quality if latency allows
MODEL = "eleven_turbo_v2"


def synthesize(text: str, voice_id: str, call_sid: str) -> str | None:
    """
    Convert text to speech using ElevenLabs.
    Returns the local file path of the saved MP3, or None on failure.

    Uses content-hashed filenames so identical lines reuse cached audio -
    like a prop room that remembers every costume already made.
    """
    if not ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY not set - falling back to Polly")
        return None

    # Hash the text + voice_id for cache key
    cache_key = hashlib.md5(f"{voice_id}:{text}".encode()).hexdigest()
    file_path = TTS_DIR / f"{cache_key}.mp3"

    # Return cached file if it exists
    if file_path.exists():
        logger.info(f"[{call_sid}] TTS cache hit: {cache_key[:8]}")
        return str(file_path)

    try:
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=MODEL,
            voice_settings=VoiceSettings(
                stability=0.45,
                similarity_boost=0.75,
                style=0.35,
                use_speaker_boost=True,
            ),
        )

        # audio is a generator - consume it
        audio_bytes = b"".join(audio)

        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        logger.info(
            f"[{call_sid}] TTS generated: {len(audio_bytes)} bytes "
            f"-> {cache_key[:8]}.mp3"
        )
        return str(file_path)

    except Exception:
        logger.exception("[%s] ElevenLabs TTS failed", call_sid)
        return None


def cleanup_old_files(max_files: int = 200):
    """
    Keep the TTS cache from growing unbounded on Render's disk.
    Deletes oldest files when count exceeds max_files.
    Called from /status on call completion.
    """
    with _cleanup_lock:
        files = sorted(TTS_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
        if len(files) > max_files:
            for f in files[:len(files) - max_files]:
                f.unlink(missing_ok=True)
                logger.info(f"TTS cache cleanup: removed {f.name}")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FillerMissingError(Exception):
    """Raised when no pre-rendered filler files exist for an agent."""


class TTSError(Exception):
    """Raised when the ElevenLabs streaming endpoint returns an error."""


# ---------------------------------------------------------------------------
# Filler audio helpers (Phase 1)
# ---------------------------------------------------------------------------

def get_filler_url(agent_name: str, base_url: str) -> str:
    """
    Return a URL pointing to a random pre-rendered filler MP3 for the agent.
    Raises FillerMissingError if no filler files have been generated yet.
    """
    agent_slug = agent_name.lower()
    filler_dir = FILLERS_DIR / agent_slug
    if not filler_dir.exists():
        raise FillerMissingError(f"No filler directory for agent: {agent_name}")
    files = list(filler_dir.glob("*.mp3"))
    if not files:
        raise FillerMissingError(f"No filler MP3s for agent: {agent_name}")
    chosen = random.choice(files)
    return f"{base_url}/audio/fillers/{agent_slug}/{chosen.name}"


# ---------------------------------------------------------------------------
# Streaming TTS (Phase 2)
# ---------------------------------------------------------------------------

def stream_tts(text: str, voice_id: str) -> Iterator[bytes]:
    """
    Yield MP3 audio chunks from the ElevenLabs streaming endpoint.

    Uses eleven_turbo_v2_5 with optimize_streaming_latency=3 for minimum
    time-to-first-byte. Raises TTSError on non-200 or missing API key.
    """
    if not ELEVENLABS_API_KEY:
        raise TTSError("ELEVENLABS_API_KEY is not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
            "style": 0.35,
            "use_speaker_boost": True,
        },
    }
    params = {
        "optimize_streaming_latency": 3,
        "output_format": "mp3_44100_64",
    }
    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        params=params,
        stream=True,
        timeout=10,
    )
    if resp.status_code != 200:
        raise TTSError(f"ElevenLabs streaming failed with status {resp.status_code}")
    for chunk in resp.iter_content(chunk_size=4096):
        if chunk:
            yield chunk
