from datetime import datetime
import os
from functools import lru_cache
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarConfigurationError(RuntimeError):
    """Raised when Google Calendar credentials are missing or invalid."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _calendar_file(env_name: str, default_name: str) -> Path:
    configured_path = os.getenv(env_name)
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return _project_root() / default_name


@lru_cache(maxsize=1)
def get_calendar_service():
    token_path = _calendar_file("GOOGLE_CALENDAR_TOKEN_FILE", "token.json")
    credentials_path = _calendar_file(
        "GOOGLE_CALENDAR_CREDENTIALS_FILE",
        "credentials.json",
    )

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise CalendarConfigurationError(
                    "Google Calendar token has expired or was revoked. "
                    f"Regenerate {token_path} by completing Google OAuth again."
                ) from exc
        else:
            if not credentials_path.exists():
                raise CalendarConfigurationError(
                    "Google Calendar credentials file was not found. "
                    f"Expected: {credentials_path}"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def check_availability(start_datetime: str, end_datetime: str):
    calendar_service = get_calendar_service()

    events_result = calendar_service.events().list(
        calendarId="primary",
        timeMin=f"{start_datetime}+03:00",
        timeMax=f"{end_datetime}+03:00",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    existing_events = events_result.get("items", [])

    return existing_events


def create_event(
    title: str,
    start_datetime: str,
    end_datetime: str
):
    calendar_service = get_calendar_service()

    event = {
        "summary": title,
        "start": {
            "dateTime": start_datetime,
            "timeZone": "Asia/Nicosia",
        },
        "end": {
            "dateTime": end_datetime,
            "timeZone": "Asia/Nicosia",
        },
    }

    created_event = calendar_service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return created_event


def delete_event(event_id: str):
    calendar_service = get_calendar_service()

    calendar_service.events().delete(
        calendarId="primary",
        eventId=event_id
    ).execute()

    return True


def update_event(
    event_id: str,
    new_start: str,
    new_end: str
):
    calendar_service = get_calendar_service()

    event = calendar_service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    event["start"] = {
        "dateTime": new_start,
        "timeZone": "Asia/Nicosia",
    }

    event["end"] = {
        "dateTime": new_end,
        "timeZone": "Asia/Nicosia",
    }

    updated_event = calendar_service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event
    ).execute()

    return updated_event


def find_event_by_title(title: str):
    calendar_service = get_calendar_service()

    now = datetime.utcnow().isoformat() + "Z"

    events_result = calendar_service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    for event in events:

        event_title = event.get("summary", "").strip().lower()

        if event_title == title.strip().lower():

            return event

    return None
