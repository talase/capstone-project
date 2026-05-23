"""Daily activity report generation from Supabase log records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.supabase_client import SupabaseConfigError, get_supabase_client


MESSAGE_LOGS_TABLE = "message_logs"
ACTIVITY_LOGS_TABLE = "agent_activity_logs"
APPROVAL_LOGS_TABLE = "approval_logs"
APPROVAL_REQUESTS_TABLE = "approval_requests"
HIGH_RISK_ALERTS_TABLE = "high_risk_alerts"
REMINDER_LOGS_TABLE = "reminder_logs"
SCHEDULED_MESSAGE_LOGS_TABLE = "scheduled_message_logs"
RAG_ACCESS_LOGS_TABLE = "rag_access_logs"
PERSONAL_CONTEXT_DECISION_LOGS_TABLE = "personal_context_decision_logs"

REPORT_TABLES = (
    MESSAGE_LOGS_TABLE,
    ACTIVITY_LOGS_TABLE,
    APPROVAL_LOGS_TABLE,
    APPROVAL_REQUESTS_TABLE,
    HIGH_RISK_ALERTS_TABLE,
    REMINDER_LOGS_TABLE,
    SCHEDULED_MESSAGE_LOGS_TABLE,
    RAG_ACCESS_LOGS_TABLE,
    PERSONAL_CONTEXT_DECISION_LOGS_TABLE,
)


class DailyReportError(RuntimeError):
    """Raised when daily report data cannot be fetched or assembled."""


def get_daily_report(
    report_date: date | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Fetch, group, and summarize one day's agent activity."""

    selected_date = report_date or date.today()
    records = fetch_records_for_date(selected_date, user_id=user_id)
    return build_daily_report(selected_date, records)


