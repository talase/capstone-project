from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ScheduleMessageRequest(BaseModel):
    phone: str
    message: str
    scheduled_time: str


@router.post("/schedule-message")
def schedule_message(data: ScheduleMessageRequest):

    return {
        "status": "success",
        "phone": data.phone,
        "message": data.message,
        "scheduled_time": data.scheduled_time
    }