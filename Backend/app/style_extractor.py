"""LLM-powered high-level style extraction.

The extractor asks for abstract traits only. It explicitly forbids raw quotes,
examples, or message imitation in the saved profile.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypeVar

from app.config import BATCH_SIZE, MODEL, get_client, load_env_file
from app.profile_store import neutral_profile, sanitize_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent

GREETINGS = ("hey", "heyy", "heyyy", "hi", "hii", "hello", "yo", "salam")
COMMON_PHRASES = (
    "no worries",
    "sounds good",
    "gotcha",
    "sure",
    "okay",
    "lol",
    "haha",
    "lmk",
    "rn",
    "tbh",
)
STYLE_EMOJIS = ("😊", "😂", "😭", "❤️", "✨", "👍")
FORMAL_MARKERS = (
    "please",
    "thank you",
    "regards",
    "kindly",
    "would you",
    "could you",
)
WARM_MARKERS = ("love", "miss you", "thank", "thanks", "no worries")
ASSISTANT_CLOSINGS = (
    "let me know if you need anything",
    "how can i help",
    "anything else",
    "let me know if i can help",
    "feel free to reach out",
)
TASK_MARKERS = (
    "review",
    "send",
    "confirm",
    "schedule",
    "deadline",
    "update",
    "complete",
    "document",
    "meeting",
    "available",
)
SUPPORTIVE_MARKERS = (
    "i'm here",
    "i am here",
    "you've got this",
    "you got this",
    "sorry",
    "hope",
    "take care",
    "don't worry",
    "do not worry",
)

T = TypeVar("T")


def load_messages(path: Path) -> list[str]:
    """Load outgoing messages from one-message-per-line or chat transcript data."""

    messages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.lower().startswith("me:"):
            message = clean.split(":", 1)[1].strip()
            if message:
                messages.append(message)
        elif ":" not in clean and not clean.lower().startswith("conversation "):
            messages.append(clean)
    return messages


def batched(messages: list[T], size: int = BATCH_SIZE) -> list[list[T]]:
    return [messages[i : i + size] for i in range(0, len(messages), size)]


def extract_style_patterns(messages: list[str]) -> dict[str, Any]:
    """Extract deterministic conversational habits from outgoing messages."""

    clean_messages = [str(message).strip() for message in messages if str(message).strip()]
    patterns: dict[str, Any] = {
        "greetings": [],
        "common_phrases": [],
        "emoji_usage": [],
        "punctuation_style": {
            "uses_exclamation": False,
            "uses_repeated_letters": False,
            "question_frequency": 0,
        },
        "tone_indicators": [],
        "conversation_behavior": {
            "reply_length_style": "medium",
            "asks_followup_often": False,
            "uses_assistant_closings": False,
            "acknowledgment_style": "short",
            "helpfulness_mode": "friend",
        },
    }
    if not clean_messages:
        return patterns

    lowered_messages = [message.lower() for message in clean_messages]
    combined = "\n".join(lowered_messages)

    patterns["greetings"] = [
        greeting
        for greeting in GREETINGS
        if re.search(rf"(?<!\w){re.escape(greeting)}(?!\w)", combined)
    ]
    patterns["common_phrases"] = [
        phrase
        for phrase in COMMON_PHRASES
        if re.search(_phrase_pattern(phrase), combined)
    ]
    patterns["emoji_usage"] = [
        emoji for emoji in STYLE_EMOJIS if any(emoji in message for message in clean_messages)
    ]

    exclamation_count = sum(message.count("!") for message in clean_messages)
    question_count = sum(1 for message in clean_messages if "?" in message)
    repeated_letters = any(
        re.search(r"([a-z])\1{2,}", message, flags=re.IGNORECASE)
        for message in clean_messages
    )
    patterns["punctuation_style"] = {
        "uses_exclamation": exclamation_count >= 2,
        "uses_repeated_letters": repeated_letters,
        "question_frequency": question_count,
    }

    word_counts = [len(re.findall(r"\b[\w']+\b", message)) for message in clean_messages]
    informal_greetings = {"hey", "heyy", "heyyy", "hi", "hii", "yo"}
    casual_signal = bool(
        informal_greetings.intersection(patterns["greetings"])
        or patterns["common_phrases"]
        or re.search(r"\b(gonna|wanna|yep|yeah|nah|omg|btw)\b", combined)
    )
    formal_signal = any(marker in combined for marker in FORMAL_MARKERS)
    warm_signal = bool(patterns["emoji_usage"]) or any(
        marker in combined for marker in WARM_MARKERS
    )
    brief_signal = sum(word_counts) / len(word_counts) <= 6
    enthusiastic_signal = (
        exclamation_count >= 2
        or repeated_letters
        or any(emoji in patterns["emoji_usage"] for emoji in ("😂", "😭", "❤️", "✨"))
    )

    tone_indicators = []
    for tone, detected in (
        ("casual", casual_signal),
        ("formal", formal_signal),
        ("warm", warm_signal),
        ("brief", brief_signal),
        ("enthusiastic", enthusiastic_signal),
    ):
        if detected:
            tone_indicators.append(tone)
    patterns["tone_indicators"] = tone_indicators
    average_word_count = sum(word_counts) / len(word_counts)
    uses_assistant_closings = any(
        closing in combined for closing in ASSISTANT_CLOSINGS
    )
    task_focused = any(
        re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", combined)
        for marker in TASK_MARKERS
    )
    supportive_signal = any(marker in combined for marker in SUPPORTIVE_MARKERS)

    if average_word_count <= 6:
        reply_length_style = "brief"
    elif average_word_count >= 16:
        reply_length_style = "detailed"
    else:
        reply_length_style = "medium"

    if supportive_signal:
        acknowledgment_style = "supportive"
    elif warm_signal:
        acknowledgment_style = "warm"
    else:
        acknowledgment_style = "short"

    if uses_assistant_closings:
        helpfulness_mode = "assistant"
    elif formal_signal or task_focused:
        helpfulness_mode = "professional"
    else:
        helpfulness_mode = "friend"

    patterns["conversation_behavior"] = {
        "reply_length_style": reply_length_style,
        "asks_followup_often": question_count / len(clean_messages) >= 0.4,
        "uses_assistant_closings": uses_assistant_closings,
        "acknowledgment_style": acknowledgment_style,
        "helpfulness_mode": helpfulness_mode,
    }
    return patterns


def _phrase_pattern(phrase: str) -> str:
    """Match a phrase and casual elongation of its final letter."""

    return rf"(?<!\w){re.escape(phrase[:-1])}{re.escape(phrase[-1])}+(?!\w)"


def _reply_text(message: str | dict[str, str]) -> str:
    if isinstance(message, str):
        return message
    return message.get("reply", "")


def build_extraction_prompt(
    messages: list[str | dict[str, str]],
    contact: str | None = None,
) -> str:
    examples = []
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, str):
            examples.append(f"{idx}. Reply: {message}")
            continue

        context = message.get("context", "").strip() or "(not provided)"
        reply = message.get("reply", "").strip()
        examples.append(f"{idx}. Incoming context: {context}\n   User reply: {reply}")

    numbered = "\n".join(examples)
    contact_note = f"Contact: {contact}" if contact else "Contact: unknown"
    return f"""
