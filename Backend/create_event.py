from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = Credentials.from_authorized_user_file("token.json", SCOPES)

service = build("calendar", "v3", credentials=creds)

event = {
    "summary": "Capstone Test Meeting",
    "start": {
        "dateTime": "2026-05-20T15:00:00",
        "timeZone": "Asia/Nicosia",
    },
    "end": {
        "dateTime": "2026-05-20T16:00:00",
        "timeZone": "Asia/Nicosia",
    },
}

created_event = service.events().insert(
    calendarId="primary",
    body=event
).execute()

print("Event created:")
print(created_event.get("htmlLink"))