"""
Style Learning System — Capstone Implementation
Matches the architecture from Figure 4:
  - Observation mode with 50-message batching
  - Global profile + per-contact profiles
  - Confidence-weighted profile merging
  - Three-tier style gating: Global+Contact / Global Only / Neutral
"""

import json
import os
import requests
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────

MODEL_NAME   = "mistral"
OLLAMA_URL   = "http://localhost:11434/api/generate"
BATCH_SIZE   = 50          # messages per style learning update
CONFIDENCE_GATE = 70.0     # threshold for activating style (matches proposal)

TRAIT_DEFAULTS = {
    "formality":  {"score": 0.5, "confidence": 0},
    "politeness": {"score": 0.5, "confidence": 0},
    "verbosity":  {"score": 0.5, "confidence": 0},
    "optimism":   {"score": 0.5, "confidence": 0},
}

# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class StyleProfile:
    """
    Abstract representation of a user's communication style.
    Intentionally high-level — not raw message imitation.
    """
    traits:             dict  = field(default_factory=lambda: dict(TRAIT_DEFAULTS))
    patterns:           list  = field(default_factory=list)
    overall_confidence: float = 0.0
    message_count:      int   = 0     # how many messages have contributed to this profile
    batch_count:        int   = 0     # how many 50-message batches have been processed

    def is_confident(self) -> bool:
        return self.overall_confidence > CONFIDENCE_GATE

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StyleProfile":
        p = cls()
        p.traits             = d.get("traits",             dict(TRAIT_DEFAULTS))
        p.patterns           = d.get("patterns",           [])
        p.overall_confidence = d.get("overall_confidence", 0.0)
        p.message_count      = d.get("message_count",      0)
        p.batch_count        = d.get("batch_count",        0)
        return p

    def merge(self, new: "StyleProfile") -> None:
        """
        Confidence-weighted merge: older profile keeps more weight when
        confidence is already high, giving new batches diminishing influence.
        This prevents a single atypical batch from wiping learned history.
        """
        old_weight = min(self.batch_count, 9) / 10    # caps at 0.9
        new_weight = 1.0 - old_weight

        for trait in self.traits:
            if trait not in new.traits:
                continue
            old_t = self.traits[trait]
            new_t = new.traits[trait]
            old_t["score"] = (
                old_weight * old_t["score"] +
                new_weight * new_t["score"]
            )
            old_t["confidence"] = (
                old_weight * old_t["confidence"] +
                new_weight * new_t["confidence"]
            )

        self.overall_confidence = (
            old_weight * self.overall_confidence +
            new_weight * new.overall_confidence
        )
        # Merge patterns: keep unique patterns (most recent wins on duplicates)
        existing = set(self.patterns)
        for p in new.patterns:
            if p not in existing:
                self.patterns.append(p)
                existing.add(p)

        self.batch_count   += 1
        self.message_count += new.message_count


# ── LLM interface ────────────────────────────────────────────────────────────

def _ask_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except requests.RequestException as e:
        print(f"[WARN] LLM call failed: {e}")
        return ""


def _parse_json(raw: str) -> Optional[dict]:
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None


# ── Core extraction ───────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a writing style analysis model. 
Analyze the OUTGOING messages below and return ONLY valid JSON matching this schema exactly:

{{
  "traits": {{
    "formality":   {{"score": 0.0, "confidence": 0}},
    "politeness":  {{"score": 0.0, "confidence": 0}},
    "verbosity":   {{"score": 0.0, "confidence": 0}},
    "optimism":    {{"score": 0.0, "confidence": 0}}
  }},
  "patterns": [],
  "overall_confidence": 0
}}

Rules:
- score: 0.0 (lowest) to 1.0 (highest)
- confidence: 0–100 (how sure you are, given the evidence)
- patterns: 2–5 short strings describing recurring stylistic habits (no direct quotes)
- overall_confidence: weighted average across traits
- Return JSON ONLY — no preamble, no markdown fences

