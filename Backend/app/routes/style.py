from fastapi import APIRouter
from pydantic import BaseModel

from app.style_engine import generate_style_adapted_response

router = APIRouter()


class StyleRequest(BaseModel):
    message: str
    contact_id: str


@router.post("/style/process")
async def process_style(data: StyleRequest):

    result = generate_style_adapted_response(
        incoming_message=data.message,
        contact_id=data.contact_id,
    )

    return result