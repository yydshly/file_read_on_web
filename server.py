"""Local file browser server."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.backend.services import annotations as annotations_mod
from src.backend.services import converter
from src.backend.services import search as search_mod
from src.backend.domain.app_metadata import APP_ID, APP_NAME, APP_VERSION, RELEASE_BASELINE
from src.backend.routes.runtime_routes import create_runtime_router
from src.backend.routes.cache_routes import create_cache_router
from src.backend.routes.annotation_routes import create_annotation_router
from src.backend.routes.ai_routes import create_ai_router
from src.backend.routes.system_routes import create_system_router
from src.backend.routes.static_routes import register_static_routes
from src.backend.routes.file_tree_routes import FileTreeRouteState, create_file_tree_router
from src.backend.routes.search_routes import SearchRouteState, create_search_router
from src.backend.infra.logging_setup import init_logging, get_logger
from src.backend.infra.safeio import read_json
from src.backend.services.runtime_state import RuntimeStateStore
from src.backend.services.tts_cache import TtsCache
from src.backend.app_context import AppContext, AppPaths

try:
    from src.backend.infra.tray_controller import TrayController
    _TRAY_AVAILABLE = True
except Exception:
    _TRAY_AVAILABLE = False
    TrayController = None  # type: ignore[assignment]

from src.ai import tasks as ai_tasks
from src.ai import factory as ai_factory
from src.ai.base import Message as AIMessage, CapabilityNotSupported
from src.backend.services.ai_document import AiDocumentService, build_ai_status

def _ensure_stdio_for_noconsole() -> None:
    """PyInstaller --noconsole may set stdout/stderr to None.

    Some logging formatters, including uvicorn defaults, expect file-like
    streams and call .isatty(). Provide safe devnull streams before logging
    and uvicorn setup.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


def _resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).parent.resolve()


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _data_base_dir() -> Path:
    app_dir = _app_base_dir()
    if not getattr(sys, "frozen", False):
        return app_dir

    portable_dir = app_dir / "app_data"
    if _is_writable_dir(portable_dir):
        return portable_dir.resolve()

    local_base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    fallback = Path(local_base) / "资料浏览器"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


APP_DIR = _app_base_dir()
DATA_DIR = _data_base_dir()
RESOURCE_DIR = _resource_base_dir()
STATIC_DIR = RESOURCE_DIR / "src" / "frontend" / "static"
CACHE_DIR = DATA_DIR / "cache"
TTS_CACHE_DIR = DATA_DIR / "cache" / "tts"   # hashed TTS audio bytes
CONFIG_PATH = DATA_DIR / "config.json"   # user-editable: AI, preferences
STATE_PATH  = DATA_DIR / "state.json"    # auto-managed: last_root, last_files, future runtime memory
ANNO_PATH = DATA_DIR / "annotations.json"
SEARCH_INDEX_PATH = DATA_DIR / "search_index.json"
DEFAULT_ROOT_REL = "教学资料"

anno_store = annotations_mod.AnnotationStore(ANNO_PATH)
tts_cache = TtsCache(TTS_CACHE_DIR)
state_store = RuntimeStateStore(STATE_PATH, CONFIG_PATH)
ai_doc_service = AiDocumentService(CACHE_DIR)

# Application context — single source of truth for mutable runtime state
ctx = AppContext(
    paths=AppPaths(
        app_dir=APP_DIR,
        data_dir=DATA_DIR,
        resource_dir=RESOURCE_DIR,
        static_dir=STATIC_DIR,
        cache_dir=CACHE_DIR,
        tts_cache_dir=TTS_CACHE_DIR,
        config_path=CONFIG_PATH,
        state_path=STATE_PATH,
        anno_path=ANNO_PATH,
        search_index_path=SEARCH_INDEX_PATH,
        default_root_rel=DEFAULT_ROOT_REL,
    ),
    anno_store=anno_store,
    state_store=state_store,
    tts_cache=tts_cache,
    ai_doc_service=ai_doc_service,
)

app = FastAPI()

# AI providers set during main() via ctx.ai_text_provider and ctx.ai_tts_provider

