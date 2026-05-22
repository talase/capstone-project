from fastapi import APIRouter
from pydantic import BaseModel

from app.style_engine import generate_style_adapted_response

router = APIRouter(prefix="/style", tags=["style"])


class StyleRequest(BaseModel):
    message: str
    contact_id: str
    user_id: str = "default_user"
    risk_level: str | None = None
    action_type: str | None = None


@router.post("/process")
async def process_style(data: StyleRequest):

    result = generate_style_adapted_response(
        incoming_message=data.message,
        contact_id=data.contact_id,
        user_id=data.user_id,
        risk_level=data.risk_level,
        action_type=data.action_type,
    )

    return result
