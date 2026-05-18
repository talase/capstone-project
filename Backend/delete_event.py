from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

EVENT_ID = "npi0hkudgdmn71p9g9ftbd3o6c"

creds = Credentials.from_authorized_user_file("token.json", SCOPES)

service = build("calendar", "v3", credentials=creds)

service.events().delete(
    calendarId="primary",
    eventId=EVENT_ID
).execute()

print("Event deleted successfully.")