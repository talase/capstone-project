import os
import re
import time
import random
import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

# =====================================================================
# .ENV LOADER
# =====================================================================
def load_dotenv():
    """Manually parse .env file to populate os.environ if it exists."""
    current = Path(__file__).resolve().parent
    for _ in range(4):
        dotenv_path = current / ".env"
        if dotenv_path.exists():
            print(f"Loading environment from {dotenv_path}")
            for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val
            break
        current = current.parent

load_dotenv()

# =====================================================================
# CONFIGURATION
# =====================================================================
# Set TEST_RUN = True to generate only 50 messages per combination/task (for testing).
# Set TEST_RUN = False for full generation.
TEST_RUN = False

BATCH_SIZE = 50

# Non-uniform distribution per combination size (for full run)
MESSAGES_PER_COMBO_SIZE_FULL = {
    1: 2000,
    2: 800,
    3: 300,
    4: 200,
    5: 200,
    6: 100,
    7: 100,
}

# In test mode every combination/task gets exactly 50 messages
MESSAGES_PER_COMBO_SIZE_TEST = {k: 50 for k in range(1, 8)}

MESSAGES_PER_COMBO_SIZE = MESSAGES_PER_COMBO_SIZE_TEST if TEST_RUN else MESSAGES_PER_COMBO_SIZE_FULL

# Normal chat target totals
NORMAL_CHAT_TARGET_FULL = 18_000
NORMAL_CHAT_TARGET_TEST = 50
NORMAL_CHAT_TARGET = NORMAL_CHAT_TARGET_TEST if TEST_RUN else NORMAL_CHAT_TARGET_FULL

MAX_WORKERS = 128
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

TEMPERATURE = 1.2

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 3

OUTPUT_DIR = Path("dataset_v3")
COMBINED_CSV_FILENAME = "combined_dataset.csv"

