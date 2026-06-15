"""Service layer for status-based Personal Context Memory."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.supabase_client import SupabaseConfigError, get_supabase_client


LOGGER = logging.getLogger(__name__)

USER_STATUS_TABLE_NAME = "user_statuses"
AVAILABLE_STATUS = "available"


class PersonalContextError(RuntimeError):
    """Raised when the personal context storage layer cannot complete a request."""


class UserStatusSet(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1)
    status: str = Field(default=AVAILABLE_STATUS, min_length=1, max_length=2000)


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str | None = Field(default=None, min_length=1, max_length=2000)


class UserStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str | None = None
    user_id: str
    status: str = AVAILABLE_STATUS
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class PersonalContext(BaseModel):
    current_status: dict[str, str]
    context: list[str] = Field(default_factory=list)


def set_user_status(status: UserStatusSet) -> dict[str, Any]:
    """Create or replace the user's current active status."""

    _validate_status(status.status)
    data = status.model_dump()
    data["is_active"] = True
    current_status = get_current_user_status(status.user_id)
    status_id = current_status.get("id")
    if status_id is not None:
        response = _status_table().update(data).eq("id", status_id).execute()
        return _single_row(response, "User status was not found.")

    response = _status_table().insert(data).execute()
    return _single_row(response, "User status was not created.")


def get_current_user_status(user_id: str) -> dict[str, Any]:
    """Return the latest active user status, or available if none exists."""

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
    if rows:
        row = rows[0]
        LOGGER.debug(
            "PCM status lookup selected row: user_id=%r status=%r row_id=%r",
            user_id,
            row.get("status"),
            row.get("id"),
        )
        return row
    LOGGER.debug(
        "PCM status lookup fallback: user_id=%r status=%s reason=%s",
        user_id,
        AVAILABLE_STATUS,
        "no active rows returned",
    )
    return _available_status(user_id)


def update_user_status(user_id: str, updates: UserStatusUpdate) -> dict[str, Any]:
    data = updates.model_dump(exclude_unset=True)
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
            )
        )

    response = _status_table().update(data).eq("id", status_id).execute()
    return _single_row(response, "User status was not found.")


def clear_user_status(user_id: str) -> dict[str, Any]:
    return set_user_status(UserStatusSet(user_id=user_id))


def build_personal_context(status: str | None) -> dict[str, Any]:
    """Build prompt context from the user's current status."""

    status_text = str(status or AVAILABLE_STATUS).strip() or AVAILABLE_STATUS
    return {
        "current_status": {"status": status_text},
        "context": _status_context(status_text),
    }


def _status_table():
    try:
        return get_supabase_client().table(USER_STATUS_TABLE_NAME)
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise PersonalContextError(str(exc)) from exc


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _single_row(response: Any, error_message: str) -> dict[str, Any]:
    rows = _rows(response)
    if not rows:
        raise PersonalContextError(error_message)
    return rows[0]


def _status_context(status: str) -> list[str]:
    if not status or _clean(status) == AVAILABLE_STATUS:
        return []
    return [f"The user's current status is: {status}"]


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _validate_status(status: str) -> None:
    if not str(status or "").strip():
        raise PersonalContextError("Status must not be empty.")


def _available_status(user_id: str) -> dict[str, Any]:
    return {
        "id": None,
        "user_id": user_id,
        "status": AVAILABLE_STATUS,
        "is_active": True,
        "created_at": None,
        "updated_at": None,
    }
