"""Service layer for Personal Context Memory rules stored in Supabase."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.daily_activity_logger import log_approval_event
from app.supabase_client import SupabaseConfigError, get_supabase_client


TABLE_NAME = "personal_context_rules"
APPROVAL_TABLE_NAME = "approval_requests"
USER_STATUS_TABLE_NAME = "user_statuses"
DEFAULT_DECISION = "auto_reply"
ALLOWED_DECISIONS = {
    "auto_reply",
    "require_approval",
    "draft_only",
    "defer",
    "blocked",
}
AVAILABLE_STATUS = "available"
SUPPORTED_USER_STATUSES = {
    "available",
    "busy",
    "unavailable",
    "traveling",
    "in_meeting",
    "do_not_disturb",
}
DECISION_PRIORITY = {
    "auto_reply": 0,
    "draft_only": 1,
    "require_approval": 2,
    "defer": 3,
    "blocked": 4,
}
DECISION_ALIASES = {
    "approval_required": "require_approval",
    "needs_approval": "require_approval",
    "approval": "require_approval",
    "deferred": "defer",
    "block": "blocked",
}
MONEY_TERMS = {
    "money",
    "cash",
    "pay",
    "payment",
    "bank",
    "transfer",
    "loan",
    "borrow",
    "invoice",
    "salary",
    "refund",
    "debt",
}


class PersonalContextError(RuntimeError):
    """Raised when the personal context storage layer cannot complete a request."""


class PersonalContextRuleBase(BaseModel):
    user_id: str = Field(..., min_length=1)
    rule_name: str = Field(..., min_length=1, max_length=120)
    rule_type: str = Field(..., min_length=1, max_length=80)
    rule_value: Any
    priority: int = 0
    contact_id: str | None = None
    topic: str | None = None
    action: str | None = None
    is_active: bool = True


class PersonalContextRuleCreate(PersonalContextRuleBase):
    pass


class PersonalContextRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=120)
    rule_type: str | None = Field(default=None, min_length=1, max_length=80)
    rule_value: Any | None = None
    priority: int | None = None
    contact_id: str | None = None
    topic: str | None = None
    action: str | None = None
    is_active: bool | None = None


class PersonalContextRule(PersonalContextRuleBase):
    model_config = ConfigDict(extra="allow")

    id: int | str
    created_at: str | None = None
    updated_at: str | None = None


class RuleEvaluationResult(BaseModel):
    decision: str
    matched_rules: list[dict[str, Any]]
    winning_rule: dict[str, Any] | None = None
    reason: str


class ApprovalRequestCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    contact_id: str | None = None
    original_message: str = Field(..., min_length=1)
    generated_reply: str = Field(..., min_length=1)
    decision: str = Field(default="require_approval")
    reason: str | None = None
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | str
    user_id: str
    contact_id: str | None = None
    original_message: str
    generated_reply: str
    decision: str
    status: str
    reason: str | None = None
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class UserStatusSet(BaseModel):
    user_id: str = Field(..., min_length=1)
    status: Literal[
        "available",
        "busy",
        "unavailable",
        "traveling",
        "in_meeting",
        "do_not_disturb",
    ] = AVAILABLE_STATUS
    status_reason: str | None = Field(default=None, max_length=300)
    expires_at: str | None = None


class UserStatusUpdate(BaseModel):
    status: Literal[
        "available",
        "busy",
        "unavailable",
        "traveling",
        "in_meeting",
        "do_not_disturb",
    ] | None = None
    status_reason: str | None = Field(default=None, max_length=300)
    expires_at: str | None = None
    is_active: bool | None = None


class UserStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | str | None = None
    user_id: str
    status: str = AVAILABLE_STATUS
    status_reason: str | None = None
    expires_at: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


def create_rule(rule: PersonalContextRuleCreate) -> dict[str, Any]:
    data = rule.model_dump(exclude_none=True)
    response = _table().insert(data).execute()
    return _single_row(response, "Rule was not created.")


def list_rules(user_id: str | None = None, active_only: bool = False) -> list[dict[str, Any]]:
    query = _table().select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    if active_only:
        query = query.eq("is_active", True)
    response = query.execute()
    return _rows(response)


def list_active_rules(user_id: str | None = None) -> list[dict[str, Any]]:
    return list_rules(user_id=user_id, active_only=True)


def update_rule(rule_id: int | str, updates: PersonalContextRuleUpdate) -> dict[str, Any]:
    data = updates.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise PersonalContextError("No update fields were provided.")
    response = _table().update(data).eq("id", rule_id).execute()
    return _single_row(response, "Rule was not found.")


def delete_rule(rule_id: int | str) -> dict[str, Any]:
    response = _table().delete().eq("id", rule_id).execute()
    deleted = _rows(response)
    if not deleted:
        raise PersonalContextError("Rule was not found.")
    return {"status": "deleted", "id": rule_id}


def set_rule_active(rule_id: int | str, is_active: bool) -> dict[str, Any]:
    response = _table().update({"is_active": is_active}).eq("id", rule_id).execute()
    return _single_row(response, "Rule was not found.")


def create_approval_request(request: ApprovalRequestCreate) -> dict[str, Any]:
    data = request.model_dump(exclude_none=True)
    data["status"] = "pending"
    response = _approval_table().insert(data).execute()
    created = _single_row(response, "Approval request was not created.")
    log_approval_event(
        status="pending",
        user_id=created.get("user_id"),
        contact_id=created.get("contact_id"),
        approval_request_id=created.get("id"),
        action_category=_approval_action_category(created),
        original_message=created.get("original_message"),
        generated_reply=created.get("generated_reply"),
        reason=created.get("reason"),
        metadata={
            "decision": created.get("decision"),
            "matched_rules": created.get("matched_rules", []),
        },
    )
    return created


def list_approval_requests(
    user_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = _approval_table().select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    if status:
        query = query.eq("status", status)
    response = query.execute()
    return _rows(response)


def get_approval_request(approval_id: int | str) -> dict[str, Any]:
    response = _approval_table().select("*").eq("id", approval_id).execute()
    return _single_row(response, "Approval request was not found.")


def set_approval_status(approval_id: int | str, status: str) -> dict[str, Any]:
    if status not in {"approved", "rejected"}:
        raise PersonalContextError("Approval status must be approved or rejected.")
    existing = get_approval_request(approval_id)
    if existing.get("status") != "pending":
        raise PersonalContextError("Only pending approval requests can be updated.")
    response = _approval_table().update({"status": status}).eq("id", approval_id).execute()
    updated = _single_row(response, "Approval request was not found.")
    log_approval_event(
        status=status,
        user_id=updated.get("user_id"),
        contact_id=updated.get("contact_id"),
        approval_request_id=updated.get("id"),
        action_category=_approval_action_category(updated),
        original_message=updated.get("original_message"),
        generated_reply=updated.get("generated_reply"),
        reason=updated.get("reason"),
        metadata={
            "decision": updated.get("decision"),
            "matched_rules": updated.get("matched_rules", []),
            "previous_status": existing.get("status"),
        },
    )
    return updated


def set_user_status(status: UserStatusSet) -> dict[str, Any]:
    """Set the current temporary status for a user.

    The service keeps only one active status per user by deactivating previous
    statuses before inserting the new current state. Setting `available`
    effectively clears temporary restrictions while still returning a row that
    the frontend can display.
    """

    _validate_status(status.status)
    _deactivate_user_statuses(status.user_id)
    data = status.model_dump(exclude_none=True)
    data["is_active"] = True
    response = _status_table().insert(data).execute()
    return _single_row(response, "User status was not created.")


def get_current_user_status(user_id: str) -> dict[str, Any]:
    """Return the active non-expired user status, or available if none exists."""

    response = (
        _status_table()
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )
    for row in _rows(response):
        if _status_is_current(row):
            return row
    return _available_status(user_id)


def update_user_status(user_id: str, updates: UserStatusUpdate) -> dict[str, Any]:
    data = updates.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise PersonalContextError("No status update fields were provided.")
    if "status" in data:
        _validate_status(data["status"])

    current_status = get_current_user_status(user_id)
    status_id = current_status.get("id")
    if status_id is None:
        return set_user_status(
            UserStatusSet(
                user_id=user_id,
                status=data.get("status", AVAILABLE_STATUS),
                status_reason=data.get("status_reason"),
                expires_at=data.get("expires_at"),
            )
        )

    response = _status_table().update(data).eq("id", status_id).execute()
    return _single_row(response, "User status was not found.")


def clear_user_status(user_id: str) -> dict[str, Any]:
    _deactivate_user_statuses(user_id)
    return _available_status(user_id)


def evaluate_personal_context_rules(
    message_data: dict[str, Any],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate active personal context rules against one incoming message."""

    matched_rules: list[dict[str, Any]] = []

    for rule in rules:
        if not rule.get("is_active", True):
            continue
        if not _rule_matches_message(rule, message_data):
            continue

        decision = _decision_for_rule(rule, message_data)
        if decision == DEFAULT_DECISION:
            continue
        matched_rules.append(
            {
                "id": rule.get("id"),
                "rule_name": rule.get("rule_name"),
                "rule_type": rule.get("rule_type"),
                "decision": decision,
                "priority": _priority_for_rule(rule),
            }
        )

    matched_rules.sort(
        key=lambda matched_rule: matched_rule.get("priority", 0),
        reverse=True,
    )
    winning_rule = matched_rules[0] if matched_rules else None
    final_decision = (
        winning_rule.get("decision", DEFAULT_DECISION)
        if winning_rule
        else DEFAULT_DECISION
    )

    reason = (
        "Highest-priority matching rule selected."
        if matched_rules
        else "No personal context rule matched; auto reply is allowed."
    )
    return {
        "decision": final_decision,
        "matched_rules": matched_rules,
        "winning_rule": winning_rule,
        "reason": reason,
        "fallback_used": False,
    }


