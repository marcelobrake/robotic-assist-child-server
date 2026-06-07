"""Rule-based memory extraction.

Initial rule (no LLM, no embeddings): when the child states a like/favorite,
store an `interest` memory. Patterns (pt-BR, case-insensitive):

- "eu gosto de X"
- "gosto de X"
- "meu favorito é X"
"""
from __future__ import annotations

import re

from ...domain.entities import Memory
from ...domain.enums import MemoryType
from ...shared.datetime import utc_now
from ...shared.ids import new_memory_id
from ..ports.memory import MemoryRepository

_INTEREST_PATTERNS = (
    re.compile(r"\beu\s+gosto\s+de\s+(.+)", re.IGNORECASE),
    re.compile(r"\bgosto\s+de\s+(.+)", re.IGNORECASE),
    re.compile(r"\bmeu\s+favorito\s+é\s+(.+)", re.IGNORECASE),
)
_TERMINATORS = re.compile(r"[.!?;,\n]")


class RuleBasedMemoryUpdater:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def evaluate(
        self, *, user_id: str, session_id: str | None, input_text: str
    ) -> list[Memory]:
        if not user_id or not input_text:
            return []
        interests = self._extract_interests(input_text)
        if not interests:
            return []

        existing = await self._repository.list_for_user(user_id)
        existing_contents = {m.content.strip().lower() for m in existing}

        created: list[Memory] = []
        for interest in interests:
            content = f"Gosta de {interest}."
            key = content.lower()
            if key in existing_contents:
                continue
            now = utc_now()
            memory = Memory(
                memory_id=new_memory_id(),
                user_id=user_id,
                session_id=session_id,
                memory_type=MemoryType.INTEREST,
                content=content,
                confidence=0.8,
                source="user_interaction",
                created_at=now,
                updated_at=now,
            )
            await self._repository.save(memory)
            created.append(memory)
            existing_contents.add(key)
        return created

    @staticmethod
    def _extract_interests(text: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for pattern in _INTEREST_PATTERNS:
            for match in pattern.finditer(text):
                interest = _TERMINATORS.split(match.group(1), 1)[0].strip()
                if not interest:
                    continue
                key = interest.lower()
                if key in seen:
                    continue
                seen.add(key)
                found.append(interest)
        return found
