# Tala

Tala is a small FastAPI backend for a WhatsApp Cloud API webhook. It exposes
basic health endpoints, verifies the webhook with Meta, receives incoming
WhatsApp messages, and sends a simple text reply back to the sender.

## Project Structure

```text
Tala/
  app/
    main.py        FastAPI app and WhatsApp webhook handlers
```

## Requirements

Install the project dependencies from the repository root:

```bash
pip install -r requirements.txt
```

The main dependencies used by Tala are:

- `fastapi`
- `uvicorn`
- `requests`
- `python-dotenv`

## Environment Variables

Create a `.env` file in the repository root, or export these variables in your
shell before running the server:

```env
WHATSAPP_TOKEN=your_meta_whatsapp_access_token
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id
WHATSAPP_VERIFY_TOKEN=choose_a_custom_verify_token
```

`WHATSAPP_VERIFY_TOKEN` must match the verify token you enter when configuring
the webhook in the Meta developer dashboard. If it is not set, the app uses
`my_secret_token` by default.

## Run Locally

From the repository root:

```bash
uvicorn Tala.app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

## Endpoints

### `GET /`

Returns a simple status message:

```json
{"message": "Backend is running"}
```

### `GET /health`

Returns a health check response:

```json
{"status": "ok"}
```

### `GET /webhook`

Used by Meta to verify the webhook subscription. The app checks:

- `hub.mode`
- `hub.verify_token`
- `hub.challenge`

If the mode is `subscribe` and the verify token matches
`WHATSAPP_VERIFY_TOKEN`, the app returns the challenge value.

### `POST /webhook`

Receives WhatsApp webhook events. For incoming text messages, the app sends
this reply through the Meta Graph API:

```text
Hello, I got your message!
```

Non-message events are acknowledged with:

```json
{"status": "received"}
```

## Testing With a Public URL

Meta needs a public HTTPS URL for webhook callbacks. During local development,
you can expose your local server with a tunneling tool such as ngrok:

```bash
ngrok http 8000
```

Use the generated HTTPS URL as the callback URL in Meta, with `/webhook`
appended:

```text
https://your-ngrok-url.ngrok-free.app/webhook
```

## Notes

- Keep `.env` files and access tokens out of version control.
- The current reply message is hard-coded in `app/main.py`.
- The app uses Meta Graph API version `v25.0`.
