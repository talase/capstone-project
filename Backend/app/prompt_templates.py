"""Prompt templates for style-adaptive WhatsApp reply generation."""

from __future__ import annotations

from typing import Any

from app.profile_store import TRAITS, sanitize_profile


NEUTRAL_TEMPLATE = """
You are generating one WhatsApp-style reply.

Use this mode because style confidence is low or unavailable:
- Reply naturally, politely, and safely.
- Do not strongly imitate the user's style.
- Do not copy any training messages or invent facts.
- Keep the reply appropriate for the risk level and action type.
- Return only the reply text, with no labels or markdown.

Contact: {contact_name}
Incoming message: {message}
Style mode: neutral
Confidence score: {confidence_score}
Risk level: {risk_level}
Action type: {action_type}

Neutral style guidance:
- Formality: {formality}
- Politeness: {politeness}
- Verbosity: {verbosity}
- Optimism: {optimism}

Global style traits:
{global_style_traits}

Contact-specific style traits:
{contact_style_traits}

Recurring patterns:
{recurring_patterns}
""".strip()


GLOBAL_STYLE_TEMPLATE = """
You are generating one WhatsApp-style reply using the user's global communication style.

Rules:
- Use only the global style profile as the style signal.
- Apply high-level traits, not exact wording from previous messages.
- Keep the reply natural for WhatsApp and suitable for the incoming message.
- Do not copy training messages or over-imitate.
- Be extra cautious if the risk level or action type suggests a sensitive action.
- Return only the reply text, with no labels or markdown.

Contact: {contact_name}
Incoming message: {message}
Style mode: global_style
Confidence score: {confidence_score}
Risk level: {risk_level}
Action type: {action_type}

Global style traits:
{global_style_traits}

Trait guidance:
- Formality: {formality}
- Politeness: {politeness}
- Verbosity: {verbosity}
- Optimism: {optimism}

Recurring global patterns:
{recurring_patterns}

Contact-specific style traits:
{contact_style_traits}
""".strip()


CONTACT_STYLE_TEMPLATE = """
You are generating one WhatsApp-style reply using the style learned for this contact.

Rules:
- Use only the contact-specific style profile as the style signal.
- Adapt to how the user usually talks with this contact.
- Apply high-level traits, not exact wording from previous messages.
- Keep the reply natural for WhatsApp and suitable for the incoming message.
- Be extra cautious if the risk level or action type suggests a sensitive action.
- Return only the reply text, with no labels or markdown.

Contact: {contact_name}
Incoming message: {message}
Style mode: contact_style
Confidence score: {confidence_score}
Risk level: {risk_level}
Action type: {action_type}

Contact-specific style traits:
{contact_style_traits}

Trait guidance:
- Formality: {formality}
- Politeness: {politeness}
- Verbosity: {verbosity}
- Optimism: {optimism}

Recurring contact patterns:
{recurring_patterns}

Global style traits:
{global_style_traits}
""".strip()


GLOBAL_CONTACT_STYLE_TEMPLATE = """
You are generating one WhatsApp-style reply using both global and contact-specific style.

Rules:
- Use global style as the general baseline.
- Give contact-specific style higher priority when it differs from global style.
- Apply high-level traits, not exact wording from previous messages.
- Keep the reply natural for WhatsApp and suitable for the incoming message.
- Do not copy training messages or over-imitate.
- Be extra cautious if the risk level or action type suggests a sensitive action.
- Return only the reply text, with no labels or markdown.

Contact: {contact_name}
Incoming message: {message}
Style mode: global_contact_style
Confidence score: {confidence_score}
Risk level: {risk_level}
Action type: {action_type}

Global style traits:
{global_style_traits}

Contact-specific style traits:
{contact_style_traits}

Priority trait guidance:
- Formality: {formality}
- Politeness: {politeness}
- Verbosity: {verbosity}
- Optimism: {optimism}

Recurring patterns:
{recurring_patterns}
""".strip()


STYLE_TEMPLATES = {
    "neutral": NEUTRAL_TEMPLATE,
    "global_style": GLOBAL_STYLE_TEMPLATE,
    "contact_style": CONTACT_STYLE_TEMPLATE,
    "global_contact_style": GLOBAL_CONTACT_STYLE_TEMPLATE,
}

STYLE_MODE_ALIASES = {
    "neutral": "neutral",
    "global": "global_style",
    "contact": "contact_style",
    "global+contact": "global_contact_style",
    "global_contact": "global_contact_style",
    "global_style": "global_style",
    "contact_style": "contact_style",
    "global_contact_style": "global_contact_style",
}


def choose_prompt_template(style_mode: str | None) -> str:
    """Return the prompt template for a selected style mode."""

    normalized_mode = STYLE_MODE_ALIASES.get((style_mode or "").strip().lower(), "neutral")
    return STYLE_TEMPLATES[normalized_mode]


