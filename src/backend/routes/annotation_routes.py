"""Annotation routes: /api/anno/*."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.backend.app_context import AppContext


class TagPaletteBody(BaseModel):
    tags: list[str]


def create_annotation_router(
    ctx: AppContext,
    *,
    has_root: Callable[[], bool],
    require_root: Callable[[], Path],
    safe_resolve: Callable[[str], Path],
) -> APIRouter:
    """Create the annotation router for annotation management endpoints."""
    router = APIRouter()

    async def _anno_patch_async(root: Path, rel_path: str, partial: dict) -> dict:
        """Offload annotation JSON write from async handlers to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: ctx.anno_store.patch(root, rel_path, partial),
        )

    @router.get("/api/anno/all")
    def api_anno_all():
        """All annotations + tag palette for the current root."""
        if not has_root():
            return {"files": {}, "tag_palette": [], "needs_root": True}
        return ctx.anno_store.all_for_root(require_root())

    @router.get("/api/anno")
    def api_anno_get(path: str = Query(...)):
        safe_resolve(path)  # validate
        return ctx.anno_store.get(require_root(), path)

    @router.patch("/api/anno")
    async def api_anno_patch(request: Request, path: str = Query(...)):
        safe_resolve(path)  # validate
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "invalid JSON body")
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be a JSON object")
        return await _anno_patch_async(require_root(), path, body)

    @router.put("/api/anno/palette")
    def api_anno_palette(body: TagPaletteBody):
        return {"palette": ctx.anno_store.set_palette(require_root(), body.tags)}

    return router