def _table():
    try:
        return get_supabase_client().table(TABLE_NAME)
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise PersonalContextError(str(exc)) from exc


def _approval_table():
    try:
        return get_supabase_client().table(APPROVAL_TABLE_NAME)
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise PersonalContextError(str(exc)) from exc


def _status_table():
    try:
        return get_supabase_client().table(USER_STATUS_TABLE_NAME)
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise PersonalContextError(str(exc)) from exc


def _deactivate_user_statuses(user_id: str) -> None:
    _status_table().update({"is_active": False}).eq("user_id", user_id).eq(
        "is_active", True
    ).execute()


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _single_row(response: Any, error_message: str) -> dict[str, Any]:
    rows = _rows(response)
    if not rows:
        raise PersonalContextError(error_message)
    return rows[0]


def _approval_action_category(row: dict[str, Any]) -> str | None:
    for rule in row.get("matched_rules", []) or []:
        rule_type = rule.get("rule_type")
        if rule_type:
            return str(rule_type)
    return row.get("decision")


def _rule_matches_message(rule: dict[str, Any], message_data: dict[str, Any]) -> bool:
    if not _matches_optional_filter(rule.get("contact_id"), _contact_candidates(message_data)):
        return False
    if not _matches_optional_filter(rule.get("topic"), _topic_candidates(message_data)):
        return False
    if not _matches_optional_filter(rule.get("action"), [message_data.get("action")]):
        return False
    return True


