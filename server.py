"""Local file browser server."""
from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import annotations as annotations_mod
import converter
import search as search_mod

BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
CACHE_DIR = BASE_DIR / "cache"
CONFIG_PATH = BASE_DIR / "config.json"
ANNO_PATH = BASE_DIR / "annotations.json"
SEARCH_INDEX_PATH = BASE_DIR / "search_index.json"
DEFAULT_ROOT_REL = "教学资料"

anno_store = annotations_mod.AnnotationStore(ANNO_PATH)

app = FastAPI()

ROOT: Path = BASE_DIR
PRECONVERT_ENABLED: bool = True

# Background preconvert state
_preconvert_task: Optional[asyncio.Task] = None
_preconvert_status: dict = {"running": False, "total": 0, "done": 0,
                             "current": None, "errors": 0, "started_at": None,
                             "finished_at": None}


# ---------- config persistence ----------

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"[browse] warn: failed to save config: {e}")


def _root_key(root: Path) -> str:
    return str(root.resolve()).replace("\\", "/")


def _get_last_file(root: Path) -> Optional[str]:
    cfg = _load_config()
    return (cfg.get("last_files") or {}).get(_root_key(root))


def _set_last_file(root: Path, rel: str) -> None:
    cfg = _load_config()
    last_files = cfg.setdefault("last_files", {})
    last_files[_root_key(root)] = rel
    cfg["last_root"] = _root_key(root)
    _save_config(cfg)


def _set_last_root(root: Path) -> None:
    cfg = _load_config()
    cfg["last_root"] = _root_key(root)
    _save_config(cfg)


# ---------- path safety ----------

def _safe_resolve(rel: str) -> Path:
    if not rel:
        raise HTTPException(400, "path is required")
    candidate = (ROOT / rel).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise HTTPException(403, "path escapes root")
    if not candidate.exists():
        raise HTTPException(404, f"not found: {rel}")
    return candidate


# ---------- tree ----------

_SKIP_NAMES = {"__pycache__", "node_modules", ".git", ".idea", ".vscode"}


def _build_tree(d: Path, recursive: bool = True) -> dict:
    children = []
    try:
        entries = sorted(
            d.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except PermissionError:
        entries = []
    for entry in entries:
        name = entry.name
        if name.startswith(".") or name in _SKIP_NAMES:
            continue
        if entry.resolve() in {CACHE_DIR.resolve(), STATIC_DIR.resolve()}:
            continue
        rel = str(entry.relative_to(ROOT)).replace("\\", "/")
        if entry.is_dir():
            children.append({"name": name, "path": rel, "type": "dir",
                             "children": _build_tree(entry, recursive)["children"] if recursive else []})
        else:
            children.append({"name": name, "path": rel, "type": "file",
                             "ext": entry.suffix.lower()})
    return {"name": d.name, "path": "", "type": "dir", "children": children}


# ---------- preconvert (background) ----------

def _scan_office_files(root: Path) -> list[Path]:
    """Recursively find all office files under root, skipping caches/hidden."""
    out: list[Path] = []
    cache_resolved = CACHE_DIR.resolve()
    static_resolved = STATIC_DIR.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place prune
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in _SKIP_NAMES
        ]
        # Avoid walking our own cache/static if root is project dir
        if Path(dirpath).resolve() in {cache_resolved, static_resolved}:
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
    if not PRECONVERT_ENABLED:
        return
    if _preconvert_task and not _preconvert_task.done():
        _preconvert_task.cancel()
    _preconvert_task = asyncio.create_task(_preconvert_worker(ROOT))


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
    if _prebuild_task and not _prebuild_task.done():
        _prebuild_task.cancel()
    _prebuild_task = asyncio.create_task(_prebuild_worker(ROOT))


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
    files: list[Path] = []
    last = _get_last_file(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_NAMES]
        for name in sorted(filenames, key=str.lower):
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            if p.suffix.lower() in converter.OFFICE_EXTS:
                files.append(p)
    if last:
        last_path = (root / last).resolve()
        for i, p in enumerate(files):
            if p.resolve() == last_path:
                return files[i + 1:i + 1 + limit]
    return files[:limit]


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
    global _background_root
    if _background_root == root:
        return
    _background_root = root
    global _warm_task
    if _warm_task and not _warm_task.done():
        _warm_task.cancel()
    _warm_task = asyncio.create_task(_warm_office_after_tree(root))


def _cancel_warm_task():
    if _warm_task and not _warm_task.done():
        _warm_task.cancel()


def _ensure_search_index_loaded() -> int:
    global _search_index_loaded_root
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
    base = ROOT if not path else _safe_resolve(path)
    if not base.is_dir():
        raise HTTPException(400, "path must be a directory")
    loop = asyncio.get_running_loop()
    tree = await loop.run_in_executor(None, _build_tree, base, bool(recursive))
    if not path:
        _start_warm_after_tree(ROOT)
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
    src = _safe_resolve(path)
    if src.is_dir():
        raise HTTPException(400, "path is a directory")

    if remember:
        _set_last_file(ROOT, path)

    kind = converter.classify(src)
    if kind == "pdf":
        return FileResponse(src, media_type="application/pdf")
    if kind == "office":
        _cancel_warm_task()
        try:
            pdf = await converter.office_to_pdf(src, CACHE_DIR, force=bool(force))
        except RuntimeError as e:
            return JSONResponse({"error": "convert_failed", "message": str(e)}, status_code=500)
        return FileResponse(pdf, media_type="application/pdf")
    if kind == "markdown":
        return HTMLResponse(converter.render_markdown(src, ROOT))
    if kind == "text":
        return HTMLResponse(converter.render_text(src))
    if kind == "image":
        return FileResponse(src, media_type=converter.image_mime(src))
    return JSONResponse({"error": "unsupported", "name": src.name, "ext": src.suffix},
                        status_code=415)


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