Messages (outgoing, batch of {count}):
{messages}
"""

def extract_style_from_batch(messages: list[str]) -> StyleProfile:
    """
    Run the style learning model on a single batch of messages.
    Returns a fresh StyleProfile representing this batch only.
    """
    text   = "\n".join(f"- {m}" for m in messages)
    prompt = EXTRACTION_PROMPT.format(count=len(messages), messages=text)
    raw    = _ask_ollama(prompt)
    data   = _parse_json(raw)

    profile = StyleProfile()
    profile.message_count = len(messages)

    if data is None:
        print("[WARN] Could not parse LLM output — returning zero-confidence profile")
        return profile

    profile.traits             = data.get("traits",             dict(TRAIT_DEFAULTS))
    profile.patterns           = data.get("patterns",           [])
    profile.overall_confidence = float(data.get("overall_confidence", 0))
    return profile


# ── Profile store ─────────────────────────────────────────────────────────────

class ProfileStore:
    """
    Persistent key-value store for style profiles.
    'global' key holds the aggregate global profile.
    Any other key is treated as a contact identifier.
    """

    def __init__(self, directory: str = "."):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = key.replace(" ", "_").replace("/", "_")
        return os.path.join(self.directory, f"profile_{safe}.json")

    def load(self, key: str) -> StyleProfile:
        path = self._path(key)
        if not os.path.exists(path):
            return StyleProfile()
        with open(path) as f:
            return StyleProfile.from_dict(json.load(f))

    def save(self, key: str, profile: StyleProfile) -> None:
        with open(self._path(key), "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def update(self, key: str, new_batch: StyleProfile) -> StyleProfile:
        """Load existing → merge → save → return merged profile."""
        existing = self.load(key)
        existing.merge(new_batch)
        self.save(key, existing)
        return existing


# ── Buffer / Observation mode ─────────────────────────────────────────────────

class MessageBuffer:
    """
    Accumulates outgoing messages. Every BATCH_SIZE messages, fires a style
    learning update. Mirrors the 'Observation Mode' from Figure 4.
    """

    def __init__(self, store: ProfileStore, batch_size: int = BATCH_SIZE):
        self.store      = store
        self.batch_size = batch_size
        self._global_buf: list[str]                  = []
        self._contact_buf: dict[str, list[str]]      = {}

    def add_message(self, text: str, contact: Optional[str] = None) -> None:
        """
        Record an outgoing message. Triggers learning automatically when
        the batch fills. Both global and per-contact buffers are maintained.
        """
        self._global_buf.append(text)
        if contact:
            self._contact_buf.setdefault(contact, []).append(text)

        if len(self._global_buf) >= self.batch_size:
            self._process_global()

        if contact and len(self._contact_buf.get(contact, [])) >= self.batch_size:
            self._process_contact(contact)

    def _process_global(self) -> None:
        batch = self._global_buf[:self.batch_size]
        self._global_buf = self._global_buf[self.batch_size:]
        print(f"[INFO] Processing global batch ({len(batch)} messages)...")
        new_profile = extract_style_from_batch(batch)
        merged = self.store.update("global", new_profile)
        print(f"[INFO] Global confidence: {merged.overall_confidence:.1f}%")

    def _process_contact(self, contact: str) -> None:
        batch = self._contact_buf[contact][:self.batch_size]
        self._contact_buf[contact] = self._contact_buf[contact][self.batch_size:]
        print(f"[INFO] Processing contact '{contact}' batch ({len(batch)} messages)...")
        new_profile = extract_style_from_batch(batch)
        merged = self.store.update(contact, new_profile)
        print(f"[INFO] Contact '{contact}' confidence: {merged.overall_confidence:.1f}%")

    @property
    def global_buffer_size(self) -> int:
        return len(self._global_buf)

    def contact_buffer_size(self, contact: str) -> int:
        return len(self._contact_buf.get(contact, []))


# ── Style retriever / gating logic ────────────────────────────────────────────

class StyleProfilesRetriever:
    """
    Implements the three-tier logic gate from Figure 4:
      Global confidence > 70% AND Contact confidence > 70% → Global + Contact
      Global confidence > 70% only                         → Global Only
      Otherwise                                            → Neutral fallback
    """

    def __init__(self, store: ProfileStore):
        self.store = store

    def get_style_mode(self, contact: Optional[str] = None) -> str:
        global_p  = self.store.load("global")
        contact_p = self.store.load(contact) if contact else StyleProfile()

        if global_p.is_confident() and contact_p.is_confident():
            return "global+contact"
        elif global_p.is_confident():
            return "global"
        else:
            return "neutral"

    def get_profiles(self, contact: Optional[str] = None) -> dict:
        mode      = self.get_style_mode(contact)
        global_p  = self.store.load("global")
        contact_p = self.store.load(contact) if contact else None
        return {
            "mode":    mode,
            "global":  global_p,
            "contact": contact_p,
        }


# ── Visualization ─────────────────────────────────────────────────────────────

def print_profile(label: str, profile: StyleProfile) -> None:
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"  Overall confidence : {profile.overall_confidence:.1f}%")
    print(f"  Batches processed  : {profile.batch_count}")
    print(f"  Messages seen      : {profile.message_count}")
    print(f"  Traits:")
    for name, t in profile.traits.items():
        bar = "█" * int(t["score"] * 20)
        print(f"    {name:<12} {t['score']:.2f}  [{bar:<20}]  conf={t['confidence']:.0f}%")
    if profile.patterns:
        print(f"  Patterns: {', '.join(profile.patterns)}")
    print(f"{'─'*50}")


def plot_profile(profile: StyleProfile, title: str, filename: str) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        traits = profile.traits
        names  = list(traits.keys())
        scores = [traits[t]["score"]      for t in names]
        confs  = [traits[t]["confidence"] / 100 for t in names]
        colors = ["#1D9E75", "#EF9F27", "#378ADD", "#534AB7"]

        fig, ax = plt.subplots(figsize=(8, 4))
        y = range(len(names))
        bars = ax.barh(y, scores, color=colors, alpha=0.85, height=0.5, label="Score")
        ax.barh(y, confs,  color=colors, alpha=0.3,  height=0.5, label="Confidence")

        ax.set_yticks(list(y))
        ax.set_yticklabels([n.capitalize() for n in names])
        ax.set_xlim(0, 1.05)
        ax.set_xlabel("Score / Confidence")
        ax.set_title(f"{title}\nOverall confidence: {profile.overall_confidence:.0f}%  |  Batches: {profile.batch_count}")
        ax.axvline(0.7, color="red", linestyle="--", linewidth=0.8, alpha=0.5, label="Gate (70%)")
        ax.legend(loc="lower right", fontsize=9)
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close()
        print(f"[INFO] Chart saved: {filename}")
    except ImportError:
        print("[WARN] matplotlib not installed — skipping charts")


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    store     = ProfileStore(directory="profiles")
    buffer    = MessageBuffer(store, batch_size=BATCH_SIZE)
    retriever = StyleProfilesRetriever(store)

    # --- Simulate 50 outgoing messages for the global buffer ---
    global_messages = (
        [
            "Hey, quick check-in 😊",
            "Please send the report by EOD.",
            "Thanks so much!",
            "Let me know when you're free.",
            "Appreciate your help!",
        ]
        * 10  # 50 messages triggers one batch
    )

    boss_messages = (
        [
            "Good afternoon, please find the updated document attached.",
            "Could you kindly review this when you have time?",
            "Thank you for your support.",
            "Please let me know if any changes are required.",
            "I appreciate your feedback.",
        ]
        * 10
    )

    friend_messages = (
        [
            "heyy omg guess what 😂",
            "send it when u can no rush",
            "thanksss bestie",
            "lol that's so funny",
            "okayyy talk later",
        ]
        * 10
    )

    print("\n=== Feeding messages into observation mode ===")
    for msg in global_messages:
        buffer.add_message(msg)

    for msg in boss_messages:
        buffer.add_message(msg, contact="boss")

    for msg in friend_messages:
        buffer.add_message(msg, contact="friend")

    print(f"\n[INFO] Remaining in global buffer  : {buffer.global_buffer_size}")
    print(f"[INFO] Remaining in boss buffer    : {buffer.contact_buffer_size('boss')}")
    print(f"[INFO] Remaining in friend buffer  : {buffer.contact_buffer_size('friend')}")

    # --- Load and display profiles ---
    global_profile = store.load("global")
    boss_profile   = store.load("boss")
    friend_profile = store.load("friend")

    print_profile("GLOBAL PROFILE",       global_profile)
    print_profile("BOSS CONTACT PROFILE", boss_profile)
    print_profile("FRIEND CONTACT PROFILE", friend_profile)

    # --- Style gating ---
    boss_result   = retriever.get_profiles("boss")
    friend_result = retriever.get_profiles("friend")
    unknown_result = retriever.get_profiles("new_client")  # no data yet

    print(f"\n=== Style gating results ===")
    print(f"  Boss      → {boss_result['mode']}")
    print(f"  Friend    → {friend_result['mode']}")
    print(f"  New client→ {unknown_result['mode']}")

    # --- Charts ---
    plot_profile(global_profile, "Global Style Profile",       "global_style.png")
    plot_profile(boss_profile,   "Boss Contact Style Profile",  "boss_style.png")
    plot_profile(friend_profile, "Friend Contact Style Profile","friend_style.png")