You are a style analysis module for outgoing WhatsApp-style messages.
Analyze the user's replies and extract only abstract communication style traits.

{contact_note}

Rules:
- Return JSON only. No markdown, no commentary.
- Analyze only the reply text when learning the user's writing style.
- Use incoming context only to understand how the user adapts their reply to the conversation.
- Never copy, imitate, or learn tone, wording, or writing style from incoming context.
- Do not imitate the messages.
- Do not include direct quotes or copied phrases from the messages.
- Patterns must be abstract, short behavioral descriptions.
- Scores must be floats from 0.0 to 1.0.
- Confidence values should be 0 to 100.
- Limit patterns to at most 5.
- Return exactly the same JSON structure defined below.

Required JSON schema:
{{
  "traits": {{
    "formality": {{"score": 0.0, "confidence": 0}},
    "politeness": {{"score": 0.0, "confidence": 0}},
    "verbosity": {{"score": 0.0, "confidence": 0}},
    "optimism": {{"score": 0.0, "confidence": 0}}
  }},
  "patterns": [],
  "overall_confidence": 0,
  "message_count": {len(messages)},
  "batch_count": 1
}}

Conversation examples:
{numbered}
""".strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse JSON safely, including responses that accidentally wrap the object."""

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def extract_style_profile(
    messages: list[str | dict[str, str]],
    contact: str | None = None,
) -> dict[str, Any]:
    """Send a batch of messages to the LLM and return a sanitized profile."""

    if not messages:
        return neutral_profile()

    replies = [_reply_text(message).strip() for message in messages]
    replies = [reply for reply in replies if reply]
    prompt = build_extraction_prompt(messages, contact)
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        raw_profile = _extract_json_object(content)
        raw_profile["patterns"] = extract_style_patterns(replies)
        return sanitize_profile(raw_profile, message_count=len(replies))
    except Exception as e:
        print("FULL ERROR:", repr(e))
        raise


def extract_file_profiles(path: Path, contact: str | None = None) -> list[dict[str, Any]]:
    messages = load_messages(path)
    return [extract_style_profile(batch, contact) for batch in batched(messages)]
