
from app.supabase_client import get_supabase_client


def save_scheduled_message(
    phone_number,
    message,
    scheduled_time,
    contact_id=None,
):

    supabase = get_supabase_client()

    data = {
        "contact_id": contact_id,
        "phone_number": phone_number,
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
