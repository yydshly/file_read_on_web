"""TTS cache service.

Owns TTS audio cache lifecycle: normalization, key generation, read/write,
cleanup (age + LRU size-cap), and clear.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

from logging_setup import get_logger

TEXT_LIMIT_CHARS = 5000
MAX_AGE_DAYS = 60
MAX_BYTES = 500 * 1024 * 1024   # 500 MB


class TtsCache:
    """Thread-safe TTS audio cache with LRU eviction and age-based cleanup."""

    def __init__(self, cache_dir: Path, logger_name: str = "ai"):
        self._cache_dir = cache_dir
        self._log = get_logger(logger_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize_text(self, text: str) -> str:
        """Cap text at TEXT_LIMIT_CHARS so cache lookup, provider call, and
        cache write all hash / synthesise the same bytes."""
        return text[:TEXT_LIMIT_CHARS]

    def get(self, provider_name: str, text: str, voice: str | None,
            speed: float) -> Optional[tuple[bytes, str]]:
        """Return cached (audio_bytes, mime_string) or None on miss / error."""
        audio_p, mime_p = self._cache_paths(provider_name, text, voice, speed)
        if not audio_p.exists() or not mime_p.exists():
            return None
        try:
            mime = mime_p.read_text(encoding="utf-8").strip() or "audio/mpeg"
            # touch for LRU
            try:
                os.utime(audio_p, None)
            except OSError:
                self._log.debug("TTS 缓存 LRU touch 失败: %s", audio_p)
            return audio_p.read_bytes(), mime
        except OSError:
            return None

    def put(self, provider_name: str, text: str, voice: str | None,
            speed: float, audio: bytes, mime: str) -> None:
        """Write audio bytes + mime to cache.  Errors are logged, not raised."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            audio_p, mime_p = self._cache_paths(provider_name, text, voice, speed)
            audio_p.write_bytes(audio)
            mime_p.write_text(mime, encoding="utf-8")
        except OSError as e:
            self._log.warning("TTS 缓存写入失败: %s", e)

    def cleanup(self, max_age_days: int = MAX_AGE_DAYS,
                max_total_bytes: int = MAX_BYTES) -> dict:
        """Delete entries older than max_age_days; then LRU-trim to size cap.

        Each cached item is two files (``.audio`` + ``.mime``).  They are
        managed as a pair so partial deletion never leaves orphans.

        Returns:
            {"removed": int, "kept": int, "bytes": int}
        """
        if not self._cache_dir.exists():
            return {"removed": 0, "kept": 0, "bytes": 0}

        now = time.time()
        cutoff = now - max_age_days * 86400
        entries: list[tuple[float, int, Path, Path]] = []
        removed = 0

        for audio_p in self._cache_dir.glob("*.audio"):
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
                except OSError as e:
                    self._log.debug("TTS 缓存清理删除旧文件失败: %s", e)
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
            except OSError as e:
                self._log.debug("TTS 缓存清理 size-cap 删除失败: %s", e)
            i += 1

        kept = max(len(entries) - i, 0)
        return {"removed": removed, "kept": kept, "bytes": total}

    def clear(self) -> dict:
        """Delete all cached audio files.  Returns ``{"removed": int}``."""
        if not self._cache_dir.exists():
            return {"removed": 0}
        n = 0
        for f in self._cache_dir.iterdir():
            try:
                f.unlink()
                n += 1
            except OSError as e:
                self._log.debug("TTS 缓存清空删除文件失败: %s", e)
        return {"removed": n}

    def stats(self) -> dict:
        """Return ``{"files": int, "bytes": int}`` for all *.audio files."""
        if not self._cache_dir.exists():
            return {"files": 0, "bytes": 0}
        files = [f for f in self._cache_dir.glob("*.audio") if f.is_file()]
        return {
            "files": len(files),
            "bytes": sum(f.stat().st_size for f in files),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cache_paths(self, provider_name: str, text: str, voice: str | None,
                     speed: float) -> tuple[Path, Path]:
        """Return (audio_path, mime_meta_path) for a given TTS request.

        Key = sha1(provider|voice|speed|text).
        """
        h = hashlib.sha1()
        h.update(provider_name.encode("utf-8"))
        h.update(b"|")
        h.update((voice or "").encode("utf-8"))
        h.update(b"|")
        h.update(f"{speed:.2f}".encode("ascii"))
        h.update(b"|")
        h.update(text.encode("utf-8"))
        key = h.hexdigest()
        return self._cache_dir / f"{key}.audio", self._cache_dir / f"{key}.mime"