# Background preconvert state
_preconvert_task: Optional[asyncio.Task] = None
_preconvert_status: dict = {"running": False, "total": 0, "done": 0,
                             "current": None, "errors": 0, "started_at": None,
                             "finished_at": None}


# ---------- config persistence ----------

# ---------- config (user-editable, read-only at runtime) ----------

def _load_config() -> dict:
    """User-editable settings (AI block, etc.). The server never writes to this."""
    d = read_json(CONFIG_PATH, default={})
    return d if isinstance(d, dict) else {}


# ---------- runtime state service ----------


# ---------- path safety ----------

def _has_root() -> bool:
    return ctx.root is not None and ctx.root.exists() and ctx.root.is_dir()


# Include runtime and cache routers
app.include_router(
    create_runtime_router(
        ctx,
        app_id=APP_ID,
        app_name=APP_NAME,
        app_version=APP_VERSION,
        release_baseline=RELEASE_BASELINE,
        converter_mod=converter,
        has_root=_has_root,
    )
)

app.include_router(
    create_cache_router(
        ctx,
        converter_mod=converter,
        cache_dir=CACHE_DIR,
        data_dir=DATA_DIR,
        search_index_path=SEARCH_INDEX_PATH,
    )
)


def _require_root() -> Path:
    if not _has_root():
        raise HTTPException(409, "请先选择资料目录")
    return ctx.root


def _safe_resolve(rel: str) -> Path:
    root = _require_root()
    if not rel:
        raise HTTPException(400, "path is required")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(403, "path escapes root")
    if not candidate.exists():
        raise HTTPException(404, f"not found: {rel}")
    return candidate


# File/tree route state and router — includes warm-office background task
file_tree_state = FileTreeRouteState(
    ctx,
    converter_mod=converter,
    cache_dir=CACHE_DIR,
    data_dir=DATA_DIR,
    static_dir=STATIC_DIR,
    app_dir=APP_DIR,
)

app.include_router(
    create_file_tree_router(
        ctx,
        file_tree_state,
        has_root=_has_root,
        require_root=_require_root,
        safe_resolve=_safe_resolve,
    )
)


# Search route state and router — includes search index prebuild state
search_route_state = SearchRouteState(
    ctx,
    search_mod=search_mod,
    cache_dir=CACHE_DIR,
    search_index_path=SEARCH_INDEX_PATH,
)

app.include_router(
    create_search_router(
        ctx,
        search_route_state,
        has_root=_has_root,
        require_root=_require_root,
    )
)


app.include_router(
    create_annotation_router(
        ctx,
        has_root=_has_root,
        require_root=_require_root,
        safe_resolve=_safe_resolve,
    )
)

app.include_router(
    create_ai_router(
        ctx,
        require_root=_require_root,
        safe_resolve=_safe_resolve,
    )
)


# ---------- preconvert (background) ----------

_SKIP_NAMES = {
    "__pycache__", "node_modules", ".git", ".idea", ".vscode",
    "build", "dist", "app_data", "_internal", "libreoffice", "LibreOffice",
}

def _scan_office_files(root: Path) -> list[Path]:
    """Recursively find all office files under root, skipping caches/hidden."""
    out: list[Path] = []
    skip_roots = {DATA_DIR.resolve(), CACHE_DIR.resolve(), STATIC_DIR.resolve()}
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place prune
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in _SKIP_NAMES
        ]
        # Avoid walking our own cache/static if root is project dir
        if Path(dirpath).resolve() in skip_roots:
            dirnames[:] = []
            continue
        for name in filenames:
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            if converter.classify(p) == "office":
                out.append(p)
    return out


