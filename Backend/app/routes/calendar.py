from datetime import datetime, timedelta
import logging
from typing import List, Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.calendar_service import (
    CalendarConfigurationError,
    check_availability,
    create_event,
    delete_event,
    find_event_by_title,
    update_event,
)

router = APIRouter()
LOGGER = logging.getLogger(__name__)


class CalendarRequest(BaseModel):
    action: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    attendees: Optional[Union[List[str], str]] = None
    original_message_text: Optional[str] = None


def build_datetime_range(date: str, time: str):
    try:
        start = datetime.strptime(f"{date}T{time}:00", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date/time format. Use date YYYY-MM-DD and time HH:MM.",
        )

    end = start + timedelta(hours=1)

    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def require_field(value: Optional[str], field_name: str):
    if value is None or not str(value).strip():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required.",
        )

    return str(value).strip()


def event_titles(events):
    return [
        event.get("summary", "Untitled event")
        for event in events
    ]


@router.post("/calendar/process")
async def process_calendar(data: CalendarRequest):
    try:
        action = require_field(data.action, "action")

        valid_actions = {
            "create_event",
            "update_event",
            "delete_event",
            "check_availability",
        }

        if action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail="Invalid action.",
            )

        title = None
        if action in {"create_event", "update_event", "delete_event"}:
            title = require_field(data.title, "title")

        start_datetime = None
        end_datetime = None
        if action in {"create_event", "update_event", "check_availability"}:
            date = require_field(data.date, "date")
            time = require_field(data.time, "time")
            start_datetime, end_datetime = build_datetime_range(date, time)

        if action == "create_event":
            existing_events = check_availability(start_datetime, end_datetime)

            if existing_events:
                return {
                    "status": "conflict",
                    "reply": "You already have an event during that time.",
                }

            created_event = create_event(title, start_datetime, end_datetime)

            return {
                "status": "success",
                "reply": f"Your meeting \"{title}\" has been scheduled successfully.",
                "event_link": created_event.get("htmlLink"),
            }

        if action == "update_event":
            existing_event = find_event_by_title(title)

            if not existing_event:
                return {
                    "status": "not_found",
                    "reply": f"I could not find an event titled \"{title}\".",
                }

            updated_event = update_event(
                existing_event["id"],
                start_datetime,
                end_datetime,
            )

            return {
                "status": "success",
                "reply": f"Your meeting \"{title}\" has been updated successfully.",
                "event_link": updated_event.get("htmlLink"),
            }

        if action == "delete_event":
            existing_event = find_event_by_title(title)

            if not existing_event:
                return {
                    "status": "not_found",
                    "reply": f"I could not find an event titled \"{title}\".",
                }

            delete_event(existing_event["id"])

            return {
                "status": "success",
                "reply": f"Your meeting \"{title}\" has been deleted successfully.",
            }

        existing_events = check_availability(start_datetime, end_datetime)

        if existing_events:
            titles = event_titles(existing_events)

            return {
                "status": "busy",
                "reply": "You already have an event during that time.",
                "events": titles,
            }

        return {
            "status": "free",
            "reply": "You are available during that time.",
        }

    except HTTPException:
        raise

    except CalendarConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        LOGGER.exception("Unexpected error while processing calendar request")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while processing calendar request: {type(exc).__name__}",
        ) from exc
