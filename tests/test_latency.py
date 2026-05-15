"""
tests/test_latency.py
=====================
Unit tests for the Phase 1-3 latency sprint.

Run with:
    pytest tests/test_latency.py -v
"""

import os
import sys
import time
import threading
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. PendingReplyRegistry — blocks until the background future resolves
# ---------------------------------------------------------------------------

def test_pending_reply_registry_blocks_until_resolved():
    from conversation import PendingReplyRegistry

    registry = PendingReplyRegistry()
    future: Future = Future()
    registry.start("CA-block-1", 0, future)

    # Resolve the future from a background thread after 50 ms
    def _resolve():
        time.sleep(0.05)
        future.set_result("https://example.com/audio.mp3")

    t = threading.Thread(target=_resolve, daemon=True)
    t.start()

    result = registry.await_result("CA-block-1", 0, timeout_sec=2.0)
    t.join(timeout=3.0)

    assert result == "https://example.com/audio.mp3"


# ---------------------------------------------------------------------------
# 2. PendingReplyRegistry — returns None when future never resolves
# ---------------------------------------------------------------------------

def test_pending_reply_registry_times_out():
    from conversation import PendingReplyRegistry

    registry = PendingReplyRegistry()
    future: Future = Future()  # never resolved
    registry.start("CA-timeout-1", 0, future)

    result = registry.await_result("CA-timeout-1", 0, timeout_sec=0.1)
    assert result is None


# ---------------------------------------------------------------------------
# 3. PendingReplyRegistry — two call_sids are fully isolated
# ---------------------------------------------------------------------------

def test_pending_reply_registry_concurrent_calls_isolated():
    from conversation import PendingReplyRegistry

    registry = PendingReplyRegistry()
    f1: Future = Future()
    f2: Future = Future()

    registry.start("CA-iso-1", 0, f1)
    registry.start("CA-iso-2", 0, f2)

    f1.set_result("url-for-ca1")
    f2.set_result("url-for-ca2")

    assert registry.await_result("CA-iso-1", 0, timeout_sec=1.0) == "url-for-ca1"
    assert registry.await_result("CA-iso-2", 0, timeout_sec=1.0) == "url-for-ca2"


# ---------------------------------------------------------------------------
# 4. generate_fillers — skips existing files (idempotent)
# ---------------------------------------------------------------------------

def test_generate_fillers_skips_existing(tmp_path, monkeypatch):
    fake_agents = {
        "mildred": {
            "name": "Mildred",
            "elevenlabs_voice_id": "voice-test",
            "filler_lines": ["Hold on dear, one moment."],
        }
    }

    # Pre-create the expected output file
    filler_dir = tmp_path / "fillers" / "mildred"
    filler_dir.mkdir(parents=True)
    (filler_dir / "00.mp3").write_bytes(b"placeholder")

    with (
        patch("scripts.generate_fillers.FILLERS_DIR", tmp_path / "fillers"),
        patch("scripts.generate_fillers.AGENTS", fake_agents),
        patch("scripts.generate_fillers.synthesize") as mock_synth,
    ):
        from scripts.generate_fillers import main
        main(force=False)
        mock_synth.assert_not_called()


# ---------------------------------------------------------------------------
# 5. generate_fillers — force=True overwrites existing file
# ---------------------------------------------------------------------------

def test_generate_fillers_force_overwrites(tmp_path):
    fake_agents = {
        "mildred": {
            "name": "Mildred",
            "elevenlabs_voice_id": "voice-test",
            "filler_lines": ["Hold on dear, one moment."],
        }
    }

    filler_dir = tmp_path / "fillers" / "mildred"
    filler_dir.mkdir(parents=True)
    existing = filler_dir / "00.mp3"
    existing.write_bytes(b"old content")

    # synthesize returns a temp file path so shutil.copy2 has a real source
    fake_src = tmp_path / "cached.mp3"
    fake_src.write_bytes(b"new content")

    with (
        patch("scripts.generate_fillers.FILLERS_DIR", tmp_path / "fillers"),
        patch("scripts.generate_fillers.AGENTS", fake_agents),
        patch("scripts.generate_fillers.synthesize", return_value=str(fake_src)) as mock_synth,
    ):
        from scripts.generate_fillers import main
        main(force=True)
        mock_synth.assert_called_once()

    assert existing.read_bytes() == b"new content"


# ---------------------------------------------------------------------------
# 6. StreamingRegistry — token resolves to correct spec on first pop
# ---------------------------------------------------------------------------

def test_streaming_route_returns_chunked_audio():
    from conversation import StreamingRegistry

    registry = StreamingRegistry()
    token = registry.register("Hello there dear.", "voice-abc")

    spec = registry.pop(token)
    assert spec is not None
    assert spec.text == "Hello there dear."
    assert spec.voice_id == "voice-abc"


# ---------------------------------------------------------------------------
# 7. StreamingRegistry — token is single-use (second pop returns None)
# ---------------------------------------------------------------------------

def test_streaming_token_single_use():
    from conversation import StreamingRegistry

    registry = StreamingRegistry()
    token = registry.register("Test text.", "voice-xyz")

    spec1 = registry.pop(token)
    assert spec1 is not None

    spec2 = registry.pop(token)
    assert spec2 is None


# ---------------------------------------------------------------------------
# 8. generate_response — max_tokens=60 when ENABLE_TOKEN_CAP=true
# ---------------------------------------------------------------------------

def test_max_tokens_enforced(monkeypatch):
    monkeypatch.setenv("ENABLE_TOKEN_CAP", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Okay dear, let me think."))]
    )

    with patch("llm.OpenAI", return_value=mock_client):
        from llm import generate_response

        agent = {
            "name": "Mildred",
            "system_prompt": "You are Mildred, a 78-year-old widow.",
            "escalation_prompt": "You are starting to feel overwhelmed.",
            "voice": "Polly.Joanna",
        }
        generate_response(
            agent=agent,
            history=[],
            user_speech="Give me your bank account number.",
        )

    # Stage 1 = classifier call, Stage 2 = persona call (last call)
    stage2_kwargs = mock_client.chat.completions.create.call_args_list[-1][1]
    assert stage2_kwargs.get("max_tokens") == 60
    assert stage2_kwargs.get("frequency_penalty") == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# 9. recent_turns — returns last 12 messages for n=6 (6 exchange-pairs)
# ---------------------------------------------------------------------------

def test_history_trimmed_to_six_turns():
    from llm import recent_turns
    from conversation import Turn

    # 10 pairs = 20 Turn objects total
    turns = []
    for i in range(10):
        turns.append(Turn(role="user", content=f"user {i}"))
        turns.append(Turn(role="assistant", content=f"assistant {i}"))

    result = recent_turns(turns, n=6)

    assert len(result) == 12  # 6 pairs × 2 roles
    # First message in the window is user-turn 4 (0-indexed pairs 4..9)
    assert result[0]["content"] == "user 4"
    assert result[-1]["content"] == "assistant 9"
