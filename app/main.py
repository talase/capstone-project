from fastapi import FastAPI, Request
from dotenv import load_dotenv
from pydantic import BaseModel
import logging
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create app
app = FastAPI()

# Read variables from .env
api_key = os.getenv("OPENAI_API_KEY")
print("API KEY:", api_key)

# ----------- DATA MODEL -----------

class Message(BaseModel):
    message: str

# ----------- ENDPOINTS -----------

# Root endpoint
@app.get("/")
def root():
    return {"message": "Backend is running"}

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    logger.info(f"✅ Full webhook data: {data}")

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        phone = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        logger.info(f"📩 User message: {message}")

        # 🔥 AUTO REPLY
        url = "https://graph.facebook.com/v25.0/1092704950586369/messages"

        headers = {
            "Authorization": "Bearer EAANlNNTUN00BRIsH7bgeLZATd3EGS72AHLjPOld7aZAEFWELeU9kARmkH1UzrlKDoR2LOA6kKN6q1DMrbCsJXBhQpyAVVBt1wHpB51koITbzNUyWw0AeGle1i111FzkGN3UWmmRmXKBkAuSGP9hqblppa5apmzu8WcsvOzTF3jyfEDc2Sb1BryZALojSS64tUpNCFRpKc1wHZCwpySNzXBugP74BW7Y6aa10GW38irZBEEm2n5Bz4Nac1dS7PZAIbivfZCcAdNCHGOm7xHu7HpQwKr5AgZDZD",
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

    except Exception as e:
        logger.error(f"❌ Error: {e}")

    return {"status": "received"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == "my_secret_token":
        return int(hub_challenge)

    return {"error": "Verification failed"}