# =====================================================================
# INTENT CLASS DEFINITIONS (description + key_signals, NO subtypes)
# =====================================================================
CLASSES_DATA = {
    "money_request": {
        "description": (
            "Messages where the sender asks for money, payment, a transfer, financial help, "
            "a refund, debt repayment, a donation, or for someone to cover a cost. "
            "The sender must be actively requesting financial help — not just mentioning money."
        ),
        "key_signals": [
            "lend me", "borrow", "pay me back", "transfer", "send money", "cover my share",
            "IBAN", "PayPal", "cash app", "I'm broke", "can you spot me", "float me",
            "invoice", "refund", "split the bill", "owe me", "need cash", "short on money",
            "donation", "chip in", "I'll pay you back", "venmo", "zelle", "wire",
            "send me", "can you pay", "sort me out", "quick loan", "debt",
        ],
    },
    "agreement_confirmation": {
        "description": (
            "Messages asking the user to sign, confirm, approve, accept, authorize, agree to, "
            "or give consent to an agreement, contract, legal document, business deal, "
            "financial arrangement, responsibility, liability, or purchase terms. "
            "The sender must be asking for a binding commitment — not just discussing terms."
        ),
        "key_signals": [
            "sign", "approve", "confirm", "accept", "authorize", "agree to", "consent",
            "contract", "agreement", "terms", "NDA", "legal document", "binding",
            "give your approval", "click accept", "signature", "co-sign", "ratify",
            "acknowledge", "tick the box", "acknowledge receipt", "agree to the terms",
            "formal agreement", "liability", "waiver", "countersign",
        ],
    },
    "book_or_reschedule_meeting": {
        "description": (
            "Messages asking the user or agent to schedule, book, arrange, set up, plan, "
            "move, postpone, reschedule, shift, delay, cancel-and-rebook, confirm a new time for, "
            "or coordinate a meeting, call, appointment, interview, session, consultation, demo, or event. "
            "The sender must be requesting that a time be set or changed — not just discussing a meeting."
        ),
        "key_signals": [
            "schedule", "book", "set up", "arrange", "block your calendar", "reschedule",
            "postpone", "move the meeting", "push back", "bring forward", "find a slot",
            "calendar invite", "Zoom call", "Teams call", "Google Meet", "free time",
            "available", "sync", "check your availability", "pick a time", "propose a time",
            "appointment", "slot", "session", "interview time", "meet up", "catch up",
        ],
    },
    "emergency_response": {
        "description": (
            "Messages reporting or requesting help for an urgent emergency where immediate attention, "
            "safety action, medical support, police/fire/ambulance contact, rescue, or crisis response is needed. "
            "The message must convey real urgency and danger — not a past story or casual mention."
        ),
        "key_signals": [
            "help me", "call 911", "call an ambulance", "call the police", "emergency", "SOS",
            "I'm trapped", "can't breathe", "bleeding", "fire", "gas leak", "collapse",
            "unconscious", "stuck", "please hurry", "send someone", "danger", "accident",
            "heart attack", "seizure", "I need help now", "come quickly", "ASAP", "hurry",
            "locked in", "she fainted", "he's not responding", "crash", "someone broke in",
        ],
    },
    "request_sending_non_sensitive_file": {
        "description": (
            "Messages asking the user or agent to send, share, attach, upload, forward, resend, "
            "submit, or provide a non-sensitive file or digital attachment such as lecture slides, "
            "general documents, creative assets, or public templates. "
            "The sender must be asking someone to actually send or share the file."
        ),
        "key_signals": [
            "send me", "share the file", "attach", "forward", "upload", "drop the link",
            "can you send", "resend", "zip it and send", "send the slides", "send the PDF",
            "share the doc", "Google Drive link", "SharePoint", "WhatsApp the file",
            "send it over", "drop it in the chat", "send the report", "can you share",
            "the notes", "the presentation", "the template", "the spreadsheet", "the CSV",
        ],
    },
    "request_sending_sensitive_file": {
        "description": (
            "Messages asking the user or agent to send, share, attach, upload, forward, submit, "
            "resend, or provide a sensitive file or digital attachment containing private identity "
            "documents, medical data, financial reports, credentials, or personal records. "
            "The sender must be asking someone to actually send or share the sensitive file."
        ),
        "key_signals": [
            "send your ID", "passport scan", "national ID", "bank statement", "salary slip",
            "payslip", "tax return", "signed contract", "NDA scan", "medical report",
            "lab results", "prescription", "send the document", "API key", "password file",
            "SSH key", "send your credentials", "insurance form", "send your visa",
            "copy of your ID", "proof of income", "employment letter", "transcript",
        ],
    },
    "request_to_send_message_to_someone_else": {
        "description": (
            "Messages asking the user or agent to send, forward, reply, text, email, notify, "
            "inform, remind, or pass a message to another person, group, team, client, manager, "
            "friend, or contact. The sender must be asking the recipient to communicate on their behalf."
        ),
        "key_signals": [
            "tell him", "let her know", "message them", "text her", "email him",
            "notify the team", "remind her", "forward this to", "pass it on",
            "send this to", "inform him", "relay this", "let them know",
            "on my behalf", "can you tell", "shoot them a message", "drop him a text",
            "contact the group", "update the client", "send an email to", "ping them",
        ],
    },
}

ALL_CLASSES = list(CLASSES_DATA.keys())

# Desired CSV column order
CSV_COLUMNS = [
    "text",
    "agreement_confirmation",
    "book_or_reschedule_meeting",
    "emergency_response",
    "money_request",
    "request_sending_non_sensitive_file",
    "request_sending_sensitive_file",
    "request_to_send_message_to_someone_else",
]

# =====================================================================
# SCENARIO SEED GENERATOR
# =====================================================================
_RELATIONSHIPS = [
    "friend", "close friend", "older sibling", "younger sibling", "parent", "child",
    "roommate", "coworker", "boss", "employee", "client", "supplier", "landlord",
    "tenant", "classmate", "professor", "study partner", "neighbor", "cousin",
    "partner/significant other", "ex", "acquaintance", "stranger in a group chat",
    "group chat member", "team lead", "intern",
]

