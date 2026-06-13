"""Service layer for Personal Context Memory rules stored in Supabase."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.supabase_client import SupabaseConfigError, get_supabase_client


LOGGER = logging.getLogger(__name__)

TABLE_NAME = "personal_context_rules"
USER_STATUS_TABLE_NAME = "user_statuses"
DEFAULT_DECISION = "auto_reply"
ALLOWED_DECISIONS = {"auto_reply", "defer"}
AVAILABLE_STATUS = "available"


class PersonalContextError(RuntimeError):
    """Raised when the personal context storage layer cannot complete a request."""


class PersonalContextRuleBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1)
    rule_name: str = Field(..., min_length=1, max_length=120)
    rule_type: str = Field(..., min_length=1, max_length=80)
    rule_value: Any
    priority: int = 0
    contact_id: str | None = None
    topic: str | None = None
    action: str | None = None
    is_active: bool = True

    @field_validator("rule_value")
    @classmethod
    def validate_rule_value(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("rule_value must not be null")
        return value


class PersonalContextRuleCreate(PersonalContextRuleBase):
    pass


class PersonalContextRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_name: str | None = Field(default=None, min_length=1, max_length=120)
    rule_type: str | None = Field(default=None, min_length=1, max_length=80)
    rule_value: Any | None = None
    priority: int | None = None
    contact_id: str | None = None
    topic: str | None = None
    action: str | None = None
    is_active: bool | None = None

    @field_validator("rule_value")
    @classmethod
    def validate_rule_value(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("rule_value must not be null")
        return value


class PersonalContextRule(PersonalContextRuleBase):
    model_config = ConfigDict(extra="allow")

    id: int | str
    created_at: str | None = None
    updated_at: str | None = None


class RuleEvaluationResult(BaseModel):
    decision: str
    context: list[str]
    matched_rules: list[dict[str, Any]]
    winning_rule: dict[str, Any] | None = None
    reason: str


class UserStatusSet(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1)
    status: str = Field(default=AVAILABLE_STATUS, min_length=1, max_length=80)
    status_reason: str | None = Field(default=None, max_length=300)
    expires_at: str | None = None


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str | None = Field(default=None, min_length=1, max_length=80)
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

    LOGGER.debug(
        "PCM status lookup: table=%s user_id=%r filters=%s order=%s",
        USER_STATUS_TABLE_NAME,
        user_id,
        {"user_id": user_id, "is_active": True},
        {"column": "created_at", "desc": True},
    )
    response = (
        _status_table()
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )
    rows = _rows(response)
    LOGGER.debug(
        "PCM status lookup result: user_id=%r row_count=%d",
        user_id,
        len(rows),
    )
    for row in rows:
        if _status_is_current(row):
            LOGGER.debug(
                "PCM status lookup selected row: user_id=%r status=%r row_id=%r",
                user_id,
                row.get("status"),
                row.get("id"),
            )
            return row
        LOGGER.debug(
            "PCM status lookup skipped expired row: user_id=%r row_id=%r expires_at=%r",
            user_id,
            row.get("id"),
            row.get("expires_at"),
        )
    LOGGER.debug(
        "PCM status lookup fallback: user_id=%r status=%s reason=%s",
        user_id,
        AVAILABLE_STATUS,
        "no active non-expired rows returned",
    )
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
    context = _status_context(message_data)

    for rule in rules:
        if not rule.get("is_active", True):
            continue
        if not _rule_matches_message(rule, message_data):
            continue

        if not _status_condition_matches(rule.get("rule_value"), message_data):
            continue
        decision = _decision_for_rule(rule)
        rule_context = _context_for_rule(rule)
        if rule_context:
            context.append(rule_context)
        matched_rules.append(
            {
                "id": rule.get("id"),
                "rule_name": rule.get("rule_name"),
                "rule_type": rule.get("rule_type"),
                "decision": decision,
                "context": rule_context,
                "priority": _priority_for_rule(rule),
            }
        )

    matched_rules.sort(
        key=lambda matched_rule: matched_rule.get("priority", 0),
        reverse=True,
    )
    deferred_rules = [
        matched_rule
        for matched_rule in matched_rules
        if matched_rule["decision"] == "defer"
    ]
    winning_rule = deferred_rules[0] if deferred_rules else None
    final_decision = (
        "defer" if winning_rule else DEFAULT_DECISION
    )

    if final_decision == "defer":
        reason = "A matching personal context rule requested reevaluation later."
    elif context:
        reason = "Reply generation may continue using the current user context."
    else:
        reason = "No relevant personal context was found; reply generation may continue."
    return {
        "decision": final_decision,
        "context": _deduplicate(context),
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


def _rule_matches_message(rule: dict[str, Any], message_data: dict[str, Any]) -> bool:
    if not _matches_optional_filter(rule.get("contact_id"), _contact_candidates(message_data)):
        return False
    if not _matches_optional_filter(rule.get("topic"), _topic_candidates(message_data)):
        return False
    if not _matches_optional_filter(rule.get("action"), [message_data.get("action")]):
        return False
    return True


def _decision_for_rule(rule: dict[str, Any]) -> str:
    rule_type = _clean(rule.get("rule_type"))
    rule_value = rule.get("rule_value")

    if isinstance(rule_value, dict):
        decision = _clean(rule_value.get("decision"))
    else:
        decision = _clean(rule_value)
    if not decision and rule_type == "defer":
        decision = "defer"
    return decision if decision in ALLOWED_DECISIONS else DEFAULT_DECISION


def _context_for_rule(rule: dict[str, Any]) -> str | None:
    rule_value = rule.get("rule_value")
    if isinstance(rule_value, dict):
        value = rule_value.get("context") or rule_value.get("description")
    elif _clean(rule_value) not in ALLOWED_DECISIONS:
        value = rule_value
    else:
        value = None
    text = str(value or "").strip()
    return text or None


def _status_condition_matches(rule_value: Any, message_data: dict[str, Any]) -> bool:
    if not isinstance(rule_value, dict) or not rule_value.get("status"):
        return True
    current_status = _clean(
        message_data.get("user_status") or message_data.get("availability")
    )
    expected_status = rule_value.get("status")
    if isinstance(expected_status, list):
        return current_status in {_clean(status) for status in expected_status}
    return current_status == _clean(expected_status)


def _status_context(message_data: dict[str, Any]) -> list[str]:
    status = str(
        message_data.get("user_status")
        or message_data.get("availability")
        or AVAILABLE_STATUS
    ).strip()
    reason = str(message_data.get("status_reason") or "").strip()
    if not status or _clean(status) == AVAILABLE_STATUS:
        return []
    context = [f"The user's current status is {status.replace('_', ' ')}."]
    if reason:
        context.append(f"Status detail: {reason}")
    return context


def _deduplicate(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


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
    return [message_data.get("topic")]


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _validate_status(status: str) -> None:
    if not str(status or "").strip():
        raise PersonalContextError("Status must not be empty.")


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
