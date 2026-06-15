"""Best-effort activity logging for daily reports."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.supabase_client import get_supabase_client

DEFAULT_USER_ID = "default_user"
LOGGER = logging.getLogger(__name__)


@dataclass
class LogResult:
    ok: bool
    table: str
    row: dict[str, Any] | None = None
    error: str | None = None

    def warning(self) -> dict[str, str] | None:
        if self.ok:
            return None
        return {"table": self.table, "error": self.error or "Unknown logging error."}


def log_message_event(
    *,
    direction: str,
    message: str,
    user_id: str | None = None,
    contact_id: str | None = None,
    channel: str = "whatsapp",
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "message_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "direction": direction,
            "message": message,
            "channel": channel,
            "metadata": metadata or {},
        },
    )


def log_agent_activity(
    *,
    status: str,
    user_id: str | None = None,
    contact_id: str | None = None,
    action_category: str | None = None,
    action_type: str | None = None,
    mode: str | None = None,
    requires_approval: bool | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "agent_activity_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "action_category": action_category,
            "action_type": action_type,
            "status": status,
            "mode": mode,
            "requires_approval": requires_approval,
            "description": description,
            "metadata": metadata or {},
        },
    )


def log_approval_event(
    *,
    status: str,
    user_id: str | None = None,
    contact_id: str | None = None,
    approval_request_id: int | str | None = None,
    action_category: str | None = None,
    original_message: str | None = None,
    generated_reply: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    log_metadata = metadata or {}
    if approval_request_id is not None:
        log_metadata = {**log_metadata, "approval_request_id": str(approval_request_id)}
    return _safe_insert(
        "approval_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "approval_request_id": _int_or_none(approval_request_id),
            "action_category": action_category,
            "status": status,
            "original_message": original_message,
            "generated_reply": generated_reply,
            "reason": reason,
            "metadata": log_metadata,
        },
    )


def log_high_risk_alert(
    *,
    risk_level: str = "high",
    user_id: str | None = None,
    contact_id: str | None = None,
    action_category: str | None = None,
    status: str = "open",
    message: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "high_risk_alerts",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "risk_level": risk_level,
            "action_category": action_category,
            "status": status,
            "message": message,
            "reason": reason,
            "metadata": metadata or {},
        },
    )


def log_reminder_created(
    *,
    reminder_text: str,
    user_id: str | None = None,
    contact_id: str | None = None,
    remind_at: str | None = None,
    status: str = "created",
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "reminder_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "reminder_text": reminder_text,
            "remind_at": remind_at,
            "status": status,
            "metadata": metadata or {},
        },
    )


def log_scheduled_message_created(
    *,
    message: str,
    user_id: str | None = None,
    contact_id: str | None = None,
    scheduled_for: str | None = None,
    status: str = "scheduled",
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "scheduled_message_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "message": message,
            "scheduled_for": scheduled_for,
            "status": status,
            "metadata": metadata or {},
        },
    )


def log_rag_access(
    *,
    user_id: str | None = None,
    contact_id: str | None = None,
    file_id: str | None = None,
    file_name: str | None = None,
    file_path: str | None = None,
    query: str | None = None,
    access_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LogResult:
    return _safe_insert(
        "rag_access_logs",
        {
            "user_id": user_id or DEFAULT_USER_ID,
            "contact_id": _clean_contact_id(contact_id),
            "file_id": file_id,
            "file_name": file_name,
            "file_path": file_path,
            "query": query,
            "access_reason": access_reason,
            "metadata": metadata or {},
        },
    )


def _safe_insert(table_name: str, payload: dict[str, Any]) -> LogResult:
    data = {key: value for key, value in payload.items() if value is not None}
    try:
        response = get_supabase_client().table(table_name).insert(data).execute()
        response_error = getattr(response, "error", None)
        if response_error:
            raise RuntimeError(str(response_error))
        rows = getattr(response, "data", None)
        row = rows[0] if isinstance(rows, list) and rows else data
        return LogResult(ok=True, table=table_name, row=row)
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        LOGGER.warning(
            "Daily activity log insert failed for %s: %s",
            table_name,
            exc,
            exc_info=True,
        )
        return LogResult(ok=False, table=table_name, error=str(exc))


def _int_or_none(value: int | str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean_contact_id(contact_id: str | None) -> str | None:
    clean_id = str(contact_id or "").strip()
    if not clean_id:
        return None
    if clean_id.startswith("={{") or "$json.contact_id" in clean_id:
        LOGGER.warning("Refusing to log unresolved contact_id template: %s", clean_id)
        return None
    return clean_id
