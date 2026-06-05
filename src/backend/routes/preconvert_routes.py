"""Preconvert routes and background task state."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter

from src.backend.app_context import AppContext


_PRECONVERT_SKIP_NAMES = {
    "__pycache__", "node_modules", ".git", ".idea", ".vscode",
    "build", "dist", "app_data", "_internal", "libreoffice", "LibreOffice",
}


class PreconvertRouteState:
    def __init__(
        self,
        ctx: AppContext,
        *,
        converter_mod: Any,
        cache_dir: Path,
        data_dir: Path,
        static_dir: Path,
    ) -> None:
        self.ctx = ctx
        self.converter = converter_mod
        self.cache_dir = cache_dir
        self.data_dir = data_dir
        self.static_dir = static_dir

        self.preconvert_task: Optional[asyncio.Task] = None
        self.preconvert_status: dict = {
            "running": False,
            "total": 0,
            "done": 0,
            "current": None,
            "errors": 0,
            "started_at": None,
            "finished_at": None,
        }

    def scan_office_files(self, root: Path) -> list[Path]:
        """Recursively find all office files under root, skipping caches/hidden."""
        out: list[Path] = []
        skip_roots = {
            self.data_dir.resolve(),
            self.cache_dir.resolve(),
            self.static_dir.resolve(),
        }
        for dirpath, dirnames, filenames in os.walk(root):
            # in-place prune
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in _PRECONVERT_SKIP_NAMES
            ]
            # Avoid walking our own cache/static if root is project dir
            if Path(dirpath).resolve() in skip_roots:
                dirnames[:] = []
                continue
            for name in filenames:
                if name.startswith("."):
                    continue
                p = Path(dirpath) / name
                if self.converter.classify(p) == "office":
                    out.append(p)
        return out

    async def preconvert_worker(self, root: Path) -> None:
        """Pre-convert all office files under root, newest first."""
        try:
            if not self.converter.find_soffice():
                print("[preconvert] LibreOffice 未安装，跳过预转换")
                return

            loop = asyncio.get_running_loop()
            files = await loop.run_in_executor(None, self.scan_office_files, root)
            files.sort(key=lambda p: -p.stat().st_mtime)

            self.preconvert_status.update(
                running=True, total=len(files), done=0, errors=0,
                current=None, started_at=time.time(), finished_at=None,
            )
            print(f"[preconvert] 开始预转换 {len(files)} 个 office 文件")

            for p in files:
                if root != self.ctx.root:  # root switched mid-run
                    print("[preconvert] 根目录变更，中止当前任务")
                    break
                self.preconvert_status["current"] = p.name
                try:
                    await self.converter.office_to_pdf(p, self.cache_dir)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.preconvert_status["errors"] += 1
                    print(f"[preconvert] 跳过 {p.name}: {e}")
                self.preconvert_status["done"] += 1
                await asyncio.sleep(0)  # cooperative yield
            print(f"[preconvert] 完成: 共 {len(files)} 个，错误 {self.preconvert_status['errors']}")
        except asyncio.CancelledError:
            print("[preconvert] 已取消")
            raise
        finally:
            self.preconvert_status["running"] = False
            self.preconvert_status["current"] = None
            self.preconvert_status["finished_at"] = time.time()

    def start_preconvert(
        self,
        *,
        has_root: Callable[[], bool],
        require_root: Callable[[], Path],
    ) -> None:
        """(Re)start the background preconvert task for current ROOT."""
        if not self.ctx.preconvert_enabled or not has_root():
            return
        if self.preconvert_task and not self.preconvert_task.done():
            self.preconvert_task.cancel()
        self.preconvert_task = asyncio.create_task(self.preconvert_worker(require_root()))

    def cancel_preconvert_task(self) -> None:
        if self.preconvert_task and not self.preconvert_task.done():
            self.preconvert_task.cancel()

    def status(self) -> dict:
        s = dict(self.preconvert_status)
        if s["total"]:
            s["progress"] = round(s["done"] / s["total"], 3)
        else:
            s["progress"] = 0.0
        return s


def create_preconvert_router(
    ctx: AppContext,
    state: PreconvertRouteState,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/preconvert/status")
    def api_preconvert_status():
        return state.status()

    return router