def fetch_records_for_date(
    report_date: date,
    user_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Collect records created during a calendar date from all report tables."""

    start_at = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)

    try:
        client = get_supabase_client()
        return {
            table_name: _fetch_table_records(
                client=client,
                table_name=table_name,
                start_at=start_at,
                end_at=end_at,
                user_id=user_id,
            )
            for table_name in REPORT_TABLES
        }
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise DailyReportError(str(exc)) from exc


def build_daily_report(
    report_date: date,
    records: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build the final JSON-compatible daily report payload."""

    message_logs = records.get(MESSAGE_LOGS_TABLE, [])
    activity_logs = records.get(ACTIVITY_LOGS_TABLE, [])
    approval_logs = records.get(APPROVAL_LOGS_TABLE, [])
    approval_requests = records.get(APPROVAL_REQUESTS_TABLE, [])
    approval_records = _merge_approval_records(approval_logs, approval_requests)
    high_risk_alerts = records.get(HIGH_RISK_ALERTS_TABLE, [])
    reminders = records.get(REMINDER_LOGS_TABLE, [])
    scheduled_messages = records.get(SCHEDULED_MESSAGE_LOGS_TABLE, [])
    rag_file_access = records.get(RAG_ACCESS_LOGS_TABLE, [])
    personal_context_decisions = records.get(PERSONAL_CONTEXT_DECISION_LOGS_TABLE, [])

    messages_received = [
        row for row in message_logs if _clean(_first_value(row, "direction", "message_direction", "type"))
        in {"received", "incoming", "inbound"}
    ]
    messages_sent = [
        row for row in message_logs if _clean(_first_value(row, "direction", "message_direction", "type"))
        in {"sent", "outgoing", "outbound"}
    ]

    automatic_actions = [
        row for row in activity_logs if _is_automatic_action(row)
    ]
    user_approved_actions = [
        row for row in [*activity_logs, *approval_records] if _status(row) in {"approved", "user_approved"}
    ]
    rejected_actions = [
        row for row in [*activity_logs, *approval_records] if _status(row) == "rejected"
    ]
    pending_approvals = _current_pending_approvals(approval_logs, approval_requests)

    needs_attention = [
        *[_attention_item("pending_approval", item) for item in pending_approvals],
        *[_attention_item("high_risk_alert", item) for item in high_risk_alerts],
    ]

    return {
        "date": report_date.isoformat(),
        "summary": {
            "messages_received": len(messages_received),
            "messages_sent": len(messages_sent),
            "automatic_actions": len(automatic_actions),
            "approved_actions": len(user_approved_actions),
            "rejected_actions": len(rejected_actions),
            "pending_approvals": len(pending_approvals),
            "high_risk_alerts": len(high_risk_alerts),
            "reminders_created": len(reminders),
            "scheduled_messages": len(scheduled_messages),
            "rag_files_accessed": _unique_rag_file_count(rag_file_access),
        },
        "detected_action_categories": _detected_action_categories(activity_logs),
        "automatic_actions": automatic_actions,
        "user_approved_actions": user_approved_actions,
        "rejected_actions": rejected_actions,
        "pending_approvals": pending_approvals,
        "high_risk_alerts": high_risk_alerts,
        "reminders": reminders,
        "scheduled_messages": scheduled_messages,
        "personal_context_decisions": personal_context_decisions,
        "rag_file_access": rag_file_access,
        "needs_attention": needs_attention,
    }


def _fetch_table_records(
    client: Any,
    table_name: str,
    start_at: datetime,
    end_at: datetime,
    user_id: str | None,
) -> list[dict[str, Any]]:
    query = (
        client.table(table_name)
        .select("*")
        .gte("created_at", start_at.isoformat())
        .lt("created_at", end_at.isoformat())
    )
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.order("created_at", desc=False).execute()
    return _rows(response)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _is_automatic_action(row: dict[str, Any]) -> bool:
    status = _status(row)
    mode = _clean(_first_value(row, "mode", "action_mode", "execution_mode"))
    requires_approval = row.get("requires_approval")
    return (
        status in {"automatic", "auto", "auto_executed"}
        or mode in {"automatic", "auto"}
        or (requires_approval is False and status in {"completed", "sent", "executed"})
    )


def _status(row: dict[str, Any]) -> str:
    return _clean(_first_value(row, "status", "action_status", "approval_status", "outcome"))


def _merge_approval_records(
    approval_logs: list[dict[str, Any]],
    approval_requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = list(approval_logs)
    seen_keys = {_approval_record_key(row) for row in approval_logs}
    for row in approval_requests:
        key = _approval_record_key(row)
        if key not in seen_keys:
            records.append(row)
            seen_keys.add(key)
    return records


def _current_pending_approvals(
    approval_logs: list[dict[str, Any]],
    approval_requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pending_requests = [row for row in approval_requests if _status(row) == "pending"]
    request_ids = {_approval_id(row) for row in approval_requests}
    orphan_pending_logs = [
        row
        for row in approval_logs
        if _status(row) == "pending" and _approval_id(row) not in request_ids
    ]
    return [*pending_requests, *orphan_pending_logs]


def _approval_record_key(row: dict[str, Any]) -> tuple[Any, str]:
    return (_approval_id(row), _status(row))


def _approval_id(row: dict[str, Any]) -> Any:
    return _first_value(row, "approval_request_id", "id")


def _detected_action_categories(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        category = _clean(
            _first_value(row, "action_category", "detected_action_category", "category")
        )
        if category:
            counts[category] = counts.get(category, 0) + 1
    return [{"category": category, "count": count} for category, count in sorted(counts.items())]


def _unique_rag_file_count(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    identities = {
        str(_first_value(row, "file_id", "file_path", "file_name", "document_id") or row.get("id"))
        for row in rows
    }
    return len({identity for identity in identities if identity})


def _attention_item(item_type: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": item_type,
        "id": item.get("id"),
        "status": item.get("status"),
        "message": _first_value(item, "title", "reason", "message", "original_message", "description"),
        "record": item,
    }


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()
