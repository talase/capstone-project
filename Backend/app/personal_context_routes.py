"""FastAPI routes for Personal Context Memory rule management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.personal_context_service import (
    ApprovalRequest,
    ApprovalRequestCreate,
    PersonalContextError,
    PersonalContextRule,
    PersonalContextRuleCreate,
    PersonalContextRuleUpdate,
    UserStatus,
    UserStatusSet,
    UserStatusUpdate,
    clear_user_status,
    create_approval_request,
    create_rule,
    delete_rule,
    get_approval_request,
    get_current_user_status,
    list_approval_requests,
    list_active_rules,
    list_rules,
    set_approval_status,
    set_rule_active,
    set_user_status,
    update_user_status,
    update_rule,
)
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/personal-context", tags=["personal-context"])


@router.post(
    "/rules",
    response_model=PersonalContextRule,
    status_code=status.HTTP_201_CREATED,
)
def create_personal_context_rule(rule: PersonalContextRuleCreate) -> dict[str, Any]:
    return _handle_service_call(lambda: create_rule(rule))


@router.get("/rules", response_model=list[PersonalContextRule])
def get_personal_context_rules(
    user_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _handle_service_call(lambda: list_rules(user_id=user_id))


@router.get("/rules/active", response_model=list[PersonalContextRule])
def get_active_personal_context_rules(
    user_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _handle_service_call(lambda: list_active_rules(user_id=user_id))


@router.put("/rules/{rule_id}", response_model=PersonalContextRule)
def update_personal_context_rule(
    rule_id: int | str,
    updates: PersonalContextRuleUpdate,
) -> dict[str, Any]:
    return _handle_service_call(lambda: update_rule(rule_id, updates))


@router.delete("/rules/{rule_id}")
def delete_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: delete_rule(rule_id))


@router.patch("/rules/{rule_id}/activate", response_model=PersonalContextRule)
def activate_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_rule_active(rule_id, True))


@router.patch("/rules/{rule_id}/deactivate", response_model=PersonalContextRule)
def deactivate_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_rule_active(rule_id, False))


@router.post(
    "/approvals",
    response_model=ApprovalRequest,
    status_code=status.HTTP_201_CREATED,
)
def create_pending_approval(request: ApprovalRequestCreate) -> dict[str, Any]:
    return _handle_service_call(lambda: create_approval_request(request))


@router.get("/approvals", response_model=list[ApprovalRequest])
def get_approval_requests(
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
) -> list[dict[str, Any]]:
    return _handle_service_call(
        lambda: list_approval_requests(user_id=user_id, status=status)
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalRequest)
def get_one_approval_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: get_approval_request(approval_id))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRequest)
def approve_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "approved"))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRequest)
def reject_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "rejected"))


@router.post("/status", response_model=UserStatus)
def set_current_status(status_request: UserStatusSet) -> dict[str, Any]:
    return _handle_service_call(lambda: set_user_status(status_request))


@router.get("/status", response_model=UserStatus)
def get_current_status(
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: get_current_user_status(user_id))


@router.patch("/status", response_model=UserStatus)
def update_current_status(
    updates: UserStatusUpdate,
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: update_user_status(user_id, updates))


@router.delete("/status", response_model=UserStatus)
def clear_current_status(
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: clear_user_status(user_id))


def _handle_service_call(callback):
    try:
        return callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PersonalContextError as exc:
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
            detail=f"Personal context service failed: {exc}",
        ) from exc
