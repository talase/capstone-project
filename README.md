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
-> Demo styled replies
-> Evaluation results
```

## Folder Structure

```text
data/                  Synthetic two-sided contact chat transcripts
src/main.py            Full end-to-end runner
src/style_extractor.py OpenRouter/DeepSeek style extraction
src/buffer.py          Global and per-contact observation buffers
src/profile_store.py   Profile save/load/merge helpers
src/evaluator.py       Checks extracted profiles against expected behavior
src/generate_data.py   Synthetic data generator
profiles/              Generated profile JSON files
results/               Generated evaluation and demo outputs
```

`profiles/` and `results/` are generated when the pipeline runs.

## Setup

From the outer project folder:

```bash
cd style_adaptation
python -m venv ../.venv
source "../.venv/bin/activate"
pip install -r requirements.txt
```

If `requirements.txt` is missing, install the main dependencies manually:

```bash
pip install openai python-dotenv
```

## Environment Variables

Create `style_adaptation/.env` and add your OpenRouter key:

```env
OPENROUTER_API_KEY=your_openrouter_key_here
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
source "/Users/asmaaabdelgawad/Desktop/style adaption/.venv/bin/activate"
"/Users/asmaaabdelgawad/Desktop/style adaption/.venv/bin/python" \
"/Users/asmaaabdelgawad/Desktop/style adaption/style_adaptation/src/main.py"
```

Or from inside `style_adaptation/` after activating the environment:

```bash
python src/main.py
```

The runner will:

1. Generate synthetic chat data if any contact files are missing.
2. Read outgoing `Me:` messages from `data/`.
3. Build global and contact-specific style profiles.
4. Save profiles in `profiles/`.
5. Run evaluation checks.
6. Generate demo replies for boss, friend, and mom.
7. Save output files in `results/`.

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
functions used by `main.py`.

## Outputs

After running `src/main.py`, the project creates:

```text
profiles/profile_global.json
profiles/profile_<contact>.json
results/style_results.json
results/test_summary.csv
results/demo_replies.json
```

These files are generated artifacts and can be deleted before committing.

## Safety Notes

- Do not commit `.env` or real API keys.
- Do not commit generated caches such as `__pycache__/` or `.pyc` files.
- The data in `data/` is synthetic, which keeps the project suitable for a
  capstone demo without exposing private chats.
