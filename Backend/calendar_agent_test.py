import json

from openai import OpenAI
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# -----------------------------
# OPENROUTER SETUP
# -----------------------------

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

# -----------------------------
# GOOGLE CALENDAR SETUP
# -----------------------------

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

# -----------------------------
# USER MESSAGE
# -----------------------------

user_message = "Schedule a meeting tomorrow at 6 PM called Team Meeting"

# -----------------------------
# PROMPT
# -----------------------------

prompt = f"""
You are a calendar scheduling assistant.

Extract the calendar action from the user request.

Return ONLY valid JSON.

IMPORTANT RULES:
- Convert relative dates like "tomorrow" into exact dates.
- Convert all times into 24-hour HH:MM format.
- Date format must be YYYY-MM-DD.
- Time format must be HH:MM.

Possible actions:
- create_event
- delete_event
- update_event
- check_availability

JSON format:
{{
  "action": "",
  "title": "",
  "date": "",
  "time": ""
}}

Today is 2026-05-18.

User request:
{user_message}
"""

# -----------------------------
# MODEL REQUEST
# -----------------------------

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],
    temperature=0
)

content = response.choices[0].message.content

print("RAW MODEL OUTPUT:")
print(content)

parsed = json.loads(content)

print("\nPARSED JSON:")
print(parsed)

# -----------------------------
# CREATE EVENT ACTION
# -----------------------------

if parsed["action"] == "create_event":

    title = parsed["title"]
    date = parsed["date"]
    time = parsed["time"]

    start_datetime = f"{date}T{time}:00"

    hour = int(time.split(":")[0]) + 1
    end_time = f"{hour:02d}:00"

    end_datetime = f"{date}T{end_time}:00"

    # -----------------------------
    # CHECK AVAILABILITY
    # -----------------------------

    events_result = calendar_service.events().list(
        calendarId="primary",
        timeMin=f"{start_datetime}+03:00",
        timeMax=f"{end_datetime}+03:00",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    existing_events = events_result.get("items", [])

    if existing_events:

        existing_titles = [
            existing.get("summary")
            for existing in existing_events
        ]

        conflict_prompt = f"""
You are a helpful scheduling assistant.

The user requested:
"{user_message}"

However, the requested time slot is already occupied.

Existing events:
{existing_titles}

Generate a short, natural WhatsApp-style reply.
"""

        conflict_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": conflict_prompt
                }
            ],
            temperature=0.7
        )

        final_reply = (
            conflict_response
            .choices[0]
            .message
            .content
        )

        print("\nASSISTANT REPLY:")
        print(final_reply)

    else:

        # -----------------------------
        # CREATE EVENT
        # -----------------------------

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

        print("\nEVENT CREATED SUCCESSFULLY")
        print(created_event.get("htmlLink"))