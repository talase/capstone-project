"""LLM-powered high-level style extraction.

The extractor asks for abstract traits only. It explicitly forbids raw quotes,
examples, or message imitation in the saved profile.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import BATCH_SIZE, MODEL, get_client, load_env_file
from app.profile_store import neutral_profile, sanitize_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent


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


def batched(messages: list[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [messages[i : i + size] for i in range(0, len(messages), size)]


def build_extraction_prompt(messages: list[str], contact: str | None = None) -> str:
    numbered = "\n".join(f"{idx + 1}. {message}" for idx, message in enumerate(messages))
    contact_note = f"Contact: {contact}" if contact else "Contact: unknown"
    return f"""
You are a style analysis module for outgoing WhatsApp-style messages.
Analyze the messages and extract only abstract communication style traits.

{contact_note}

Rules:
- Return JSON only. No markdown, no commentary.
- Do not imitate the messages.
- Do not include direct quotes or copied phrases from the messages.
- Patterns must be abstract, short behavioral descriptions.
- Scores must be floats from 0.0 to 1.0.
- Confidence values should be 0 to 100.
- Limit patterns to at most 5.

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

Messages:
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


def extract_style_profile(messages: list[str], contact: str | None = None) -> dict[str, Any]:
    """Send a batch of messages to the LLM and return a sanitized profile."""

    if not messages:
        return neutral_profile()

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
        return sanitize_profile(raw_profile, message_count=len(messages))
    except Exception as e:
        print("FULL ERROR:", repr(e))
        raise


def extract_file_profiles(path: Path, contact: str | None = None) -> list[dict[str, Any]]:
    messages = load_messages(path)
    return [extract_style_profile(batch, contact) for batch in batched(messages)]
