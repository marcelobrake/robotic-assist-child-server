from __future__ import annotations

import re
from pathlib import Path

from ...application.ports.speech import StoredAudio

_AUDIO_ID_RE = re.compile(r"^aud_[A-Za-z0-9_-]{1,64}$")
_CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "pcm": "audio/wav",
    "flac": "audio/flac",
}


def content_type_for_format(output_format: str) -> str:
    return _CONTENT_TYPES.get(_normalize_format(output_format), "audio/mpeg")


def _normalize_format(value: str) -> str:
    # ElevenLabs formats look like "mp3_44100_128"; keep the codec prefix only.
    normalized = (value or "mp3").strip().lower().lstrip(".")
    codec = normalized.split("_", 1)[0]
    if codec == "mpeg":
        return "mp3"
    return codec or "mp3"


class LocalAudioStore:
    def __init__(self, *, storage_path: str, public_base_url: str) -> None:
        self._storage_path = Path(storage_path)
        self._public_base_url = public_base_url.rstrip("/")
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def save(
        self, *, audio_id: str, content: bytes, content_type: str, output_format: str
    ) -> tuple[Path, str]:
        extension = self._extension(content_type, output_format)
        path = self._path_for(audio_id, extension)
        path.write_bytes(content)
        return path, f"{self._public_base_url}/{audio_id}"

    def resolve(self, audio_id: str) -> StoredAudio | None:
        if not _AUDIO_ID_RE.match(audio_id):
            return None
        for extension in _CONTENT_TYPES:
            path = self._path_for(audio_id, extension)
            if path.exists() and path.is_file():
                return StoredAudio(
                    path=path, content_type=_CONTENT_TYPES[extension]
                )
        return None

    def _extension(self, content_type: str, output_format: str) -> str:
        normalized_type = (content_type or "").split(";")[0].strip().lower()
        for extension, mapped_type in _CONTENT_TYPES.items():
            if mapped_type == normalized_type:
                return extension
        return _normalize_format(output_format)

    def _path_for(self, audio_id: str, extension: str) -> Path:
        if not _AUDIO_ID_RE.match(audio_id):
            raise ValueError("Invalid audio id")
        return self._storage_path / f"{audio_id}.{_normalize_format(extension)}"
