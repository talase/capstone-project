from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from datetime import datetime
import os

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = None

# Load existing token if it exists
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file(
        "token.json",
        SCOPES
    )

# If no valid credentials, login again
if not creds or not creds.valid:

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(port=0)

    # Save new token
    with open("token.json", "w") as token:
        token.write(creds.to_json())

calendar_service = build(
    "calendar",
    "v3",
    credentials=creds
)


def check_availability(start_datetime: str, end_datetime: str):

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