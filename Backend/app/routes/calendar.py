from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.calendar_agent import process_calendar_request

router = APIRouter()


class CalendarRequest(BaseModel):
    message: str


@router.post("/calendar/process")
async def process_calendar(data: CalendarRequest):

    result = process_calendar_request(data.message)

    return result