from app.supabase_client import get_supabase_client


def save_scheduled_message(
    phone,
    message,
    scheduled_time
):
    
    import os

    print("SUPABASE URL RAW:")
    print(repr(os.getenv("SUPABASE_URL")))

    supabase = get_supabase_client()

    data = {
        "phone": phone,
        "message": message,
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