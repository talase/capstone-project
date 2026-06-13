"""Approval workflow storage, kept separate from Personal Context Memory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.daily_activity_logger import log_approval_event
from app.supabase_client import SupabaseConfigError, get_supabase_client


APPROVAL_TABLE_NAME = "approvals"
HIGH_RISK_LEVELS = {"high", "high_risk", "critical"}


class ApprovalError(RuntimeError):
    """Raised when approval storage cannot complete a request."""


class ApprovalRequestCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    contact_id: str | None = None
    original_message: str = Field(..., min_length=1)
    generated_reply: str = Field(..., min_length=1)
    reason: str | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | str
    user_id: str
    contact_id: str | None = None
    original_message: str
    generated_reply: str
    status: str
    reason: str | None = None
    decision: str | None = None
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


def evaluate_risk_approval(risk_level: str | None) -> dict[str, Any]:
    normalized_risk = str(risk_level or "").strip().lower()
    required = normalized_risk in HIGH_RISK_LEVELS
    return {
        "required": required,
        "risk_level": normalized_risk or None,
        "reason": (
            "High-risk message requires approval before sending."
            if required
            else None
        ),
    }


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
        original_message=created.get("original_message"),
        generated_reply=created.get("generated_reply"),
        reason=created.get("reason"),
        metadata={"source": "risk_approval"},
    )
    return created


def list_approvals(
    user_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = _approval_table().select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    if status:
        query = query.eq("status", status)
    return _rows(query.execute())


def get_approval_request(approval_id: int | str) -> dict[str, Any]:
    response = _approval_table().select("*").eq("id", approval_id).execute()
    return _single_row(response, "Approval request was not found.")


def set_approval_status(approval_id: int | str, status: str) -> dict[str, Any]:
    if status not in {"approved", "rejected"}:
        raise ApprovalError("Approval status must be approved or rejected.")
    existing = get_approval_request(approval_id)
    if existing.get("status") != "pending":
        raise ApprovalError("Only pending approval requests can be updated.")
    response = _approval_table().update({"status": status}).eq("id", approval_id).execute()
    updated = _single_row(response, "Approval request was not found.")
    log_approval_event(
        status=status,
        user_id=updated.get("user_id"),
        contact_id=updated.get("contact_id"),
        approval_request_id=updated.get("id"),
        original_message=updated.get("original_message"),
        generated_reply=updated.get("generated_reply"),
        reason=updated.get("reason"),
        metadata={
            "source": "risk_approval",
            "previous_status": existing.get("status"),
        },
    )
    return updated


def _approval_table():
    try:
        return get_supabase_client().table(APPROVAL_TABLE_NAME)
    except SupabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - depends on Supabase runtime
        raise ApprovalError(str(exc)) from exc


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _single_row(response: Any, error_message: str) -> dict[str, Any]:
    rows = _rows(response)
    if not rows:
        raise ApprovalError(error_message)
    return rows[0]
