# Style Adaptation Capstone

This project learns high-level messaging style profiles from synthetic
WhatsApp-style conversations. The data files include both sides of each chat,
while the extractor learns only from outgoing `Me:` lines. It extracts abstract
traits such as formality, politeness, verbosity, and optimism, then uses those
traits to choose a safe reply style.

The system does not store or reuse raw message examples in generated replies.
It saves only summarized style profiles.

## Project Flow

```text
Synthetic contact conversations
-> Observation buffer
-> 50-message style extraction batches
-> Global and per-contact profiles
-> Confidence gate
-> Style-aware response generation
-> Evaluation results
```

## Folder Structure

```text
data/                  Synthetic two-sided contact chat transcripts
src/style_engine.py    Full end-to-end runner and response pipeline
src/style_extractor.py OpenRouter/DeepSeek style extraction
src/buffer.py          Global and per-contact observation buffers
src/profile_store.py   Profile save/load/merge helpers
src/prompt_templates.py Style-specific LLM prompt templates
src/evaluator.py       Checks extracted profiles against expected behavior
src/generate_data.py   Synthetic data generator
app/main.py            FastAPI WhatsApp webhook backend
style_api.py           Optional Flask demo API
profiles/              Generated profile JSON files
results/               Generated evaluation and demo outputs
```

`profiles/` and `results/` are generated when the pipeline runs.

## Setup

From the outer project folder:

```bash
cd style_adaptation
python -m venv .venv
source ".venv/bin/activate"
pip install -r requirements.txt
```

If `requirements.txt` is missing, install the main dependencies manually:

```bash
pip install openai python-dotenv fastapi flask requests uvicorn
```

## Environment Variables

Create `style_adaptation/.env` and add your OpenRouter key:

```env
OPENROUTER_API_KEY=your_openrouter_key_here
WHATSAPP_TOKEN=your_whatsapp_cloud_api_token
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id
WHATSAPP_VERIFY_TOKEN=my_secret_token
```

This project uses the OpenAI Python SDK with OpenRouter's compatible API:

```text
Base URL: https://openrouter.ai/api/v1
Model: deepseek/deepseek-v4-flash
```

`OPENAI_API_KEY` is not enough for this runner unless the value is actually an
OpenRouter key and is copied to `OPENROUTER_API_KEY`.

## Run the Full Pipeline

From the outer folder:

```bash
source "/Users/asmaaabdelgawad/Desktop/style adaption/style_adaptation/.venv/bin/activate"
python "/Users/asmaaabdelgawad/Desktop/style adaption/style_adaptation/src/style_engine.py"
```

Or from inside `style_adaptation/` after activating the environment:

```bash
python src/style_engine.py
```

The runner will:

1. Generate synthetic chat data if any contact files are missing.
2. Read outgoing `Me:` messages from `data/`.
3. Build global and contact-specific style profiles.
4. Save profiles in `profiles/`.
5. Run evaluation checks.
6. Generate demo replies for boss, friend, and mom.
7. Save output files in `results/`.

## Run the Backend

The recommended backend for the WhatsApp/n8n demo is the FastAPI app:

```bash
uvicorn app.main:app --reload --port 8000
```

Useful endpoints:

```text
GET  /health
GET  /webhook    WhatsApp verification endpoint
POST /webhook    WhatsApp incoming-message endpoint
```

`style_api.py` is kept as a smaller optional Flask API for local testing:

```bash
python style_api.py
```

Its `POST /reply` endpoint accepts either `contact` or `contact_id`:

```json
{
  "message": "are you coming today?",
  "contact_id": "friend"
}
```

Example response:

```json
{
  "reply": "...",
  "style_mode": "global_contact",
  "contact_id": "friend",
  "profile_contact": "friend",
  "global_confidence": 90,
  "contact_confidence": 77,
  "generation_status": "generated",
  "llm_error": false
}
```

## Contact Mapping

Saved demo profiles use names such as `friend`, `mom`, and `boss`, but real
WhatsApp webhooks send phone numbers. To map a phone number to a saved profile,
copy `contact_map.example.json` to `contact_map.json` and edit it:

```json
{
  "+15551234567": "friend",
  "905551112233": "mom"
}
```

`contact_map.json` is ignored by git so real phone numbers are not committed.

## Useful Commands

Generate synthetic two-sided chat data:

```bash
python src/generate_data.py
```

Run evaluation after profiles exist:

```bash
python src/evaluator.py
```

Run the style extractor module alone:

```bash
python src/style_extractor.py
```

This last command may print nothing because `style_extractor.py` mainly defines
functions used by `style_engine.py`.

## Outputs

After running `src/style_engine.py`, the project creates:

```text
profiles/profile_global.json
profiles/profile_<contact>.json
results/style_results.json
results/test_summary.csv
results/demo_replies.json
```

These files are generated artifacts and can be deleted before committing.
They are ignored by `.gitignore`; if they were already tracked by git, remove
them from the git index once with:

```bash
git rm --cached -r profiles results
```

## Safety Notes

- Do not commit `.env` or real API keys.
- Do not commit `contact_map.json` because it can contain real phone numbers.
- Do not commit generated caches such as `__pycache__/` or `.pyc` files.
- The data in `data/` is synthetic, which keeps the project suitable for a
  capstone demo without exposing private chats.
