
from app.supabase_client import get_supabase_client


def save_scheduled_message(
    phone,
    message,
    scheduled_time
):

    supabase = get_supabase_client()

    data = {
        "message_text": message,
        "scheduled_time": scheduled_time,
        "status": "pending"
    }

    response = (
        supabase
        .table("scheduled_messages")
        .insert(data)
        .execute()
    )

    return response
