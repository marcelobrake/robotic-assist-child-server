"""Application ports (interfaces).

These Protocols define the contracts the application layer depends on.
Infrastructure adapters implement them. Future providers (OpenRouter,
ElevenLabs, Mongo/Redis repositories) plug in here without changing use cases.
"""
from .conversation_provider import ConversationModelProvider, ConversationRequest
from .interaction_repository import InteractionRepository
from .memory import MemoryPolicy, MemoryRepository, MemoryRetriever, MemoryUpdater
from .prompt_repository import PromptRepository
from .safety_guard import SafetyGuardPort
from .speech import SpeechToTextProvider, TextToSpeechProvider

__all__ = [
    "ConversationModelProvider",
    "ConversationRequest",
    "InteractionRepository",
    "MemoryPolicy",
    "MemoryRepository",
    "MemoryRetriever",
    "MemoryUpdater",
    "PromptRepository",
    "SafetyGuardPort",
    "SpeechToTextProvider",
    "TextToSpeechProvider",
]
