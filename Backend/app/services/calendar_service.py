from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = Credentials.from_authorized_user_file(
    "token.json",
    SCOPES
)

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

    event["start"]["dateTime"] = new_start
    event["end"]["dateTime"] = new_end

    updated_event = calendar_service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event
    ).execute()

    return updated_event