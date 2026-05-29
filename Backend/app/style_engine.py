"""End-to-end runner for the style adaptation capstone project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import daily_activity_logger as activity_logger
from app.buffer import StyleBuffer, choose_style_mode
from app.config import MODEL, get_client, load_env_file
from app.evaluator import evaluate_profiles
from app.generate_data import generate_messages_per_contact
from app.personal_context_service import (
    ApprovalRequestCreate,
    create_approval_request,
    evaluate_personal_context_rules,
    get_current_user_status,
    list_active_rules,
)
from app.profile_store import load_global_profile, load_profile, resolve_profile_contact
from app.prompt_templates import build_prompt
from app.style_extractor import load_messages


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
    user_id: str = "default_user",
    risk_level: str | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Run the final style-aware response generation pipeline."""

    clean_message = (incoming_message or "").strip()
    clean_contact = (contact_id or "").strip()
    profile_contact = resolve_profile_contact(clean_contact)
    logging_warnings: list[dict[str, str]] = []

    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_message_event(
            direction="received",
            message=clean_message,
            user_id=user_id,
            contact_id=clean_contact,
            metadata={
                "risk_level": risk_level,
                "action_type": action_type,
            },
        ),
    )

    # Missing or malformed profile JSON falls back to neutral profiles.
    global_profile = load_global_profile(user_id=user_id)
    contact_profile = load_profile(clean_contact, user_id=user_id)

    # Confidence gating chooses which style signal is reliable enough to use.
    mode = choose_style_mode(global_profile, contact_profile)
    global_confidence = int(global_profile.get("overall_confidence", 0) or 0)
    contact_confidence = int(contact_profile.get("overall_confidence", 0) or 0)
    current_status = _get_current_status(user_id)
    personal_context = _evaluate_personal_context(
        {
            "message": clean_message,
            "contact_id": clean_contact,
            "profile_contact": profile_contact,
            "risk_level": risk_level,
            "topic": risk_level,
            "action": action_type,
            "user_id": user_id,
            # Temporary status is a governance signal. Rules can match it via
            # rule_type=busy_status/availability and rule_value.status.
            "user_status": current_status["status"],
            "availability": current_status["status"],
        }
    )

    generation = generate_styled_reply_result(
        incoming_message=clean_message,
        contact_name=profile_contact,
        mode=mode,
        global_profile=global_profile,
        contact_profile=contact_profile,
        risk_level=risk_level,
        action_type=action_type,
    )
    reply = generation["reply"]
    pcm_decision = personal_context["decision"]
    final_action = _final_action_for_decision(pcm_decision)
    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_message_event(
            direction="sent",
            message=reply,
            user_id=user_id,
            contact_id=clean_contact,
            metadata={
                "generated_only": final_action != "send",
                "generation_status": generation["generation_status"],
                "llm_error": generation["llm_error"],
                "final_action": final_action,
            },
        ),
    )
    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_personal_context_decision(
            decision=pcm_decision,
            user_id=user_id,
            contact_id=clean_contact,
            reason=personal_context["reason"],
            matched_rules=personal_context["matched_rules"],
            original_message=clean_message,
            final_action=final_action,
            metadata={
                "risk_level": risk_level,
                "action_type": action_type,
                "current_status": current_status.get("status"),
            },
        ),
    )
    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_agent_activity(
            status=_activity_status_for_final_action(final_action),
            user_id=user_id,
            contact_id=clean_contact,
            action_category=action_type,
            action_type=action_type,
            mode="automatic" if final_action == "send" else None,
            requires_approval=final_action == "approval_required",
            description=personal_context["reason"],
            metadata={
                "pcm_decision": pcm_decision,
                "risk_level": risk_level,
                "style_mode": mode,
            },
        ),
    )
    if _is_high_risk(risk_level):
        _collect_logging_warning(
            logging_warnings,
            activity_logger.log_high_risk_alert(
                risk_level=risk_level or "high",
                user_id=user_id,
                contact_id=clean_contact,
                action_category=action_type,
                message=clean_message,
                reason=personal_context["reason"],
                metadata={
                    "final_action": final_action,
                    "matched_rules": personal_context["matched_rules"],
                },
            ),
        )

    approval_request = None
    if pcm_decision == "require_approval":
        approval_request = _create_pending_approval_request(
            user_id=user_id,
            contact_id=clean_contact,
            original_message=clean_message,
            generated_reply=reply,
            personal_context=personal_context,
        )

    return {
        "reply": reply,
        "generated_reply": reply,
        "style_mode": mode,
        "contact_id": clean_contact,
        "profile_contact": profile_contact,
        "global_confidence": global_confidence,
        "contact_confidence": contact_confidence,
        "generation_status": generation["generation_status"],
        "llm_error": generation["llm_error"],
        "personal_context": personal_context,
        "current_status": current_status,
        "pcm_decision": pcm_decision,
        "matched_rules": personal_context["matched_rules"],
        "pcm_reason": personal_context["reason"],
        "final_action": final_action,
        "approval_request": approval_request,
        "daily_report_logging_warnings": logging_warnings,
    }


