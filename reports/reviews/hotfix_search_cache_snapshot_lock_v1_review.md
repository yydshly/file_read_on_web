# Review: HOTFIX-SEARCH-CACHE-SNAPSHOT-LOCK-V1

## Summary

Fixed the search cache concurrency bug `"dictionary changed size during iteration"` in `src/backend/services/search.py` by applying consistent locking and snapshot isolation to all mutable dictionary/set access.

---

## Baseline

```
commit  0fcd7cf Split search routes
branch  main
origin  https://github.com/yydshly/file_read_on_web.git
```

---

## Problem Confirmed

The `save_index()` function iterated `_text_cache.items()` and `_skipped.items()` directly while other threads could mutate those structures, causing `"dictionary changed size during iteration"` errors.

---

## Root Cause

Three separate concurrency violations:

1. **`save_index()`** iterated live mutable dicts — `_text_cache` and `_skipped` — without holding the lock or first snapshotting.
2. **`_get_text()`** read and wrote `_text_cache` and `_scanned` without any locking.
3. **`_extract_pdf()`** wrote to `_skipped` without locking.
4. **`index_stats()`, `skipped_files()`, `scanned_files()`, `is_scanned()`** read live mutable state without locks.

---

## Changes

### Fix 1: Lock-protected mutation helpers

Added `_set_skipped(abs_key, reason)` and `_mark_scanned(abs_key, scanned)` that hold `_cache_lock` for the duration of each write.

Replaced all direct writes:
- `_skipped[str(p.resolve())] = ...` → `_set_skipped(...)`
- `_scanned.add(...)` / `_scanned.discard(...)` → `_mark_scanned(...)`

Also applied to `_extract_pdf()` which was writing to `_skipped` without locking.

### Fix 2: Double-check locking in `_get_text()`

Rewrote `_get_text()` to use the classic double-check locking pattern:

1. Fast path: read `_text_cache` under `_cache_lock` — return if mtime matches.
2. Slow path: extract text **outside** the lock (can be slow for PDFs).
3. Re-check mtime to detect concurrent file changes.
4. Write to `_text_cache` under `_cache_lock`, with a second double-check to avoid overwriting a concurrent cache entry.

Scanned-PDF detection now reads `_skipped` under lock (`is_skipped` snapshot) before calling `_mark_scanned()`.

### Fix 3: Snapshot in `save_index()`

`save_index()` now:
1. Acquires `_cache_lock` and copies both `_text_cache` and `_skipped` into local snapshots.
2. Releases the lock immediately.
3. Iterates only the snapshots to build the payload.
4. Writes JSON **outside** the lock.

This eliminates all iteration over live mutable structures while holding the lock.

### Fix 4: Lock-protected read-only accessors

- `index_stats()` — snapshots all three collections under lock, computes stats from snapshots.
- `skipped_files()` — returns `dict(_skipped)` under lock.
- `scanned_files(root)` — copies `_scanned` set under lock, iterates the snapshot.
- `is_scanned(p)` — checks membership under lock.

---

## Locking Design

| Operation | Lock held? | Notes |
|-----------|-----------|-------|
| `_set_skipped()` | ✅ full | writes to `_skipped` |
| `_mark_scanned()` | ✅ full | writes to `_scanned` |
| `_get_text()` fast path | ✅ brief | dict lookup only |
| `_get_text()` extraction | ❌ | CPU-bound PDF/text extraction |
| `_get_text()` cache write | ✅ full | double-check pattern |
| `save_index()` snapshot | ✅ full | only copies dicts |
| `save_index()` payload build | ❌ | iterates snapshots |
| `index_stats()` | ✅ full | copies all collections |
| `skipped_files()` | ✅ full | returns dict copy |
| `scanned_files()` | ✅ full | copies set |
| `is_scanned()` | ✅ full | membership check |
| `clear_cache()` | ✅ full | clears all |

---

## Snapshot Design

- `text_cache_snapshot = dict(_text_cache)` — shallow copy of dict structure
- `skipped_snapshot = dict(_skipped)` — shallow copy
- `scanned_snapshot = list(_scanned)` — snapshot of set as list for safe iteration

All snapshots are created under lock and iterated outside the lock to minimize lock hold time.

---

## API Compatibility

All public function signatures and return types are unchanged:

| Function | Return type | Changed? |
|----------|-------------|----------|
| `search()` | `list[dict]` | No |
| `prebuild()` | `int` | No |
| `save_index()` | `bool` | No |
| `load_index()` | `int` | No |
| `index_stats()` | `dict` | No |
| `skipped_files()` | `dict` | No |
| `scanned_files()` | `list[str]` | No |
| `get_indexed_text()` | `str` | No |
| `is_scanned()` | `bool` | No |
| `clear_cache()` | `None` | No |

---

## Concurrency Stress Result

```
SEARCH_CACHE_CONCURRENCY_PASS
```

4 search threads + 1 save thread, 200 files, 80 save operations — zero errors. Confirms the snapshot pattern eliminates the dictionary iteration crash.

---

## Prebuild Checkpoint Result

```
SEARCH_CACHE_PREBUILD_CHECKPOINT_PASS
```

40 files indexed, checkpoint called ≥1 time during prebuild, index file saved successfully.

---

## Dev Smoke

```
/api/search: OK count=20
/api/search/rebuild: OK
SEARCH_CACHE_DEV_SMOKE_PASS
Shutdown: {'ok': True}
```

No `save_index failed: dictionary changed size during iteration` warnings observed after the fix.

---

## Forbidden Changes Review

| Item | Status |
|------|--------|
| `server.py` unchanged | PASS |
| `src/backend/routes/**` unchanged | PASS |
| `src/backend/services/converter.py` unchanged | PASS |
| `src/backend/infra/**` unchanged | PASS |
| Search algorithm remains substring-based | PASS |
| PDF page cap remains 200 | PASS |
| Text length cap remains 2MB | PASS |
| Scanned threshold remains 100 chars | PASS |
| Search response shape unchanged | PASS |
| Prebuild behavior unchanged | PASS |
| Checkpoint frequency unchanged | PASS |
| `load_index`/`save_index` format unchanged | PASS |

---

## Known Issues

- Search algorithm remains substring-based (no change)
- `/api/tree` recursive default remains unchanged (unrelated)
- Lifecycle extraction remains deferred (not in scope)
- Prompt caching remains deferred (not in scope)
- `save_index` still uses best-effort error handling with warning log (preserved)

---

## Decision

**PASS**

All validations passed:
- `python -m compileall .` — clean
- `SEARCH_CACHE_IMPORT_PASS` — pass
- `SEARCH_CACHE_CONTENT_PASS` — pass
- `SEARCH_CACHE_API_PRESERVATION_PASS` — pass
- `SEARCH_CACHE_CONCURRENCY_PASS` — pass (4+1 threads, 200 files, 80 saves)
- `SEARCH_CACHE_PREBUILD_CHECKPOINT_PASS` — pass
- `SEARCH_CACHE_DEV_SMOKE_PASS` — pass
- Only `src/backend/services/search.py` modified
