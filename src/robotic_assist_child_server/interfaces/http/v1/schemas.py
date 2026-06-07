"""HTTP DTOs. All fields use snake_case; dates are RFC3339 UTC strings."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ....domain.enums import ClientType, MemoryType, Role


class HealthStatus(BaseModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)


class VersionResponse(BaseModel):
    service_name: str
    service_version: str
    deployment_environment: str


class PromptSummary(BaseModel):
    id: str
    path: str
    content_hash: str
    loaded_at: str
    required: bool


class PromptDetail(PromptSummary):
    content: str


class PromptListResponse(BaseModel):
    count: int
    prompts: list[PromptSummary]


class PromptReloadResponse(BaseModel):
    status: str
    count: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=255)
    role: Role = Role.PARENT


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: Role
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    memory_type: MemoryType = MemoryType.INTEREST
    session_id: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: str = Field(default="manual", max_length=64)


class MemoryResponse(BaseModel):
    memory_id: str
    user_id: str
    session_id: str | None = None
    memory_type: MemoryType
    content: str
    confidence: float
    source: str
    created_at: str
    updated_at: str
    expires_at: str | None = None


class MemoryListResponse(BaseModel):
    count: int
    memories: list[MemoryResponse]


class TextInteractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None
    generate_audio: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_input_text_contract(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "text" not in normalized and "input_text" in normalized:
            normalized["text"] = normalized["input_text"]
        metadata = normalized.get("metadata")
        if (
            "device_id" not in normalized
            and isinstance(metadata, dict)
            and isinstance(metadata.get("device_id"), str)
        ):
            normalized["device_id"] = metadata["device_id"]
        return normalized


class GeneratedImageResponse(BaseModel):
    image_id: str
    image_url: str
    content_type: str
    provider: str
    model: str
    created_at: str
    expires_at: str | None = None


class GeneratedAudioResponse(BaseModel):
    audio_id: str
    audio_url: str
    content_type: str
    duration_ms: int | None = None
    provider: str
    model: str
    created_at: str
    expires_at: str | None = None


class TextInteractionResponse(BaseModel):
    interaction_id: str
    session_id: str
    user_id: str
    client_type: ClientType
    input_text: str
    response_text: str
    assistant_text: str
    expression: str
    intent: str
    image_prompt: str | None = None
    image: GeneratedImageResponse | None = None
    audio: GeneratedAudioResponse | None = None
    status: str
    created_at: str
    device_id: str | None = None