async def _preconvert_worker(root: Path):
    """Pre-convert all office files under root, newest first."""
    global _preconvert_status
    try:
        if not converter.find_soffice():
            print("[preconvert] LibreOffice 未安装，跳过预转换")
            return

        loop = asyncio.get_running_loop()
        files = await loop.run_in_executor(None, _scan_office_files, root)
        files.sort(key=lambda p: -p.stat().st_mtime)

        _preconvert_status.update(
            running=True, total=len(files), done=0, errors=0,
            current=None, started_at=time.time(), finished_at=None,
        )
        print(f"[preconvert] 开始预转换 {len(files)} 个 office 文件")

        for p in files:
            if root != ctx.root:  # root switched mid-run
                print("[preconvert] 根目录变更，中止当前任务")
                break
            _preconvert_status["current"] = p.name
            try:
                await converter.office_to_pdf(p, CACHE_DIR)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _preconvert_status["errors"] += 1
                print(f"[preconvert] 跳过 {p.name}: {e}")
            _preconvert_status["done"] += 1
            await asyncio.sleep(0)  # cooperative yield
        print(f"[preconvert] 完成: 共 {len(files)} 个，错误 {_preconvert_status['errors']}")
    except asyncio.CancelledError:
        print("[preconvert] 已取消")
        raise
    finally:
        _preconvert_status["running"] = False
        _preconvert_status["current"] = None
        _preconvert_status["finished_at"] = time.time()


def _start_preconvert():
    """(Re)start the background preconvert task for current ROOT."""
    global _preconvert_task
    if not ctx.preconvert_enabled or not _has_root():
        return
    if _preconvert_task and not _preconvert_task.done():
        _preconvert_task.cancel()
    _preconvert_task = asyncio.create_task(_preconvert_worker(_require_root()))


def _stop_background_tasks():
    # search prebuild state is owned by search_route_state; delegate
    search_route_state.reset_for_root_change_or_shutdown()
    search_route_state.cancel_prebuild_task()

    # warm task state is owned by file_tree_state; delegate
    file_tree_state.reset_background_root()
    file_tree_state.cancel_warm_task()

    if _preconvert_task and not _preconvert_task.done():
        _preconvert_task.cancel()




@app.on_event("startup")
async def _on_startup():
    # Startup prebuild/preconvert is intentionally disabled.
    # Index loading is performed lazily in _ensure_search_index_loaded().
    return


@app.on_event("shutdown")
async def _on_shutdown():
    _stop_background_tasks()
    # Final flush of debounced state (HOTFIX #4) — never lose the user's
    # last click just because we shut down before the timer fired.
    try:
        ctx.state_store.flush(force=True)
    except Exception:
        pass


# ---------- routes ----------

@app.get("/api/preconvert/status")
def api_preconvert_status():
    s = dict(_preconvert_status)
    if s["total"]:
        s["progress"] = round(s["done"] / s["total"], 3)
    else:
        s["progress"] = 0.0
    return s


# ---------- annotations ----------


register_static_routes(app, STATIC_DIR)


# ---------- startup ----------

def _open_app_url(url: str) -> bool:
    """Open app URL in the default browser as visibly/reliably as possible.

    Windows: prefers os.startfile (opens in existing window, most visible).
    Other: uses webbrowser.open with new=2 (new tab, foreground).
    Always logs result.
    """
    log = get_logger("browse")
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            webbrowser.open(url, new=2)
        log.info("已请求打开浏览器页面: %s", url)
        return True
    except Exception as e:
        log.warning("打开浏览器页面失败: %s", e)
        try:
            webbrowser.open(url, new=2)
            log.info("已通过 webbrowser fallback 打开页面: %s", url)
            return True
        except Exception as e2:
            log.warning("webbrowser fallback 也失败: %s", e2)
            return False


def _open_browser_when_ready(url: str, health_url: str, timeout: float = 8.0):
    """Wait for the server to be ready (health endpoint responds), then open URL.

    Uses a background thread so it never blocks startup.
    """
    def _open():
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                import urllib.request
                with urllib.request.urlopen(health_url, timeout=0.4) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        _open_app_url(url)
    threading.Thread(target=_open, daemon=True).start()


def _resolve_initial_root(cli_root: Optional[str]) -> Optional[Path]:
    """Priority: explicit CLI > saved state last_root > default folder under APP_DIR."""
    # explicit CLI takes precedence
    if cli_root:
        p = Path(cli_root)
        if not p.is_absolute():
            p = (APP_DIR / p).resolve()
        if p.exists() and p.is_dir():
            return p.resolve()
        print(f"[browse] warn: --root '{p}' not found, falling back")

    # saved state
    saved = ctx.state_store.get_last_root()
    if saved:
        p = Path(saved)
        if p.exists() and p.is_dir():
            return p.resolve()
        print(f"[browse] warn: saved last_root '{saved}' no longer exists, falling back")

    # default
    p = (APP_DIR / DEFAULT_ROOT_REL).resolve()
    if p.exists() and p.is_dir():
        return p
    if getattr(sys, "frozen", False):
        return None
    return APP_DIR


