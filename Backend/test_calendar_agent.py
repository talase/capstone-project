from app.agents.calendar_agent import process_calendar_request

result = process_calendar_request(
    "Schedule a meeting tomorrow at 6 PM called Team Meeting"
)

print(result)
