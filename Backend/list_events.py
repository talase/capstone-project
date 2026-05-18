import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = Credentials.from_authorized_user_file("token.json", SCOPES)

service = build("calendar", "v3", credentials=creds)

now = datetime.datetime.utcnow().isoformat() + "Z"

events_result = service.events().list(
    calendarId="primary",
    timeMin=now,
    maxResults=50,
    singleEvents=True,
    orderBy="startTime"
).execute()

events = events_result.get("items", [])

for event in events:
    print("SUMMARY:", event.get("summary"))
    print("EVENT ID:", event.get("id"))
    print("-------------------")