def _decision_for_rule(rule: dict[str, Any], message_data: dict[str, Any]) -> str:
    rule_type = _clean(rule.get("rule_type"))
    rule_value = rule.get("rule_value")

    if rule_type in {
        "require_approval",
        "approval_required",
        "needs_approval",
        "approval",
        "contact_requires_approval",
    }:
        return "require_approval"
    if rule_type in {"blocked", "block"}:
        return "blocked"
    if rule_type in {"draft_only", "work_hours_draft"}:
        return "draft_only" if _work_hours_match(rule_value, message_data) else DEFAULT_DECISION
    if rule_type in {"defer", "deferred", "busy_status", "availability"}:
        return "defer" if _busy_status_match(rule_value, message_data) else DEFAULT_DECISION
    if rule_type in {"no_auto_send", "topic_requires_approval", "money_requires_approval"}:
        return "require_approval"

    decision = _normalize_decision(rule_value)
    return decision if decision in ALLOWED_DECISIONS else "require_approval"


def _normalize_decision(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("decision")
    decision = _clean(value)
    return DECISION_ALIASES.get(decision, decision)


def _priority_for_rule(rule: dict[str, Any]) -> int:
    try:
        return int(rule.get("priority", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _matches_optional_filter(expected: Any, actual_values: list[Any]) -> bool:
    if expected in (None, "", "*", "any"):
        return True
    expected_clean = _clean(expected)
    return expected_clean in {_clean(value) for value in actual_values if value is not None}


def _contact_candidates(message_data: dict[str, Any]) -> list[Any]:
    return [
        message_data.get("contact_id"),
        message_data.get("profile_contact"),
        message_data.get("contact_name"),
    ]


def _topic_candidates(message_data: dict[str, Any]) -> list[Any]:
    message = _clean(message_data.get("message"))
    explicit_topic = message_data.get("topic")
    candidates = [explicit_topic, message_data.get("risk_level")]
    if any(term in message for term in MONEY_TERMS):
        candidates.append("money")
    return candidates


def _work_hours_match(rule_value: Any, message_data: dict[str, Any]) -> bool:
    if not rule_value:
        return True
    if isinstance(rule_value, dict):
        window = rule_value.get("hours") or rule_value.get("window")
    else:
        window = str(rule_value)
    if not window or "-" not in window:
        return True

    start_raw, end_raw = [part.strip() for part in window.split("-", 1)]
    current_time = message_data.get("current_time")
    now_time = _parse_time(current_time) if current_time else datetime.now().time()
    start_time = _parse_time(start_raw)
    end_time = _parse_time(end_raw)
    if not start_time or not end_time:
        return True
    if start_time <= end_time:
        return start_time <= now_time <= end_time
    return now_time >= start_time or now_time <= end_time


def _busy_status_match(rule_value: Any, message_data: dict[str, Any]) -> bool:
    status = _clean(message_data.get("user_status") or message_data.get("availability"))
    if status in {"busy", "do_not_disturb", "unavailable", "in_meeting"}:
        return True
    if isinstance(rule_value, dict):
        expected = rule_value.get("status")
    else:
        expected = rule_value
    return bool(expected) and _clean(expected) == status


def _parse_time(value: Any) -> time | None:
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _validate_status(status: str) -> None:
    if status not in SUPPORTED_USER_STATUSES:
        raise PersonalContextError(
            "Unsupported status. Use one of: "
            + ", ".join(sorted(SUPPORTED_USER_STATUSES))
        )


def _status_is_current(row: dict[str, Any]) -> bool:
    expires_at = row.get("expires_at")
    if not expires_at:
        return True
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed > datetime.now(timezone.utc)


def _available_status(user_id: str) -> dict[str, Any]:
    return {
        "id": None,
        "user_id": user_id,
        "status": AVAILABLE_STATUS,
        "status_reason": None,
        "expires_at": None,
        "is_active": True,
        "created_at": None,
        "updated_at": None,
    }
