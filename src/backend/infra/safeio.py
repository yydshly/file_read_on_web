"""Atomic JSON IO with a single rolling backup.

Centralised so config / annotations / search_index all share the same
robustness story: write to a temp file, fsync, replace; before each write,
copy the previous good file to ``<name>.bak``.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, keep_backup: bool = True) -> None:
    """Write ``data`` to ``path`` atomically.

    1. If ``path`` exists, copy it to ``path.bak`` first (rolling 1-deep backup).
    2. Write to ``path.tmp`` and ``os.replace`` to ``path``.

    Raises ``OSError`` on disk problems; callers should decide whether to
    surface or swallow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if keep_backup and path.exists():
        try:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        except OSError:
            # backup failure shouldn't block the primary write
            pass

    tmp = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def read_json(path: Path, default: Any = None, *, try_backup: bool = True) -> Any:
    """Read JSON; fall back to ``.bak`` on parse error."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if try_backup:
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            try:
                return json.loads(backup.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
    return default
