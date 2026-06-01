
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.scheduler_service import save_scheduled_message

import requests

from datetime import datetime
from zoneinfo import ZoneInfo

router = APIRouter()


def to_turkey_iso(scheduled_time: str):
    dt = datetime.fromisoformat(scheduled_time)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Istanbul"))

    return dt.isoformat()


class ScheduleMessageRequest(BaseModel):
    phone: str
    message: str
    scheduled_time: str


@router.post("/schedule-message")
def schedule_message(data: ScheduleMessageRequest):

    # Convert to Turkey timezone ISO format
    scheduled_time = to_turkey_iso(data.scheduled_time)

    # Save into Supabase table
    save_scheduled_message(
        data.phone,
        data.message,
        scheduled_time
    )

    # Trigger n8n webhook
    requests.post(
        "https://ryham4918.app.n8n.cloud/webhook/schedule-message",
        json={
            "phone_number": data.phone,
            "message_text": data.message,
            "scheduled_time": scheduled_time
        }
    )

    return {
        "status": "success",
        "message": "Scheduled message saved successfully"
    }

