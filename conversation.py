"""
conversation.py
===============
In-memory call state — a detective's case file, not just a transcript.

Each active call has a CallState that tracks:
- What agent is handling it and the full conversation history
- What we know about the scam (type, tactic, what they've asked for)
- What the agent has already tried (to avoid repetition)
- Scammer frustration signals (the real escalation trigger)

For production scale (multi-worker Render), swap the dict for Redis.
Single-worker free tier: in-memory is fine.
"""

import secrets
import time
import random
import logging
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field

from agents import AGENTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    role: str       # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_message(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class CallState:
    call_sid: str
    agent_key: str
    agent: dict
    started_at: float
    turns: list[Turn] = field(default_factory=list)
    escalated: bool = False

    # What we know about the scam
    scam_type: str | None = None
    scammer_tactic: str | None = None
    asked_for: set[str] = field(default_factory=set)

    # What the agent has already done (avoid repetition)
    tactics_used: list[str] = field(default_factory=list)   # rolling last 5
    objects_mentioned: set[str] = field(default_factory=set)

    # Scammer frustration signals
    scammer_frustration_signals: int = 0
    repeated_demands: int = 0

    @property
    def history(self) -> list[dict]:
        """OpenAI-format message list derived from turns."""
        return [t.to_message() for t in self.turns]

    @property
    def turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "user")

    @property
    def should_escalate_now(self) -> bool:
        return (
            self.scammer_frustration_signals >= 2
            or self.repeated_demands >= 2
            or self.turn_count >= 15
        )


# ---------------------------------------------------------------------------
# Agent tactic classifiers (tracks what the agent has already used)
# ---------------------------------------------------------------------------

_AGENT_TACTIC_PATTERNS: dict[str, list[str]] = {
    "ask_repeat": [
        "say that again", "repeat that", "fuzzy", "couldn't hear",
        "speak up", "pardon",
    ],
    "defer_to_linda": ["linda"],
    "physical_interrupt": ["hold on", "oven", "timer", "cat just"],
    "confuse_name": ["how do you spell", "spell that", "did you say"],
    "tangent_cat": ["mister whiskers", "whiskers"],
    "tangent_harold": ["harold"],
}

_OBJECT_PATTERNS: dict[str, list[str]] = {
    "cat": ["mister whiskers", "whiskers", "the cat"],
    "harold": ["harold"],
    "linda": ["linda"],
    "glasses": ["glasses", "spectacles"],
    "pen": ["pen", "write this down"],
}


def _update_agent_tactics(state: CallState, agent_reply: str) -> None:
    """
    Detect which tactic the agent just used and update
    tactics_used (rolling last 5) and objects_mentioned.
    """
    reply_lower = agent_reply.lower()

    for tactic, patterns in _AGENT_TACTIC_PATTERNS.items():
        if any(p in reply_lower for p in patterns):
            state.tactics_used.append(tactic)
            if len(state.tactics_used) > 5:
                state.tactics_used.pop(0)
            break   # one tactic label per turn

    for obj, patterns in _OBJECT_PATTERNS.items():
        if any(p in reply_lower for p in patterns):
            state.objects_mentioned.add(obj)


# ---------------------------------------------------------------------------
# Module-level call registry
# ---------------------------------------------------------------------------

_calls: dict[str, CallState] = {}
_calls_lock = threading.Lock()


def assign_agent(call_sid: str, preferred: str | None = None) -> dict:
    """
    Assign an agent to a new call (preferred if valid, else "timmy").
    Idempotent: returns the existing agent if the call is already known.
    """
    with _calls_lock:
        existing = _calls.get(call_sid)
        if existing:
            return existing.agent

        agent_key = preferred if preferred in AGENTS else "timmy"
        agent = AGENTS[agent_key]
        _calls[call_sid] = CallState(
            call_sid=call_sid,
            agent_key=agent_key,
            agent=agent,
            started_at=time.time(),
        )

    logger.info("[%s] Assigned agent: %s", call_sid, agent["name"])
    return agent


def get_state(call_sid: str) -> CallState | None:
    """Return call state or None if the call is unknown."""
    return _calls.get(call_sid)


