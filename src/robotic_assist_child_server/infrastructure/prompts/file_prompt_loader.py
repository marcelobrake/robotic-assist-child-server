"""Filesystem prompt loader.

Reads `metadata/prompt_manifest.yaml` from the prompts repository and loads
each referenced `.md` file. Implements the PromptRepository port. Reload
rebuilds the in-memory cache without restarting the application.
"""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import yaml

from ...domain.entities import Prompt
from ...shared.datetime import utc_now
from ...shared.errors import PromptNotFoundError
from ...shared.logging import get_logger

_MANIFEST_RELATIVE_PATH = Path("metadata") / "prompt_manifest.yaml"

logger = get_logger(__name__)


class FilePromptLoader:
    def __init__(self, repository_path: str | Path) -> None:
        self._root = Path(repository_path)
        self._lock = threading.RLock()
        self._prompts: dict[str, Prompt] = {}
        self._loaded = False

    @property
    def manifest_path(self) -> Path:
        return self._root / _MANIFEST_RELATIVE_PATH

    def load_all(self) -> list[Prompt]:
        with self._lock:
            prompts = self._read_from_disk()
            self._prompts = {p.id: p for p in prompts}
            self._loaded = True
            logger.info(
                "prompts loaded",
                extra={
                    "event_name": "prompt.load_all",
                    "attributes": {
                        "count": len(prompts),
                        "manifest_path": str(self.manifest_path),
                    },
                },
            )
            return list(self._prompts.values())

    def reload(self) -> list[Prompt]:
        logger.info("reloading prompts", extra={"event_name": "prompt.reload"})
        return self.load_all()

    def list(self) -> list[Prompt]:
        with self._lock:
            return list(self._prompts.values())

    def get(self, prompt_id: str) -> Prompt | None:
        with self._lock:
            return self._prompts.get(prompt_id)

    def get_or_raise(self, prompt_id: str) -> Prompt:
        prompt = self.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' não encontrado.")
        return prompt

    def is_loaded(self) -> bool:
        with self._lock:
            return self._loaded and bool(self._prompts)

    def _read_from_disk(self) -> list[Prompt]:
        manifest_path = self.manifest_path
        if not manifest_path.is_file():
            raise PromptNotFoundError(
                f"Manifest de prompts não encontrado em {manifest_path}."
            )

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        entries = manifest.get("prompts", [])
        loaded_at = utc_now()
        prompts: list[Prompt] = []

        for entry in entries:
            prompt_id = entry["id"]
            relative_path = entry["path"]
            required = bool(entry.get("required", False))
            file_path = self._root / relative_path

            if not file_path.is_file():
                if required:
                    raise PromptNotFoundError(
                        f"Prompt obrigatório ausente: {relative_path}"
                    )
                logger.warning(
                    "optional prompt file missing",
                    extra={
                        "event_name": "prompt.load_all",
                        "attributes": {"path": relative_path},
                    },
                )
                continue

            content = file_path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            prompts.append(
                Prompt(
                    id=prompt_id,
                    path=relative_path,
                    content=content,
                    content_hash=content_hash,
                    loaded_at=loaded_at,
                    required=required,
                )
            )

        return prompts