def _is_our_service_running(host: str, port: int, timeout: float = 0.35) -> bool:
    """Check if our app is already running on host:port.

    Returns True only if the service responds with our app_id.
    Returns False if port is free or occupied by another service.
    """
    try:
        conn = socket.create_connection((host, port), timeout=timeout)
        conn.close()
    except (socket.error, OSError):
        return False
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if APP_ID in body:
                return True
    except Exception:
        pass
    return False


def _delayed_exit(delay: float = 0.6):
    """Exit the process after a short delay (runs in a background thread)."""
    def _exit():
        time.sleep(delay)
        os._exit(0)
    t = threading.Thread(target=_exit, daemon=True)
    t.start()


# Tray controller set during main() via ctx.tray_controller


def _request_app_shutdown(reason: str = "api") -> None:
    """Shared shutdown logic for both /api/shutdown and tray exit.

    Order of operations matters here:
      1. Flush the debounced state buffer (bb4af627 follow-up #2) — the
         500ms debounce timer might still be pending; without this the
         user's most recent file click could be lost when os._exit fires.
      2. Stop the tray + kill orphan soffice subprocesses.
      3. Schedule the actual process exit.
    """
    log = get_logger("browse")
    log.info("收到退出程序请求 (reason=%s)", reason)

    # 1) Force-flush in-memory state to disk BEFORE we start tearing things
    #    down. Safe to call repeatedly — atexit handlers will no-op on the
    #    re-entry since _state_dirty becomes False after a successful write.
    try:
        ctx.state_store.flush(force=True)
    except Exception:
        log.exception("state flush during shutdown failed (continuing)")

    killed = converter.kill_orphan_soffice()
    if killed:
        log.info("退出时清理 %d 个残留 soffice 进程", killed)

    # Stop the tray icon if running
    if ctx.tray_controller is not None:
        try:
            ctx.tray_controller.stop()
        except Exception:
            pass
        ctx.tray_controller = None

    _delayed_exit(0.6)


app.include_router(
    create_system_router(
        ctx,
        has_root=_has_root,
        require_root=_require_root,
        safe_resolve=_safe_resolve,
        stop_background_tasks=_stop_background_tasks,
        request_app_shutdown=_request_app_shutdown,
    )
)


