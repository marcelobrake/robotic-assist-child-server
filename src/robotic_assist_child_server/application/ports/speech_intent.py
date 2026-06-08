"""Speech intent classification port (listener mode).

In continuous-listening (listener) mode the mobile client streams whatever it
captured. Before the assistant responds, a classifier decides whether the
transcribed utterance is actually directed at the robot or is just background
speech/noise. Keeping this behind a port lets a rule-based MVP be swapped for a
model-based classifier later without touching the use case.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Stable reason codes returned by classifiers.
REASON_NO_SPEECH = "no_speech"
REASON_BACKGROUND_NOISE = "background_noise"
REASON_TOO_SHORT = "too_short"
REASON_NOT_ADDRESSED = "not_addressed_to_robot"
REASON_VALID = "valid_interaction"


@dataclass(frozen=True, slots=True)
class SpeechIntentResult:
    should_respond: bool
    reason: str


@runtime_checkable
class SpeechIntentClassifier(Protocol):
    def classify(self, text: str) -> SpeechIntentResult: ...
