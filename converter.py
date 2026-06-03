"""File type dispatch and LibreOffice conversion."""
from __future__ import annotations

import asyncio
import hashlib
import os
import posixpath
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import markdown as md_lib

OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"}
IMAGE_EXTS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp", ".svg": "image/svg+xml"}
TEXT_EXTS = {".txt", ".log", ".csv"}


def find_soffice() -> Optional[str]:
    """Locate the LibreOffice executable."""
    env = os.environ.get("SOFFICE_PATH")
    if env and os.path.exists(env):
        return env
    in_path = shutil.which("soffice") or shutil.which("soffice.exe")
    if in_path:
        return in_path
    candidates = [
        r"D:\software\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _cache_key(src: Path) -> str:
    st = src.stat()
    raw = f"{src.resolve()}|{int(st.st_mtime)}|{st.st_size}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# Per-key locks so concurrent requests for the same file de-dupe the work.
_conv_locks: dict[str, asyncio.Lock] = {}
_conv_locks_guard = asyncio.Lock()


async def _get_lock(key: str) -> asyncio.Lock:
    async with _conv_locks_guard:
        lock = _conv_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _conv_locks[key] = lock
        return lock


_FAIL_CACHE_TTL = 24 * 3600  # remember a failure for 24h


async def office_to_pdf(src: Path, cache_dir: Path,
                         force: bool = False) -> Path:
    """Convert an office document to PDF via LibreOffice, with caching + dedup.

    Concurrent requests for the same file wait on a shared lock; the second
    arrival sees the cached PDF the first one just produced.

    If a prior conversion failed recently, raises immediately with the cached
    error (use force=True to retry).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(src)
    out_pdf = cache_dir / f"{key}.pdf"
    err_marker = cache_dir / f"{key}.err"

    if out_pdf.exists() and out_pdf.stat().st_size > 0:
        # touch for LRU eviction
        try:
            os.utime(out_pdf, None)
        except OSError:
            pass
        return out_pdf

    if not force and err_marker.exists():
        try:
            if time.time() - err_marker.stat().st_mtime < _FAIL_CACHE_TTL:
                msg = err_marker.read_text(encoding="utf-8", errors="ignore")
                raise RuntimeError(
                    f"上次转换失败（已缓存 24h，可手动删除 cache/{err_marker.name} 重试）: {msg}"
                )
        except OSError:
            pass

    lock = await _get_lock(key)
    async with lock:
        # Re-check after acquiring: another coroutine may have just finished it.
        if out_pdf.exists() and out_pdf.stat().st_size > 0:
            return out_pdf

        soffice = find_soffice()
        if not soffice:
            raise RuntimeError(
                "未检测到 LibreOffice。请安装后重试：https://www.libreoffice.org/download/download/"
            )

        def _record_failure(msg: str) -> None:
            try:
                err_marker.write_text(msg, encoding="utf-8")
            except OSError:
                pass

        with tempfile.TemporaryDirectory(prefix="lo_") as tmpdir:
            profile_dir = Path(tmpdir) / f"profile_{uuid.uuid4().hex}"
            out_dir = Path(tmpdir) / "out"
            out_dir.mkdir()
            profile_uri = profile_dir.as_uri()

            cmd = [
                soffice,
                f"-env:UserInstallation={profile_uri}",
                "--headless",
                "--norestore",
                "--nofirststartwizard",
                "--convert-to", "pdf",
                "--outdir", str(out_dir),
                str(src.resolve()),
            ]
            # Strip Python-related env vars: LibreOffice ships its own embedded
            # Python; our parent's PYTHONHOME/PATH would break it.
            clean_env = {
                k: v for k, v in os.environ.items()
                if not k.startswith("PYTHON")
                and k not in {"VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"}
            }

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=180
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                msg = "LibreOffice 转换超时（>180s）"
                _record_failure(msg)
                raise RuntimeError(msg)

            if proc.returncode != 0:
                stderr = stderr_b.decode("utf-8", errors="ignore")
                stdout = stdout_b.decode("utf-8", errors="ignore")
                msg = f"LibreOffice 转换失败 (rc={proc.returncode}): {stderr or stdout}"
                _record_failure(msg)
                raise RuntimeError(msg)
            produced = list(out_dir.glob("*.pdf"))
            if not produced:
                msg = "LibreOffice 未生成 PDF 文件"
                _record_failure(msg)
                raise RuntimeError(msg)
            shutil.move(str(produced[0]), out_pdf)
            # success — drop any stale failure marker
            try:
                err_marker.unlink()
            except OSError:
                pass
        return out_pdf


_HTML_TPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title>
<base target="_top">
<style>
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 860px; margin: 24px auto; padding: 0 24px; line-height: 1.7; color: #222; }}
pre {{ background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }}
code {{ background: #f6f8fa; padding: 2px 5px; border-radius: 4px; }}
pre code {{ background: transparent; padding: 0; }}
table {{ border-collapse: collapse; margin: 12px 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; }}
blockquote {{ border-left: 4px solid #ddd; padding: 0 12px; color: #666; margin: 12px 0; }}
img {{ max-width: 100%; }}
h1, h2, h3 {{ border-bottom: 1px solid #eee; padding-bottom: 4px; }}
a {{ color: #2d6cdf; }}
</style></head><body>{body}</body></html>
"""


# Match src="..." or href="..." on <img> and <a> tags
_REL_ATTR = re.compile(
    r"""(<(?:img|a)\b[^>]*?\b(?:src|href)\s*=\s*['"])([^'"]+)(['"])""",
    re.IGNORECASE,
)


def _rewrite_relative_urls(html: str, md_parent_rel: str) -> str:
    """Rewrite relative img src / a href to /api/raw URLs under ROOT."""
    def repl(m: re.Match) -> str:
        prefix, url, suffix = m.group(1), m.group(2), m.group(3)
        # Skip absolute / protocol / anchors / already-served / data
        if re.match(r"^(?:[a-z]+:|//|#|/api/|/static/|data:)", url, re.I):
            return m.group(0)
        # join with md's parent directory (posix style, relative to ROOT)
        joined = posixpath.normpath(posixpath.join(md_parent_rel or ".", url))
        if joined.startswith("..") or joined.startswith("/"):
            return m.group(0)  # outside root — leave alone
        new_url = "/api/raw?path=" + quote(joined, safe="/")
        return f"{prefix}{new_url}{suffix}"
    return _REL_ATTR.sub(repl, html)


def render_markdown(src: Path, root: Path) -> str:
    text = src.read_text(encoding="utf-8", errors="replace")
    html = md_lib.markdown(
        text,
        extensions=["fenced_code", "tables", "toc", "codehilite", "sane_lists"],
        extension_configs={"codehilite": {"guess_lang": False, "noclasses": True}},
    )
    try:
        md_parent_rel = src.parent.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        md_parent_rel = ""
    html = _rewrite_relative_urls(html, md_parent_rel)
    return _HTML_TPL.format(title=src.name, body=html)


def render_text(src: Path) -> str:
    text = src.read_text(encoding="utf-8", errors="replace")
    escaped = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return _HTML_TPL.format(title=src.name, body=f"<pre>{escaped}</pre>")


def classify(src: Path) -> str:
    """Return logical type: pdf | office | markdown | text | image | unsupported."""
    ext = src.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".md":
        return "markdown"
    if ext in OFFICE_EXTS:
        return "office"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in TEXT_EXTS:
        return "text"
    return "unsupported"


def image_mime(src: Path) -> str:
    return IMAGE_EXTS.get(src.suffix.lower(), "application/octet-stream")


# ---------- cache management ----------

def cache_stats(cache_dir: Path) -> dict:
    if not cache_dir.exists():
        return {"files": 0, "bytes": 0}
    files = list(cache_dir.glob("*.pdf"))
    total = sum(f.stat().st_size for f in files)
    return {"files": len(files), "bytes": total}


def cleanup_cache(cache_dir: Path, max_age_days: int = 30,
                  max_total_bytes: int = 2 * 1024 * 1024 * 1024) -> dict:
    """Delete cache entries older than max_age_days; then trim to size cap (LRU by atime).

    Also removes stale .err markers older than the negative-cache TTL.
    """
    if not cache_dir.exists():
        return {"removed": 0, "kept": 0, "bytes": 0}

    now = time.time()
    # purge expired .err markers
    for ef in cache_dir.glob("*.err"):
        try:
            if now - ef.stat().st_mtime > _FAIL_CACHE_TTL:
                ef.unlink()
        except OSError:
            pass

    cutoff = now - max_age_days * 86400
    entries = []
    removed = 0
    for f in cache_dir.glob("*.pdf"):
        try:
            st = f.stat()
        except OSError:
            continue
        atime = max(st.st_atime, st.st_mtime)
        if atime < cutoff:
            try:
                f.unlink()
                removed += 1
                continue
            except OSError:
                pass
        entries.append((atime, st.st_size, f))

    # size-cap pass
    entries.sort()  # oldest atime first
    total = sum(e[1] for e in entries)
    i = 0
    while total > max_total_bytes and i < len(entries):
        _, size, f = entries[i]
        try:
            f.unlink()
            total -= size
            removed += 1
        except OSError:
            pass
        i += 1

    kept = max(len(entries) - i, 0)
    return {"removed": removed, "kept": kept, "bytes": total}
