"""Read-only aggregate metrics for the frontend dashboard."""

from __future__ import annotations

from collections import Counter
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.supabase_client import SupabaseConfigError, get_supabase_client


router = APIRouter(prefix="/dashboard-summary", tags=["dashboard-summary"])


class DashboardActionCount(BaseModel):
    action_type: str
    count: int


class DashboardSummary(BaseModel):
    approvals_total: int
    approvals_pending: int
    approvals_approved: int
    approvals_rejected: int
    approvals_executed: int
    approvals_blocked: int
    messages_total: int
    incoming_messages: int
    outgoing_messages: int
    contacts_total: int
    uploaded_files_total: int
    sensitive_files: int
    non_sensitive_files: int
    actions_by_type: list[DashboardActionCount]


@router.get("", response_model=DashboardSummary)
def get_dashboard_summary(
    user_id: str = Query(default="default_user"),
) -> DashboardSummary:
    """Return live dashboard totals without exposing any write operation."""

    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )

    try:
        client = get_supabase_client()
        approval_rows = _fetch_all_rows(
            client,
            table="approvals",
            columns="action_type,status",
            filters=(("eq", "user_id", clean_user_id),),
        )
        message_rows = _fetch_all_rows(
            client,
            table="messages",
            columns="id,direction",
        )
        contact_rows = _fetch_all_rows(
            client,
            table="contacts",
            columns="id",
        )
        file_rows = _fetch_all_rows(
            client,
            table="files",
            columns="id,is_sensitive",
            filters=(("like", "storage_path", "dashboard_uploads/%"),),
        )
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase dashboard summary failed: {exc}",
        ) from exc

    approval_statuses = Counter(
        str(row.get("status") or "unknown").strip().lower()
        for row in approval_rows
    )
    action_counts: Counter[str] = Counter()
    for row in approval_rows:
        action_counts.update(_action_types(row.get("action_type")))
    message_directions = Counter(
        str(row.get("direction") or "unknown").strip().lower()
        for row in message_rows
    )
    sensitive_files = sum(
        1 for row in file_rows if bool(row.get("is_sensitive", False))
    )

    return DashboardSummary(
        approvals_total=len(approval_rows),
        approvals_pending=approval_statuses["pending"],
        approvals_approved=approval_statuses["approved"],
        approvals_rejected=approval_statuses["rejected"],
        approvals_executed=approval_statuses["executed"],
        approvals_blocked=approval_statuses["blocked_high_risk"],
        messages_total=len(message_rows),
        incoming_messages=message_directions["incoming"],
        outgoing_messages=message_directions["outgoing"],
        contacts_total=len(contact_rows),
        uploaded_files_total=len(file_rows),
        sensitive_files=sensitive_files,
        non_sensitive_files=len(file_rows) - sensitive_files,
        actions_by_type=[
            DashboardActionCount(action_type=action_type, count=count)
            for action_type, count in action_counts.most_common()
        ],
    )


def _fetch_all_rows(
    client,
    *,
    table: str,
    columns: str,
    filters: tuple[tuple[str, str, object], ...] = (),
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = client.table(table).select(columns)
        for operation, column, value in filters:
            query = getattr(query, operation)(column, value)
        response = query.range(offset, offset + page_size - 1).execute()
        response_error = getattr(response, "error", None)
        if response_error:
            raise RuntimeError(response_error)

        page = [
            row
            for row in (getattr(response, "data", None) or [])
            if isinstance(row, dict)
        ]
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return rows


def _action_types(value: object) -> list[str]:
    if isinstance(value, list):
        actions = value
    else:
        text = str(value or "").strip()
        if not text:
            return ["unknown_action"]
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                actions = parsed
            else:
                actions = [text]
        else:
            actions = [text]

    normalized = [str(action).strip() for action in actions if str(action).strip()]
    return normalized or ["unknown_action"]
