from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.entities import Prompt


@runtime_checkable
class PromptRepository(Protocol):
    """Port for loading and accessing prompts."""

    def load_all(self) -> list[Prompt]:
        ...

    def reload(self) -> list[Prompt]:
        ...

    def list(self) -> list[Prompt]:
        ...

    def get(self, prompt_id: str) -> Prompt | None:
        ...

    def is_loaded(self) -> bool:
        ...