_SETTINGS = [
    "at work", "in university", "at home", "at a hospital", "while traveling",
    "in a café", "commuting on public transport", "at a party", "on vacation",
    "during exam season", "working remotely", "during a road trip", "late at night",
    "early morning", "during Ramadan", "at the gym", "in a waiting room",
    "during a busy workday", "on a weekend", "during a job search",
]

_EMOTIONS = [
    "stressed", "chill and relaxed", "angry", "desperate", "cheerful", "exhausted",
    "embarrassed", "panicked", "bored", "guilt-tripping", "apologetic", "excited",
    "annoyed", "anxious", "frustrated", "happy", "hesitant", "nervous", "confused",
]

_URGENCY = [
    "very urgent", "semi-urgent", "not urgent at all", "casual", "deadline-driven",
    "last-minute", "planned ahead", "completely spontaneous",
]

def generate_scenario_seed():
    """Return a short randomized scenario description."""
    rel = random.choice(_RELATIONSHIPS)
    setting = random.choice(_SETTINGS)
    emotion = random.choice(_EMOTIONS)
    urgency = random.choice(_URGENCY)
    return f"A {emotion} {rel} {setting}, {urgency} situation"


# =====================================================================
# PROMPT BUILDERS
# =====================================================================
_RANDOMNESS_BLOCK = """
CRITICAL RANDOMNESS RULES — Make every single message feel like a DIFFERENT real person typed it:
- TONE: randomly vary across angry, chill, sarcastic, panicked, professional, passive-aggressive, sweet, blunt, awkward, pleading
- FORMALITY: some messages should be formal business English, some extremely casual slang, some broken grammar
- PUNCTUATION: some with perfect punctuation, some with ZERO punctuation at all, some with excessive !!! or ..., random mid-sentence commas
- SPELLING: at least 20% of messages should have realistic typos and abbreviations — ur, pls, tmrw, omw, gonna, wanna, ngl, teh, recieve, snd, cn u, lmk, asap, rn, brb, imo
- CASING: mix proper case, ALL CAPS for emphasis, all lowercase, rAnDoM casing — do not always use proper sentence case
- LENGTH: vary wildly within the batch — some messages should be 3-5 words, some 10-15 words, some 30+ words
- OPENERS: vary how messages start — "hey", "yo", "bro", "listen", straight into the request, "hi", "hello there", mid-thought, "so basically", "ok so", nothing at all, emoji only opener
- FILLER WORDS: randomly sprinkle "like", "basically", "honestly", "ngl", "lowkey", "fr", "idk", "tbh", "lol", "haha", "omg", "wait"
- WHATSAPP QUIRKS: some should reference voice notes ("was gonna send a voice note but"), forwarded-style, "I just saw your message", reply-to-previous style, "wdym", "???", "seen ✓✓", "can u check ur whatsapp"
- EMOTIONAL STATE: vary — stressed, excited, guilt-tripping, cheerful, exhausted, annoyed, desperate, casual, embarrassed, matter-of-fact

ANTI-REPETITION RULES:
- Do NOT start more than 2 messages with the same word
- Do NOT reuse the same sentence structure more than once
- Vary message length wildly — do not make them all the same length
- Each message should feel like it came from a completely different person in a completely different situation

FORMAT RULES:
- Output plain text only — one message per line
- No numbering, no bullets, no dashes at the start
- No quotation marks around messages
- No explanations or commentary
- English only (no Arabic, Turkish, or other languages)
""".strip()


