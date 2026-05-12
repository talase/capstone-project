"""Generate synthetic outgoing WhatsApp-style messages for each contact.

Each file contains one outgoing message per line. The data is synthetic on
purpose: it gives the style extractor enough signal without exposing real chats.
"""

from __future__ import annotations

import random
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


CONTACT_STYLES = {
    "mom": {
        "openers": ["Hi mom", "Mama", "Dear mom", "My lovely mom"],
        "bodies": [
            "I hope you are feeling okay today",
            "please take care and rest when you can",
            "I made sure to finish what you asked me",
            "I will call you after I get home",
            "thank you for always checking on me",
        ],
        "closers": ["love you", "please don't worry", "sending hugs", "take care of yourself"],
    },
    "dad": {
        "openers": ["Hi dad", "Dad", "Hello dad", "Okay dad"],
        "bodies": [
            "I checked the details and it should be fine",
            "I will handle it after work",
            "the payment is done",
            "I will send the document tonight",
            "the appointment is confirmed",
        ],
        "closers": ["thank you", "will update you", "all good", "respectfully"],
    },
    "teacher": {
        "openers": ["Dear teacher", "Hello professor", "Good morning", "Dear sir"],
        "bodies": [
            "I would like to ask about the assignment deadline",
            "I have reviewed the lecture notes and prepared my questions",
            "could you please confirm the required format",
            "I apologize for the inconvenience and appreciate your guidance",
            "I will submit the work according to the instructions",
        ],
        "closers": ["thank you for your time", "best regards", "sincerely", "with appreciation"],
    },
    "boss": {
        "openers": ["Hi", "Hello", "Good morning", "Noted"],
        "bodies": [
            "I will send the file before the deadline",
            "the task is in progress",
            "I checked the numbers and updated the sheet",
            "I can join the meeting at the scheduled time",
            "the report is ready for review",
        ],
        "closers": ["thanks", "will update shortly", "done", "on it"],
    },
    "friend": {
        "openers": ["heyyy", "bro", "bestie", "yoo"],
        "bodies": [
            "that was actually so funny",
            "I'm coming in a bit",
            "send me the pic when you can",
            "we need to go there again",
            "I cannot believe that happened",
        ],
        "closers": ["lol", "haha", "😂", "fr", "see yaa"],
    },
    "sister": {
        "openers": ["sis", "hey you", "little troublemaker", "okay queen"],
        "bodies": [
            "I saved you some food",
            "stop stealing my charger",
            "tell me the story when you get back",
            "I will help you choose the outfit",
            "that drama is too good",
        ],
        "closers": ["haha", "love you", "don't be late", "text me", "😂"],
    },
    "delivery": {
        "openers": ["Hi", "Hello", "Please", "Ok"],
        "bodies": [
            "leave it at the door",
            "call me when outside",
            "the address is correct",
            "I am at the main gate",
            "order number is ready",
        ],
        "closers": ["thanks", "gate 2", "cash paid", "near reception"],
    },
}


def build_message(style: dict[str, list[str]]) -> str:
    """Create one synthetic message from a contact's style pieces."""

    opener = random.choice(style["openers"])
    body = random.choice(style["bodies"])
    closer = random.choice(style["closers"])

    if random.random() < 0.25:
        extra = random.choice(style["bodies"])
        return f"{opener}, {body}. Also, {extra}. {closer}."

    return f"{opener}, {body}. {closer}."


def generate_messages_per_contact(count: int = 120, seed: int = 42) -> None:
    """Generate contact files in the data directory."""

    random.seed(seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for contact, style in CONTACT_STYLES.items():
        messages = [build_message(style) for _ in range(count)]
        output_path = DATA_DIR / f"{contact}.txt"
        output_path.write_text("\n".join(messages) + "\n", encoding="utf-8")
        print(f"Generated {len(messages)} messages: {output_path}")


if __name__ == "__main__":
    generate_messages_per_contact()
