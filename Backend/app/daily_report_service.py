"""Daily activity report generation from Supabase log records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.supabase_client import SupabaseConfigError, get_supabase_client


MESSAGES_TABLE = "messages"
ACTIVITY_LOGS_TABLE = "agent_activity_logs"
APPROVALS_TABLE = "approvals"
HIGH_RISK_ALERTS_TABLE = "high_risk_alerts"
REMINDER_LOGS_TABLE = "reminder_logs"
SCHEDULED_MESSAGE_LOGS_TABLE = "scheduled_message_logs"
RAG_ACCESS_LOGS_TABLE = "rag_access_logs"
PERSONAL_CONTEXT_DECISION_LOGS_TABLE = "personal_context_decision_logs"

REPORT_TABLES = (
    MESSAGES_TABLE,
    ACTIVITY_LOGS_TABLE,
    APPROVALS_TABLE,
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
    print("daily report start_at:", start_at.isoformat())
    print("daily report end_at:", end_at.isoformat())

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

    print("REPORT_TABLES:", REPORT_TABLES)
    print("messages records count:", len(records.get("messages", [])))
    print("messages directions:", [row.get("direction") for row in records.get("messages", [])])
    print("messages sample:", records.get("messages", [])[:3])
    for table_name, rows in records.items():
        print(f"REPORT DEBUG: {table_name} -> {len(rows)} rows")
        if rows:
            print(f"REPORT DEBUG SAMPLE {table_name}:", rows[0])

    messages = records.get(MESSAGES_TABLE, [])
    activity_logs = records.get(ACTIVITY_LOGS_TABLE, [])
    approvals = records.get(APPROVALS_TABLE, [])
    high_risk_alerts = records.get(HIGH_RISK_ALERTS_TABLE, [])
    reminders = records.get(REMINDER_LOGS_TABLE, [])
    scheduled_messages = records.get(SCHEDULED_MESSAGE_LOGS_TABLE, [])
    rag_file_access = records.get(RAG_ACCESS_LOGS_TABLE, [])
    personal_context_decisions = records.get(PERSONAL_CONTEXT_DECISION_LOGS_TABLE, [])

    messages_received = [
        row for row in messages if _clean(row.get("direction"))
        in {"incoming", "received", "inbound"}
    ]
    messages_sent = [
        row for row in messages if _clean(row.get("direction"))
        in {"outgoing", "sent", "outbound"}
    ]

    automatic_actions = [
        row for row in activity_logs if _is_automatic_action(row)
    ]
    user_approved_actions = [
        row for row in [*activity_logs, *approvals] if _status(row) in {"approved", "user_approved"}
    ]
    rejected_actions = [
        row for row in [*activity_logs, *approvals] if _status(row) == "rejected"
    ]
    pending_approvals = _current_pending_approvals(approvals)

    needs_attention = [
        *[_attention_item("pending_approval", item) for item in pending_approvals],
        *[_attention_item("high_risk_alert", item) for item in high_risk_alerts],
    ]

    return {
        "date": report_date.isoformat(),
        "summary": {
            "messages_received": len(messages_received),
            "messages_sent": len(messages_sent),
            "auto_replies": len(automatic_actions),
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
    if table_name == MESSAGES_TABLE:
        print("fetching table:", table_name)
        print("start_at:", start_at.isoformat())
        print("end_at:", end_at.isoformat())
        direct_messages_response = (
            client.table("messages")
            .select("*")
            .limit(5)
            .execute()
        )
        print("direct messages no date filter response:", direct_messages_response)
        print(
            "direct messages no date filter data:",
            getattr(direct_messages_response, "data", None),
        )
        direct_messages_date_response = (
            client.table("messages")
            .select("direction,created_at,message_text")
            .gte("created_at", "2026-06-05 00:00:00+00")
            .lt("created_at", "2026-06-06 00:00:00+00")
            .execute()
        )
        print("direct messages space timestamp response:", direct_messages_date_response)
        print(
            "direct messages space timestamp data:",
            getattr(direct_messages_date_response, "data", None),
        )
        print(
            "generated query filters:",
            {
                "table_name": table_name,
                "created_at_gte": start_at.isoformat(),
                "created_at_lt": end_at.isoformat(),
                "user_id_filter_applied": bool(user_id and _table_has_user_id(table_name)),
            },
        )
    if table_name == HIGH_RISK_ALERTS_TABLE:
        print("fetching table:", table_name)
    if user_id and _table_has_user_id(table_name):
        query = query.eq("user_id", user_id)
    response = query.order("created_at", desc=False).execute()
    rows = _rows(response)
    if table_name == MESSAGES_TABLE:
        print("raw response:", response)
        print("raw response data:", getattr(response, "data", None))
        print("rows returned:", len(rows))
    if table_name == HIGH_RISK_ALERTS_TABLE:
        print("raw response:", response)
        print("raw response data:", getattr(response, "data", None))
        print("rows returned:", len(rows))
    return rows


def _table_has_user_id(table_name: str) -> bool:
    return table_name != MESSAGES_TABLE


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


def _current_pending_approvals(approvals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in approvals if _status(row) == "pending"]


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
