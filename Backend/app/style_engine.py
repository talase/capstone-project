"""End-to-end runner for the style adaptation capstone project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.buffer import StyleBuffer, choose_style_mode
from app.config import MODEL, get_client, load_env_file
from app.evaluator import evaluate_profiles
from app.generate_data import generate_messages_per_contact
from app.profile_store import load_global_profile, load_profile, resolve_profile_contact
from app.prompt_templates import build_prompt
from app.style_extractor import load_messages


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
PROFILES_DIR = PROJECT_ROOT / "profiles"
CONTACTS_TO_DEMO = ("boss", "friend", "mom")
FALLBACK_REPLY = "Sure, I will send it today."


def ensure_data_exists() -> None:
    required = ["mom", "dad", "teacher", "boss", "friend", "sister", "delivery"]
    missing = [name for name in required if not (DATA_DIR / f"{name}.txt").exists()]
    if missing:
        print("Synthetic data missing. Generating data files...")
        generate_messages_per_contact()


def observe_all_messages() -> None:
    """Simulate observation mode over every contact file in data/."""

    style_buffer = StyleBuffer()
    contact_files = sorted(DATA_DIR.glob("*.txt"))
    for contact_file in contact_files:
        contact = contact_file.stem
        for message in load_messages(contact_file):
            style_buffer.observe(contact, message)
    style_buffer.flush_all()


def reset_profiles() -> None:
    """Start a full capstone run from clean saved profiles."""

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    for profile_file in PROFILES_DIR.glob("profile_*.json"):
        profile_file.unlink()


def generate_styled_reply(
    incoming_message: str,
    contact_name: str,
    mode: str,
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
    risk_level: str | None = None,
    action_type: str | None = None,
) -> str:
    """Generate one reply using the selected style mode via OpenRouter."""

    result = generate_styled_reply_result(
        incoming_message=incoming_message,
        contact_name=contact_name,
        mode=mode,
        global_profile=global_profile,
        contact_profile=contact_profile,
        risk_level=risk_level,
        action_type=action_type,
    )
    return result["reply"]


def generate_styled_reply_result(
    incoming_message: str,
    contact_name: str,
    mode: str,
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
    risk_level: str | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Generate one reply and include whether the LLM or fallback produced it."""

    # The prompt builder centralizes all mode-specific style instructions.
    prompt = build_prompt(
        message=incoming_message,
        contact_name=contact_name,
        style_mode=mode,
        global_profile=global_profile,
        contact_profile=contact_profile,
        risk_level=risk_level,
        action_type=action_type,
    )

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        reply = (response.choices[0].message.content or "").strip()
        return {
            "reply": reply or FALLBACK_REPLY,
            "generation_status": "generated" if reply else "fallback",
            "llm_error": not bool(reply),
        }
    except Exception as exc:
        print(f"Reply generation failed for {contact_name}: {exc}")
        return {
            "reply": FALLBACK_REPLY,
            "generation_status": "fallback",
            "llm_error": True,
        }


def generate_style_adapted_response(
    incoming_message: str,
    contact_id: str,
    risk_level: str | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Run the final style-aware response generation pipeline."""

    clean_message = (incoming_message or "").strip()
    clean_contact = (contact_id or "").strip()
    profile_contact = resolve_profile_contact(clean_contact)

    # Missing or malformed profile JSON falls back to neutral profiles.
    global_profile = load_global_profile()
    contact_profile = load_profile(clean_contact)

    # Confidence gating chooses which style signal is reliable enough to use.
    mode = choose_style_mode(global_profile, contact_profile)
    global_confidence = int(global_profile.get("overall_confidence", 0) or 0)
    contact_confidence = int(contact_profile.get("overall_confidence", 0) or 0)

    generation = generate_styled_reply_result(
        incoming_message=clean_message,
        contact_name=profile_contact,
        mode=mode,
        global_profile=global_profile,
        contact_profile=contact_profile,
        risk_level=risk_level,
        action_type=action_type,
    )

    return {
        "reply": generation["reply"],
        "style_mode": mode,
        "contact_id": clean_contact,
        "profile_contact": profile_contact,
        "global_confidence": global_confidence,
        "contact_confidence": contact_confidence,
        "generation_status": generation["generation_status"],
        "llm_error": generation["llm_error"],
    }


def run_gating_and_demo() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    global_profile = load_global_profile()
    outputs: dict[str, Any] = {}
    incoming = "Can you send me the file today?"

    for contact_file in sorted(DATA_DIR.glob("*.txt")):
        contact = contact_file.stem
        contact_profile = load_profile(contact)
        mode = choose_style_mode(global_profile, contact_profile)
        outputs[contact] = {
            "mode": mode,
            "global_confidence": global_profile.get("overall_confidence", 0),
            "contact_confidence": contact_profile.get("overall_confidence", 0),
        }

    demo_replies = {}
    for contact in CONTACTS_TO_DEMO:
        contact_profile = load_profile(contact)
        mode = choose_style_mode(global_profile, contact_profile)
        demo_replies[contact] = generate_styled_reply(
            incoming,
            contact,
            mode,
            global_profile,
            contact_profile,
        )

    outputs["demo"] = {
        "incoming_message": incoming,
        "replies": demo_replies,
    }
    (RESULTS_DIR / "demo_replies.json").write_text(
        json.dumps(outputs, indent=2), encoding="utf-8"
    )
    return outputs


def main() -> None:
    load_env_file()
    get_client()
    ensure_data_exists()
    reset_profiles()
    print("Observation Mode -> buffering outgoing messages...")
    observe_all_messages()
    print("Profiles saved in profiles/.")

    print("\nRunning evaluator...")
    evaluate_profiles()

    print("\nRunning confidence gate and styled reply demo...")
    outputs = run_gating_and_demo()
    print(json.dumps(outputs["demo"], indent=2))
    print("\nDone. Results saved in results/.")


if __name__ == "__main__":
    main()
