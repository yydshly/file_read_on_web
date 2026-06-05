"""Search routes and search-index prebuild state."""
from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, Query

from src.backend.app_context import AppContext


class SearchRouteState:
    """Holds mutable search prebuild/index state."""

    SEARCH_INDEX_SAVE_MIN_INTERVAL = 10.0

    def __init__(
        self,
        ctx: AppContext,
        *,
        search_mod: Any,
        cache_dir: Path,
        search_index_path: Path,
    ) -> None:
        self.ctx = ctx
        self.search_mod = search_mod
        self.cache_dir = cache_dir
        self.search_index_path = search_index_path

        self.prebuild_task: Optional[asyncio.Task] = None
        self.prebuild_root: Optional[Path] = None
        self.search_index_loaded_root: Optional[Path] = None
        self.last_search_index_save_at: float = 0.0
        self.search_index_save_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Shutdown / reset
    # ------------------------------------------------------------------

    def reset_for_root_change_or_shutdown(self) -> None:
        self.prebuild_root = None
        self.search_index_loaded_root = None

    def cancel_prebuild_task(self) -> None:
        if self.prebuild_task and not self.prebuild_task.done():
            self.prebuild_task.cancel()

    # ------------------------------------------------------------------
    # Search index management
    # ------------------------------------------------------------------

    def ensure_search_index_loaded(self, has_root: Callable[[], bool]) -> int:
        if not has_root():
            return 0
        if self.search_index_loaded_root == self.ctx.root:
            return 0
        loaded = self.search_mod.load_index(self.search_index_path)
        self.search_index_loaded_root = self.ctx.root
        return loaded

    def maybe_save_search_index(self) -> bool:
        now = time.time()
        with self.search_index_save_lock:
            if now - self.last_search_index_save_at < self.SEARCH_INDEX_SAVE_MIN_INTERVAL:
                return False
            self.last_search_index_save_at = now
        return self.search_mod.save_index(self.search_index_path)

    # ------------------------------------------------------------------
    # Prebuild worker
    # ------------------------------------------------------------------

    async def prebuild_worker(self, root: Path) -> None:
        self.prebuild_root = root
        loop = asyncio.get_running_loop()
        print(f"[search] 开始建索引 (root={root.name})")

        def _should_continue():
            return self.prebuild_root == root

        def _checkpoint():
            self.search_mod.save_index(self.search_index_path)

        try:
            await loop.run_in_executor(
                None,
                self.search_mod.prebuild,
                root,
                self.cache_dir,
                _should_continue,
                _checkpoint,
            )
        except asyncio.CancelledError:
            print("[search] 索引任务已取消（已保存当前进度）")
            try:
                self.search_mod.save_index(self.search_index_path)
            except Exception:
                pass
            raise
        if _should_continue():
            await loop.run_in_executor(None, self.search_mod.save_index, self.search_index_path)
            s = self.search_mod.index_stats()
            print(f"[search] 索引完成: {s['cached_files']} 个文件, "
                  f"{s['cached_bytes']/1024:.0f} KB, 跳过 {s['skipped']} 个")

    async def start_prebuild(self, require_root: Callable[[], Path], has_root: Callable[[], bool]) -> None:
        if not has_root():
            return
        if self.prebuild_task and not self.prebuild_task.done():
            self.prebuild_task.cancel()
        self.prebuild_task = asyncio.create_task(self.prebuild_worker(require_root()))


def create_search_router(
    ctx: AppContext,
    state: SearchRouteState,
    *,
    has_root: Callable[[], bool],
    require_root: Callable[[], Path],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/search")
    async def api_search(q: str = Query(...), limit: int = 50):
        """Full-text substring search. CPU-bound — runs in default executor."""
        root = require_root()
        loop = asyncio.get_running_loop()
        loaded = await loop.run_in_executor(None, state.ensure_search_index_loaded, has_root)
        results = await loop.run_in_executor(
            None, state.search_mod.search, root, state.cache_dir, q, limit
        )
        saved = await loop.run_in_executor(None, state.maybe_save_search_index)
        return {
            "query": q,
            "count": len(results),
            "results": results,
            "index": state.search_mod.index_stats(),
            "prebuild": state.search_mod.prebuild_status(),
            "loaded": loaded,
            "index_saved": saved,
        }

    @router.get("/api/search/status")
    def api_search_status():
        if not has_root():
            s = state.search_mod.prebuild_status()
            s["needs_root"] = True
            return s
        return state.search_mod.prebuild_status()

    @router.get("/api/search/skipped")
    def api_search_skipped():
        if not has_root():
            return {"skipped": {}, "needs_root": True}
        return {"skipped": state.search_mod.skipped_files()}

    @router.get("/api/search/scanned")
    def api_search_scanned():
        """List PDFs we detected as scanned (image-only). These can't be searched
        or fed to the AI text pipeline without OCR."""
        if not has_root():
            return {"scanned": [], "needs_root": True}
        return {"scanned": state.search_mod.scanned_files(require_root())}

    @router.post("/api/search/rebuild")
    async def api_search_rebuild():
        if not has_root():
            return {"ok": False, "needs_root": True, "detail": "请先选择资料目录"}
        state.search_mod.clear_cache()
        await state.start_prebuild(require_root, has_root)
        return {"ok": True}

    return router