def main():
    _ensure_stdio_for_noconsole()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="initial root directory (overrides saved config)")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-preconvert", action="store_true",
                        help="disable background pre-conversion of office files")
    parser.add_argument("--force-server", action="store_true",
                        help="start server even if another instance is already running")
    parser.add_argument("--tray", action="store_true",
                        help="force-enable system tray (useful in dev mode)")
    parser.add_argument("--no-tray", action="store_true",
                        help="disable system tray")
    args = parser.parse_args()

    # HOTFIX-MIGRATION-TTS-CLEANUP-V1 Fix A:
    # Initialize logging BEFORE legacy state migration runs, so any migration
    # warnings / info land in app.log. This matters most in PyInstaller
    # --noconsole builds where stderr may be unavailable.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_dir = init_logging(DATA_DIR)
    log = get_logger("browse")

    # Migrate legacy last_root/last_files (used to live in config.json) into state.json
    ctx.state_store.migrate_legacy_config()

    # Check for existing service BEFORE initializing full state
    if not args.force_server and _is_our_service_running(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        log.info("已有服务运行中 (%s)，复用已有服务", url)
        if not args.no_browser:
            opened = _open_app_url(url)
            if not opened:
                log.warning("请手动访问: %s", url)
        return

    # Determine whether to enable the tray icon.
    # Default: enabled in packaged (frozen) mode, disabled in dev mode.
    tray_enabled = (getattr(sys, "frozen", False) or args.tray) and not args.no_tray
    tray_started = False

    ctx.root = _resolve_initial_root(args.root)
    ctx.preconvert_enabled = not args.no_preconvert
    if _has_root():
        ctx.state_store.set_last_root(_require_root())
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cleaned = converter.cleanup_cache(CACHE_DIR, max_age_days=30)
    if cleaned["removed"]:
        log.info("PDF cache: 删除 %d 项过期，保留 %d 项 (%.1f MB)",
                 cleaned["removed"], cleaned["kept"], cleaned["bytes"]/1024/1024)
    tts_cleaned = ctx.tts_cache.cleanup()
    if tts_cleaned["removed"]:
        log.info("TTS cache: 删除 %d 项过期，保留 %d 项 (%.1f MB)",
                 tts_cleaned["removed"], tts_cleaned["kept"], tts_cleaned["bytes"]/1024/1024)

    soffice = converter.find_soffice()
    log.info("程序启动: %s", APP_NAME)
    log.info("version: %s", APP_VERSION)
    log.info("release_baseline: %s", RELEASE_BASELINE)
    log.info("app_dir: %s", APP_DIR)
    log.info("data: %s", DATA_DIR)
    log.info("config: %s", CONFIG_PATH)
    log.info("frozen: %s", getattr(sys, "frozen", False))
    log.info("log_dir: %s", log_dir)
    log.info("root: %s", ctx.root)
    log.info("LibreOffice: %s",
             soffice or "未检测到（doc/docx/xlsx 等格式将无法预览，请安装 LibreOffice）")
    log.info("host: %s  port: %s", args.host, args.port)
    log.info("open http://%s:%d/", args.host, args.port)

    # AI providers (best-effort: missing config just disables AI features)
    cfg = _load_config()
    ai_cfg = cfg.get("ai") or {}
    try:
        ctx.ai_text_provider = ai_factory.make_active(ai_cfg)
    except Exception as e:
        log.warning("AI text provider 初始化失败: %s", e)
    try:
        ctx.ai_tts_provider = ai_factory.make_tts(ai_cfg)
    except Exception as e:
        log.warning("AI tts provider 初始化失败: %s", e)
    log.info("AI text: %s",
             ctx.ai_text_provider.info() if ctx.ai_text_provider else "未配置")
    log.info("AI tts:  %s",
             ctx.ai_tts_provider.info() if ctx.ai_tts_provider else "未配置")

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}/"
        health_url = f"http://{args.host}:{args.port}/api/health"
        _open_browser_when_ready(url, health_url)

    # Start system tray (after duplicate check, before uvicorn)
    log.info("tray_enabled: %s", tray_enabled)
    if tray_enabled and _TRAY_AVAILABLE and TrayController is not None:
        url = f"http://{args.host}:{args.port}/"
        log_file = log_dir / "app.log"
        icon_path = STATIC_DIR / "favicon.ico"
        tc = TrayController(
            app_name=APP_NAME,
            url=url,
            data_dir=DATA_DIR,
            log_file=log_file,
            icon_path=icon_path,
            open_url=_open_app_url,
            shutdown_callback=_request_app_shutdown,
        )
        tray_started = tc.start()
        log.info("tray_started: %s", tray_started)
        if tray_started:
            ctx.tray_controller = tc
    elif tray_enabled:
        log.warning("tray_enabled but dependencies unavailable (pystray/Pillow missing)")

    # Ensure orphaned soffice subprocesses are killed on exit AND the
    # debounced state buffer is flushed (HOTFIX-LOCAL-RESPONSIVENESS-V1 #4).
    import atexit, signal
    def _on_exit(*_a):
        try:
            ctx.state_store.flush(force=True)
        except Exception:
            pass
        killed = converter.kill_orphan_soffice()
        if killed:
            log.warning("退出时清理 %d 个残留 soffice 进程", killed)
        if ctx.tray_controller is not None:
            try:
                ctx.tray_controller.stop()
            except Exception:
                pass
    atexit.register(_on_exit)
    try:
        signal.signal(signal.SIGINT, lambda *_: (_on_exit(), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda *_: (_on_exit(), sys.exit(0)))
    except (ValueError, AttributeError):
        # signal.signal may fail in non-main thread or on some platforms
        pass

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", log_config=None)


if __name__ == "__main__":
    main()
