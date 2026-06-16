
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.scheduler_service import save_scheduled_message
from app.supabase_client import SupabaseConfigError, get_supabase_client

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError
from typing import Optional

router = APIRouter()
TURKEY_TIMEZONE = timezone(timedelta(hours=3))


def to_turkey_iso(scheduled_time: str):
    dt = datetime.fromisoformat(scheduled_time)

    if dt.tzinfo is None:
        try:
            turkey_timezone = ZoneInfo("Europe/Istanbul")
        except ZoneInfoNotFoundError:
            turkey_timezone = TURKEY_TIMEZONE

        dt = dt.replace(tzinfo=turkey_timezone)

    return dt.isoformat()


class ScheduleMessageRequest(BaseModel):
    phone: str
    message: str
    scheduled_time: str
    contact_id: Optional[str] = None


@router.post("/schedule-message")
def schedule_message(data: ScheduleMessageRequest):
    phone = normalize_phone_number(data.phone)
    message = data.message.strip()
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone is required.",
        )
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required.",
        )

    try:
        scheduled_time = to_turkey_iso(data.scheduled_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_time must be a valid ISO date/time.",
        ) from exc

    contact_id = data.contact_id or find_contact_id_by_phone(phone)

    # Save into Supabase table
    try:
        save_scheduled_message(
            phone,
            message,
            scheduled_time,
            contact_id=contact_id,
        )
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save scheduled message: {exc}",
        ) from exc

    return {
        "status": "success",
        "message": "Scheduled message saved successfully. n8n will pick it up from scheduled_messages.",
        "scheduled_time": scheduled_time,
        "contact_id": contact_id,
    }


def normalize_phone_number(phone_number: str) -> str:
    return (
        phone_number.replace(" ", "")
        .replace("+", "")
        .replace("-", "")
        .strip()
    )


def find_contact_id_by_phone(phone_number: str) -> str | None:
    try:
        rows = (
            get_supabase_client()
            .table("contacts")
            .select("id")
            .eq("phone_number", phone_number)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return None

    return str(rows[0]["id"]) if rows else None

