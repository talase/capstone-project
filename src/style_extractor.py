"""LLM-powered high-level style extraction.

The extractor asks for abstract traits only. It explicitly forbids raw quotes,
examples, or message imitation in the saved profile.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None

from profile_store import neutral_profile, sanitize_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
BATCH_SIZE = 50
MODEL = "deepseek/deepseek-v4-flash"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def env_file_status() -> list[str]:
    """Return redacted status for env files checked by the loader."""

    statuses = []
    seen: set[Path] = set()
    for env_path in env_file_paths():
        resolved = env_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not env_path.exists():
            statuses.append(f"{env_path}: missing")
            continue
        keys = _read_env_keys(env_path)
        has_key = "OPENROUTER_API_KEY" in keys
        has_openai_key = "OPENAI_API_KEY" in keys
        openai_note = ", OPENAI_API_KEY=yes" if has_openai_key else ""
        statuses.append(
            f"{env_path}: exists, OPENROUTER_API_KEY={'yes' if has_key else 'no'}"
            f"{openai_note}"
        )
    return statuses


def env_file_paths() -> list[Path]:
    return [
        PROJECT_ROOT / ".env",
        WORKSPACE_ROOT / ".env",
        WORKSPACE_ROOT / ".venv" / ".env",
        Path.cwd() / ".env",
        Path.cwd() / ".venv" / ".env",
    ]


def load_env_file() -> None:
    """Load OPENROUTER_API_KEY from common local .env locations.

    The recommended location is style_adaptation/.env, but this also supports
    the workspace .env and .venv/.env because IDEs often create those first.
    """

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None

    for env_path in env_file_paths():
        if not env_path.exists():
            continue
        if load_dotenv is not None:
            load_dotenv(env_path, override=False)
        _load_env_manually(env_path)


def _load_env_manually(env_path: Path) -> None:
    """Tiny .env parser for KEY=value lines, used when python-dotenv is absent."""

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        if clean.startswith("export "):
            clean = clean.removeprefix("export ").strip()
        key, value = clean.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _read_env_keys(env_path: Path) -> list[str]:
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    keys: list[str] = []
    for line in lines:
        clean = line.strip()
        if clean.startswith("export "):
            clean = clean.removeprefix("export ").strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key = clean.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


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


def get_client() -> OpenAI:
    load_env_file()
    if OpenAI is None:
        raise RuntimeError(
            "The openai package is not installed. Run: pip install -r requirements.txt"
        )
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        checked = "\n".join(f"- {status}" for status in env_file_status())
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set.\n"
            "Add this line to style_adaptation/.env or .venv/.env:\n"
            "OPENROUTER_API_KEY=your_openrouter_key_here\n\n"
            "This script uses DeepSeek through OpenRouter, so OPENAI_API_KEY is "
            "not enough unless that value is actually an OpenRouter key and you "
            "copy it to OPENROUTER_API_KEY.\n\n"
            f"Checked env files:\n{checked}"
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


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
            extra_body={
                "provider": {
                    "only": ["deepseek"],
                }
            },
        )
        content = response.choices[0].message.content or ""
        raw_profile = _extract_json_object(content)
        return sanitize_profile(raw_profile, message_count=len(messages))
    except Exception as exc:
        print(f"Style extraction failed for {contact or 'global'}: {exc}")
        return neutral_profile(message_count=len(messages), batch_count=1)


def extract_file_profiles(path: Path, contact: str | None = None) -> list[dict[str, Any]]:
    messages = load_messages(path)
    return [extract_style_profile(batch, contact) for batch in batched(messages)]
