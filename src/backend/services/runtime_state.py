"""Runtime state persistence service.

Owns state.json loading, debounced saving, force flush, and legacy config
migration.  config.json is read-only at runtime; this module never writes it.

Schema (state.json):
    {
        "last_root": "...",           # absolute path string
        "last_files": {               # keyed by _root_key(root)
            "<root_key>": "<relative path>"
        }
    }
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Optional

from src.backend.infra.safeio import atomic_write_json, read_json
from src.backend.infra.logging_setup import get_logger

_STATE_DEBOUNCE_SECONDS = 0.5


class RuntimeStateStore:
    """Thread-safe, debounced state persistence with legacy config migration."""

    def __init__(self, state_path: Path, config_path: Path, logger_name: str = "browse"):
        self._state_path = state_path
        self._config_path = config_path
        self._log = get_logger(logger_name)

        self._lock = threading.Lock()
        self._cache: Optional[dict] = None
        self._dirty = False
        self._timer: Optional[threading.Timer] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """Return the cached state dict, loading lazily from disk once."""
        with self._lock:
            if self._cache is None:
                d = read_json(self._state_path, default={})
                self._cache = d if isinstance(d, dict) else {}
            return self._cache

    def flush(self, force: bool = False) -> None:
        """Write the in-memory state to disk if dirty.  Safe to call from
        any thread (including atexit / signal handlers)."""
        with self._lock:
            if self._cache is None or (not self._dirty and not force):
                return
            snapshot = deepcopy(self._cache)
            self._dirty = False
        try:
            atomic_write_json(self._state_path, snapshot)
        except Exception as e:
            # Re-mark dirty so the next mutation triggers another attempt.
            with self._lock:
                self._dirty = True
            try:
                self._log.warning("state flush failed: %s", e)
            except Exception:
                pass

    def migrate_legacy_config(self) -> None:
        """Import legacy ``last_root`` / ``last_files`` keys from ``config.json``
        into the runtime-managed ``state.json``.

        Migration is **state-only** — it never writes ``config.json``.
        It runs only when state.json does not yet exist.
        On failure it leaves config.json untouched so the next startup can retry.
        """
        if self._state_path.exists():
            return
        cfg = read_json(self._config_path, default={})
        if not isinstance(cfg, dict):
            return

        # Read (do NOT mutate) legacy keys from cfg.
        moved: dict = {}
        if "last_root" in cfg:
            moved["last_root"] = cfg["last_root"]
        if "last_files" in cfg:
            moved["last_files"] = cfg["last_files"]
        if not moved:
            return

        # Stage state in memory + schedule debounced flush, then force flush
        # so the migration is durable before we report success.
        self._cache = moved
        self._dirty = True
        self._schedule_flush()
        self.flush(force=True)

        if self._state_path.exists():
            self._log.info(
                "迁移：legacy last_root / last_files 已导入 state.json；"
                "config.json 中旧字段将被忽略"
            )
        else:
            self._log.warning(
                "迁移：state.json 落盘失败，config.json 保持不变以便下次启动重试"
            )

    def get_last_root(self) -> Optional[str]:
        """Return the cached last_root string, or None."""
        if self._cache is None:
            self.load()
        with self._lock:
            state = self._cache if self._cache is not None else {}
            return state.get("last_root")

    def set_last_root(self, root: Path) -> None:
        """Set last_root in memory and schedule a debounced disk flush."""
        if self._cache is None:
            self.load()
        key = self._root_key(root)
        with self._lock:
            self._cache["last_root"] = key  # type: ignore[index]
            self._dirty = True
        self._schedule_flush()

    def get_last_file(self, root: Path) -> Optional[str]:
        """Return the cached last_file for ``root``, or None."""
        if self._cache is None:
            self.load()
        key = self._root_key(root)
        with self._lock:
            state = self._cache if self._cache is not None else {}
            return (state.get("last_files") or {}).get(key)

    def set_last_file(self, root: Path, rel_path: str) -> None:
        """Atomically update last_files[root] + last_root in memory, then
        schedule a debounced disk flush."""
        if self._cache is None:
            self.load()
        key = self._root_key(root)
        with self._lock:
            last_files = self._cache.setdefault("last_files", {})  # type: ignore[union-attr]
            last_files[key] = rel_path
            self._cache["last_root"] = key  # type: ignore[index]
            self._dirty = True
        self._schedule_flush()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _root_key(root: Path) -> str:
        return str(root.resolve()).replace("\\", "/")

    def _schedule_flush(self) -> None:
        """Debounce: arm a single-shot timer; rapid calls collapse to one write."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(_STATE_DEBOUNCE_SECONDS, self.flush)
            self._timer.daemon = True
            self._timer.start()
