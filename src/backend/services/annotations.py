"""Thread-safe JSON store for per-file annotations (star/tags/notes/...)
grouped by root directory.

Layout on disk:
{
  "roots": {
    "<absolute root path posix>": {
      "files": {
        "<relative file path>": {
          "starred": true,
          "tags": ["重点", "已看"],
          "notes": "...",
          "pdf_last_page": 12,
          "updated_at": 1700000000
        }
      },
      "tag_palette": ["已看", "重点", "待复习"]
    }
  }
}
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy
from pathlib import Path

from src.backend.infra.safeio import atomic_write_json, read_json

_DEFAULT_PALETTE = ["已看", "重点", "待复习"]


def _normroot(root: Path) -> str:
    return str(root.resolve()).replace("\\", "/")


class AnnotationStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()

    # ---------- io ----------

    def _load(self) -> dict:
        d = read_json(self.path, default={"roots": {}})
        if not isinstance(d, dict):
            d = {"roots": {}}
        d.setdefault("roots", {})
        return d

    def _save_locked(self) -> None:
        atomic_write_json(self.path, self._data)

    # ---------- helpers ----------

    def _root_bucket(self, root: Path) -> dict:
        key = _normroot(root)
        bucket = self._data["roots"].setdefault(key, {})
        bucket.setdefault("files", {})
        bucket.setdefault("tag_palette", list(_DEFAULT_PALETTE))
        return bucket

    # ---------- public API ----------

    def all_for_root(self, root: Path) -> dict:
        with self._lock:
            bucket = self._root_bucket(root)
            return deepcopy(bucket)

    def get(self, root: Path, rel_path: str) -> dict:
        with self._lock:
            bucket = self._root_bucket(root)
            return deepcopy(bucket["files"].get(rel_path, {}))

    def patch(self, root: Path, rel_path: str, partial: dict) -> dict:
        """Merge partial into the entry; keys set to None are removed.
        Returns the resulting entry."""
        with self._lock:
            bucket = self._root_bucket(root)
            cur = bucket["files"].setdefault(rel_path, {})
            for k, v in partial.items():
                if v is None or v == "" or v == [] or v == {}:
                    cur.pop(k, None)
                else:
                    cur[k] = v
            if cur:
                cur["updated_at"] = int(time.time())
                bucket["files"][rel_path] = cur
            else:
                bucket["files"].pop(rel_path, None)
            self._save_locked()
            return deepcopy(cur)

    def set_palette(self, root: Path, tags: list[str]) -> list[str]:
        with self._lock:
            bucket = self._root_bucket(root)
            # dedupe, preserve order
            seen = set()
            unique = []
            for t in tags:
                t = (t or "").strip()
                if not t or t in seen:
                    continue
                seen.add(t)
                unique.append(t)
            bucket["tag_palette"] = unique
            self._save_locked()
            return list(unique)

    def rename_path(self, root: Path, old_rel: str, new_rel: str) -> bool:
        """Move annotation entry when a file is renamed/moved (best-effort)."""
        with self._lock:
            bucket = self._root_bucket(root)
            if old_rel in bucket["files"] and new_rel not in bucket["files"]:
                bucket["files"][new_rel] = bucket["files"].pop(old_rel)
                self._save_locked()
                return True
            return False