def build_combination_prompt(combo, batch_count):
    """Build the v3 prompt for a given combination of intents."""
    num_intents = len(combo)
    seed = generate_scenario_seed()

    # Active intents block
    active_block = ""
    for idx, class_name in enumerate(combo, 1):
        info = CLASSES_DATA[class_name]
        # Pick 5–8 random key signals to show (keeps prompts varied across batches)
        num_signals = min(len(info["key_signals"]), random.randint(5, 8))
        signals = random.sample(info["key_signals"], num_signals)
        signals_str = ", ".join(f'"{s}"' for s in signals)
        active_block += (
            f"\n{idx}. {class_name.upper().replace('_', ' ')}\n"
            f"   What it means: {info['description']}\n"
            f"   Example signal words/phrases (pick some, vary them, don't overuse): {signals_str}\n"
        )

    # Inactive intents block
    inactive_classes = [c for c in ALL_CLASSES if c not in combo]
    inactive_block = ""
    if inactive_classes:
        inactive_block = "\nINACTIVE INTENTS — messages MUST NOT contain or trigger any of these:\n"
        _negative_hints = {
            "money_request": "do not ask for money, payments, loans, transfers, or to cover expenses",
            "agreement_confirmation": "do not ask to sign, confirm, approve, or consent to any agreement",
            "book_or_reschedule_meeting": "do not ask to book, schedule, reschedule, or coordinate any meeting or call",
            "emergency_response": "do not report medical, accident, fire, or safety emergencies",
            "request_sending_non_sensitive_file": "do not ask to send, share, or upload general slides, reports, or non-sensitive files",
            "request_sending_sensitive_file": "do not ask to send, share, or upload IDs, passports, bank statements, or sensitive credentials",
            "request_to_send_message_to_someone_else": "do not ask to text, email, notify, or relay a message to another person",
        }
        for c in inactive_classes:
            inactive_block += f"- NO {c.replace('_', ' ')}: {_negative_hints[c]}\n"

    # Combination guidance
    if num_intents > 1:
        combo_guidance = (
            f"Every single message MUST satisfy ALL {num_intents} active intents simultaneously. "
            "Do NOT write separate messages for each intent. "
            "All requested actions must naturally co-exist within the same message text."
        )
    else:
        combo_guidance = (
            f"Every single message MUST satisfy the '{combo[0]}' intent. "
            "The intent must be clearly present — the message must actually perform the described action."
        )

    prompt = f"""Generate {batch_count} unique realistic WhatsApp-style chat messages for a multi-label intent classification dataset.

SCENARIO SEED (use as loose inspiration — not a rigid template):
{seed}

TASK: {combo_guidance}

ACTIVE INTENTS (every message MUST genuinely contain ALL of these):
{active_block.strip()}

CLASS PRESENCE RULE — CRITICAL:
Every message MUST actually perform / request the action described by EACH active intent.
The intent can be expressed very explicitly (obvious request) or more subtly/indirectly — but it MUST always be present and clearly identifiable. Do not generate messages where the intent is absent or only vaguely implied.
{inactive_block.strip()}

{_RANDOMNESS_BLOCK}"""
    return prompt


