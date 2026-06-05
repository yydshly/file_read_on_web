"""System routes: /api/root, /api/reveal, /api/pick-folder, /api/shutdown."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.backend.app_context import AppContext
from src.backend.infra.logging_setup import get_logger


class RootBody(BaseModel):
    path: str


def _bring_explorer_to_front_later(target: Path) -> None:
    """Best-effort Windows Explorer foreground on a background thread.

    Uses ctypes to find and restore/foreground the most recently active
    Explorer window (CabinetWClass or ExploreWClass).  Does not block,
    does not raise, and logs outcomes.
    """
    if not sys.platform.startswith("win"):
        return

    def _run():
        try:
            import ctypes
            import time
            time.sleep(0.8)

            user32 = ctypes.windll.user32
            SW_RESTORE = 9

            for class_name in ("CabinetWClass", "ExploreWClass"):
                hwnd = user32.FindWindowW(class_name, None)
                if hwnd:
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetForegroundWindow(hwnd)
                    get_logger("browse").info(
                        "已请求前置资源管理器窗口: %s", target
                    )
                    return

            get_logger("browse").info(
                "未找到可前置的资源管理器窗口: %s", target
            )
        except Exception as e:
            get_logger("browse").warning(
                "前置资源管理器窗口失败: %s", e
            )

    threading.Thread(target=_run, daemon=True, name="ExplorerForeground").start()


def create_system_router(
    ctx: AppContext,
    *,
    has_root: Callable[[], bool],
    require_root: Callable[[], Path],
    safe_resolve: Callable[[str], Path],
    stop_background_tasks: Callable[[], None],
    request_app_shutdown: Callable[[str], None],
) -> APIRouter:
    """Create the system router for system/control endpoints."""
    router = APIRouter()

    @router.get("/api/root")
    def api_root_get():
        if not has_root():
            return {"root": None, "last_file": None, "needs_root": True}
        root = require_root()
        return {
            "root": str(root),
            "last_file": ctx.state_store.get_last_file(root),
            "needs_root": False,
        }

    @router.post("/api/root")
    def api_root_set(body: RootBody):
        new_path = Path(body.path).expanduser()
        if not new_path.is_absolute():
            new_path = (ctx.paths.app_dir / new_path).resolve()
        new_path = new_path.resolve()
        if not new_path.exists() or not new_path.is_dir():
            raise HTTPException(400, f"not a directory: {new_path}")
        stop_background_tasks()
        ctx.root = new_path
        ctx.state_store.set_last_root(ctx.root)
        # HOTFIX-LOCAL-RESPONSIVENESS-V1 #2:
        # Do NOT clear the search text cache on root change. _text_cache is
        # keyed by absolute path, so entries for the old root cannot collide
        # with the new root. Wiping everything forced a full re-extract of
        # files the user might switch back to. The /api/search/rebuild
        # endpoint remains the explicit "wipe + rebuild" knob.
        return {
            "root": str(ctx.root),
            "last_file": ctx.state_store.get_last_file(ctx.root),
            "needs_root": False,
        }

    @router.post("/api/reveal")
    def api_reveal(body: RootBody):
        """Show the file in the OS file manager (Explorer / Finder / xdg-open)."""
        src = safe_resolve(body.path)
        log = get_logger("browse")
        foreground_attempted = False
        try:
            if sys.platform.startswith("win"):
                # explorer /select,"<path>" must be passed as ONE command-line
                # string. If we use a list, Python's list2cmdline wraps the whole
                # `/select,<path>` in quotes and explorer fails to parse the flag,
                # falling back to its default folder.
                win_path = str(src).replace("/", "\\")
                subprocess.Popen(f'explorer /select,"{win_path}"')
                _bring_explorer_to_front_later(src)
                foreground_attempted = True
                log.info("打开本地位置: %s", src)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(src)])
                log.info("打开本地位置: %s", src)
            else:
                subprocess.Popen(["xdg-open", str(src.parent)])
                log.info("打开本地位置: %s", src)
        except Exception as e:
            raise HTTPException(500, f"reveal failed: {e}")
        return {
            "ok": True,
            "path": str(src),
            "parent": str(src.parent),
            "foreground_attempted": foreground_attempted,
        }

    @router.post("/api/shutdown")
    def api_shutdown(request: Request):
        """Shutdown the server (local-only)."""
        client = request.client
        if client is None or client.host not in ("127.0.0.1", "localhost", "::1"):
            raise HTTPException(403, "仅允许本地访问")
        request_app_shutdown(reason=f"api:{client.host}")
        return {"ok": True, "message": "程序正在退出"}

    @router.post("/api/pick-folder")
    def api_pick_folder():
        """Open a native OS folder-picker dialog (server-side via tkinter)."""
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as e:
            raise HTTPException(500, f"tkinter unavailable: {e}")

        selected: list[str] = []

        def _pick():
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                initial = str(ctx.root) if has_root() else str(ctx.paths.app_dir)
                chosen = filedialog.askdirectory(
                    title="选择资料根目录", initialdir=initial, parent=root
                )
            finally:
                root.destroy()
            if chosen:
                selected.append(chosen)

        # tkinter must run on the main thread of its own; use a dedicated thread
        t = threading.Thread(target=_pick)
        t.start()
        t.join(timeout=300)  # up to 5 minutes for user to choose

        if not selected:
            return {"path": None}
        return {"path": selected[0]}

    return router
