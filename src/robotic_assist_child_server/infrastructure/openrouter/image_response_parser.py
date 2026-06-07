from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any

_DATA_URL_RE = re.compile(r"^data:(?P<content_type>image/[-+.a-zA-Z0-9]+);base64,(?P<data>.+)$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class ParsedImageReference:
    kind: str
    value: str
    content_type: str | None = None


class ImageResponseParser:
    def parse(self, payload: Any) -> ParsedImageReference:
        reference = self._find_reference(payload)
        if reference is None:
            raise ValueError("OpenRouter image response did not contain an image")
        return reference

    def decode_base64(self, value: str) -> bytes:
        return self._decode_base64(value)

    def _find_reference(self, value: Any) -> ParsedImageReference | None:
        if isinstance(value, dict):
            direct = self._direct_reference(value)
            if direct is not None:
                return direct
            for child in value.values():
                found = self._find_reference(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = self._find_reference(item)
                if found is not None:
                    return found
        elif isinstance(value, str):
            return self._string_reference(value)
        return None

    def _direct_reference(self, value: dict[str, Any]) -> ParsedImageReference | None:
        content_type = self._content_type(value)

        for key in ("b64_json", "base64", "image_base64"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return ParsedImageReference(
                    kind="base64", value=candidate, content_type=content_type
                )

        data = value.get("data")
        value_type = str(value.get("type", "")).lower()
        if (
            isinstance(data, str)
            and self._looks_like_base64(data)
            and (content_type is not None or "image" in value_type)
        ):
            return ParsedImageReference(kind="base64", value=data, content_type=content_type)

        for key in ("url", "image_url"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return self._string_reference(candidate, content_type=content_type)
            if isinstance(candidate, dict):
                nested = self._direct_reference(candidate)
                if nested is not None:
                    return nested
        return None

    def _string_reference(
        self, value: str, *, content_type: str | None = None
    ) -> ParsedImageReference | None:
        stripped = value.strip()
        if stripped.startswith(("http://", "https://")):
            return ParsedImageReference(kind="url", value=stripped, content_type=content_type)
        match = _DATA_URL_RE.match(stripped)
        if match:
            return ParsedImageReference(
                kind="base64",
                value=match.group("data"),
                content_type=match.group("content_type"),
            )
        return None

    @staticmethod
    def _content_type(value: dict[str, Any]) -> str | None:
        for key in ("content_type", "mime_type", "media_type"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith("image/"):
                return candidate
        return None

    @staticmethod
    def _looks_like_base64(value: str) -> bool:
        stripped = value.strip()
        return len(stripped) >= 16 and not stripped.startswith(("http://", "https://"))

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        normalized = "".join(value.strip().split())
        padding = (-len(normalized)) % 4
        try:
            return base64.b64decode(normalized + ("=" * padding), validate=True)
        except binascii.Error as exc:
            raise ValueError("Invalid image base64 payload") from exc