def build_normal_chat_prompt(batch_count):
    """Build the v3 prompt for normal chat messages."""
    seed = generate_scenario_seed()

    prompt = f"""Generate {batch_count} unique realistic WhatsApp-style chat messages for an intent classification dataset.

SCENARIO SEED (use as loose inspiration — not a rigid template):
{seed}

WHAT THESE MESSAGES ARE:
These are "normal_chat" messages — everyday human conversation that does NOT ask anyone to perform any specific action. They are regular, natural chat messages.

TYPES OF MESSAGES TO GENERATE (mix these freely):
- Casual greetings, check-ins, small talk ("hey what's up", "how's it going", "miss you man")
- Daily life updates (food, weather, commute, hobbies, errands, weekend plans)
- Opinions, advice-giving, recommendations (without making an action request)
- Jokes, memes, reactions, teasing, banter, sarcasm
- Emotional support, sharing feelings, venting, encouragement
- Status updates ("I'm busy rn", "just got home", "omw")
- Thanks, apologies, polite replies, acknowledgments
- General questions and curiosity ("what time does it open?", "do you know if...")
- Work/school chat that doesn't request any action
- Gossip, sharing news, reacting to something

IMPORTANT — NEGATIVE EXAMPLES (include these throughout — about 30-40% of messages):
These mention action-related topics but MUST NOT actually request the action.
This is critical: the message must feel like normal chat even when touching these topics.

- MONEY mentioned but NOT a money request: Talk about prices, salary, rent, spending, budgets — but do NOT ask for money or payment.
  Good: "rent went up again ugh", "I spent like 200 on groceries wtf", "did you see how expensive flights are rn"
  Bad: "can you send me 200 for rent" (this IS a money request — do NOT generate this)

- MEETING mentioned but NOT a scheduling request: Mention meetings, calls, appointments — but do NOT ask to book or reschedule.
  Good: "that meeting was so long omg", "I have a dentist thing tomorrow", "the zoom kept freezing lol"
  Bad: "can we reschedule our meeting to Thursday" (this IS a scheduling request — do NOT generate this)

- FILE mentioned but NOT a file request: Mention documents, slides, photos — but do NOT ask anyone to send or share them.
  Good: "I finally finished the presentation", "that photo from yesterday was so funny", "the report looks good"
  Bad: "can you send me the slides" (this IS a file request — do NOT generate this)

- EMERGENCY mentioned but NOT an emergency: Mention health, accidents, hospitals — in a past-tense, casual, or storytelling way.
  Good: "I had a minor fender bender last week lol", "my headache finally went away", "remember the fire alarm in class haha"
  Bad: "I'm having a heart attack help" (this IS an emergency — do NOT generate this)

- AGREEMENT/CONTRACT mentioned but NOT an approval request: Mention contracts or terms without asking to sign or approve.
  Good: "I read the lease and honestly it's confusing", "the new company policy is kind of strict ngl"
  Bad: "please sign the contract today" (this IS an agreement request — do NOT generate this)

- SENDING A MESSAGE mentioned but NOT a message-relay request: Talk about texts/emails without asking to forward or send them.
  Good: "did she ever text you back", "I haven't checked my email yet lol", "his reply was so unexpected"
  Bad: "can you text Ahmed and let him know" (this IS a message relay request — do NOT generate this)

- SENSITIVE DOCUMENT mentioned but NOT a request to send it: Mention passports, IDs, bank documents casually.
  Good: "I need to renew my passport soon", "lost my bank card ugh", "my ID photo is embarrassing"
  Bad: "please send me a scan of your passport" (this IS a sensitive file request — do NOT generate this)

{_RANDOMNESS_BLOCK}"""
    return prompt


# =====================================================================
# API CLIENT + CALL
# =====================================================================
def create_client():
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"Missing API key. Set the {API_KEY_ENV} environment variable.")
    return OpenAI(api_key=api_key, base_url=BASE_URL)


