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
import logging
from openai import OpenAI
from agents import ESCALATION_TURN

logger = logging.getLogger(__name__)

# Keep responses short — this is voice, not text. 1-3 sentences max.
# Long responses get cut off or sound unnatural over the phone.
MAX_TOKENS = 120
MODEL = "gpt-4o-mini"


def generate_response(
    agent: dict,
    history: list[dict],
    user_speech: str,
    escalate: bool = False,
) -> str:
    """
    Generate the agent's next spoken response.

    Args:
        agent       : Agent definition dict from agents.py
        history     : Full conversation history so far
        user_speech : What the caller just said (STT result from Twilio)
        escalate    : Whether to inject the escalation prompt this turn

    Returns:
        Plain text response (no SSML, no markdown — Twilio reads it as-is)
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build the system message
    system_content = agent["system_prompt"].strip()

    if escalate:
        system_content += "\n\n" + agent["escalation_prompt"].strip()
        logger.info("Escalation prompt injected")

    # Voice-specific instructions appended to every system prompt
    system_content += """

VOICE OUTPUT RULES (critical — you are speaking, not writing):
- Maximum 2-3 sentences per response. Voice conversations are short turns.
- No lists, no bullet points, no markdown of any kind.
- No asterisks, no quotation marks around words for emphasis.
- Spell out numbers: "forty-seven" not "47".
- Never start a response with "I" — vary your sentence openers.
- End every response with either a question, a reason to wait, or an incomplete thought.
- Do not summarize what they said back to them verbatim.
"""

    messages = [{"role": "system", "content": system_content}]

    # Add conversation history (last 10 turns max to stay within context)
    messages.extend(history[-20:])

    # Add the current user input
    messages.append({"role": "user", "content": user_speech})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=0.85,   # Slightly creative but consistent
            presence_penalty=0.6,  # Discourages repeating the same stall tactics
        )
        reply = response.choices[0].message.content.strip()
        logger.info(f"LLM response ({len(reply)} chars): {reply[:80]}...")
        return reply

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        # Fail gracefully — return a stall line so the call doesn't drop
        return "Hold on just one moment, I'm having a little trouble hearing you."


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
