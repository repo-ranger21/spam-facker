"""
llm.py
======
LLM conversation engine for SpamFacker voice agents.

Architecture (like a telephone switchboard with a writer in the middle):
  Twilio captures speech → /respond webhook → this module →
  OpenAI generates in-character response → Flask returns TwiML → Twilio speaks it

Model: gpt-4o-mini (fast, cheap, good enough for real-time voice)
Swap to gpt-4o for higher quality if latency allows.
Swap to claude-sonnet-4-20250514 via Anthropic SDK if preferred.

Response time budget: Twilio times out Gather after 5 seconds of silence.
Target LLM response < 2 seconds. Keep max_tokens tight.
"""

import os
import json
import logging
from openai import OpenAI
from conversation import CallState

logger = logging.getLogger(__name__)

# Stage 1 classifier: fast, cheap, structured (~200 ms, ~$0.0001/turn)
CLASSIFIER_MODEL = "gpt-4o-mini"
# Stage 2 persona: higher quality for character realism
MODEL = "gpt-4o"
# Hard cap — agents shouldn't monologue; voice turns are short
MAX_TOKENS = 60


_VOICE_RULES = """

VOICE OUTPUT RULES - HUMAN REALISM (critical):
- You are speaking out loud on a phone call. Not writing. Not texting.
- Maximum 2 sentences per response. Phone conversations are short turns.
- Use natural spoken filler where it fits your character:
    Mildred: "Oh" "Now let me see" "Well" "Goodness"
    Gary: "Yeah" "Look" "Hold on" "Right"
    Timmy: "Okay" "So" "Um" "Right so"
    Shanika: "Okay but" "Wait" "No but" "Right right right"
    Bruce: "Listen" "No" "Let me stop you" "Look"
- Self-correct mid-sentence occasionally:
    "I need to - actually, wait. Let me back up."
    "The card is - no, that's the library one."
- Vary sentence length. Mix very short with slightly longer.
    "No." is a complete response. Use it.
    "Hang on." is a complete response. Use it.
- Never use perfect grammar exclusively. Real speech has fragments.
- Never start consecutive responses with the same word.
- Never use formal transition phrases: "Additionally" "Furthermore"
  "That being said" "I understand that" - these are AI tells.
- Never summarize what they just said before responding to it.
  "I understand you're saying X" -> immediate AI tell. Never do this.
- Never apologize for confusion. Real people just redirect.
- End every response with either:
    a) A question that requires their answer
    b) An incomplete thought that makes them wait
    c) A task you are visibly performing that requires them to hold
- No asterisks. No quotes for emphasis. No markdown of any kind.
- Numbers spoken: "forty-seven" not "47". "January" not "1/1".
"""

_CLASSIFIER_PROMPT = """\
Classify the scammer's utterance. Return JSON with exactly these fields:
  "intent": demand_payment|demand_info|create_urgency|threaten|build_rapport|verify_identity|other
  "ask_for": ssn|card_number|bank_account|address|dob|pin|gift_card|wire_transfer|null
  "pressure": urgency|authority|sympathy|reward|none
  "frustrated": true if they say listen/focus/stop/pay attention/ma'am please, else false
  "scam_type": irs|medicare|tech_support|gift_card|romance|lottery|unknown
Return only the JSON object, no explanation.\
"""


def classify_utterance(
    utterance: str,
    state: CallState | None,
    client: OpenAI,
) -> dict:
    """Stage 1: fast gpt-4o-mini classification of the scammer's utterance."""
    _FALLBACK: dict = {
        "intent": "unknown",
        "ask_for": None,
        "pressure": "none",
        "frustrated": False,
        "scam_type": None,
    }
    try:
        response = client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFIER_PROMPT},
                {"role": "user", "content": utterance},
            ],
            max_tokens=120,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        logger.info("[classifier] %s", result)
        return result
    except Exception:
        logger.exception("Classifier failed; using fallback")
        return _FALLBACK


def _apply_classification(state: CallState, c: dict) -> None:
    """Apply LLM classification results to the call state."""
    ask = c.get("ask_for")
    if ask:
        if ask in state.asked_for:
            state.repeated_demands += 1
        else:
            state.asked_for.add(ask)
    if c.get("frustrated"):
        state.scammer_frustration_signals += 1
    if state.scam_type is None:
        scam = c.get("scam_type")
        if scam and scam != "unknown":
            state.scam_type = scam
    if state.scammer_tactic is None:
        pressure = c.get("pressure")
        if pressure and pressure != "none":
            state.scammer_tactic = pressure


