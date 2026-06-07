from __future__ import annotations

from fastapi import APIRouter

from . import auth, health, images, interactions, memories, prompts, version


def build_v1_router() -> APIRouter:
    router = APIRouter(prefix="/v1")
    router.include_router(health.router)
    router.include_router(version.router)
    router.include_router(auth.router)
    router.include_router(prompts.router)
    router.include_router(images.router)
    router.include_router(interactions.router)
    router.include_router(memories.router)
    return router
