from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

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
async def webhook(request: Request) -> dict[str, str]:
    data = await request.json()
    logger.info("Full webhook data: %s", data)

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            logger.info("Non-message event received")
            return {"status": "received"}

        message = value["messages"][0]["text"]["body"]
        phone = value["messages"][0]["from"]
        logger.info("User message: %s", message)

                # Send message to n8n
        requests.post(
            "http://localhost:5678/webhook-test/whatsapp",
            json={
                "message": message,
                "phone": phone,
            },
            timeout=10,
        )

        if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            logger.error("WhatsApp credentials are not configured")
            return {"status": "missing_credentials"}

        url = (
            "https://graph.facebook.com/v25.0/"
            f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "body": "Hello, I got your message!",
            },
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        logger.info("Reply sent: %s", response.text)

    except Exception as exc:
        logger.error("Error: %s", exc)

    return {"status": "received"}
