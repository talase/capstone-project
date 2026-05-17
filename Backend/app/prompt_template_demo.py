"""Small demo for prompt template selection and prompt generation."""

from __future__ import annotations

from app.buffer import choose_style_mode
from app.prompt_templates import build_prompt


def demo_profile(overall_confidence: int, contact_style: bool = False) -> dict:
    """Create a small profile with a chosen confidence score for demos."""

    if contact_style:
        traits = {
            "formality": {"score": 0.18, "confidence": overall_confidence},
            "politeness": {"score": 0.62, "confidence": overall_confidence},
            "verbosity": {"score": 0.28, "confidence": overall_confidence},
            "optimism": {"score": 0.88, "confidence": overall_confidence},
        }
        patterns = [
            "uses casual wording with friendly energy",
            "often includes quick reassurance",
        ]
    else:
        traits = {
            "formality": {"score": 0.45, "confidence": overall_confidence},
            "politeness": {"score": 0.78, "confidence": overall_confidence},
            "verbosity": {"score": 0.38, "confidence": overall_confidence},
            "optimism": {"score": 0.66, "confidence": overall_confidence},
        }
        patterns = [
            "keeps replies brief and clear",
            "uses warm acknowledgements before answering",
        ]

    return {
        "traits": traits,
        "patterns": patterns,
        "overall_confidence": overall_confidence,
    }


def demo_prompt_generation() -> None:
    """Print confidence-gate outcomes and final prompts for all style modes."""

    examples = [
        (
            "Case 1: global high, contact low",
            demo_profile(85),
            demo_profile(20, contact_style=True),
            "global",
        ),
        (
            "Case 2: global high, contact high",
            demo_profile(85),
            demo_profile(82, contact_style=True),
            "global_contact",
        ),
        (
            "Case 3: global low, contact high",
            demo_profile(25),
            demo_profile(82, contact_style=True),
            "contact",
        ),
        (
            "Case 4: both low or missing",
            {},
            {},
            "neutral",
        ),
    ]

    for label, global_profile, contact_profile, expected_mode in examples:
        selected_mode = choose_style_mode(global_profile, contact_profile)
        print(f"\n{'=' * 20} {label} {'=' * 20}")
        print(f"global confidence: {global_profile.get('overall_confidence', 0)}")
        print(f"contact confidence: {contact_profile.get('overall_confidence', 0)}")
        print(f"selected style_mode: {selected_mode}")
        print(f"expected style_mode: {expected_mode}")
        print("\nFinal prompt:")
        print(
            build_prompt(
                message="Can you send me the file today?",
                contact_name="friend",
                style_mode=selected_mode,
                global_profile=global_profile,
                contact_profile=contact_profile,
                risk_level="low",
                action_type="send_file",
            )
        )


if __name__ == "__main__":
    demo_prompt_generation()