def build_prompt(
    message: str,
    contact_name: str,
    style_mode: str,
    global_profile: dict | None = None,
    contact_profile: dict | None = None,
    risk_level: str | None = None,
    action_type: str | None = None,
) -> str:
    """Build the final LLM prompt from profiles and the selected style mode."""

    normalized_mode = STYLE_MODE_ALIASES.get((style_mode or "").strip().lower(), "neutral")
    safe_global = _safe_profile(global_profile)
    safe_contact = _safe_profile(contact_profile)
    active_profile = _active_profile(normalized_mode, safe_global, safe_contact)

    values = {
        "message": _clean_text(message, "No incoming message provided."),
        "contact_name": _clean_text(contact_name, "Unknown contact"),
        "confidence_score": _confidence_for_mode(normalized_mode, safe_global, safe_contact),
        "risk_level": _clean_text(risk_level, "not provided"),
        "action_type": _clean_text(action_type, "not provided"),
        "global_style_traits": _format_style_traits(safe_global),
        "contact_style_traits": _format_style_traits(safe_contact),
        "recurring_patterns": _format_recurring_patterns(
            normalized_mode,
            safe_global.get("patterns", []),
            safe_contact.get("patterns", []),
        ),
    }

    for trait in TRAITS:
        values[trait] = _format_trait(active_profile, trait)

    return choose_prompt_template(normalized_mode).format(**values)


def _safe_profile(profile: dict | None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        profile = {}
    return sanitize_profile(profile)


def _active_profile(
    normalized_mode: str,
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
) -> dict[str, Any]:
    if normalized_mode == "contact_style":
        return contact_profile
    if normalized_mode == "global_contact_style":
        return _merge_for_prompt(global_profile, contact_profile)
    if normalized_mode == "global_style":
        return global_profile
    return sanitize_profile({})


def _merge_for_prompt(
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
) -> dict[str, Any]:
    """Combine profiles for display, favoring contact traits with confidence."""

    merged = sanitize_profile(global_profile)
    for trait in TRAITS:
        contact_trait = contact_profile["traits"][trait]
        global_trait = global_profile["traits"][trait]
        merged["traits"][trait] = (
            contact_trait if contact_trait.get("confidence", 0) > 0 else global_trait
        )
    merged["patterns"] = contact_profile.get("patterns", []) or global_profile.get("patterns", [])
    merged["overall_confidence"] = min(
        100,
        round(
            (
                global_profile.get("overall_confidence", 0)
                + contact_profile.get("overall_confidence", 0)
            )
            / 2
        ),
    )
    return merged


def _confidence_for_mode(
    normalized_mode: str,
    global_profile: dict[str, Any],
    contact_profile: dict[str, Any],
) -> int:
    global_confidence = int(global_profile.get("overall_confidence", 0))
    contact_confidence = int(contact_profile.get("overall_confidence", 0))
    if normalized_mode == "global_style":
        return global_confidence
    if normalized_mode == "contact_style":
        return contact_confidence
    if normalized_mode == "global_contact_style":
        return round((global_confidence + contact_confidence) / 2)
    return max(global_confidence, contact_confidence, 0)


def _format_style_traits(profile: dict[str, Any]) -> str:
    lines = []
    for trait in TRAITS:
        lines.append(f"- {trait}: {_format_trait(profile, trait)}")
    lines.append(f"- overall_confidence: {profile.get('overall_confidence', 0)}/100")
    return "\n".join(lines)


def _format_trait(profile: dict[str, Any], trait: str) -> str:
    trait_data = profile.get("traits", {}).get(trait, {})
    score = _as_float(trait_data.get("score"), 0.5)
    confidence = int(_as_float(trait_data.get("confidence"), 0))
    return f"{_trait_label(trait, score)} (score={score:.2f}, confidence={confidence}/100)"


def _trait_label(trait: str, score: float) -> str:
    low_label, high_label = {
        "formality": ("casual", "formal"),
        "politeness": ("direct", "polite"),
        "verbosity": ("concise", "detailed"),
        "optimism": ("reserved", "warm/optimistic"),
    }.get(trait, ("low", "high"))

    if score < 0.35:
        return low_label
    if score > 0.65:
        return high_label
    return "balanced"


def _format_recurring_patterns(
    normalized_mode: str,
    global_patterns: list[str],
    contact_patterns: list[str],
) -> str:
    if normalized_mode == "global_style":
        return _bullet_list(global_patterns)
    if normalized_mode == "contact_style":
        return _bullet_list(contact_patterns)
    if normalized_mode == "global_contact_style":
        return "\n".join(
            [
                "Global:",
                _bullet_list(global_patterns),
                "Contact-specific:",
                _bullet_list(contact_patterns),
            ]
        )
    return "- No strong recurring patterns. Use a natural neutral reply."


def _bullet_list(items: list[str]) -> str:
    clean_items = [_clean_text(item, "") for item in items if _clean_text(item, "")]
    if not clean_items:
        return "- No reliable recurring patterns available."
    return "\n".join(f"- {item}" for item in clean_items)


def _clean_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
