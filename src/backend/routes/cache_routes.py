"""Cache routes: /api/cache/clear, /api/cache/stats, /api/cache/cleanup."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from src.backend.app_context import AppContext
from src.backend.services.tts_cache import TtsCache


def _dir_stats(d: Path, glob: str = "*") -> dict:
    """Return file count and total bytes for files in directory matching glob."""
    if not d.exists():
        return {"files": 0, "bytes": 0}
    files = [f for f in d.glob(glob) if f.is_file()]
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}


def create_cache_router(
    ctx: AppContext,
    *,
    converter_mod: Any,
    cache_dir: Path,
    data_dir: Path,
    search_index_path: Path,
) -> APIRouter:
    """Create the cache router for cache management endpoints."""
    router = APIRouter()

    @router.post("/api/cache/clear")
    def api_cache_clear():
        cache_dir.mkdir(parents=True, exist_ok=True)
        removed = 0
        skipped = 0
        for f in cache_dir.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                    removed += 1
            except OSError:
                skipped += 1  # likely held by an in-flight FileResponse on Windows
        return {"ok": True, "removed": removed, "skipped": skipped}

    @router.get("/api/cache/stats")
    def api_cache_stats():
        """Unified view of every on-disk cache the app maintains."""
        pdf = converter_mod.cache_stats(cache_dir)
        tts = ctx.tts_cache.stats()
        idx = {
            "files": search_index_path.exists() and 1 or 0,
            "bytes": search_index_path.stat().st_size if search_index_path.exists() else 0,
        }
        logs = _dir_stats(data_dir / "logs")
        return {
            "office_pdf": {
                **pdf,
                "limit_bytes": 2 * 1024 * 1024 * 1024,
                "max_age_days": 30,
            },
            "tts_audio": {
                **tts,
                "limit_bytes": TtsCache.MAX_BYTES,
                "max_age_days": TtsCache.MAX_AGE_DAYS,
            },
            "search_index": idx,
            "logs": logs,
            "total_bytes": pdf["bytes"] + tts["bytes"] + idx["bytes"] + logs["bytes"],
        }

    @router.post("/api/cache/cleanup")
    def api_cache_cleanup():
        """Run cleanup on every cache (LRU + age)."""
        return {
            "office_pdf": converter_mod.cleanup_cache(cache_dir, max_age_days=30),
            "tts_audio": ctx.tts_cache.cleanup(),
        }

    return router
