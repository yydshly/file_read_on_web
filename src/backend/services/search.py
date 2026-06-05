"""Substring-based content search across all readable files under a root.

Strategy:
- For .pdf — extract text via pypdf, capped at 200 pages per file.
- For .md / .txt / .log / .csv — read directly as UTF-8.
- For office files (.doc/.docx/.xls/.xlsx/.ppt/.pptx/...) — use the
  preconverted PDF in cache_dir if it exists; otherwise skip.

Text is cached in memory keyed by absolute path + mtime so repeated searches
are fast. Search itself is a simple case-insensitive substring scan — works
well for Chinese without needing a tokenizer like jieba.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from . import converter

log = logging.getLogger("search")

try:
    import pypdf  # type: ignore
except ImportError:  # pragma: no cover
    pypdf = None  # noqa

_TEXT_EXTS = {".md", ".txt", ".log", ".csv"}
_PDF_PAGE_CAP = 200                # don't extract beyond this many pages
_TEXT_LEN_CAP = 2_000_000          # 2MB per file capped
_PDF_MAX_BYTES = 30 * 1024 * 1024  # skip PDFs larger than 30 MB
_SCANNED_TEXT_THRESHOLD = 100      # below this many extracted chars -> likely scanned
_text_cache: dict[str, tuple[float, str]] = {}
_skipped: dict[str, str] = {}      # abs path -> reason (file completely skipped)
_scanned: set[str] = set()         # abs paths of PDFs detected as scanned (image-only)
_cache_lock = threading.Lock()
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".idea", ".vscode",
    "build", "dist", "app_data", "_internal", "libreoffice", "LibreOffice",
}


# ------------------------------------------------------------------
# Internal helpers — lock-protected mutation
# ------------------------------------------------------------------

def _set_skipped(abs_key: str, reason: str) -> None:
    """Thread-safe write to _skipped."""
    with _cache_lock:
        _skipped[abs_key] = reason


def _mark_scanned(abs_key: str, scanned: bool) -> None:
    """Thread-safe write to _scanned."""
    with _cache_lock:
        if scanned:
            _scanned.add(abs_key)
        else:
            _scanned.discard(abs_key)


# ------------------------------------------------------------------
# Text extraction
# ------------------------------------------------------------------

def _extract_pdf(p: Path) -> str:
    if pypdf is None:
        return ""
    try:
        size = p.stat().st_size
    except OSError:
        return ""
    abs_key = str(p.resolve())
    if size > _PDF_MAX_BYTES:
        _set_skipped(abs_key, f"too large ({size/1024/1024:.1f} MB > {_PDF_MAX_BYTES/1024/1024:.0f} MB)")
        return ""
    try:
        reader = pypdf.PdfReader(str(p))
    except Exception as e:
        _set_skipped(abs_key, f"pypdf open failed: {e}")
        return ""
    parts: list[str] = []
    n = min(len(reader.pages), _PDF_PAGE_CAP)
    for i in range(n):
        try:
            parts.append(reader.pages[i].extract_text() or "")
        except Exception:
            continue
        if sum(len(s) for s in parts) > _TEXT_LEN_CAP:
            break
    return "\n".join(parts)[:_TEXT_LEN_CAP]


def _extract_text(p: Path, cache_dir: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(p)
    if ext in _TEXT_EXTS:
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:_TEXT_LEN_CAP]
        except Exception:
            return ""
    if ext in converter.OFFICE_EXTS:
        try:
            key = converter._cache_key(p)
        except OSError:
            return ""
        pdf = cache_dir / f"{key}.pdf"
        if pdf.exists():
            return _extract_pdf(pdf)
    return ""


# ------------------------------------------------------------------
# Text cache access — double-check locking
# ------------------------------------------------------------------

def _get_text(p: Path, cache_dir: Path) -> str:
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return ""
    abs_key = str(p.resolve())

    # Fast path: check cache under lock
    with _cache_lock:
        cached = _text_cache.get(abs_key)
        if cached and cached[0] == mtime:
            return cached[1]

    # Slow path: extract text (outside lock — can be slow for PDFs)
    text = _extract_text(p, cache_dir)

    # If mtime changed while extracting, don't cache stale content
    try:
        current_mtime = p.stat().st_mtime
    except OSError:
        return text
    if current_mtime != mtime:
        return text

    # Write to cache under lock, with double-check
    with _cache_lock:
        # Another thread may have cached it while we were extracting
        cached = _text_cache.get(abs_key)
        if cached and cached[0] == mtime:
            return cached[1]
        _text_cache[abs_key] = (mtime, text)

    # Track scanned PDFs: those whose pypdf yields almost no text.
    # Check skipped snapshot safely under lock.
    with _cache_lock:
        is_skipped = abs_key in _skipped

    if not is_skipped and p.suffix.lower() == ".pdf":
        _mark_scanned(abs_key, len(text.strip()) < _SCANNED_TEXT_THRESHOLD)

    return text


def _snippet(text: str, lc_text: str, q_lc: str, q_len: int,
             before: int = 30, after: int = 60) -> list[str]:
    out: list[str] = []
    start = 0
    for _ in range(3):
        idx = lc_text.find(q_lc, start)
        if idx < 0:
            break
        a = max(0, idx - before)
        b = min(len(text), idx + q_len + after)
        snippet = text[a:b].replace("\n", " ").replace("\r", " ").strip()
        # prefix ellipsis when not at start
        if a > 0:
            snippet = "…" + snippet
        if b < len(text):
            snippet = snippet + "…"
        out.append(snippet)
        start = idx + q_len
    return out


def search(root: Path, cache_dir: Path, query: str, limit: int = 50) -> list[dict]:
    """Return [{path, name, hits, snippets}], sorted by hit count desc."""
    q = (query or "").strip()
    if not q:
        return []
    q_lc = q.lower()
    q_len = len(q_lc)
    results: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
        # don't descend into our own cache dir if root == project dir
        if Path(dirpath).resolve() == cache_dir.resolve():
            dirnames[:] = []
            continue
        for name in filenames:
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            text = _get_text(p, cache_dir)
            if not text:
                continue
            tl = text.lower()
            if q_lc not in tl:
                continue
            total = tl.count(q_lc)
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            results.append({
                "path": rel,
                "name": name,
                "hits": total,
                "snippets": _snippet(text, tl, q_lc, q_len),
            })
            if len(results) >= limit * 4:  # collect more then trim after sort
                break
        if len(results) >= limit * 4:
            break

    results.sort(key=lambda r: -r["hits"])
    return results[:limit]


def index_stats() -> dict:
    with _cache_lock:
        values = list(_text_cache.values())
        skipped_count = len(_skipped)
        scanned_count = len(_scanned)
    return {
        "cached_files": len(values),
        "cached_bytes": sum(len(t) for _, t in values),
        "skipped": skipped_count,
        "scanned": scanned_count,
    }


def skipped_files() -> dict:
    with _cache_lock:
        return dict(_skipped)


def scanned_files(root: Path | None = None) -> list[str]:
    """Return paths detected as scanned (image-only) PDFs. If root provided,
    paths are returned root-relative; otherwise absolute."""
    with _cache_lock:
        scanned_snapshot = list(_scanned)
    out = []
    for abs_p in scanned_snapshot:
        if root is None:
            out.append(abs_p)
        else:
            try:
                rel = str(Path(abs_p).relative_to(root)).replace("\\", "/")
                out.append(rel)
            except ValueError:
                continue
    return out


def get_indexed_text(p: Path, cache_dir: Path) -> str:
    """Public accessor for the cached text of a file (extracts if missing)."""
    return _get_text(p, cache_dir)


def is_scanned(p: Path) -> bool:
    with _cache_lock:
        return str(p.resolve()) in _scanned


def clear_cache() -> None:
    with _cache_lock:
        _text_cache.clear()
        _skipped.clear()
        _scanned.clear()


# ---------- background prebuild & disk persistence ----------

_prebuild_status: dict = {
    "running": False, "total": 0, "done": 0, "current": None,
    "started_at": None, "finished_at": None, "errors": 0,
}


def prebuild_status() -> dict:
    s = dict(_prebuild_status)
    s.update(index_stats())
    return s


def prebuild(root: Path, cache_dir: Path,
             should_continue: Callable[[], bool] | None = None,
             checkpoint: Callable[[], None] | None = None,
             checkpoint_every: int = 30,
             checkpoint_interval: float = 30.0) -> int:
    """Walk root, extract text for all files, populate the in-memory cache.

    `should_continue` is consulted periodically to allow cancellation when
    the root directory changes mid-run.

    `checkpoint` is invoked every `checkpoint_every` files OR every
    `checkpoint_interval` seconds, whichever comes first — for persisting
    partial progress to disk so a Ctrl+C doesn't lose the work.

    Returns the number of files indexed.
    """
    _prebuild_status.update(
        running=True, total=0, done=0, current=None,
        started_at=time.time(), finished_at=None, errors=0,
    )
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if should_continue and not should_continue():
            break
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
        if Path(dirpath).resolve() == cache_dir.resolve():
            dirnames[:] = []
            continue
        for name in filenames:
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            ext = p.suffix.lower()
            if ext in _TEXT_EXTS or ext == ".pdf" or ext in converter.OFFICE_EXTS:
                paths.append(p)

    _prebuild_status["total"] = len(paths)
    indexed = 0
    last_ckpt_time = time.time()
    last_ckpt_done = 0
    for p in paths:
        if should_continue and not should_continue():
            break
        _prebuild_status["current"] = p.name
        try:
            _get_text(p, cache_dir)
            indexed += 1
        except Exception:
            _prebuild_status["errors"] += 1
        _prebuild_status["done"] += 1

        if checkpoint:
            now = time.time()
            if (_prebuild_status["done"] - last_ckpt_done >= checkpoint_every
                    or now - last_ckpt_time >= checkpoint_interval):
                try:
                    checkpoint()
                except Exception:
                    pass
                last_ckpt_done = _prebuild_status["done"]
                last_ckpt_time = now

    if checkpoint:
        try: checkpoint()
        except Exception: pass

    _prebuild_status["running"] = False
    _prebuild_status["current"] = None
    _prebuild_status["finished_at"] = time.time()
    return indexed


def _clean_utf8_text(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def save_index(index_path: Path) -> bool:
    """Persist the text cache to disk. Best-effort; returns success bool."""
    from src.backend.infra.safeio import atomic_write_json
    try:
        # Snapshot dictionaries under lock — iteration outside the lock
        with _cache_lock:
            text_cache_snapshot = dict(_text_cache)
            skipped_snapshot = dict(_skipped)

        payload = {
            "version": 1,
            "files": {
                k: {"mtime": v[0], "text": _clean_utf8_text(v[1])}
                for k, v in text_cache_snapshot.items()
            },
            "skipped": {
                k: _clean_utf8_text(v)
                for k, v in skipped_snapshot.items()
            },
            "saved_at": time.time(),
        }

        atomic_write_json(index_path, payload)
        return True
    except Exception as e:
        log.warning("save_index failed: %s", e)
        return False


def load_index(index_path: Path) -> int:
    """Restore the text cache from disk. Drops entries whose source file has
    changed mtime. Returns number of entries loaded."""
    from src.backend.infra.safeio import read_json
    payload = read_json(index_path, default=None)
    if not isinstance(payload, dict):
        return 0
    files = payload.get("files") or {}
    loaded = 0
    with _cache_lock:
        for abs_path, entry in files.items():
            try:
                if Path(abs_path).stat().st_mtime != entry.get("mtime"):
                    continue
            except OSError:
                continue
            _text_cache[abs_path] = (entry["mtime"], entry.get("text", ""))
            loaded += 1
        for k, v in (payload.get("skipped") or {}).items():
            _skipped[k] = v
    return loaded
