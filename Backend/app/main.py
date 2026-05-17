from __future__ import annotations

import logging
import os
from typing import Any

import requests
from fastapi import FastAPI, Request

from app.config import load_env_file
from app.style_engine import generate_style_adapted_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env_file()

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secret_token")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Backend is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)

    return {"error": "Verification failed"}


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    data = await request.json()
    logger.info("Full webhook data: %s", data)

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if value.get("statuses"):
            logger.info("Ignoring status update")
            return {"status": "ignored"}

        messages = value.get("messages")
        if not messages:
            logger.info("Non-message event received")
            return {"status": "received"}

        incoming = messages[0]
        message_type = incoming.get("type")
        if message_type != "text":
            logger.info("Ignoring non-text message type: %s", message_type)
            return {"status": "ignored"}

        phone = incoming.get("from")
        metadata = value.get("metadata", {})
        bot_identifiers = {
            identifier
            for identifier in (
                WHATSAPP_PHONE_NUMBER_ID,
                metadata.get("phone_number_id"),
                metadata.get("display_phone_number"),
            )
            if identifier
        }
        if phone and phone in bot_identifiers:
            logger.info("Ignoring message from bot identity: %s", phone)
            return {"status": "ignored"}

        message = incoming.get("text", {}).get("body")
        if not message:
            logger.info("Ignoring text message without body")
            return {"status": "ignored"}

        logger.info("User message: %s", message)

        result = generate_style_adapted_response(
            incoming_message=message,
            contact_id=phone or "",
        )
        reply = result["reply"]

        # Send message to n8n.
        n8n_response = requests.post(
            "http://localhost:5678/webhook/whatsapp",
            json={
                "message": message,
                "phone": phone,
                "reply": reply,
                "style_mode": result["style_mode"],
                "profile_contact": result["profile_contact"],
                "global_confidence": result["global_confidence"],
                "contact_confidence": result["contact_confidence"],
                "generation_status": result["generation_status"],
                "llm_error": result["llm_error"],
            },
            timeout=10,
        )
        print(n8n_response.text)

        return {"status": "received", **result}

    except Exception as exc:
        logger.error("Error: %s", exc)

    return {"status": "received"}
