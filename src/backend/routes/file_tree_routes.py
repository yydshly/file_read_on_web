"""File, tree, and raw preview routes, plus warm-office background task state."""
from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Callable, Optional, Any

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from src.backend.app_context import AppContext


_FILE_TREE_SKIP_NAMES = {
    "__pycache__", "node_modules", ".git", ".idea", ".vscode",
    "build", "dist", "app_data", "_internal", "libreoffice", "LibreOffice",
}


class FileTreeRouteState:
    """Holds mutable warm-office background task state for file/tree routes."""

    def __init__(
        self,
        ctx: AppContext,
        *,
        converter_mod: Any,
        cache_dir: Path,
        data_dir: Path,
        static_dir: Path,
        app_dir: Path,
    ) -> None:
        self.ctx = ctx
        self.converter = converter_mod
        self.cache_dir = cache_dir
        self.data_dir = data_dir
        self.static_dir = static_dir
        self.app_dir = app_dir

        self.background_root: Optional[Path] = None
        self.warm_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Warm task lifecycle
    # ------------------------------------------------------------------

    def cancel_warm_task(self) -> None:
        if self.warm_task and not self.warm_task.done():
            self.warm_task.cancel()

    def reset_background_root(self) -> None:
        self.background_root = None

    # ------------------------------------------------------------------
    # Tree building helpers
    # ------------------------------------------------------------------

    def skip_tree_entry(self, entry: Path) -> bool:
        name = entry.name
        if name.startswith(".") or name in _FILE_TREE_SKIP_NAMES:
            return True
        try:
            resolved = entry.resolve()
        except OSError:
            return True
        skip_roots = {
            self.data_dir.resolve(),
            self.cache_dir.resolve(),
            self.static_dir.resolve(),
            (self.app_dir / "app_data").resolve(),
            (self.app_dir / "_internal").resolve(),
            (self.app_dir / "libreoffice").resolve(),
            (self.app_dir / "LibreOffice").resolve(),
        }
        return resolved in skip_roots

    def build_tree(self, d: Path, root: Path, recursive: bool = True) -> dict:
        children = []
        try:
            entries = sorted(
                d.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            entries = []
        for entry in entries:
            if self.skip_tree_entry(entry):
                continue
            name = entry.name
            rel = str(entry.relative_to(root)).replace("\\", "/")
            if entry.is_dir():
                children.append({
                    "name": name,
                    "path": rel,
                    "type": "dir",
                    "children": self.build_tree(entry, root, recursive)["children"] if recursive else [],
                })
            else:
                children.append({
                    "name": name,
                    "path": rel,
                    "type": "file",
                    "ext": entry.suffix.lower(),
                })
        return {"name": d.name, "path": "", "type": "dir", "children": children}

    def iter_files_in_tree_order(self, d: Path):
        """Yield files in the same visual order as the left tree."""
        try:
            entries = sorted(
                d.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (OSError, PermissionError):
            return

        for entry in entries:
            if self.skip_tree_entry(entry):
                continue
            if entry.is_dir():
                yield from self.iter_files_in_tree_order(entry)
            else:
                yield entry

    # ------------------------------------------------------------------
    # Warm-office background task
    # ------------------------------------------------------------------

    def warm_office_candidates(self, root: Path, limit: int = 2) -> list[Path]:
        """Return the next ``limit`` office files immediately after the user's
        last-opened file. The anchor file can be ANY type, so we scan all
        files in sorted order and look for office files coming after the
        anchor's position.
        """
        all_files = list(self.iter_files_in_tree_order(root))

        last = self.ctx.state_store.get_last_file(root)
        start = 0
        if last:
            last_path = (root / last).resolve()
            for i, p in enumerate(all_files):
                if p.resolve() == last_path:
                    start = i + 1
                    break

        result: list[Path] = []
        for p in all_files[start:]:
            if p.suffix.lower() in self.converter.OFFICE_EXTS:
                result.append(p)
                if len(result) >= limit:
                    break
        return result

    async def warm_office_after_tree(self, root: Path) -> None:
        await asyncio.sleep(1.0)
        if self.ctx.root != root:
            return
        for p in self.warm_office_candidates(root, limit=2):
            if self.ctx.root != root:
                return
            try:
                await self.converter.office_to_pdf(p, self.cache_dir)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[prewarm] skip {p.name}: {e}")

    def start_warm_after_tree(self, root: Path) -> None:
        """Initial warm kicked once after /api/tree is loaded for this root."""
        if self.background_root == root:
            return
        self.background_root = root
        self.restart_warm(root)

    def restart_warm(self, root: Path) -> None:
        """Re-spawn the warm task. Used after each /api/file so the next 2
        office files (relative to the user's current position) get preconverted."""
        if root != self.ctx.root:
            return
        if self.warm_task and not self.warm_task.done():
            self.warm_task.cancel()
        self.warm_task = asyncio.create_task(self.warm_office_after_tree(root))


def create_file_tree_router(
    ctx: AppContext,
    state: FileTreeRouteState,
    *,
    has_root: Callable[[], bool],
    require_root: Callable[[], Path],
    safe_resolve: Callable[[str], Path],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/tree")
    async def api_tree(path: str = "", recursive: int = 1):
        if not has_root():
            if path:
                raise HTTPException(409, "请先选择资料目录")
            return {"name": "", "path": "", "type": "dir", "children": [], "needs_root": True}
        root = require_root()
        base = root if not path else safe_resolve(path)
        if not base.is_dir():
            raise HTTPException(400, "path must be a directory")
        loop = asyncio.get_running_loop()
        tree = await loop.run_in_executor(None, state.build_tree, base, root, bool(recursive))
        if not path:
            state.start_warm_after_tree(root)
        return tree

    @router.get("/api/file")
    async def api_file(path: str = Query(...), remember: int = 1, force: int = 0):
        root = require_root()
        src = safe_resolve(path)
        if src.is_dir():
            raise HTTPException(400, "path is a directory")

        if remember:
            ctx.state_store.set_last_file(root, path)

        kind = state.converter.classify(src)
        response: Response
        if kind == "pdf":
            response = FileResponse(src, media_type="application/pdf")
        elif kind == "office":
            state.cancel_warm_task()
            try:
                pdf = await state.converter.office_to_pdf(src, state.cache_dir, force=bool(force))
            except RuntimeError as e:
                return JSONResponse({"error": "convert_failed", "message": str(e)}, status_code=500)
            response = FileResponse(pdf, media_type="application/pdf")
        elif kind == "markdown":
            response = HTMLResponse(state.converter.render_markdown(src, root))
        elif kind == "text":
            response = HTMLResponse(state.converter.render_text(src))
        elif kind == "image":
            response = FileResponse(src, media_type=state.converter.image_mime(src))
        else:
            return JSONResponse(
                {"error": "unsupported", "name": src.name, "ext": src.suffix},
                status_code=415,
            )

        if remember and ctx.preconvert_enabled:
            state.restart_warm(root)

        return response

    @router.get("/api/raw")
    def api_raw(path: str = Query(...)):
        src = safe_resolve(path)
        if src.is_dir():
            raise HTTPException(400, "path is a directory")
        mime, _ = mimetypes.guess_type(src.name)
        return FileResponse(
            src,
            media_type=mime or "application/octet-stream",
            filename=src.name,
        )

    return router
