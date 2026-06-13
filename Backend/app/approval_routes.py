"""FastAPI routes for approval workflows."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.approval_service import (
    ApprovalError,
    ApprovalRequest,
    ApprovalRequestCreate,
    create_approval_request,
    get_approval_request,
    list_approvals,
    set_approval_status,
)
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=ApprovalRequest, status_code=status.HTTP_201_CREATED)
def create_pending_approval(request: ApprovalRequestCreate) -> dict[str, Any]:
    return _handle_service_call(lambda: create_approval_request(request))


@router.get("", response_model=list[ApprovalRequest])
def get_approvals(
    user_id: str | None = Query(default=None),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|approved|rejected)$",
    ),
) -> list[dict[str, Any]]:
    return _handle_service_call(
        lambda: list_approvals(user_id=user_id, status=status_filter)
    )


@router.get("/{approval_id}", response_model=ApprovalRequest)
def get_one_approval_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: get_approval_request(approval_id))


@router.post("/{approval_id}/approve", response_model=ApprovalRequest)
def approve_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "approved"))


@router.post("/{approval_id}/reject", response_model=ApprovalRequest)
def reject_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "rejected"))


def _handle_service_call(callback):
    try:
        return callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ApprovalError as exc:
        message = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval service failed: {exc}",
        ) from exc
