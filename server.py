"""Local file browser server."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import annotations as annotations_mod
import converter
import search as search_mod
from logging_setup import init_logging, get_logger
from safeio import atomic_write_json, read_json

import ai as ai_mod
from ai import tasks as ai_tasks
from ai import factory as ai_factory
from ai.base import Message as AIMessage, CapabilityNotSupported, ProviderConfigError

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
STATIC_DIR = RESOURCE_DIR / "static"
APP_ID = "file_read_on_web"
APP_NAME = "资料浏览器"
CACHE_DIR = DATA_DIR / "cache"
TTS_CACHE_DIR = DATA_DIR / "cache" / "tts"   # hashed TTS audio bytes
CONFIG_PATH = DATA_DIR / "config.json"   # user-editable: AI, preferences
STATE_PATH  = DATA_DIR / "state.json"    # auto-managed: last_root, last_files, future runtime memory
ANNO_PATH = DATA_DIR / "annotations.json"
SEARCH_INDEX_PATH = DATA_DIR / "search_index.json"
DEFAULT_ROOT_REL = "教学资料"

anno_store = annotations_mod.AnnotationStore(ANNO_PATH)

app = FastAPI()

ROOT: Optional[Path] = None
PRECONVERT_ENABLED: bool = True

# AI providers built from config on startup; either may be None if not configured.
ai_text_provider = None     # type: ignore[var-annotated]
ai_tts_provider = None      # type: ignore[var-annotated]

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


# ---------- state (auto-managed runtime memory) ----------

def _load_state() -> dict:
    d = read_json(STATE_PATH, default={})
    return d if isinstance(d, dict) else {}


def _save_state(state: dict) -> None:
    try:
        atomic_write_json(STATE_PATH, state)
    except Exception as e:
        try:
            get_logger("browse").warning("failed to save state: %s", e)
        except Exception:
            pass


def _migrate_legacy_state() -> None:
    """Older versions kept last_root / last_files inside config.json. If we
    see them there (and state.json hasn't been initialised), move them out so
    config.json becomes purely user-edited.

    Migration is idempotent and runs only once (gated by state.json existence).
    """
    if STATE_PATH.exists():
        return
    cfg = _load_config()
    legacy_keys = {"last_root", "last_files"}
    moved = {k: cfg.pop(k) for k in list(cfg.keys()) if k in legacy_keys}
    if not moved:
        return

    # 1. Persist the runtime state.
    _save_state(moved)

    # 2. Rewrite config.json without the migrated keys so the user sees a
    #    clean file. Their other keys (ai, future preferences) are kept.
    #    If config.json ends up empty, write a hint pointing at the example.
    if not cfg:
        cfg = {
            "_doc": (
                "本文件用于用户偏好（AI 等）。运行时记忆（上次目录、上次文件）"
                "在同目录的 state.json 自动管理。配置模板见 config.example.json。"
            )
        }
    try:
        atomic_write_json(CONFIG_PATH, cfg)
    except Exception as e:
        try:
            get_logger("browse").warning(
                "migration: 无法回写 config.json，旧字段仍残留: %s", e
            )
        except Exception:
            pass

    try:
        get_logger("browse").info(
            "迁移：last_root / last_files 已从 config.json 移到 state.json"
        )
    except Exception:
        pass


def _root_key(root: Path) -> str:
    return str(root.resolve()).replace("\\", "/")


def _get_last_file(root: Path) -> Optional[str]:
    state = _load_state()
    return (state.get("last_files") or {}).get(_root_key(root))


def _set_last_file(root: Path, rel: str) -> None:
    state = _load_state()
    last_files = state.setdefault("last_files", {})
    last_files[_root_key(root)] = rel
    state["last_root"] = _root_key(root)
    _save_state(state)


def _set_last_root(root: Path) -> None:
    state = _load_state()
    state["last_root"] = _root_key(root)
    _save_state(state)


# ---------- path safety ----------

def _has_root() -> bool:
    return ROOT is not None and ROOT.exists() and ROOT.is_dir()


def _require_root() -> Path:
    if not _has_root():
        raise HTTPException(409, "请先选择资料目录")
    return ROOT


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


# ---------- tree ----------

_SKIP_NAMES = {
    "__pycache__", "node_modules", ".git", ".idea", ".vscode",
    "build", "dist", "app_data", "_internal", "libreoffice", "LibreOffice",
}


def _skip_tree_entry(entry: Path) -> bool:
    name = entry.name
    if name.startswith(".") or name in _SKIP_NAMES:
        return True
    try:
        resolved = entry.resolve()
    except OSError:
        return True
    skip_roots = {
        DATA_DIR.resolve(),
        CACHE_DIR.resolve(),
        STATIC_DIR.resolve(),
        (APP_DIR / "app_data").resolve(),
        (APP_DIR / "_internal").resolve(),
        (APP_DIR / "libreoffice").resolve(),
        (APP_DIR / "LibreOffice").resolve(),
    }
    return resolved in skip_roots


def _build_tree(d: Path, recursive: bool = True) -> dict:
    root = _require_root()
    children = []
    try:
        entries = sorted(
            d.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except PermissionError:
        entries = []
    for entry in entries:
        if _skip_tree_entry(entry):
            continue
        name = entry.name
        rel = str(entry.relative_to(root)).replace("\\", "/")
        if entry.is_dir():
            children.append({"name": name, "path": rel, "type": "dir",
                             "children": _build_tree(entry, recursive)["children"] if recursive else []})
        else:
            children.append({"name": name, "path": rel, "type": "file",
                             "ext": entry.suffix.lower()})
    return {"name": d.name, "path": "", "type": "dir", "children": children}


def _iter_files_in_tree_order(d: Path):
    """Yield files in the same visual order as the left tree."""
    try:
        entries = sorted(
            d.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except (OSError, PermissionError):
        return

    for entry in entries:
        if _skip_tree_entry(entry):
            continue
        if entry.is_dir():
            yield from _iter_files_in_tree_order(entry)
        else:
            yield entry


# ---------- preconvert (background) ----------

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
            if root != ROOT:  # root switched mid-run
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
    if not PRECONVERT_ENABLED or not _has_root():
        return
    if _preconvert_task and not _preconvert_task.done():
        _preconvert_task.cancel()
    _preconvert_task = asyncio.create_task(_preconvert_worker(_require_root()))


# Background search-index prebuild
_prebuild_task: Optional[asyncio.Task] = None
_prebuild_root: Optional[Path] = None
_background_root: Optional[Path] = None
_warm_task: Optional[asyncio.Task] = None
_search_index_loaded_root: Optional[Path] = None


async def _prebuild_worker(root: Path):
    global _prebuild_root
    _prebuild_root = root
    loop = asyncio.get_running_loop()
    print(f"[search] 开始建索引 (root={root.name})")

    def _should_continue():
        return _prebuild_root == root

    def _checkpoint():
        search_mod.save_index(SEARCH_INDEX_PATH)

    try:
        await loop.run_in_executor(
            None, search_mod.prebuild, root, CACHE_DIR,
            _should_continue, _checkpoint
        )
    except asyncio.CancelledError:
        print("[search] 索引任务已取消（已保存当前进度）")
        try:
            search_mod.save_index(SEARCH_INDEX_PATH)
        except Exception:
            pass
        raise
    if _should_continue():
        await loop.run_in_executor(None, search_mod.save_index, SEARCH_INDEX_PATH)
        s = search_mod.index_stats()
        print(f"[search] 索引完成: {s['cached_files']} 个文件, "
              f"{s['cached_bytes']/1024:.0f} KB, 跳过 {s['skipped']} 个")


def _start_prebuild():
    global _prebuild_task
    if not _has_root():
        return
    if _prebuild_task and not _prebuild_task.done():
        _prebuild_task.cancel()
    _prebuild_task = asyncio.create_task(_prebuild_worker(_require_root()))


def _stop_background_tasks():
    global _prebuild_root, _background_root, _search_index_loaded_root
    _prebuild_root = None
    _background_root = None
    _search_index_loaded_root = None
    if _preconvert_task and not _preconvert_task.done():
        _preconvert_task.cancel()
    if _prebuild_task and not _prebuild_task.done():
        _prebuild_task.cancel()
    if _warm_task and not _warm_task.done():
        _warm_task.cancel()


def _warm_office_candidates(root: Path, limit: int = 2) -> list[Path]:
    """Return the next ``limit`` *office* files immediately after the user's
    last-opened file. The anchor file can be ANY type (PDF, MD, office…),
    so we scan all files in sorted order and look for office files coming
    after the anchor's position.
    """
    all_files = list(_iter_files_in_tree_order(root))

    last = _get_last_file(root)
    start = 0
    if last:
        last_path = (root / last).resolve()
        for i, p in enumerate(all_files):
            if p.resolve() == last_path:
                start = i + 1
                break

    result: list[Path] = []
    for p in all_files[start:]:
        if p.suffix.lower() in converter.OFFICE_EXTS:
            result.append(p)
            if len(result) >= limit:
                break
    return result


async def _warm_office_after_tree(root: Path):
    await asyncio.sleep(1.0)
    if ROOT != root:
        return
    for p in _warm_office_candidates(root, limit=2):
        if ROOT != root:
            return
        try:
            await converter.office_to_pdf(p, CACHE_DIR)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[prewarm] skip {p.name}: {e}")


def _start_warm_after_tree(root: Path):
    """Initial warm kicked once after /api/tree is loaded for this root."""
    global _background_root
    if _background_root == root:
        return
    _background_root = root
    _restart_warm(root)


def _restart_warm(root: Path):
    """Re-spawn the warm task. Used after each /api/file so the next 2
    office files (relative to the user's *current* position) get preconverted."""
    global _warm_task
    if root != ROOT:
        return
    if _warm_task and not _warm_task.done():
        _warm_task.cancel()
    _warm_task = asyncio.create_task(_warm_office_after_tree(root))


def _cancel_warm_task():
    if _warm_task and not _warm_task.done():
        _warm_task.cancel()


def _ensure_search_index_loaded() -> int:
    global _search_index_loaded_root
    if not _has_root():
        return 0
    if _search_index_loaded_root == ROOT:
        return 0
    loaded = search_mod.load_index(SEARCH_INDEX_PATH)
    _search_index_loaded_root = ROOT
    return loaded


@app.on_event("startup")
async def _on_startup():
    return
    # restore index from disk first (instant for already-known files)
    loaded = search_mod.load_index(SEARCH_INDEX_PATH)
    if loaded:
        print(f"[search] 从磁盘恢复 {loaded} 个文件的索引")
    _start_preconvert()
    _start_prebuild()


@app.on_event("shutdown")
async def _on_shutdown():
    _stop_background_tasks()


# ---------- routes ----------

@app.get("/api/tree")
async def api_tree(path: str = "", recursive: int = 1):
    if not _has_root():
        if path:
            raise HTTPException(409, "请先选择资料目录")
        return {"name": "", "path": "", "type": "dir", "children": [], "needs_root": True}
    root = _require_root()
    base = root if not path else _safe_resolve(path)
    if not base.is_dir():
        raise HTTPException(400, "path must be a directory")
    loop = asyncio.get_running_loop()
    tree = await loop.run_in_executor(None, _build_tree, base, bool(recursive))
    if not path:
        _start_warm_after_tree(root)
    return tree


@app.get("/api/preconvert/status")
def api_preconvert_status():
    s = dict(_preconvert_status)
    if s["total"]:
        s["progress"] = round(s["done"] / s["total"], 3)
    else:
        s["progress"] = 0.0
    return s


@app.get("/api/file")
async def api_file(path: str = Query(...), remember: int = 1, force: int = 0):
    root = _require_root()
    src = _safe_resolve(path)
    if src.is_dir():
        raise HTTPException(400, "path is a directory")

    if remember:
        _set_last_file(root, path)

    kind = converter.classify(src)
    response: Response
    if kind == "pdf":
        response = FileResponse(src, media_type="application/pdf")
    elif kind == "office":
        _cancel_warm_task()
        try:
            pdf = await converter.office_to_pdf(src, CACHE_DIR, force=bool(force))
        except RuntimeError as e:
            return JSONResponse({"error": "convert_failed", "message": str(e)}, status_code=500)
        response = FileResponse(pdf, media_type="application/pdf")
    elif kind == "markdown":
        response = HTMLResponse(converter.render_markdown(src, root))
    elif kind == "text":
        response = HTMLResponse(converter.render_text(src))
    elif kind == "image":
        response = FileResponse(src, media_type=converter.image_mime(src))
    else:
        return JSONResponse({"error": "unsupported", "name": src.name, "ext": src.suffix},
                            status_code=415)

    # After the user has moved to a new file, restart prewarm so the next
    # 2 office files (relative to the new position) get queued in background.
    # last_file has already been updated above when remember=1.
    if remember and PRECONVERT_ENABLED:
        _restart_warm(root)

    return response


@app.get("/api/raw")
def api_raw(path: str = Query(...)):
    src = _safe_resolve(path)
    if src.is_dir():
        raise HTTPException(400, "path is a directory")
    mime, _ = mimetypes.guess_type(src.name)
    return FileResponse(src, media_type=mime or "application/octet-stream",
                        filename=src.name)


@app.post("/api/cache/clear")
def api_cache_clear():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    skipped = 0
    for f in CACHE_DIR.iterdir():
        try:
            if f.is_file():
                f.unlink()
                removed += 1
        except OSError:
            skipped += 1  # likely held by an in-flight FileResponse on Windows
    return {"ok": True, "removed": removed, "skipped": skipped}


def _dir_stats(d: Path, glob: str = "*") -> dict:
    if not d.exists():
        return {"files": 0, "bytes": 0}
    files = [f for f in d.glob(glob) if f.is_file()]
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}


@app.get("/api/cache/stats")
def api_cache_stats():
    """Unified view of every on-disk cache the app maintains."""
    pdf = converter.cache_stats(CACHE_DIR)
    tts = _dir_stats(TTS_CACHE_DIR, "*.audio")
    idx = {
        "files": SEARCH_INDEX_PATH.exists() and 1 or 0,
        "bytes": SEARCH_INDEX_PATH.stat().st_size if SEARCH_INDEX_PATH.exists() else 0,
    }
    logs = _dir_stats(DATA_DIR / "logs")
    return {
        "office_pdf": {
            **pdf,
            "limit_bytes": 2 * 1024 * 1024 * 1024,
            "max_age_days": 30,
        },
        "tts_audio": {
            **tts,
            "limit_bytes": TTS_CACHE_MAX_BYTES,
            "max_age_days": TTS_CACHE_MAX_AGE_DAYS,
        },
        "search_index": idx,
        "logs": logs,
        "total_bytes": pdf["bytes"] + tts["bytes"] + idx["bytes"] + logs["bytes"],
    }


@app.post("/api/cache/cleanup")
def api_cache_cleanup():
    """Run cleanup on every cache (LRU + age)."""
    return {
        "office_pdf": converter.cleanup_cache(CACHE_DIR, max_age_days=30),
        "tts_audio":  _tts_cleanup(),
    }


@app.get("/api/search")
async def api_search(q: str = Query(...), limit: int = 50):
    """Full-text substring search. CPU-bound — runs in default executor."""
    root = _require_root()
    loop = asyncio.get_running_loop()
    loaded = await loop.run_in_executor(None, _ensure_search_index_loaded)
    results = await loop.run_in_executor(
        None, search_mod.search, root, CACHE_DIR, q, limit
    )
    await loop.run_in_executor(None, search_mod.save_index, SEARCH_INDEX_PATH)
    return {"query": q, "count": len(results), "results": results,
            "index": search_mod.index_stats(),
            "prebuild": search_mod.prebuild_status(),
            "loaded": loaded}


@app.get("/api/search/status")
def api_search_status():
    if not _has_root():
        s = search_mod.prebuild_status()
        s["needs_root"] = True
        return s
    return search_mod.prebuild_status()


@app.get("/api/search/skipped")
def api_search_skipped():
    if not _has_root():
        return {"skipped": {}, "needs_root": True}
    return {"skipped": search_mod.skipped_files()}


@app.get("/api/search/scanned")
def api_search_scanned():
    """List PDFs we detected as scanned (image-only). These can't be searched
    or fed to the AI text pipeline without OCR."""
    if not _has_root():
        return {"scanned": [], "needs_root": True}
    return {"scanned": search_mod.scanned_files(_require_root())}


# Thresholds for AI eligibility (kept in one place so tests/UI can fetch).
_AI_TEXT_HARD_LIMIT_CHARS = 1_400_000   # ~500K tokens at avg 2.8 chars/token
_AI_TEXT_SOFT_LIMIT_CHARS = 280_000     # ~100K tokens — above this we do summarize-first


@app.get("/api/file/ai-eligibility")
def api_file_ai_eligibility(path: str = Query(...)):
    """Tell the UI whether AI features apply to this file and why not."""
    _require_root()
    src = _safe_resolve(path)
    info = {
        "path": path,
        "supported": True,
        "mode": "direct",   # direct | summarize_first | unsupported
        "reasons": [],
        "char_count": 0,
        "is_scanned": False,
    }
    kind = converter.classify(src)
    if kind == "image":
        info["mode"] = "vision_required"
        info["reasons"].append("图片需要 vision 能力（未启用时不可用）")
        return info
    if kind == "unsupported":
        info["supported"] = False
        info["mode"] = "unsupported"
        info["reasons"].append(f"不支持的文件类型：{src.suffix}")
        return info

    if kind in ("pdf", "office", "markdown", "text"):
        text = search_mod.get_indexed_text(src, CACHE_DIR)
        info["char_count"] = len(text)
        if kind == "pdf" and search_mod.is_scanned(src):
            info["supported"] = False
            info["is_scanned"] = True
            info["mode"] = "unsupported"
            info["reasons"].append(
                "扫描版 PDF 没有文本层，无法用于 AI 整理 / 对话"
                "（可点页面右上 🖼 用 vision 单页识别）"
            )
            return info
        if not text.strip():
            # Office files extract text from the converted PDF in cache.
            # If the PDF isn't there yet, eligibility is still "supported"
            # — the actual AI call will trigger conversion on demand.
            if kind == "office":
                info["mode"] = "needs_conversion"
                info["reasons"].append(
                    "首次使用时需要先转换为 PDF（首条 AI 请求会触发，约 3-15s）"
                )
                return info
            info["supported"] = False
            info["mode"] = "unsupported"
            info["reasons"].append("尚未索引到任何文本内容（可能预转换/索引还没跑完）")
            return info
        if info["char_count"] > _AI_TEXT_HARD_LIMIT_CHARS:
            info["supported"] = False
            info["mode"] = "unsupported"
            info["reasons"].append(
                f"文档过大（{info['char_count']:,} 字符 > {_AI_TEXT_HARD_LIMIT_CHARS:,}），"
                "RAG 切分能力在后续版本支持"
            )
            return info
        if info["char_count"] > _AI_TEXT_SOFT_LIMIT_CHARS:
            info["mode"] = "summarize_first"
            info["reasons"].append(
                f"文档较长（{info['char_count']:,} 字符），将先生成结构化摘要，"
                "后续问答基于摘要 + 检索片段"
            )
    return info


@app.post("/api/search/rebuild")
def api_search_rebuild():
    if not _has_root():
        return {"ok": False, "needs_root": True, "detail": "请先选择资料目录"}
    search_mod.clear_cache()
    _start_prebuild()
    return {"ok": True}


# ---------- AI ----------

class AiChatBody(BaseModel):
    path: str
    question: str
    history: list[dict] = []   # list of {role, content}
    summarize_first: bool = False
    stream: bool = True


class AiSummarizeBody(BaseModel):
    path: str
    force: bool = False        # ignore cached ai_summary in annotations
    stream: bool = True


class AiTtsBody(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0


def _ai_require_text() -> Any:
    if ai_text_provider is None:
        raise HTTPException(503, "AI 未启用：请在 config.json.ai 中配置 active provider")
    return ai_text_provider


def _ai_require_tts() -> Any:
    if ai_tts_provider is None:
        raise HTTPException(503, "AI TTS 未启用：请配置 ai.tts_provider 或让 active provider 支持 TTS")
    return ai_tts_provider


async def _ai_load_document(path: str) -> tuple[Path, str]:
    """Resolve a file and return (Path, indexed text). Raises HTTPException
    with a clear reason if AI features are unavailable for this file.

    For office files this awaits ``office_to_pdf`` if needed — extraction
    relies on the converted PDF being present in cache. Without this, AI
    actions on a freshly opened (but not yet pre-converted) office file
    would error with "尚未索引到文本".
    """
    src = _safe_resolve(path)
    if src.is_dir():
        raise HTTPException(400, "path is a directory")
    kind = converter.classify(src)
    if kind == "image":
        raise HTTPException(400, "图片请走 vision 接口")
    if kind == "unsupported":
        raise HTTPException(400, f"不支持的文件类型：{src.suffix}")
    if kind == "pdf" and search_mod.is_scanned(src):
        raise HTTPException(
            422,
            "扫描版 PDF 无文本层，无法用于 AI 整理 / 对话。"
            "可在预览页用 🖼 vision 单页识别。",
        )

    # Office: ensure the converted PDF exists before we try to read text from it.
    # office_to_pdf is cached + locked, so this is a no-op on hit.
    if kind == "office":
        try:
            await converter.office_to_pdf(src, CACHE_DIR)
        except RuntimeError as e:
            raise HTTPException(
                422, f"该 office 文件无法转换为 PDF，AI 不可用：{e}"
            )

    text = search_mod.get_indexed_text(src, CACHE_DIR)
    if kind == "pdf" and (search_mod.is_scanned(src) or not text.strip()):
        raise HTTPException(
            422,
            "扫描版 PDF 没有可提取的文本层，暂不支持 AI 整理 / 对话。"
            "请先通过 OCR 转成可复制文本后再使用。",
        )
    if not text.strip():
        raise HTTPException(422, "文档尚未索引到文本（预转换 / 索引可能还没跑完）")
    if len(text) > _AI_TEXT_HARD_LIMIT_CHARS:
        raise HTTPException(
            413,
            f"文档过大（{len(text):,} 字符 > {_AI_TEXT_HARD_LIMIT_CHARS:,}）；"
            "等待后续版本的 RAG 切分支持。",
        )
    return src, text


def _mask_key(k: Optional[str]) -> str:
    if not k:
        return "(empty)"
    k = str(k)
    if len(k) <= 8:
        return "*" * len(k)
    return f"{k[:4]}…{k[-4:]} (len={len(k)})"


@app.get("/api/ai/status")
def api_ai_status():
    """Status + masked credential preview so users can verify the running
    process actually picked up their env vars."""
    text_info = ai_text_provider.info() if ai_text_provider else None
    tts_info = ai_tts_provider.info() if ai_tts_provider else None
    if text_info and hasattr(ai_text_provider, "api_key"):
        text_info["api_key_preview"] = _mask_key(ai_text_provider.api_key)
        if hasattr(ai_text_provider, "group_id"):
            text_info["group_id_preview"] = _mask_key(getattr(ai_text_provider, "group_id", ""))
    if tts_info and hasattr(ai_tts_provider, "api_key"):
        tts_info["api_key_preview"] = _mask_key(ai_tts_provider.api_key)
        if hasattr(ai_tts_provider, "group_id"):
            tts_info["group_id_preview"] = _mask_key(getattr(ai_tts_provider, "group_id", ""))
        if hasattr(ai_tts_provider, "base_url"):
            tts_info["base_url"] = getattr(ai_tts_provider, "base_url")
    # Also surface which env vars the OS reports — useful when users wonder
    # whether their `set` / `setx` actually reached this process.
    env_seen = {}
    for k in ("MINIMAX_API_KEY", "MINIMAX_GROUP_ID", "MIMO_API_KEY"):
        env_seen[k] = _mask_key(os.environ.get(k))
    return {
        "text": text_info,
        "tts": tts_info,
        "providers_available": ai_factory.available_provider_types(),
        "thresholds": {
            "hard_limit_chars": _AI_TEXT_HARD_LIMIT_CHARS,
            "soft_limit_chars": _AI_TEXT_SOFT_LIMIT_CHARS,
        },
        "env": env_seen,
    }


def _sse_stream(token_iter):
    """Wrap an async iterator of text deltas in Server-Sent-Events frames."""
    async def gen():
        try:
            async for item in token_iter:
                if not item:
                    continue
                if isinstance(item, dict):
                    payload = json.dumps(item, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    continue
                delta = item
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"
            yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/ai/summarize")
async def api_ai_summarize(body: AiSummarizeBody):
    provider = _ai_require_text()

    async def run_stream():
        yield {"stage": "准备文档"}
        src, text = await _ai_load_document(body.path)
        root = _require_root()
        rel = body.path

        if not body.force:
            yield {"stage": "检查已生成摘要"}
            anno = anno_store.get(root, rel)
            cached = (anno or {}).get("ai_summary")
            if cached:
                yield {"stage": "使用已生成摘要", "cached": True}
                yield cached
                return

        yield {"stage": "AI 正在整理文档"}
        chunks = []
        async for d in ai_tasks.summarize_document(provider, src.name, text):
            chunks.append(d)
            yield d

        full = "".join(chunks).strip()
        if full:
            yield {"stage": "保存生成结果"}
            anno_store.patch(root, rel, {"ai_summary": full})

    if body.stream:
        return _sse_stream(run_stream())

    src, text = await _ai_load_document(body.path)
    root = _require_root()
    rel = body.path
    if not body.force:
        anno = anno_store.get(root, rel)
        cached = (anno or {}).get("ai_summary")
        if cached:
            return {"summary": cached, "cached": True}

    full = ""
    async for d in ai_tasks.summarize_document(provider, src.name, text):
        full += d
    if full.strip():
        anno_store.patch(root, rel, {"ai_summary": full.strip()})
    return {"summary": full, "cached": False}


@app.post("/api/ai/chat")
async def api_ai_chat(body: AiChatBody):
    provider = _ai_require_text()
    src, text = await _ai_load_document(body.path)
    history = [AIMessage(role=m["role"], content=m["content"]) for m in body.history
               if m.get("role") in {"user", "assistant"} and m.get("content")]

    async def run():
        async for d in ai_tasks.chat_about_document(
            provider, src.name, text, history, body.question
        ):
            yield d

    if body.stream:
        return _sse_stream(run())

    full = ""
    async for d in run():
        full += d
    return {"answer": full}


def _tts_cache_paths(provider_name: str, text: str, voice: str | None,
                     speed: float) -> tuple[Path, Path]:
    """Return (audio_path, mime_meta_path) for a given TTS request.
    Key = sha1(provider|model-config|text|voice|speed)."""
    import hashlib
    h = hashlib.sha1()
    h.update(provider_name.encode("utf-8"))
    h.update(b"|")
    h.update((voice or "").encode("utf-8"))
    h.update(b"|")
    h.update(f"{speed:.2f}".encode("ascii"))
    h.update(b"|")
    h.update(text.encode("utf-8"))
    key = h.hexdigest()
    return TTS_CACHE_DIR / f"{key}.audio", TTS_CACHE_DIR / f"{key}.mime"


def _tts_cache_get(provider_name: str, text: str, voice: str | None,
                   speed: float) -> Optional[tuple[bytes, str]]:
    audio_p, mime_p = _tts_cache_paths(provider_name, text, voice, speed)
    if not audio_p.exists() or not mime_p.exists():
        return None
    try:
        mime = mime_p.read_text(encoding="utf-8").strip() or "audio/mpeg"
        # touch for LRU
        try: os.utime(audio_p, None)
        except OSError: pass
        return audio_p.read_bytes(), mime
    except OSError:
        return None


def _tts_cache_put(provider_name: str, text: str, voice: str | None,
                   speed: float, audio: bytes, mime: str) -> None:
    try:
        TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        audio_p, mime_p = _tts_cache_paths(provider_name, text, voice, speed)
        audio_p.write_bytes(audio)
        mime_p.write_text(mime, encoding="utf-8")
    except OSError as e:
        get_logger("ai").warning("TTS 缓存写入失败: %s", e)


# Default thresholds — exposed so they can be tuned from a single place
TTS_CACHE_MAX_AGE_DAYS = 60
TTS_CACHE_MAX_BYTES    = 500 * 1024 * 1024   # 500 MB


def _tts_cleanup(max_age_days: int = TTS_CACHE_MAX_AGE_DAYS,
                 max_total_bytes: int = TTS_CACHE_MAX_BYTES) -> dict:
    """Delete TTS cache entries older than max_age_days; then LRU-trim to size cap.

    Each cached item is two files (``.audio`` + ``.mime``). They're managed as
    a pair so partial deletion never leaves orphans.
    """
    if not TTS_CACHE_DIR.exists():
        return {"removed": 0, "kept": 0, "bytes": 0}

    now = time.time()
    cutoff = now - max_age_days * 86400
    entries = []   # [(atime, size, audio_path, mime_path)]
    removed = 0

    for audio_p in TTS_CACHE_DIR.glob("*.audio"):
        mime_p = audio_p.with_suffix(".mime")
        try:
            st = audio_p.stat()
        except OSError:
            continue
        atime = max(st.st_atime, st.st_mtime)
        if atime < cutoff:
            try:
                audio_p.unlink(missing_ok=True)
                mime_p.unlink(missing_ok=True)
                removed += 1
                continue
            except OSError:
                pass
        entries.append((atime, st.st_size, audio_p, mime_p))

    # size-cap pass (oldest atime first)
    entries.sort()
    total = sum(e[1] for e in entries)
    i = 0
    while total > max_total_bytes and i < len(entries):
        _, size, audio_p, mime_p = entries[i]
        try:
            audio_p.unlink(missing_ok=True)
            mime_p.unlink(missing_ok=True)
            total -= size
            removed += 1
        except OSError:
            pass
        i += 1

    kept = max(len(entries) - i, 0)
    return {"removed": removed, "kept": kept, "bytes": total}


@app.post("/api/ai/tts")
async def api_ai_tts(body: AiTtsBody):
    provider = _ai_require_tts()
    if not body.text.strip():
        raise HTTPException(400, "text 不能为空")

    # 1) Try local cache first — same text/voice/speed = same audio.
    hit = _tts_cache_get(provider.name, body.text, body.voice, body.speed)
    if hit is not None:
        audio, mime = hit
        return Response(content=audio, media_type=mime,
                        headers={"X-TTS-Cache": "hit"})

    # 2) Cache miss — call the provider.
    try:
        result = await provider.tts(body.text, voice=body.voice, speed=body.speed)
    except CapabilityNotSupported as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        get_logger("ai").exception("TTS 失败")
        raise HTTPException(502, f"TTS 失败：{e}")

    # Providers return (bytes, mime). Tolerate old bytes-only too.
    if isinstance(result, tuple) and len(result) == 2:
        audio, mime = result
    else:
        audio, mime = result, "audio/mpeg"

    # 3) Save to disk for next time.
    _tts_cache_put(provider.name, body.text, body.voice, body.speed, audio, mime)

    return Response(content=audio, media_type=mime,
                    headers={"X-TTS-Cache": "miss"})


@app.get("/api/ai/tts/stats")
def api_ai_tts_stats():
    """Kept for backwards-compat; the unified /api/cache/stats is preferred."""
    return _dir_stats(TTS_CACHE_DIR, "*.audio")


@app.post("/api/ai/tts/clear")
def api_ai_tts_clear():
    if not TTS_CACHE_DIR.exists():
        return {"removed": 0}
    n = 0
    for f in TTS_CACHE_DIR.iterdir():
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return {"removed": n}


# ---------- annotations ----------

@app.get("/api/anno/all")
def api_anno_all():
    """All annotations + tag palette for the current root."""
    if not _has_root():
        return {"files": {}, "tag_palette": [], "needs_root": True}
    return anno_store.all_for_root(_require_root())


@app.get("/api/anno")
def api_anno_get(path: str = Query(...)):
    _safe_resolve(path)  # validate
    return anno_store.get(_require_root(), path)


@app.patch("/api/anno")
async def api_anno_patch(request: Request, path: str = Query(...)):
    _safe_resolve(path)  # validate
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    return anno_store.patch(_require_root(), path, body)


class TagPaletteBody(BaseModel):
    tags: list[str]


@app.put("/api/anno/palette")
def api_anno_palette(body: TagPaletteBody):
    return {"palette": anno_store.set_palette(_require_root(), body.tags)}


@app.get("/api/health")
def api_health():
    return {"ok": True, "app_id": APP_ID, "app_name": APP_NAME,
            "soffice": converter.find_soffice(),
            "root": str(ROOT) if _has_root() else None,
            "needs_root": not _has_root()}


@app.get("/api/root")
def api_root_get():
    if not _has_root():
        return {"root": None, "last_file": None, "needs_root": True}
    root = _require_root()
    return {
        "root": str(root),
        "last_file": _get_last_file(root),
        "needs_root": False,
    }


class RootBody(BaseModel):
    path: str


@app.post("/api/root")
def api_root_set(body: RootBody):
    global ROOT
    new_path = Path(body.path).expanduser()
    if not new_path.is_absolute():
        new_path = (APP_DIR / new_path).resolve()
    new_path = new_path.resolve()
    if not new_path.exists() or not new_path.is_dir():
        raise HTTPException(400, f"not a directory: {new_path}")
    _stop_background_tasks()
    ROOT = new_path
    _set_last_root(ROOT)
    # Reset & re-build search index for the new root.
    search_mod.clear_cache()
    return {"root": str(ROOT), "last_file": _get_last_file(ROOT), "needs_root": False}


@app.post("/api/reveal")
def api_reveal(body: RootBody):
    """Show the file in the OS file manager (Explorer / Finder / xdg-open)."""
    src = _safe_resolve(body.path)
    try:
        if sys.platform.startswith("win"):
            # explorer /select,"<path>" must be passed as ONE command-line
            # string. If we use a list, Python's list2cmdline wraps the whole
            # `/select,<path>` in quotes and explorer fails to parse the flag,
            # falling back to its default folder.
            win_path = str(src).replace("/", "\\")
            subprocess.Popen(f'explorer /select,"{win_path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(src)])
        else:
            subprocess.Popen(["xdg-open", str(src.parent)])
    except Exception as e:
        raise HTTPException(500, f"reveal failed: {e}")
    return {"ok": True}


@app.post("/api/shutdown")
def api_shutdown(request: Request):
    """Shutdown the server (local-only)."""
    client = request.client
    if client is None or client.host not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(403, "仅允许本地访问")
    log = get_logger("browse")
    log.info("收到退出程序请求 from %s", client.host)
    killed = converter.kill_orphan_soffice()
    if killed:
        log.info("退出时清理 %d 个残留 soffice 进程", killed)
    _delayed_exit(0.6)
    return {"ok": True, "message": "程序正在退出"}


@app.post("/api/pick-folder")
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
            initial = str(ROOT) if _has_root() else str(APP_DIR)
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


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon():
    """Serve favicon from static directory."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    raise HTTPException(404, "favicon not found")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
    state = _load_state()
    saved = state.get("last_root")
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
    args = parser.parse_args()

    # Migrate legacy last_root/last_files (used to live in config.json) into state.json
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_state()

    log_dir = init_logging(DATA_DIR)
    log = get_logger("browse")

    # Check for existing service BEFORE initializing full state
    if not args.force_server and _is_our_service_running(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        log.info("已有服务运行中 (%s)，复用已有服务", url)
        if not args.no_browser:
            opened = _open_app_url(url)
            if not opened:
                log.warning("请手动访问: %s", url)
        return

    global ROOT, PRECONVERT_ENABLED
    ROOT = _resolve_initial_root(args.root)
    PRECONVERT_ENABLED = not args.no_preconvert
    if _has_root():
        _set_last_root(_require_root())
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cleaned = converter.cleanup_cache(CACHE_DIR, max_age_days=30)
    if cleaned["removed"]:
        log.info("PDF cache: 删除 %d 项过期，保留 %d 项 (%.1f MB)",
                 cleaned["removed"], cleaned["kept"], cleaned["bytes"]/1024/1024)
    tts_cleaned = _tts_cleanup()
    if tts_cleaned["removed"]:
        log.info("TTS cache: 删除 %d 项过期，保留 %d 项 (%.1f MB)",
                 tts_cleaned["removed"], tts_cleaned["kept"], tts_cleaned["bytes"]/1024/1024)

    soffice = converter.find_soffice()
    log.info("程序启动: %s", APP_NAME)
    log.info("app_dir: %s", APP_DIR)
    log.info("data: %s", DATA_DIR)
    log.info("config: %s", CONFIG_PATH)
    log.info("frozen: %s", getattr(sys, "frozen", False))
    log.info("log_dir: %s", log_dir)
    log.info("root: %s", ROOT)
    log.info("LibreOffice: %s",
             soffice or "未检测到（doc/docx/xlsx 等格式将无法预览，请安装 LibreOffice）")
    log.info("host: %s  port: %s", args.host, args.port)
    log.info("open http://%s:%d/", args.host, args.port)

    # AI providers (best-effort: missing config just disables AI features)
    global ai_text_provider, ai_tts_provider
    cfg = _load_config()
    ai_cfg = cfg.get("ai") or {}
    try:
        ai_text_provider = ai_factory.make_active(ai_cfg)
    except Exception as e:
        log.warning("AI text provider 初始化失败: %s", e)
        ai_text_provider = None
    try:
        ai_tts_provider = ai_factory.make_tts(ai_cfg)
    except Exception as e:
        log.warning("AI tts provider 初始化失败: %s", e)
        ai_tts_provider = None
    log.info("AI text: %s",
             ai_text_provider.info() if ai_text_provider else "未配置")
    log.info("AI tts:  %s",
             ai_tts_provider.info() if ai_tts_provider else "未配置")

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}/"
        health_url = f"http://{args.host}:{args.port}/api/health"
        _open_browser_when_ready(url, health_url)

    # Ensure orphaned soffice subprocesses are killed on exit
    import atexit, signal
    def _on_exit(*_a):
        killed = converter.kill_orphan_soffice()
        if killed:
            log.warning("退出时清理 %d 个残留 soffice 进程", killed)
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
