"""Runtime routes: /api/health and /api/version."""
from __future__ import annotations

import sys
from typing import Any, Callable

from fastapi import APIRouter

from src.backend.app_context import AppContext


def create_runtime_router(
    ctx: AppContext,
    *,
    app_id: str,
    app_name: str,
    app_version: str,
    release_baseline: str,
    converter_mod: Any,
    has_root: Callable[[], bool],
) -> APIRouter:
    """Create the runtime router for health and version endpoints."""
    router = APIRouter()

    @router.get("/api/health")
    def api_health():
        return {
            "ok": True,
            "app_id": app_id,
            "app_name": app_name,
            "version": app_version,
            "soffice": converter_mod.find_soffice(),
            "root": str(ctx.root) if has_root() else None,
            "needs_root": not has_root(),
        }

    @router.get("/api/version")
    def api_version():
        return {
            "ok": True,
            "app_id": app_id,
            "app_name": app_name,
            "version": app_version,
            "release_baseline": release_baseline,
            "frozen": bool(getattr(sys, "frozen", False)),
        }

    return router