@app.get("/api/cache/stats")
def api_cache_stats():
    return converter.cache_stats(CACHE_DIR)


@app.get("/api/search")
async def api_search(q: str = Query(...), limit: int = 50):
    """Full-text substring search. CPU-bound — runs in default executor."""
    loop = asyncio.get_running_loop()
    loaded = await loop.run_in_executor(None, _ensure_search_index_loaded)
    results = await loop.run_in_executor(
        None, search_mod.search, ROOT, CACHE_DIR, q, limit
    )
    await loop.run_in_executor(None, search_mod.save_index, SEARCH_INDEX_PATH)
    return {"query": q, "count": len(results), "results": results,
            "index": search_mod.index_stats(),
            "prebuild": search_mod.prebuild_status(),
            "loaded": loaded}


@app.get("/api/search/status")
def api_search_status():
    return search_mod.prebuild_status()


@app.get("/api/search/skipped")
def api_search_skipped():
    return {"skipped": search_mod.skipped_files()}


@app.post("/api/search/rebuild")
def api_search_rebuild():
    search_mod.clear_cache()
    _start_prebuild()
    return {"ok": True}


# ---------- annotations ----------

@app.get("/api/anno/all")
def api_anno_all():
    """All annotations + tag palette for the current root."""
    return anno_store.all_for_root(ROOT)


@app.get("/api/anno")
def api_anno_get(path: str = Query(...)):
    _safe_resolve(path)  # validate
    return anno_store.get(ROOT, path)


@app.patch("/api/anno")
async def api_anno_patch(request: Request, path: str = Query(...)):
    _safe_resolve(path)  # validate
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    return anno_store.patch(ROOT, path, body)


class TagPaletteBody(BaseModel):
    tags: list[str]


@app.put("/api/anno/palette")
def api_anno_palette(body: TagPaletteBody):
    return {"palette": anno_store.set_palette(ROOT, body.tags)}


@app.get("/api/health")
def api_health():
    return {"ok": True, "soffice": converter.find_soffice(), "root": str(ROOT)}


@app.get("/api/root")
def api_root_get():
    return {
        "root": str(ROOT),
        "last_file": _get_last_file(ROOT),
    }


class RootBody(BaseModel):
    path: str


@app.post("/api/root")
def api_root_set(body: RootBody):
    global ROOT
    new_path = Path(body.path).expanduser()
    if not new_path.is_absolute():
        new_path = (BASE_DIR / new_path).resolve()
    new_path = new_path.resolve()
    if not new_path.exists() or not new_path.is_dir():
        raise HTTPException(400, f"not a directory: {new_path}")
    _stop_background_tasks()
    ROOT = new_path
    _set_last_root(ROOT)
    # Reset & re-build search index for the new root.
    search_mod.clear_cache()
    return {"root": str(ROOT), "last_file": _get_last_file(ROOT)}


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
            initial = str(ROOT) if ROOT.exists() else str(BASE_DIR)
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


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- startup ----------

def _open_browser_later(url: str, delay: float = 1.0):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def _resolve_initial_root(cli_root: Optional[str]) -> Path:
    """Priority: explicit CLI > saved config last_root > default folder under BASE_DIR."""
    # explicit CLI takes precedence
    if cli_root:
        p = Path(cli_root)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        if p.exists() and p.is_dir():
            return p.resolve()
        print(f"[browse] warn: --root '{p}' not found, falling back")

    # saved config
    cfg = _load_config()
    saved = cfg.get("last_root")
    if saved:
        p = Path(saved)
        if p.exists() and p.is_dir():
            return p.resolve()
        print(f"[browse] warn: saved last_root '{saved}' no longer exists, falling back")

    # default
    p = (BASE_DIR / DEFAULT_ROOT_REL).resolve()
    if p.exists() and p.is_dir():
        return p
    return BASE_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="initial root directory (overrides saved config)")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-preconvert", action="store_true",
                        help="disable background pre-conversion of office files")
    args = parser.parse_args()

    global ROOT, PRECONVERT_ENABLED
    ROOT = _resolve_initial_root(args.root)
    PRECONVERT_ENABLED = not args.no_preconvert
    _set_last_root(ROOT)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cleaned = converter.cleanup_cache(CACHE_DIR, max_age_days=30)
    if cleaned["removed"]:
        print(f"[browse] cache: 删除 {cleaned['removed']} 项过期，保留 {cleaned['kept']} 项 "
              f"({cleaned['bytes']/1024/1024:.1f} MB)")

    soffice = converter.find_soffice()
    print(f"[browse] root: {ROOT}")
    print(f"[browse] LibreOffice: {soffice or '未检测到（doc/docx/xlsx 等格式将无法预览，请安装 LibreOffice）'}")
    print(f"[browse] open http://{args.host}:{args.port}/")

    if not args.no_browser:
        _open_browser_later(f"http://{args.host}:{args.port}/")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