def _evaluate_personal_context(message_data: dict[str, Any]) -> dict[str, Any]:
    """Load and evaluate active personal context rules without blocking replies."""

    try:
        rules = list_active_rules(user_id=message_data.get("user_id"))
        result = evaluate_personal_context_rules(message_data, rules)
        return _enforce_high_risk_approval(message_data, result)
    except Exception as exc:
        return _enforce_high_risk_approval(message_data, {
            "decision": "auto_reply",
            "matched_rules": [],
            "winning_rule": None,
            "reason": f"Personal context rules unavailable: {exc}",
            "fallback_used": True,
        })


def _get_current_status(user_id: str) -> dict[str, Any]:
    """Return current user status, falling back to available if storage is unavailable."""

    try:
        return get_current_user_status(user_id)
    except Exception as exc:
        return {
            "id": None,
            "user_id": user_id,
            "status": "available",
            "status_reason": f"Status unavailable: {exc}",
            "expires_at": None,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
        }


def _enforce_high_risk_approval(
    message_data: dict[str, Any],
    personal_context: dict[str, Any],
) -> dict[str, Any]:
    """Prevent high-risk messages from being sent automatically."""

    if not _is_high_risk(message_data.get("risk_level")):
        return personal_context

    matched_rules = list(personal_context.get("matched_rules", []))
    matched_rules.append(
        {
            "id": "system_high_risk_gate",
            "rule_name": "High risk messages require approval",
            "rule_type": "system_governance",
            "decision": "require_approval",
            "priority": 999,
        }
    )
    return {
        "decision": "require_approval",
        "matched_rules": matched_rules,
        "winning_rule": matched_rules[-1],
        "reason": "High-risk message requires approval before sending.",
        "fallback_used": personal_context.get("fallback_used", False),
    }


def _final_action_for_decision(decision: str) -> str:
    return {
        "auto_reply": "send",
        "draft_only": "draft",
        "require_approval": "approval_required",
        "defer": "deferred",
        "blocked": "blocked",
    }.get(decision, "approval_required")


def _activity_status_for_final_action(final_action: str) -> str:
    return {
        "send": "automatic",
        "draft": "draft",
        "approval_required": "pending",
        "deferred": "deferred",
        "blocked": "blocked",
    }.get(final_action, "pending")


def _is_high_risk(risk_level: str | None) -> bool:
    return str(risk_level or "").strip().lower() in {"high", "high_risk", "critical"}


def _collect_logging_warning(
    warnings: list[dict[str, str]],
    result: activity_logger.LogResult,
) -> None:
    warning = result.warning()
    if warning:
        warnings.append(warning)


def _create_pending_approval_request(
    user_id: str,
    contact_id: str,
    original_message: str,
    generated_reply: str,
    personal_context: dict[str, Any],
) -> dict[str, Any] | None:
    """Persist an approval request, but never block the response if storage fails."""

    try:
        return create_approval_request(
            ApprovalRequestCreate(
                user_id=user_id,
                contact_id=contact_id,
                original_message=original_message,
                generated_reply=generated_reply,
                decision=personal_context["decision"],
                reason=personal_context["reason"],
                matched_rules=personal_context["matched_rules"],
            )
        )
    except Exception as exc:
        return {
            "status": "not_created",
            "error": str(exc),
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
