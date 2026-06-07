from __future__ import annotations

import re
from pathlib import Path

from ...application.ports.image_generation import StoredImage

_IMAGE_ID_RE = re.compile(r"^img_[A-Za-z0-9_-]{1,64}$")
_CONTENT_TYPES = {
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
_EXTENSIONS = {value: key for key, value in _CONTENT_TYPES.items()}
_EXTENSIONS["image/jpeg"] = "jpg"


class LocalImageStore:
    def __init__(
        self,
        *,
        storage_path: str,
        public_base_url: str,
        default_output_format: str = "png",
    ) -> None:
        self._storage_path = Path(storage_path)
        self._public_base_url = public_base_url.rstrip("/")
        self._default_output_format = self._normalize_format(default_output_format)
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def save(
        self, *, image_id: str, content: bytes, content_type: str, output_format: str
    ) -> tuple[Path, str]:
        extension = self._extension(content_type, output_format)
        path = self._path_for(image_id, extension)
        path.write_bytes(content)
        return path, f"{self._public_base_url}/{image_id}"

    def resolve(self, image_id: str) -> StoredImage | None:
        if not _IMAGE_ID_RE.match(image_id):
            return None
        extensions = [self._default_output_format]
        extensions.extend(ext for ext in _CONTENT_TYPES if ext not in extensions)
        for extension in extensions:
            path = self._path_for(image_id, extension)
            if path.exists() and path.is_file():
                content_type = _detect_content_type(path)
                if content_type is None:
                    return None
                return StoredImage(path=path, content_type=content_type)
        return None

    @staticmethod
    def _normalize_format(value: str) -> str:
        normalized = (value or "png").strip().lower().lstrip(".")
        if normalized == "jpeg":
            return "jpg"
        return normalized or "png"

    def _extension(self, content_type: str, output_format: str) -> str:
        normalized_format = self._normalize_format(output_format)
        normalized_type = (content_type or "").split(";")[0].strip().lower()
        return _EXTENSIONS.get(normalized_type) or normalized_format

    def _path_for(self, image_id: str, extension: str) -> Path:
        if not _IMAGE_ID_RE.match(image_id):
            raise ValueError("Invalid image id")
        return self._storage_path / f"{image_id}.{self._normalize_format(extension)}"


def _detect_content_type(path: Path) -> str | None:
    header = path.read_bytes()[:16]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None
