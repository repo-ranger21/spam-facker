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
MAX_TOKENS = 90
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
            temperature=0.92,
            presence_penalty=0.8,
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
