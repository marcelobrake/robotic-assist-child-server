"""Application ports (interfaces).

These Protocols define the contracts the application layer depends on.
Infrastructure adapters implement them. Future providers (OpenRouter,
ElevenLabs, Mongo/Redis repositories) plug in here without changing use cases.
"""
from .conversation_provider import (
    ConversationMessage,
    ConversationModelProvider,
    ConversationRequest,
    ConversationResponse,
)
from .interaction_repository import InteractionRepository
from .image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageStoragePort,
    StoredImage,
)
from .memory import MemoryPolicy, MemoryRepository, MemoryRetriever, MemoryUpdater
from .prompt_repository import PromptRepository
from .safety_guard import SafetyGuardPort
from .security import PasswordHasherPort, TokenServicePort
from .speech import (
    AudioStoragePort,
    SpeechSynthesisRequest,
    SpeechToTextProvider,
    SpeechTranscription,
    SpeechTranscriptionRequest,
    StoredAudio,
    TextToSpeechProvider,
)
from .speech_intent import SpeechIntentClassifier, SpeechIntentResult
from .user_repository import UserRepository

__all__ = [
    "ConversationModelProvider",
    "ConversationMessage",
    "ConversationRequest",
    "ConversationResponse",
    "AudioStoragePort",
    "InteractionRepository",
    "ImageGenerationProvider",
    "ImageGenerationRequest",
    "ImageStoragePort",
    "MemoryPolicy",
    "MemoryRepository",
    "MemoryRetriever",
    "MemoryUpdater",
    "PasswordHasherPort",
    "PromptRepository",
    "SafetyGuardPort",
    "SpeechIntentClassifier",
    "SpeechIntentResult",
    "SpeechSynthesisRequest",
    "SpeechToTextProvider",
    "SpeechTranscription",
    "SpeechTranscriptionRequest",
    "StoredAudio",
    "StoredImage",
    "TextToSpeechProvider",
    "TokenServicePort",
    "UserRepository",
]
