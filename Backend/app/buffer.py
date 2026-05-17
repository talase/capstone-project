"""Observation buffers that trigger style extraction every 50 messages."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Any

from app.profile_store import update_profile
from app.style_extractor import BATCH_SIZE, extract_style_profile


Extractor = Callable[[list[str], str | None], dict[str, Any]]
CONFIDENCE_GATE = 70


class StyleBuffer:
    """Maintain global and per-contact buffers for outgoing messages."""

    def __init__(
        self,
        batch_size: int = BATCH_SIZE,
        extractor: Extractor = extract_style_profile,
    ) -> None:
        self.batch_size = batch_size
        self.extractor = extractor
        self.global_buffer: list[str] = []
        self.contact_buffers: dict[str, list[str]] = defaultdict(list)

    def observe(self, contact: str, message: str) -> None:
        """Observe one outgoing message and update profiles when buffers fill."""

        clean_contact = contact.strip().lower()
        clean_message = message.strip()
        if not clean_contact or not clean_message:
            return

        self.global_buffer.append(clean_message)
        self.contact_buffers[clean_contact].append(clean_message)

        if len(self.global_buffer) >= self.batch_size:
            self._flush_global()

        if len(self.contact_buffers[clean_contact]) >= self.batch_size:
            self._flush_contact(clean_contact)

    def flush_all(self) -> None:
        """Flush remaining partial buffers at the end of observation mode."""

        if self.global_buffer:
            self._flush_global()
        for contact in list(self.contact_buffers):
            if self.contact_buffers[contact]:
                self._flush_contact(contact)

    def _flush_global(self) -> None:
        batch = self.global_buffer[: self.batch_size]
        self.global_buffer = self.global_buffer[self.batch_size :]
        profile = self.extractor(batch, "global")
        update_profile(profile, "global")

    def _flush_contact(self, contact: str) -> None:
        batch = self.contact_buffers[contact][: self.batch_size]
        self.contact_buffers[contact] = self.contact_buffers[contact][self.batch_size :]
        profile = self.extractor(batch, contact)
        update_profile(profile, contact)


def choose_style_mode(global_profile: dict[str, Any], contact_profile: dict[str, Any]) -> str:
    """Confidence gate for response generation."""

    global_confidence = _profile_confidence(global_profile)
    contact_confidence = _profile_confidence(contact_profile)

    if global_confidence >= CONFIDENCE_GATE and contact_confidence >= CONFIDENCE_GATE:
        return "global_contact"
    if contact_confidence >= CONFIDENCE_GATE:
        return "contact"
    if global_confidence >= CONFIDENCE_GATE:
        return "global"
    return "neutral"


def _profile_confidence(profile: dict[str, Any] | None) -> int:
    if not isinstance(profile, dict):
        return 0
    try:
        return int(round(float(profile.get("overall_confidence", 0))))
    except (TypeError, ValueError):
        return 0
