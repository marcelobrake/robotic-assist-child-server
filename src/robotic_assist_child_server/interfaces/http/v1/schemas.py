"""HTTP DTOs. All fields use snake_case; dates are RFC3339 UTC strings."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ....domain.enums import ClientType


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


class TextInteractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None


class TextInteractionResponse(BaseModel):
    interaction_id: str
    session_id: str
    user_id: str
    client_type: ClientType
    input_text: str
    response_text: str
    created_at: str
    device_id: str | None = None
