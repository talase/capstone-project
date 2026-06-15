"""Dashboard approvals enriched with related contact, message, and file data."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.supabase_client import SupabaseConfigError, get_supabase_client


router = APIRouter(prefix="/dashboard-approvals", tags=["dashboard-approvals"])
RiskLevel = Literal["low", "medium", "high"]


class DashboardApproval(BaseModel):
    id: str
    message_id: str | None = None
    contact_id: str | None = None
    action_type: str
    risk_level: RiskLevel | None = None
    status: str
    file_id: str | None = None
    phone_number: str | None = None
    approval_message: str | None = None
    target_contact_id: str | None = None
    target_contact_name: str | None = None
    message_to_send: str | None = None
    request_text: str | None = None
    proposed_response: str | None = None
    user_edited_response: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None

    requester_name: str
    requester_phone_number: str | None = None
    source_message_text: str | None = None
    source_message_direction: str | None = None
    source_message_created_at: str | None = None
    file_name: str | None = None
    file_storage_path: str | None = None
    file_type: str | None = None
    file_is_sensitive: bool | None = None
    target_contact_phone_number: str | None = None


@router.get("", response_model=list[DashboardApproval])
def list_dashboard_approvals(
    user_id: str = Query(default="default_user"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[DashboardApproval]:
    """Return approval rows with related IDs translated into useful labels."""

    clean_user_id = _required_user_id(user_id)
    client = get_supabase_client_or_503()

    approval_response = _execute_supabase_call(
        lambda: (
            client.table("approvals")
            .select(
                "id,message_id,contact_id,action_type,risk_level,status,file_id,"
                "phone_number,approval_message,target_contact_id,target_contact_name,"
                "message_to_send,request_text,proposed_response,user_edited_response,"
                "created_at,resolved_at"
            )
            .eq("user_id", clean_user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ),
        action="fetch approvals",
    )
    approval_rows = _dict_rows(approval_response)

    contact_response = _execute_supabase_call(
        lambda: (
            client.table("contacts")
            .select("id,name,phone_number")
            .execute()
        ),
        action="fetch contacts",
    )
    contacts = _dict_rows(contact_response)

    message_ids = _unique_ids(approval_rows, "message_id")
    file_ids = _unique_ids(approval_rows, "file_id")
    message_rows = _fetch_related_rows(
        client,
        table="messages",
        columns="id,contact_id,message_text,direction,created_at",
        ids=message_ids,
    )
    file_rows = _fetch_related_rows(
        client,
        table="files",
        columns="id,file_name,storage_path,file_type,is_sensitive",
        ids=file_ids,
    )

    contacts_by_id = _rows_by_id(contacts)
    contacts_by_phone = {
        _normalize_phone(row.get("phone_number")): row
        for row in contacts
        if _normalize_phone(row.get("phone_number"))
    }
    messages_by_id = _rows_by_id(message_rows)
    files_by_id = _rows_by_id(file_rows)

    return [
        _enrich_approval(
            row,
            contacts_by_id=contacts_by_id,
            contacts_by_phone=contacts_by_phone,
            messages_by_id=messages_by_id,
            files_by_id=files_by_id,
        )
        for row in approval_rows
        if row.get("id")
    ]


def _enrich_approval(
    row: dict[str, Any],
    *,
    contacts_by_id: dict[str, dict[str, Any]],
    contacts_by_phone: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    files_by_id: dict[str, dict[str, Any]],
) -> DashboardApproval:
    message = messages_by_id.get(str(row.get("message_id") or ""))
    contact_id = str(row.get("contact_id") or "")
    if not contact_id and message:
        contact_id = str(message.get("contact_id") or "")

    contact = contacts_by_id.get(contact_id)
    if contact is None:
        contact = contacts_by_phone.get(_normalize_phone(row.get("phone_number")))

    target_contact_id = str(row.get("target_contact_id") or "")
    target_contact = contacts_by_id.get(target_contact_id)
    file_row = files_by_id.get(str(row.get("file_id") or ""))

    requester_name = (
        str(contact.get("name"))
        if contact and contact.get("name")
        else "Unknown contact"
    )
    target_name = (
        str(target_contact.get("name"))
        if target_contact and target_contact.get("name")
        else _optional_text(row.get("target_contact_name"))
    )

    return DashboardApproval(
        id=str(row["id"]),
        message_id=_optional_text(row.get("message_id")),
        contact_id=_optional_text(row.get("contact_id")),
        action_type=str(row.get("action_type") or "unknown_action"),
        risk_level=_risk_level(row.get("risk_level")),
        status=str(row.get("status") or "unknown"),
        file_id=_optional_text(row.get("file_id")),
        phone_number=_optional_text(row.get("phone_number")),
        approval_message=_optional_text(row.get("approval_message")),
        target_contact_id=_optional_text(row.get("target_contact_id")),
        target_contact_name=target_name,
        message_to_send=_optional_text(row.get("message_to_send")),
        request_text=_optional_text(row.get("request_text")),
        proposed_response=_optional_text(row.get("proposed_response")),
        user_edited_response=_optional_text(row.get("user_edited_response")),
        created_at=_optional_text(row.get("created_at")),
        resolved_at=_optional_text(row.get("resolved_at")),
        requester_name=requester_name,
        requester_phone_number=(
            _optional_text(contact.get("phone_number"))
            if contact
            else _optional_text(row.get("phone_number"))
        ),
        source_message_text=(
            _optional_text(message.get("message_text")) if message else None
        ),
        source_message_direction=(
            _optional_text(message.get("direction")) if message else None
        ),
        source_message_created_at=(
            _optional_text(message.get("created_at")) if message else None
        ),
        file_name=(
            _optional_text(file_row.get("file_name")) if file_row else None
        ),
        file_storage_path=(
            _optional_text(file_row.get("storage_path")) if file_row else None
        ),
        file_type=(
            _optional_text(file_row.get("file_type")) if file_row else None
        ),
        file_is_sensitive=(
            bool(file_row.get("is_sensitive")) if file_row else None
        ),
        target_contact_phone_number=(
            _optional_text(target_contact.get("phone_number"))
            if target_contact
            else None
        ),
    )


def _fetch_related_rows(
    client,
    *,
    table: str,
    columns: str,
    ids: list[str],
) -> list[dict[str, Any]]:
    if not ids:
        return []
    response = _execute_supabase_call(
        lambda: (
            client.table(table)
            .select(columns)
            .in_("id", ids)
            .execute()
        ),
        action=f"fetch {table}",
    )
    return _dict_rows(response)


def _required_user_id(user_id: str) -> str:
    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )
    return clean_user_id


def get_supabase_client_or_503():
    try:
        return get_supabase_client()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _execute_supabase_call(callback, *, action: str):
    try:
        response = callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase {action} failed: {exc}",
        ) from exc

    response_error = getattr(response, "error", None)
    if response_error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase {action} failed: {response_error}",
        )
    return response


def _dict_rows(response) -> list[dict[str, Any]]:
    return [
        row
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, dict)
    ]


def _rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in rows
        if row.get("id") is not None
    }


def _unique_ids(rows: list[dict[str, Any]], column: str) -> list[str]:
    return sorted(
        {
            str(row[column])
            for row in rows
            if row.get(column) is not None and str(row[column]).strip()
        }
    )


def _normalize_phone(value: object) -> str:
    return (
        str(value or "")
        .replace(" ", "")
        .replace("+", "")
        .replace("-", "")
        .strip()
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _risk_level(value: object) -> RiskLevel | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"low", "medium", "high"} else None
