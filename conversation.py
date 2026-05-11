"""
conversation.py
===============
In-memory conversation state per active call.

Think of this like a stage manager's clipboard:
- One clipboard per active call (keyed by Twilio CallSid)
- Tracks which agent is assigned, the full conversation history,
  how many turns have elapsed, and when the call started
- Clipboards are cleaned up automatically when the call ends

For production scale (multi-worker Render), swap the dict for Redis.
Single-worker free tier: in-memory is fine.
"""

import time
import random
import logging
from agents import AGENTS, ESCALATION_TURN

logger = logging.getLogger(__name__)

# Active calls: { call_sid: { agent, history, turns, started_at } }
_calls: dict[str, dict] = {}


def assign_agent(call_sid: str, preferred: str | None = None) -> dict:
    """
    Assign a random agent to a new call (or a preferred one if specified).
    Stores initial state and returns the agent definition.
    """
    agent_key = preferred if preferred in AGENTS else random.choice(list(AGENTS.keys()))
    agent = AGENTS[agent_key]

    _calls[call_sid] = {
        "agent_key": agent_key,
        "agent": agent,
        "history": [],          # list of {"role": "user"|"assistant", "content": "..."}
        "turns": 0,
        "started_at": time.time(),
        "escalated": False,
    }

    logger.info(f"[{call_sid}] Assigned agent: {agent['name']}")
    return agent


def get_state(call_sid: str) -> dict | None:
    """Return call state or None if call is unknown."""
    return _calls.get(call_sid)


def add_exchange(call_sid: str, user_speech: str, agent_reply: str):
    """
    Append one full exchange (user → agent) to the call history
    and increment the turn counter.
    """
    state = _calls.get(call_sid)
    if not state:
        return

    state["history"].append({"role": "user",      "content": user_speech})
    state["history"].append({"role": "assistant",  "content": agent_reply})
    state["turns"] += 1

    elapsed = int(time.time() - state["started_at"])
    logger.info(
        f"[{call_sid}] Turn {state['turns']} | "
        f"Agent: {state['agent']['name']} | "
        f"Elapsed: {elapsed}s"
    )


def should_escalate(call_sid: str) -> bool:
    """
    Returns True the first time this call crosses the escalation threshold.
    Flips the escalated flag so the prompt is only injected once.
    """
    state = _calls.get(call_sid)
    if not state:
        return False
    if state["turns"] >= ESCALATION_TURN and not state["escalated"]:
        state["escalated"] = True
        logger.info(f"[{call_sid}] Escalation triggered at turn {state['turns']}")
        return True
    return False


def elapsed_seconds(call_sid: str) -> int:
    """How long this call has been active."""
    state = _calls.get(call_sid)
    if not state:
        return 0
    return int(time.time() - state["started_at"])


def end_call(call_sid: str):
    """
    Remove call state when the call ends.
    Called from the /status webhook on call completion.
    """
    state = _calls.pop(call_sid, None)
    if state:
        elapsed = int(time.time() - state["started_at"])
        logger.info(
            f"[{call_sid}] Call ended | "
            f"Agent: {state['agent']['name']} | "
            f"Duration: {elapsed}s | "
            f"Turns: {state['turns']}"
        )


def get_stall_tactic(call_sid: str) -> str:
    """
    Return a random stall tactic from the agent's tactic list.
    Used when the LLM gets a very short or empty speech input.
    """
    state = _calls.get(call_sid)
    if not state:
        return "Sorry, could you repeat that?"
    tactics = state["agent"].get("tactics", [])
    return random.choice(tactics) if tactics else "Could you say that again?"
