"""Rule-based speech intent classifier for listener mode.

Decides whether a transcribed utterance is actually directed at the robot
before the assistant responds. Conservative on purpose: in continuous-listening
mode it should stay quiet unless reasonably sure the child is talking to it.

Implements the ``SpeechIntentClassifier`` port. A model-based classifier can
replace it later without touching the use case.
"""
from __future__ import annotations

import re

from ..ports.speech_intent import (
    REASON_BACKGROUND_NOISE,
    REASON_NO_SPEECH,
    REASON_NOT_ADDRESSED,
    REASON_TOO_SHORT,
    REASON_VALID,
    SpeechIntentResult,
)

# The robot's name; being addressed by name is always a valid interaction.
_ROBOT_NAME = "cubinho"

# Short greetings that only count as a valid interaction with extra context.
_GREETINGS = {"oi", "olá", "ola", "ei"}
_MIN_GREETING_WORDS = 2

# Filler/noise utterances that should never trigger a response.
_NOISE_WORDS = {"é", "eh", "ah", "ahn", "hum", "hmm", "uhum", "teste"}

_USEFUL_CHARS_RE = re.compile(r"[0-9a-zà-öø-ÿ]", re.IGNORECASE)
_MIN_USEFUL_CHARS = 2

_DEFAULT_TRIGGERS = (
    "cubinho",
    "oi",
    "olá",
    "ei",
    "conta",
    "desenha",
    "explica",
    "me ajuda",
    "brinca",
)


class RuleBasedSpeechIntentClassifier:
    def __init__(
        self,
        *,
        allowed_triggers: list[str] | tuple[str, ...] = _DEFAULT_TRIGGERS,
        require_addressing: bool = True,
    ) -> None:
        self._require_addressing = require_addressing
        # Command/keyword triggers (greetings handled separately by the
        # sufficient-context rule, the robot name by the addressing rule).
        self._keyword_triggers = tuple(
            trigger.strip().lower()
            for trigger in allowed_triggers
            if trigger.strip()
            and trigger.strip().lower() not in _GREETINGS
            and trigger.strip().lower() != _ROBOT_NAME
        )

    def classify(self, text: str) -> SpeechIntentResult:
        cleaned = (text or "").strip()
        if not cleaned:
            return SpeechIntentResult(False, REASON_NO_SPEECH)

        lowered = cleaned.lower()
        if lowered in _NOISE_WORDS:
            return SpeechIntentResult(False, REASON_BACKGROUND_NOISE)

        useful_chars = len(_USEFUL_CHARS_RE.findall(lowered))
        if useful_chars < _MIN_USEFUL_CHARS:
            return SpeechIntentResult(False, REASON_TOO_SHORT)

        words = lowered.split()

        # Positive signals.
        if _ROBOT_NAME in lowered:
            return SpeechIntentResult(True, REASON_VALID)
        if "?" in cleaned:
            return SpeechIntentResult(True, REASON_VALID)
        if any(trigger in lowered for trigger in self._keyword_triggers):
            return SpeechIntentResult(True, REASON_VALID)
        if words[0] in _GREETINGS and len(words) >= _MIN_GREETING_WORDS:
            return SpeechIntentResult(True, REASON_VALID)

        # Negative signals.
        if words[0] in _GREETINGS:
            # A bare greeting with no further context.
            return SpeechIntentResult(False, REASON_TOO_SHORT)
        if len(words) < _MIN_GREETING_WORDS:
            # Very short utterance without greeting/command.
            return SpeechIntentResult(False, REASON_TOO_SHORT)
        if self._require_addressing:
            return SpeechIntentResult(False, REASON_NOT_ADDRESSED)
        return SpeechIntentResult(True, REASON_VALID)
