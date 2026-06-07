"""Dependency container / composition root.

Wires concrete adapters to application ports. Keeping construction here means
use cases and controllers depend only on interfaces. Future adapters
(OpenRouter, Mongo, Postgres) are swapped in this single place.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ..application.ports.memory import MemoryRepository
from ..application.services.memory_retriever import SimpleMemoryRetriever
from ..application.services.memory_updater import RuleBasedMemoryUpdater
from ..application.services.prompt_composer import PromptComposer
from ..application.services.safety_guard import SafetyGuard
from ..application.use_cases import (
    AuthenticateUser,
    CreateMemory,
    HandleTextInteraction,
    ListMemories,
    RegisterUser,
)
from ..infrastructure.auth import Argon2Hasher, JwtService
from ..infrastructure.database import create_engine, create_session_factory
from ..infrastructure.images import LocalImageStore
from ..infrastructure.openrouter import (
    FakeConversationProvider,
    FakeImageGenerationProvider,
    OpenRouterConversationProvider,
    OpenRouterImageGenerationProvider,
)
from ..infrastructure.prompts import FilePromptLoader
from ..infrastructure.repositories import (
    InMemoryInteractionRepository,
    InMemoryMemoryRepository,
    SqlAlchemyUserRepository,
)
from .settings import Settings


@dataclass(slots=True)
class Container:
    settings: Settings
    db_engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    prompt_loader: FilePromptLoader
    prompt_composer: PromptComposer
    safety_guard: SafetyGuard
    conversation_provider: FakeConversationProvider | OpenRouterConversationProvider
    image_store: LocalImageStore
    image_provider: FakeImageGenerationProvider | OpenRouterImageGenerationProvider
    interaction_repository: InMemoryInteractionRepository
    user_repository: SqlAlchemyUserRepository
    memory_repository: MemoryRepository
    memory_retriever: SimpleMemoryRetriever
    memory_updater: RuleBasedMemoryUpdater
    password_hasher: Argon2Hasher
    token_service: JwtService
    handle_text_interaction: HandleTextInteraction
    register_user: RegisterUser
    authenticate_user: AuthenticateUser
    create_memory: CreateMemory
    list_memories: ListMemories


def _build_memory_repository(settings: Settings) -> MemoryRepository:
    if settings.mongodb_uri:
        # Imported lazily so the MVP/tests don't require the motor driver.
        from ..infrastructure.mongodb import create_mongo_memory_repository

        return create_mongo_memory_repository(
            settings.mongodb_uri, settings.mongodb_database
        )
    return InMemoryMemoryRepository()


def _build_conversation_provider(
    settings: Settings, fake_provider: FakeConversationProvider
) -> FakeConversationProvider | OpenRouterConversationProvider:
    provider_name = settings.conversation_provider.strip().lower()
    if provider_name == "openrouter":
        return OpenRouterConversationProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            chat_model=settings.openrouter_chat_model,
            chat_model_fallback=settings.openrouter_chat_model_fallback,
            http_referer=settings.openrouter_http_referer,
            app_title=settings.openrouter_app_title,
            temperature=settings.conversation_temperature,
            max_tokens=settings.conversation_max_tokens,
            timeout_seconds=settings.conversation_timeout_seconds,
            max_retries=settings.openrouter_max_retries,
            fallback_to_fake=settings.openrouter_fallback_to_fake,
            fake_provider=fake_provider,
        )
    return fake_provider


def _build_image_provider(
    settings: Settings,
    image_store: LocalImageStore,
    fake_provider: FakeImageGenerationProvider,
) -> FakeImageGenerationProvider | OpenRouterImageGenerationProvider:
    provider_name = settings.image_provider.strip().lower()
    if provider_name == "openrouter":
        return OpenRouterImageGenerationProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            image_model=settings.openrouter_image_model,
            http_referer=settings.openrouter_http_referer,
            app_title=settings.openrouter_app_title,
            timeout_seconds=settings.image_timeout_seconds,
            max_retries=settings.image_max_retries,
            fallback_to_fake=settings.image_fallback_to_fake,
            output_format=settings.image_output_format,
            image_store=image_store,
            fake_provider=fake_provider,
        )
    return fake_provider


def build_container(settings: Settings) -> Container:
    prompt_loader = FilePromptLoader(settings.prompts_repository_path)
    prompt_composer = PromptComposer(prompt_loader)
    safety_guard = SafetyGuard()
    fake_conversation_provider = FakeConversationProvider()
    conversation_provider = _build_conversation_provider(
        settings, fake_conversation_provider
    )
    image_store = LocalImageStore(
        storage_path=settings.image_storage_path,
        public_base_url=settings.public_image_base_url,
        default_output_format=settings.image_output_format,
    )
    fake_image_provider = FakeImageGenerationProvider(image_store=image_store)
    image_provider = _build_image_provider(settings, image_store, fake_image_provider)
    interaction_repository = InMemoryInteractionRepository()

    db_engine = create_engine(settings.resolved_database_url)
    session_factory = create_session_factory(db_engine)
    user_repository = SqlAlchemyUserRepository(session_factory)

    memory_repository = _build_memory_repository(settings)
    memory_retriever = SimpleMemoryRetriever(memory_repository)
    memory_updater = RuleBasedMemoryUpdater(memory_repository)

    password_hasher = Argon2Hasher()
    token_service = JwtService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expires_minutes,
    )

    handle_text_interaction = HandleTextInteraction(
        composer=prompt_composer,
        provider=conversation_provider,
        safety_guard=safety_guard,
        interaction_repository=interaction_repository,
        memory_retriever=memory_retriever,
        memory_updater=memory_updater,
        image_provider=image_provider,
        image_generation_enabled=settings.image_generation_enabled,
        image_default_aspect_ratio=settings.image_default_aspect_ratio,
        image_default_size=settings.image_default_size,
        image_output_format=settings.image_output_format,
    )
    register_user = RegisterUser(
        user_repository=user_repository,
        password_hasher=password_hasher,
    )
    authenticate_user = AuthenticateUser(
        user_repository=user_repository,
        password_hasher=password_hasher,
    )
    create_memory = CreateMemory(memory_repository)
    list_memories = ListMemories(memory_repository)

    return Container(
        settings=settings,
        db_engine=db_engine,
        session_factory=session_factory,
        prompt_loader=prompt_loader,
        prompt_composer=prompt_composer,
        safety_guard=safety_guard,
        conversation_provider=conversation_provider,
        image_store=image_store,
        image_provider=image_provider,
        interaction_repository=interaction_repository,
        user_repository=user_repository,
        memory_repository=memory_repository,
        memory_retriever=memory_retriever,
        memory_updater=memory_updater,
        password_hasher=password_hasher,
        token_service=token_service,
        handle_text_interaction=handle_text_interaction,
        register_user=register_user,
        authenticate_user=authenticate_user,
        create_memory=create_memory,
        list_memories=list_memories,
    )
