"""Static route registration: GET /, GET /favicon.ico, /static mount."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_static_routes(app: FastAPI, static_dir: Path) -> None:
    """Register static file routes directly on the FastAPI app.

    Static file mounting needs direct access to the FastAPI app instance,
    so this module uses a register function rather than APIRouter.
    """

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/favicon.ico")
    def favicon():
        """Serve favicon from static directory."""
        favicon_path = static_dir / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(favicon_path)
        raise HTTPException(404, "favicon not found")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
