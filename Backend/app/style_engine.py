"""End-to-end runner for the style adaptation capstone project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.buffer import StyleBuffer, choose_style_mode
from app.config import MODEL, get_client, load_env_file
from app.evaluator import evaluate_profiles
from app.generate_data import generate_messages_per_contact
from app.profile_store import load_profile
from app.style_extractor import load_messages

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
PROFILES_DIR = PROJECT_ROOT / "profiles"
CONTACTS_TO_DEMO = ("boss", "friend", "mom")


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


def profile_summary(profile: dict[str, Any]) -> str:
    traits = profile.get("traits", {})
    parts = []
    for trait_name, trait_data in traits.items():
        parts.append(
            f"{trait_name}: score={trait_data.get('score', 0.5)}, "
            f"confidence={trait_data.get('confidence', 0)}"
        )
    patterns = "; ".join(profile.get("patterns", []))
    return "\n".join(parts + [f"patterns: {patterns}"])


def generate_styled_reply(
    incoming_message: str,
    contact_name: str,
    mode: str,
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
) -> str:
    """Generate one reply using the selected style mode via OpenRouter."""

    if mode == "global+contact":
        profile_text = (
            "Use global tendencies as a base and contact tendencies as the stronger signal.\n"
            f"Global profile:\n{profile_summary(global_profile)}\n\n"
            f"Contact profile:\n{profile_summary(contact_profile)}"
        )
    elif mode == "global":
        profile_text = f"Use only this global style profile:\n{profile_summary(global_profile)}"
    else:
        profile_text = "Use a neutral, polite, concise messaging style."

    prompt = f"""
You write a single safe WhatsApp-style reply.

Rules:
- Do not copy or imitate any original training messages.
- Use only high-level style traits.
- Keep the reply natural and brief.
- Return only the reply text, no labels or markdown.

Contact: {contact_name}
Incoming message: {incoming_message}
Selected style mode: {mode}

{profile_text}
""".strip()

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        print("FULL ERROR:", repr(e))
        raise


def run_gating_and_demo() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    global_profile = load_profile("global")
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


#if __name__ == "__main__":
 #   main()
