"""Generate synthetic WhatsApp-style conversations for each contact.

Each contact file contains multi-turn conversations with messages from both
sides. Lines that start with "Me:" represent the user's outgoing messages and
are the only lines used for style extraction.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from style_extractor import MODEL, get_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
TARGET_CONVERSATIONS = 24
MIN_CONVERSATIONS = 20
MIN_OUTGOING_MESSAGES = 120
CONVERSATIONS_PER_REQUEST = 2


CONTACT_SPECS = {
    "mom": {
        "relationship": "mother",
        "style": "warm, caring, reassuring, polite, emotionally attentive",
        "topics": [
            "checking if she ate and took medicine",
            "planning a family visit",
            "sending a document she asked for",
            "coming home late after class",
            "helping her with an appointment",
        ],
    },
    "dad": {
        "relationship": "father",
        "style": "practical, respectful, concise, calm, update-focused",
        "topics": [
            "car maintenance",
            "a bank payment",
            "confirming an appointment",
            "sending paperwork",
            "checking directions",
        ],
    },
    "teacher": {
        "relationship": "university teacher",
        "style": "formal, polite, clear, careful, academically respectful",
        "topics": [
            "assignment deadline",
            "lecture notes",
            "project feedback",
            "absence from class",
            "submission format",
        ],
    },
    "boss": {
        "relationship": "work manager",
        "style": "professional, concise, responsible, task-oriented",
        "topics": [
            "sending a report",
            "meeting schedule",
            "spreadsheet updates",
            "client follow-up",
            "deadline status",
        ],
    },
    "friend": {
        "relationship": "close friend",
        "style": "casual, playful, expressive, energetic, informal",
        "topics": [
            "making weekend plans",
            "reacting to a funny story",
            "choosing a cafe",
            "sharing photos",
            "planning a movie night",
        ],
    },
    "sister": {
        "relationship": "sister",
        "style": "casual, teasing, affectionate, relaxed, expressive",
        "topics": [
            "borrowing clothes",
            "saving food",
            "family gossip",
            "choosing an outfit",
            "sharing a charger",
        ],
    },
    "delivery": {
        "relationship": "delivery driver",
        "style": "short, practical, direct, polite, location-focused",
        "topics": [
            "confirming the gate",
            "asking to leave an order at the door",
            "sharing delivery instructions",
            "confirming payment",
            "answering a location call",
        ],
    },
}


def build_generation_prompt(
    contact: str,
    spec: dict[str, Any],
    start_index: int = 1,
    count: int = TARGET_CONVERSATIONS,
) -> str:
    topics = "\n".join(f"- {topic}" for topic in spec["topics"])
    end_index = start_index + count - 1
    return f"""
Generate synthetic WhatsApp chat data for a capstone project.

Contact file: {contact}.txt
Relationship: {spec["relationship"]}
User writing style for lines by "Me": {spec["style"]}

Create {count} realistic conversations, numbered Conversation {start_index} through Conversation {end_index}. Each conversation must:
- Have a short title line in this exact format: Conversation N: topic.
- Include 12 to 16 message lines.
- Include both speakers.
- Include at least 6 lines from "Me:".
- Use "Me:" for the user's outgoing messages.
- Use "{contact.title()}:" for the contact's messages.
- Sound like an ongoing real chat, with replies that depend on previous lines.
- Avoid standalone one-line examples.
- Avoid private personal data, addresses, phone numbers, emails, or real names.
- Keep messages natural and WhatsApp-like.
- Do not include markdown fences or commentary.

Use these topic ideas:
{topics}

