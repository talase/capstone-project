"""FastAPI routes for dashboard contact management."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.supabase_client import SupabaseConfigError, get_supabase_client


router = APIRouter(prefix="/contacts", tags=["contacts"])


class ContactCreate(BaseModel):
    name: str
    phone_number: str
    relationship_type: Optional[str] = None
    notes: Optional[str] = None
    can_receive_requested_messages: bool = False
    message_aliases: Optional[List[str]] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    relationship_type: Optional[str] = None
    notes: Optional[str] = None
    can_receive_requested_messages: Optional[bool] = None
    message_aliases: Optional[List[str]] = None


def normalize_phone_number(phone_number: str) -> str:
    """Remove common formatting characters before storing a phone number."""

    return (
        phone_number.replace(" ", "")
        .replace("+", "")
        .replace("-", "")
        .strip()
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_contact(contact: ContactCreate) -> dict[str, Any]:
    """Create a dashboard contact."""

    name = contact.name.strip()
    phone_number = normalize_phone_number(contact.phone_number)
    _validate_required_contact_fields(name=name, phone_number=phone_number)

    row = {
        "name": name,
        "phone_number": phone_number,
        "relationship_type": contact.relationship_type,
        "notes": contact.notes,
        "can_receive_requested_messages": contact.can_receive_requested_messages,
        "message_aliases": contact.message_aliases,
    }

    response = _execute_supabase_call(
        lambda: get_supabase_client().table("contacts").insert(row).execute(),
        action="insert",
    )
    return _single_row_or_error(response, not_found_message=None)


@router.get("")
def list_contacts() -> list[dict[str, Any]]:
    """Return all contacts for dashboard display."""

    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("contacts")
            .select(
                "id,name,phone_number,relationship_type,notes,"
                "can_receive_requested_messages,message_aliases,created_at,updated_at"
            )
            .order("created_at", desc=True)
            .execute()
        ),
        action="fetch",
    )
    return getattr(response, "data", None) or []


@router.patch("/{contact_id}")
def update_contact(contact_id: str, updates: ContactUpdate) -> dict[str, Any]:
    """Update only the provided fields on one contact."""

    update_payload = _model_to_update_dict(updates)

    if "name" in update_payload:
        if update_payload["name"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name cannot be empty.",
            )
        update_payload["name"] = update_payload["name"].strip()
        if not update_payload["name"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name cannot be empty.",
            )

    if "phone_number" in update_payload:
        if update_payload["phone_number"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number cannot be empty.",
            )
        update_payload["phone_number"] = normalize_phone_number(
            update_payload["phone_number"]
        )
        if not update_payload["phone_number"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number cannot be empty.",
            )

    if not update_payload:
        return _get_contact_or_404(contact_id)

    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("contacts")
            .update(update_payload)
            .eq("id", contact_id)
            .execute()
        ),
        action="update",
    )
    return _single_row_or_error(
        response,
        not_found_message="Contact not found.",
    )


@router.delete("/{contact_id}")
def delete_contact(contact_id: str) -> dict[str, str]:
    """Delete one contact by id."""

    _get_contact_or_404(contact_id)
    _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("contacts")
            .delete()
            .eq("id", contact_id)
            .execute()
        ),
        action="delete",
    )
    return {"message": "Contact deleted successfully."}


def _validate_required_contact_fields(*, name: str, phone_number: str) -> None:
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name cannot be empty.",
        )

    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_number cannot be empty.",
        )


def _get_contact_or_404(contact_id: str) -> dict[str, Any]:
    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("contacts")
            .select("*")
            .eq("id", contact_id)
            .limit(1)
            .execute()
        ),
        action="fetch",
    )
    return _single_row_or_error(response, not_found_message="Contact not found.")


def _execute_supabase_call(callback, *, action: str):
    try:
        response = callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        _raise_database_error(str(exc), action=action, source_exception=exc)

    response_error = getattr(response, "error", None)
    if response_error:
        _raise_database_error(str(response_error), action=action)

    return response


def _single_row_or_error(
    response,
    *,
    not_found_message: str | None,
) -> dict[str, Any]:
    rows = getattr(response, "data", None) or []
    if rows:
        return rows[0]

    if not_found_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=not_found_message,
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database operation succeeded but did not return a row.",
    )


def _model_to_update_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


def _raise_database_error(
    message: str,
    *,
    action: str,
    source_exception: Exception | None = None,
) -> None:
    if _is_duplicate_phone_error(message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A contact with this phone_number already exists.",
        ) from source_exception

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Supabase {action} failed: {message}",
    ) from source_exception


def _is_duplicate_phone_error(message: str) -> bool:
    lower_message = message.lower()
    return (
        "duplicate key" in lower_message
        or "unique constraint" in lower_message
        or "23505" in lower_message
        or ("phone_number" in lower_message and "already" in lower_message)
    )
