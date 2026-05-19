import json

from datetime import datetime

from openai import OpenAI

from app.services.calendar_service import (
    check_availability,
    create_event,
)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)


def process_calendar_request(user_message: str):

    today = datetime.now().strftime("%Y-%m-%d")

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

Today is {today}.

User request:
{user_message}
"""

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

    if parsed["action"] == "create_event":

        title = parsed["title"]
        date = parsed["date"]
        time = parsed["time"]

        start_datetime = f"{date}T{time}:00"

        hour = int(time.split(":")[0]) + 1
        end_time = f"{hour:02d}:00"

        end_datetime = f"{date}T{end_time}:00"

        existing_events = check_availability(
            start_datetime,
            end_datetime
        )

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

            return {
                "status": "conflict",
                "reply": final_reply
            }

        created_event = create_event(
            title,
            start_datetime,
            end_datetime
        )

        success_reply = f"""
Your meeting "{title}" has been scheduled successfully.
"""

        return {
            "status": "success",
            "reply": success_reply,
            "event_link": created_event.get("htmlLink")
        }

    return {
        "status": "unknown",
        "reply": "I could not understand the request."
    }