def add_exchange(
    call_sid: str, user_speech: str, agent_reply: str
) -> None:
    """
    Record one exchange (user → agent), update the scam case file,
    and track which tactics the agent just used.
    """
    state = _calls.get(call_sid)
    if not state:
        return

    state.turns.append(Turn(role="user", content=user_speech))
    state.turns.append(Turn(role="assistant", content=agent_reply))

    _update_agent_tactics(state, agent_reply)

    elapsed = int(time.time() - state.started_at)
    logger.info(
        "[%s] Turn %d | Agent: %s | Elapsed: %ds",
        call_sid,
        state.turn_count,
        state.agent["name"],
        elapsed,
    )


def should_escalate(call_sid: str) -> bool:
    """
    Returns True the first time this call meets the escalation threshold.
    Triggered by scammer frustration signals, repeated demands,
    or a 15-turn safety net — not a fixed turn count.
    """
    state = _calls.get(call_sid)
    if not state:
        return False
    if state.should_escalate_now and not state.escalated:
        state.escalated = True
        logger.info(
            "[%s] Escalation triggered — frustration=%d "
            "repeated=%d turns=%d",
            call_sid,
            state.scammer_frustration_signals,
            state.repeated_demands,
            state.turn_count,
        )
        return True
    return False


def elapsed_seconds(call_sid: str) -> int:
    """How long this call has been active, in seconds."""
    state = _calls.get(call_sid)
    if not state:
        return 0
    return int(time.time() - state.started_at)


def end_call(call_sid: str) -> None:
    """Remove call state when the call ends."""
    state = _calls.pop(call_sid, None)
    if state:
        elapsed = int(time.time() - state.started_at)
        logger.info(
            "[%s] Call ended | Agent: %s | Duration: %ds | Turns: %d",
            call_sid,
            state.agent["name"],
            elapsed,
            state.turn_count,
        )


def get_stall_tactic(call_sid: str) -> str:
    """Return a stall line from the agent's tactic list."""
    state = _calls.get(call_sid)
    if not state:
        return "Sorry, could you repeat that?"
    tactics = state.agent.get("tactics", [])
    return random.choice(tactics) if tactics else "Could you say that again?"


# ---------------------------------------------------------------------------
# Pending-reply registry (Phase 1 — async filler flow)
# ---------------------------------------------------------------------------

@dataclass
class PendingReply:
    call_sid: str
    seq: int
    future: Future
    started_at: float


class PendingReplyRegistry:
    """
    Tracks in-flight LLM+TTS background tasks by (call_sid, seq) key.
    Thread-safe; designed to be swapped for a Redis-backed version.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._replies: dict[tuple[str, int], PendingReply] = {}

    def start(self, call_sid: str, seq: int, future: Future) -> None:
        with self._lock:
            self._replies[(call_sid, seq)] = PendingReply(
                call_sid=call_sid,
                seq=seq,
                future=future,
                started_at=time.time(),
            )

    def await_result(self, call_sid: str, seq: int, timeout_sec: float) -> str | None:
        with self._lock:
            pending = self._replies.get((call_sid, seq))
        if pending is None:
            return None
        try:
            result = pending.future.result(timeout=timeout_sec)
            return result if isinstance(result, str) else None
        except Exception:
            return None

    def cleanup(self, call_sid: str) -> None:
        with self._lock:
            keys = [k for k in self._replies if k[0] == call_sid]
            for k in keys:
                self._replies[k].future.cancel()
                del self._replies[k]


# ---------------------------------------------------------------------------
# Streaming-token registry (Phase 2 — ElevenLabs chunked streaming)
# ---------------------------------------------------------------------------

@dataclass
class StreamSpec:
    text: str
    voice_id: str
    expires_at: float


class StreamingRegistry:
    """
    Maps single-use tokens to (text, voice_id) specs for the streaming TTS
    endpoint. Tokens expire after ttl_sec seconds and are consumed on pop().
    """

    def __init__(self, ttl_sec: float = 60.0) -> None:
        self._lock = threading.RLock()
        self._specs: dict[str, StreamSpec] = {}
        self._ttl_sec = ttl_sec

    def register(self, text: str, voice_id: str) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._specs[token] = StreamSpec(
                text=text,
                voice_id=voice_id,
                expires_at=time.time() + self._ttl_sec,
            )
        return token

    def pop(self, token: str) -> StreamSpec | None:
        with self._lock:
            spec = self._specs.pop(token, None)
        if spec is None:
            return None
        if time.time() > spec.expires_at:
            return None
        return spec

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._specs.items() if now > v.expires_at]
            for k in expired:
                del self._specs[k]