Return JSON only with this schema:
{{
  "conversations": [
    {{
      "title": "Conversation {start_index}: short topic",
      "messages": [
        {{"speaker": "Me", "text": "message text"}},
        {{"speaker": "{contact.title()}", "text": "message text"}}
      ]
    }}
  ]
}}
""".strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _clean_line(text: str) -> str:
    clean = " ".join(text.replace("\n", " ").split())
    clean = re.sub(r"\b\d{4,}\b", "the number", clean)
    clean = re.sub(r"\b[A-Z][a-z]+ and [A-Z][a-z]+\b", "the team leads", clean)
    return clean


def conversation_blocks(contact: str, data: dict[str, Any]) -> list[str]:
    """Convert generated JSON into a readable WhatsApp-style transcript."""

    contact_label = contact.title()
    blocks: list[str] = []

    for idx, conversation in enumerate(data.get("conversations", []), start=1):
        title = _clean_line(conversation.get("title") or f"Conversation {idx}")
        if not title.lower().startswith("conversation"):
            title = f"Conversation {idx}: {title}"

        lines = [title]
        for message in conversation.get("messages", []):
            speaker = str(message.get("speaker", "")).strip()
            text = _clean_line(str(message.get("text", "")))
            if not text:
                continue
            if speaker.lower() == "me":
                speaker = "Me"
            else:
                speaker = contact_label
            lines.append(f"{speaker}: {text}")

        me_count = sum(1 for line in lines if line.startswith("Me:"))
        contact_count = sum(1 for line in lines if line.startswith(f"{contact_label}:"))
        if me_count >= 4 and contact_count >= 4:
            blocks.append("\n".join(lines))

    if not blocks:
        raise ValueError(f"No valid conversations generated for {contact}")

    return blocks


def format_conversations(contact: str, data: dict[str, Any]) -> str:
    blocks = conversation_blocks(contact, data)
    me_total = sum(line.startswith("Me:") for block in blocks for line in block.splitlines())
    if len(blocks) < MIN_CONVERSATIONS or me_total < MIN_OUTGOING_MESSAGES:
        raise ValueError(f"Not enough valid conversations generated for {contact}")
    return "\n\n".join(blocks) + "\n"


def format_raw_transcript(
    contact: str,
    content: str,
    min_conversations: int = MIN_CONVERSATIONS,
    min_outgoing: int = MIN_OUTGOING_MESSAGES,
) -> str:
    """Fallback for model responses that are already transcript-like."""

    contact_label = contact.title()
    blocks: list[str] = []
    current: list[str] = []
    conversation_count = 0

    for raw_line in content.splitlines():
        line = _clean_line(raw_line)
        if not line or line.startswith("```"):
            continue
        if line.lower().startswith("conversation "):
            if current:
                blocks.append("\n".join(current))
            conversation_count += 1
            current = [line]
            continue
        if line.lower().startswith("me:"):
            current.append(f"Me: {line.split(':', 1)[1].strip()}")
            continue
        if ":" in line and current:
            current.append(f"{contact_label}: {line.split(':', 1)[1].strip()}")

    if current:
        blocks.append("\n".join(current))

    valid_blocks = []
    for idx, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if not lines[0].lower().startswith("conversation "):
            lines.insert(0, f"Conversation {idx}: chat")
        me_count = sum(1 for line in lines if line.startswith("Me:"))
        contact_count = sum(1 for line in lines if line.startswith(f"{contact_label}:"))
        if me_count >= 4 and contact_count >= 4:
            valid_blocks.append("\n".join(lines))

    me_total = sum(
        line.startswith("Me:") for block in valid_blocks for line in block.splitlines()
    )
    if (
        conversation_count
        and len(valid_blocks) >= min_conversations
        and me_total >= min_outgoing
    ):
        return "\n\n".join(valid_blocks) + "\n"
    raise ValueError(f"No valid conversations generated for {contact}")


def generate_conversation_chunk(
    contact: str,
    spec: dict[str, Any],
    start_index: int,
    count: int,
) -> list[str]:
    client = get_client()
    prompt = build_generation_prompt(contact, spec, start_index, count)

    last_error: Exception | None = None
    for attempt in range(1, 4):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6 + (attempt * 0.1),
            max_tokens=2500,
            timeout=90,
            extra_body={
                "provider": {
                    "only": ["deepseek"],
                }
            },
        )
        content = response.choices[0].message.content or ""
        try:
            return conversation_blocks(contact, _extract_json_object(content))
        except ValueError as exc:
            last_error = exc
            try:
                return format_raw_transcript(
                    contact,
                    content,
                    min_conversations=1,
                    min_outgoing=4,
                ).strip().split("\n\n")
            except ValueError as raw_exc:
                last_error = raw_exc
                prompt = (
                    build_generation_prompt(contact, spec, start_index, count)
                    + "\n\nYour previous response was invalid. Return only valid JSON "
                    "with conversations and messages exactly matching the schema."
                )

    raise ValueError(f"Could not generate valid chunk for {contact}") from last_error


def generate_contact_conversations(contact: str, spec: dict[str, Any]) -> str:
    blocks: list[str] = []

    for start_index in range(1, TARGET_CONVERSATIONS + 1, CONVERSATIONS_PER_REQUEST):
        count = min(CONVERSATIONS_PER_REQUEST, TARGET_CONVERSATIONS - start_index + 1)
        blocks.extend(generate_conversation_chunk(contact, spec, start_index, count))

    me_total = sum(line.startswith("Me:") for block in blocks for line in block.splitlines())
    if len(blocks) < MIN_CONVERSATIONS or me_total < MIN_OUTGOING_MESSAGES:
        raise ValueError(f"Not enough valid conversations generated for {contact}")

    return "\n\n".join(blocks) + "\n"


def generate_messages_per_contact() -> None:
    """Generate contact chat files in the data directory."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for contact, spec in CONTACT_SPECS.items():
        transcript = generate_contact_conversations(contact, spec)
        output_path = DATA_DIR / f"{contact}.txt"
        output_path.write_text(transcript, encoding="utf-8")
        line_count = sum(1 for line in transcript.splitlines() if line.strip())
        print(f"Generated {line_count} chat lines: {output_path}")


if __name__ == "__main__":
    generate_messages_per_contact()
