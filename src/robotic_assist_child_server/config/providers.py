"""Dependency container / composition root.

Wires concrete adapters to application ports. Keeping construction here means
use cases and controllers depend only on interfaces. Future adapters
(OpenRouter, Mongo, Postgres) are swapped in this single place.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..application.services.prompt_composer import PromptComposer
from ..application.services.safety_guard import SafetyGuard
from ..application.use_cases import HandleTextInteraction
from ..infrastructure.openrouter import FakeConversationProvider
from ..infrastructure.prompts import FilePromptLoader
from ..infrastructure.repositories import InMemoryInteractionRepository
from .settings import Settings


@dataclass(slots=True)
class Container:
    settings: Settings
    prompt_loader: FilePromptLoader
    prompt_composer: PromptComposer
    safety_guard: SafetyGuard
    conversation_provider: FakeConversationProvider
    interaction_repository: InMemoryInteractionRepository
    handle_text_interaction: HandleTextInteraction


def build_container(settings: Settings) -> Container:
    prompt_loader = FilePromptLoader(settings.prompts_repository_path)
    prompt_composer = PromptComposer(prompt_loader)
    safety_guard = SafetyGuard()
    conversation_provider = FakeConversationProvider()
    interaction_repository = InMemoryInteractionRepository()

    handle_text_interaction = HandleTextInteraction(
        composer=prompt_composer,
        provider=conversation_provider,
        safety_guard=safety_guard,
        interaction_repository=interaction_repository,
    )

    return Container(
        settings=settings,
        prompt_loader=prompt_loader,
        prompt_composer=prompt_composer,
        safety_guard=safety_guard,
        conversation_provider=conversation_provider,
        interaction_repository=interaction_repository,
        handle_text_interaction=handle_text_interaction,
    )