def call_model(client, prompt):
    """Call the model with retry handling."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate clean plain-text training data for a multi-label intent "
                            "classification system. Follow all formatting and content rules exactly. "
                            "Output ONLY the messages — no commentary, no numbering, no bullets."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=4000,
                extra_body={
                    "provider": {
                        "only": ["deepseek"],
                        "allow_fallbacks": False,
                    }
                },
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            print(f"  API attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError(f"API call failed after {MAX_RETRIES} attempts: {last_error}")


# =====================================================================
# TEXT CLEANING + FILTERING
# =====================================================================
def clean_line(line):
    line = line.strip()
    line = re.sub(r"^\s*(?:[-*\u2022]+|\d+[\).\:-]?)\s*", "", line)
    line = line.replace("\u201c", "").replace("\u201d", "").replace('"', "")
    line = line.replace("\u2018", "'").replace("\u2019", "'")
    line = line.strip().strip("'").strip()
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_assistant_explanation(line):
    normalized = line.strip().lower().rstrip(":")
    prefixes = (
        "here are", "sure, here are", "below are", "these are",
        "i generated", "the messages are", "here is", "sure",
        "of course", "certainly", "happy to", "as requested",
    )
    return normalized.startswith(prefixes)


def is_valid_message(message):
    if len(message.strip()) < 4:
        return False
    normalized = message.lower()
    bad_phrases = (
        "step by step", "instructions", "how to", "recipe for",
        "method to", "json", "label:", "intent:", "subtype:",
        "active intent", "inactive intent", "scenario seed",
    )
    if any(p in normalized for p in bad_phrases):
        return False
    # Reject obvious non-English characters
    if re.search(
        r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff"
        r"\u00e7\u011f\u0131\u00f6\u015f\u00fc"
        r"\u00c7\u011e\u0130\u00d6\u015e\u00dc]",
        message,
    ):
        return False
    return True


def clean_messages(raw_text, seen_messages, max_new=None):
    cleaned = []
    for raw_line in raw_text.splitlines():
        if is_assistant_explanation(raw_line):
            continue
        msg = clean_line(raw_line)
        if not msg or not is_valid_message(msg):
            continue
        dedup_key = re.sub(r"\s+", " ", msg.strip().lower())
        if dedup_key in seen_messages:
            continue
        seen_messages.add(dedup_key)
        cleaned.append(msg)
        if max_new is not None and len(cleaned) >= max_new:
            break
    return cleaned


# =====================================================================
# COMBINATION GENERATION
# =====================================================================
def get_all_combinations():
    """Generate all 127 non-empty subsets of the 7 intent classes."""
    combos = []
    n = len(ALL_CLASSES)
    for i in range(1, 1 << n):
        combo = [ALL_CLASSES[j] for j in range(n) if (i >> j) & 1]
        combos.append(combo)
    return combos


def process_combination(combo_idx, combo, client, total_combos):
    """Generate messages for one combination of intents."""
    target = MESSAGES_PER_COMBO_SIZE[len(combo)]
    combo_name = "__".join(sorted(combo))
    filepath = OUTPUT_DIR / f"{combo_name}.txt"

    label = f"[COMBO {combo_idx}/{total_combos}]"
    print(f"{label} Start: {combo_name} (target={target})")

    # Resume from existing file
    seen_messages = set()
    messages = []
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            c = clean_line(line)
            if c and is_valid_message(c):
                seen_messages.add(re.sub(r"\s+", " ", c.lower()))
                messages.append(c)
        if len(messages) >= target:
            print(f"{label} Already complete: {combo_name} ({len(messages)} msgs)")
            return combo, messages, "combo"
        print(f"{label} Resuming: {combo_name} ({len(messages)}/{target} loaded)")

    attempts = 0
    max_attempts = 5 if TEST_RUN else 60

    while len(messages) < target:
        attempts += 1
        if attempts > max_attempts:
            print(f"{label} Max attempts reached for {combo_name}. Collected {len(messages)}/{target}")
            break
        remaining = target - len(messages)
        batch_count = min(BATCH_SIZE, remaining)
        prompt = build_combination_prompt(combo, batch_count)
        try:
            raw = call_model(client, prompt)
            new_msgs = clean_messages(raw, seen_messages, max_new=remaining)
            messages.extend(new_msgs)
            filepath.write_text("\n".join(messages) + "\n", encoding="utf-8")
            print(f"{label} {combo_name} batch {attempts}: +{len(new_msgs)} → {len(messages)}/{target}")
        except Exception as e:
            print(f"{label} Error batch {attempts}: {e}")
            time.sleep(2)

    return combo, messages, "combo"


# =====================================================================
# NORMAL CHAT GENERATION
# =====================================================================
def process_normal_chat(client):
    """Generate all normal_chat messages in a single task."""
    target = NORMAL_CHAT_TARGET
    filepath = OUTPUT_DIR / "normal_chat.txt"

    label = "[NORMAL CHAT]"
    print(f"{label} Start (target={target})")

    seen_messages = set()
    messages = []
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            c = clean_line(line)
            if c and is_valid_message(c):
                seen_messages.add(re.sub(r"\s+", " ", c.lower()))
                messages.append(c)
        if len(messages) >= target:
            print(f"{label} Already complete ({len(messages)} msgs)")
            return messages
        print(f"{label} Resuming ({len(messages)}/{target} loaded)")

    attempts = 0
    max_attempts = 5 if TEST_RUN else 500

    while len(messages) < target:
        attempts += 1
        if attempts > max_attempts:
            print(f"{label} Max attempts reached. Collected {len(messages)}/{target}")
            break
        remaining = target - len(messages)
        batch_count = min(BATCH_SIZE, remaining)
        prompt = build_normal_chat_prompt(batch_count)
        try:
            raw = call_model(client, prompt)
            new_msgs = clean_messages(raw, seen_messages, max_new=remaining)
            messages.extend(new_msgs)
            filepath.write_text("\n".join(messages) + "\n", encoding="utf-8")
            print(f"{label} Batch {attempts}: +{len(new_msgs)} → {len(messages)}/{target}")
        except Exception as e:
            print(f"{label} Error batch {attempts}: {e}")
            time.sleep(2)

    return messages


# =====================================================================
# MAIN
# =====================================================================
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = create_client()
    combinations = get_all_combinations()
    total_combos = len(combinations)

    # Calculate expected totals
    total_combo_msgs = sum(MESSAGES_PER_COMBO_SIZE[len(c)] for c in combinations)
    grand_total = total_combo_msgs + NORMAL_CHAT_TARGET

    print("=" * 65)
    print("  Synthetic Data Generation V3")
    print(f"  Mode: {'TEST RUN (50 per task)' if TEST_RUN else 'FULL RUN'}")
    print(f"  Classes: {len(ALL_CLASSES)}  |  Combinations: {total_combos}")
    print(f"  Temperature: {TEMPERATURE}")
    print(f"  Distribution: {MESSAGES_PER_COMBO_SIZE}")
    print(f"  Normal chat target: {NORMAL_CHAT_TARGET}")
    print(f"  Expected grand total: ~{grand_total:,}")
    print("=" * 65)

    all_combo_data = []
    normal_chat_messages = []

    # Run combinations + normal chat in parallel
    # Normal chat runs as one "worker" alongside the combination workers
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all combination tasks
        futures = {
            executor.submit(process_combination, idx, combo, client, total_combos): (idx, combo)
            for idx, combo in enumerate(combinations, start=1)
        }
        # Submit normal chat as one task
        normal_future = executor.submit(process_normal_chat, client)
        futures[normal_future] = (-1, None)  # sentinel

        for future in as_completed(futures):
            idx, combo = futures[future]
            if combo is None:
                # Normal chat result
                try:
                    normal_chat_messages = future.result()
                    print(f"[NORMAL CHAT] Completed: {len(normal_chat_messages)} messages")
                except Exception as e:
                    print(f"[NORMAL CHAT] Exception: {e}")
            else:
                combo_name = "__".join(sorted(combo))
                try:
                    combo, messages, _ = future.result()
                    print(f"[COMBO {idx}/{total_combos}] Done: {combo_name} ({len(messages)} msgs)")
                    for msg in messages:
                        row = {"text": msg}
                        for c in ALL_CLASSES:
                            row[c] = 1 if c in combo else 0
                        all_combo_data.append(row)
                except Exception as e:
                    print(f"[COMBO {idx}/{total_combos}] Exception for {combo_name}: {e}")

    # Build combined CSV
    all_data = []

    # Add combination rows
    all_data.extend(all_combo_data)

    # Add normal chat rows (all labels = 0)
    for msg in normal_chat_messages:
        row = {"text": msg}
        for c in ALL_CLASSES:
            row[c] = 0
        all_data.append(row)

    if not all_data:
        print("No data generated.")
        return

    # Shuffle
    random.shuffle(all_data)

    # Write combined CSV
    csv_path = OUTPUT_DIR / COMBINED_CSV_FILENAME
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_data)

    print("\n" + "=" * 65)
    print("  GENERATION COMPLETE")
    print(f"  Combination messages : {len(all_combo_data):,}")
    print(f"  Normal chat messages : {len(normal_chat_messages):,}")
    print(f"  Total rows in CSV    : {len(all_data):,}")
    print(f"  Saved to             : {csv_path}")
    print("=" * 65)

    # Preview first 3 rows
    print("\nFirst 3 rows:")
    for row in all_data[:3]:
        print(f"  {row}")


if __name__ == "__main__":
    main()
