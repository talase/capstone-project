from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

EVENT_ID = "94penrfbbnvcc0acteqk4anrug"

creds = Credentials.from_authorized_user_file("token.json", SCOPES)

service = build("calendar", "v3", credentials=creds)

event = service.events().get(
    calendarId="primary",
    eventId=EVENT_ID
).execute()

event["start"]["dateTime"] = "2026-05-21T18:00:00"
event["end"]["dateTime"] = "2026-05-21T19:00:00"

updated_event = service.events().update(
    calendarId="primary",
    eventId=EVENT_ID,
    body=event
).execute()

print("Event updated successfully.")
print(updated_event.get("htmlLink"))