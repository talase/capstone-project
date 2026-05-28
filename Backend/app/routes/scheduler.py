from fastapi import APIRouter
from pydantic import BaseModel
from app.services.scheduler_service import save_scheduled_message

import requests

router = APIRouter()


class ScheduleMessageRequest(BaseModel):
    phone: str
    message: str
    scheduled_time: str


@router.post("/schedule-message")
def schedule_message(data: ScheduleMessageRequest):

    save_scheduled_message(
        data.phone,
        data.message,
        data.scheduled_time
    )

    # Trigger n8n webhook
    requests.post(
        "https://ryham4918.app.n8n.cloud/webhook/schedule-message",
        json={
            "phone_number": data.phone,
            "message_text": data.message,
            "scheduled_time": data.scheduled_time
        }
    )

    return {
        "status": "success",
        "message": "Scheduled message saved successfully"
    }