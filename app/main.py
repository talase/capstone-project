from fastapi import FastAPI, Request
from dotenv import load_dotenv
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

api_key = os.getenv("OPENAI_API_KEY")
print("API KEY:", api_key)

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == "my_secret_token":
        return int(hub_challenge)

    return {"error": "Verification failed"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    logger.info(f"✅ Full webhook data: {data}")

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" in value:
            message = value["messages"][0]["text"]["body"]
            phone = value["messages"][0]["from"]

            logger.info(f"📩 User message: {message}")

            url = "https://graph.facebook.com/v25.0/1092704950586369/messages"

            headers = {
                "Authorization": "Bearer EAANlNNTUN00BRTROeVfJYopUttZCZBew175YEfSJuOXXgFTMJecLmQIAd5Ibxd0SN4Gd5kkkbKQwoTyZBN5nc4UYx6SmrreLErygfwHR5lUJ3Wy5d0R2aFA8LMDYoWP6Gz1duAJJmPfcZCZCZADfWZAiSlAzxeLDZC3YLMU1gHZAeNN6VlGaBQIZBWxF9UJUWtNyYniPKlaBiRgw8FcZBK3wML9sZAi2dZCL25ifshR7yzflADHEnGQLUC2gvEhmjEqkIPZC3mJsvqEgCkUE2Lt7a2iYa0",
                "Content-Type": "application/json"
            }

            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {
                    "body": "Hello 👋 I got your message!"
                }
            }

            response = requests.post(url, headers=headers, json=payload)
            logger.info(f"📤 Reply sent: {response.text}")

        else:
            logger.info("ℹ️ Non-message event received")

    except Exception as e:
        logger.error(f"❌ Error: {e}")

    return {"status": "received"}
