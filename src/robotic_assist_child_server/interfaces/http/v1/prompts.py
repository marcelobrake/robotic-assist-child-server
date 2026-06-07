from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ....config.providers import Container
from ....domain.entities import Prompt
from ....shared.datetime import to_rfc3339
from .deps import get_container
from .schemas import (
    PromptDetail,
    PromptListResponse,
    PromptReloadResponse,
    PromptSummary,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _to_summary(prompt: Prompt) -> PromptSummary:
    return PromptSummary(
        id=prompt.id,
        path=prompt.path,
        content_hash=prompt.content_hash,
        loaded_at=to_rfc3339(prompt.loaded_at),
        required=prompt.required,
    )


@router.get("", response_model=PromptListResponse)
def list_prompts(container: Container = Depends(get_container)) -> PromptListResponse:
    prompts = container.prompt_loader.list()
    summaries = [_to_summary(p) for p in prompts]
    return PromptListResponse(count=len(summaries), prompts=summaries)


@router.get("/{prompt_id}", response_model=PromptDetail)
def get_prompt(
    prompt_id: str, container: Container = Depends(get_container)
) -> PromptDetail:
    prompt = container.prompt_loader.get(prompt_id)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{prompt_id}' não encontrado.",
        )
    return PromptDetail(
        id=prompt.id,
        path=prompt.path,
        content_hash=prompt.content_hash,
        loaded_at=to_rfc3339(prompt.loaded_at),
        required=prompt.required,
        content=prompt.content,
    )


@router.post("/reload", response_model=PromptReloadResponse)
def reload_prompts(
    container: Container = Depends(get_container),
) -> PromptReloadResponse:
    prompts = container.prompt_loader.reload()
    return PromptReloadResponse(status="reloaded", count=len(prompts))
