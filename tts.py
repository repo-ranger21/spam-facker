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
from pathlib import Path
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

logger = logging.getLogger(__name__)

TTS_DIR = Path("static/tts")
TTS_DIR.mkdir(parents=True, exist_ok=True)

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

        logger.info(f"[{call_sid}] TTS generated: {len(audio_bytes)} bytes -> {cache_key[:8]}.mp3")
        return str(file_path)

    except Exception as e:
        logger.error(f"[{call_sid}] ElevenLabs TTS failed: {e}")
        return None


def cleanup_old_files(max_files: int = 200):
    """
    Keep the TTS cache from growing unbounded on Render's disk.
    Deletes oldest files when count exceeds max_files.
    Called from /status on call completion.
    """
    files = sorted(TTS_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    if len(files) > max_files:
        for f in files[:len(files) - max_files]:
            f.unlink(missing_ok=True)
            logger.info(f"TTS cache cleanup: removed {f.name}")
