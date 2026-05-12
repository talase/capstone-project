# Style Adaptation / Extract Style Using LLM

This project learns high-level communication style profiles from outgoing WhatsApp-style messages. It does **not** store or imitate raw messages. It extracts abstract traits such as formality, politeness, verbosity, optimism, and a few short behavior patterns.

Architecture:

`Observation Mode -> 50-message Buffer -> LLM Style Extraction -> Global/Contact Profiles -> Confidence Gate -> Styled Reply Generation`

## Install

```bash
cd style_adaptation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure OpenRouter

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
OPENROUTER_API_KEY=your_real_key
```

The preferred location is `style_adaptation/.env`. The code also checks
the workspace `.env` and `.venv/.env`, but the file must contain a normal
`OPENROUTER_API_KEY=...` line.

The code uses the OpenAI SDK as an OpenRouter-compatible client:

- Base URL: `https://openrouter.ai/api/v1`
- Model: `deepseek/deepseek-v4-flash`
- Provider routing: `provider.only = ["deepseek"]`

This project does not use Ollama, Hugging Face, or the OpenAI API directly.

## Generate Synthetic Data

```bash
python src/generate_data.py
```

This creates at least 100 outgoing messages per contact in `data/`:

- `mom.txt`
- `dad.txt`
- `teacher.txt`
- `boss.txt`
- `friend.txt`
- `sister.txt`
- `delivery.txt`

Each file has one synthetic message per line.

## Run Full Pipeline

```bash
python src/main.py
```

The main script:

1. Generates data if files are missing.
2. Simulates observation mode by reading outgoing messages.
3. Buffers messages globally and per contact.
4. Every 50 messages, sends a batch to the LLM for abstract style extraction.
5. Saves profiles in `profiles/`.
6. Runs confidence gating.
7. Generates demo replies for boss, friend, and mom.
8. Saves results in `results/`.

## Run Evaluation

```bash
python src/evaluator.py
```

The evaluator reads saved profiles and writes:

- `results/style_results.json`
- `results/test_summary.csv`

It checks expected behavior:

- Teacher and boss should have high formality.
- Friend and sister should have lower formality and higher optimism.
- Delivery should have low verbosity.
- Mom should have high politeness and warmth-like optimism.

## Profile Schema

Profiles are saved as JSON:

```json
{
  "traits": {
    "formality": {"score": 0.0, "confidence": 0},
    "politeness": {"score": 0.0, "confidence": 0},
    "verbosity": {"score": 0.0, "confidence": 0},
    "optimism": {"score": 0.0, "confidence": 0}
  },
  "patterns": [],
  "overall_confidence": 0,
  "message_count": 0,
  "batch_count": 0
}
```

Confidence values are normalized if the model returns `0.0-1.0` instead of `0-100`. Pattern lists are capped to five short abstract patterns, and quote-like patterns are removed.

## Confidence Gate

The gate selects style mode like this:

- If global confidence is greater than 70 and contact confidence is greater than 70: `global+contact`
- If global confidence is greater than 70 only: `global`
- Otherwise: `neutral`

## Add a New Contact

Add a new file to `data/`, for example:

```text
data/cousin.txt
```

Put one outgoing message per line. The buffer and profile store automatically create `profiles/profile_cousin.json` after enough messages are observed.