def _build_call_context(c: dict, state: CallState | None) -> str:
    """Build a [CALL CONTEXT] block from classification + accumulated state."""
    scam = (state.scam_type if state else None) or "unknown"
    intent = c.get("intent", "unknown")
    pressure = c.get("pressure", "none")
    lines = [
        "[CALL CONTEXT]",
        f"Scam type: {scam}",
        f"Scammer just: {intent} (pressure: {pressure})",
    ]
    if state and state.asked_for:
        lines.append(
            "Already asked for: " + ", ".join(sorted(state.asked_for))
        )
    if state and state.tactics_used:
        recent = state.tactics_used[-3:]
        lines.append(f"Avoid repeating: {recent}")
    if state and state.scammer_frustration_signals >= 1:
        lines.append(
            f"Frustration level: {state.scammer_frustration_signals}"
        )
    return "\n".join(lines)


def _trim_history(history: list[dict], last_n: int = 6) -> list[dict]:
    """Return the last last_n exchange-pairs (2 * last_n messages)."""
    return history[-(last_n * 2):]


def recent_turns(turns: list, n: int = 6) -> list[dict]:
    """
    Return the last n exchange-pairs from a list of Turn objects as
    OpenAI message dicts.  Used by build_messages and unit tests.
    """
    return [t.to_message() for t in turns[-(n * 2):]]


def build_messages(
    call_state: "CallState",
    scammer_utterance: str,
    classification: dict | None = None,
    escalate: bool = False,
) -> list[dict]:
    """
    Assemble the full messages list for the Stage 2 persona call.
    Respects ENABLE_TOKEN_CAP for history depth.
    """
    agent = call_state.agent
    system_content = agent["system_prompt"].strip()
    if escalate:
        system_content += "\n\n" + agent["escalation_prompt"].strip()
    system_content += _VOICE_RULES
    if classification:
        system_content += "\n\n" + _build_call_context(classification, call_state)
    n = 6 if os.getenv("ENABLE_TOKEN_CAP", "false").lower() == "true" else 10
    return [
        {"role": "system", "content": system_content},
        *recent_turns(call_state.turns, n=n),
        {"role": "user", "content": scammer_utterance},
    ]


def generate_response(
    agent: dict,
    history: list[dict],
    user_speech: str,
    escalate: bool = False,
    state: CallState | None = None,
) -> str:
    """
    Generate the agent's next spoken response (two-stage pipeline).

    Stage 1: gpt-4o-mini classifies the scammer's utterance (~200 ms).
    Stage 2: gpt-4o generates the persona response with surgical context.

    Returns plain text (no SSML, no markdown).
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Stage 1: classify the scammer's utterance and update the case file
    classification = classify_utterance(user_speech, state, client)
    if state is not None:
        _apply_classification(state, classification)

    # Build the system message
    system_content = agent["system_prompt"].strip()
    if escalate:
        system_content += "\n\n" + agent["escalation_prompt"].strip()
        logger.info("Escalation prompt injected")
    system_content += _VOICE_RULES

    # Inject per-turn context: intent + accumulated scam intel
    system_content += "\n\n" + _build_call_context(classification, state)

    # Stage 2: persona response — gpt-4o with trimmed history
    _token_cap = os.getenv("ENABLE_TOKEN_CAP", "false").lower() == "true"
    _history_depth = 6 if _token_cap else 10
    messages = [{"role": "system", "content": system_content}]
    messages.extend(_trim_history(history, last_n=_history_depth))
    messages.append({"role": "user", "content": user_speech})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=60 if _token_cap else 90,
            temperature=0.9,
            presence_penalty=0.6,
            frequency_penalty=0.3 if _token_cap else 0.0,
        )
        reply = response.choices[0].message.content.strip()
        logger.info(
            "LLM response (%d chars): %s...", len(reply), reply[:80]
        )
        return reply

    except Exception:
        logger.exception("LLM call failed")
        return (
            "Hold on just one moment, "
            "I'm having a little trouble hearing you."
        )


def generate_stall(agent: dict) -> str:
    """
    Ultra-fast fallback for when STT returns empty or very short input.
    Skips history — just generates a quick in-character stall.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": agent["system_prompt"].strip()},
                {"role": "user",   "content": "[The caller said something unclear. Stay in character and ask them to repeat themselves in one short sentence.]"},
            ],
            max_tokens=40,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        import random
        return random.choice(agent.get("tactics", ["Sorry, could you say that again?"]))
