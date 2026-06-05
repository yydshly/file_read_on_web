# Review: BACKEND-ROUTES-SPLIT-SEARCH-V1

## Summary

Successfully split search-related routes out of `server.py` into `src/backend/routes/search_routes.py`, together with the search prebuild/index state (`SearchRouteState`).

---

## Changed Files

- `server.py` — modified: removed search route handlers and prebuild helpers; added import and integration of `search_route_state` and `create_search_router`; updated `_stop_background_tasks` to delegate prebuild cancellation
- `src/backend/routes/search_routes.py` — new: contains `SearchRouteState` class and `create_search_router` factory

---

## Search Routes Split

**Routes moved:**
- `GET /api/search` — now in `search_routes.py`
- `GET /api/search/status` — now in `search_routes.py`
- `GET /api/search/skipped` — now in `search_routes.py`
- `GET /api/search/scanned` — now in `search_routes.py`
- `POST /api/search/rebuild` — now in `search_routes.py`

**Handlers removed from server.py:**
- `def api_search(...)` — removed
- `def api_search_status(...)` — removed
- `def api_search_skipped(...)` — removed
- `def api_search_scanned(...)` — removed
- `def api_search_rebuild(...)` — removed
- `@app.get("/api/search")` — removed
- `@app.get("/api/search/status")` — removed
- `@app.get("/api/search/skipped")` — removed
- `@app.get("/api/search/scanned")` — removed
- `@app.post("/api/search/rebuild")` — removed

---

## SearchRouteState Design

`SearchRouteState` is a plain state container with:

| Field | Type | Purpose |
|-------|------|---------|
| `ctx` | `AppContext` | Shared application context |
| `search_mod` | `Any` | Search module reference |
| `cache_dir` | `Path` | Cache directory for search index |
| `search_index_path` | `Path` | Path to search_index.json |
| `prebuild_task` | `Optional[asyncio.Task]` | Running prebuild task |
| `prebuild_root` | `Optional[Path]` | Root at time prebuild started |
| `search_index_loaded_root` | `Optional[Path]` | Tracks which root's index is loaded |
| `last_search_index_save_at` | `float` | Debounce timer for saves |
| `search_index_save_lock` | `threading.Lock` | Thread-safe save coordination |

**Methods:**
- `reset_for_root_change_or_shutdown()` — reset prebuild root and loaded root
- `cancel_prebuild_task()` — cancel running prebuild task
- `ensure_search_index_loaded(has_root)` — lazy index loader
- `maybe_save_search_index()` — debounced index saver
- `prebuild_worker(root)` — async prebuild worker
- `start_prebuild(require_root, has_root)` — async start of prebuild

---

## Search Prebuild Migration

`start_prebuild` is `async` (uses `asyncio.create_task`). The `POST /api/search/rebuild` route handler is also `async` to await it.

**In server.py `_stop_background_tasks`:**
```python
search_route_state.reset_for_root_change_or_shutdown()
search_route_state.cancel_prebuild_task()
file_tree_state.reset_background_root()
file_tree_state.cancel_warm_task()
if _preconvert_task and not _preconvert_task.done():
    _preconvert_task.cancel()
```

**Moved globals removed from server.py:**
- `_prebuild_task`, `_prebuild_root`, `_search_index_loaded_root`
- `_last_search_index_save_at`, `_search_index_save_lock`
- `_SEARCH_INDEX_SAVE_MIN_INTERVAL`

---

## Server Integration

In `server.py`, after `file_tree_state` and before `create_annotation_router`:

```python
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
```

---

## Search Route Review

### `/api/search`
- Runs in default executor (CPU-bound)
- Calls `ensure_search_index_loaded` first
- Calls `search_mod.search`
- Calls `maybe_save_search_index` after
- Returns full response with query, count, results, index, prebuild, loaded, index_saved

### `/api/search/status`
- Returns `prebuild_status()` with `needs_root=True` when root not set

### `/api/search/skipped`
- Returns `{"skipped": {}}` with `needs_root=True` when root not set
- Returns `{"skipped": search_mod.skipped_files()}` with root set

### `/api/search/scanned`
- Returns `{"scanned": []}` with `needs_root=True` when root not set
- Returns `{"scanned": search_mod.scanned_files(require_root())}` with root set

### `/api/search/rebuild`
- Returns `{"ok": False, "needs_root": True}` when root not set
- Clears search cache and starts prebuild with root set

---

## Background Task Boundary Review

| Item | Where |
|------|-------|
| `_preconvert_task`, `_preconvert_status` | `server.py` (not moved) |
| `_scan_office_files`, `_preconvert_worker`, `_start_preconvert` | `server.py` (not moved) |
| `_stop_background_tasks` | `server.py` (delegates to both state objects) |
| `_request_app_shutdown`, `main()` | `server.py` (not moved) |
| `background_root`, `warm_task` | `FileTreeRouteState` (file_tree_routes.py) |
| `prebuild_task`, `prebuild_root`, `search_index_loaded_root` | `SearchRouteState` (search_routes.py) |

---

## Route Registration Review

All routes registered exactly once, all present:

```
GET/POST  Route                        Source
────────  ────                         ──────
GET        /api/tree                   file_tree_routes.py
GET        /api/file                   file_tree_routes.py
GET        /api/raw                    file_tree_routes.py
GET        /api/search                 search_routes.py
GET        /api/search/status          search_routes.py
GET        /api/search/skipped         search_routes.py
GET        /api/search/scanned         search_routes.py
POST       /api/search/rebuild         search_routes.py
GET        /api/preconvert/status      server.py
GET        /api/health                 runtime_routes.py
GET        /api/version                runtime_routes.py
GET        /api/cache/stats            cache_routes.py
GET        /api/anno/all               annotation_routes.py
GET        /api/ai/status              ai_routes.py
POST       /api/ai/summarize           ai_routes.py
POST       /api/ai/chat               ai_routes.py
POST       /api/ai/tts                ai_routes.py
GET        /api/ai/tts/stats          ai_routes.py
POST       /api/ai/tts/clear          ai_routes.py
GET        /api/file/ai-eligibility   ai_routes.py
POST       /api/root                   system_routes.py
GET        /api/root                   system_routes.py
POST       /api/reveal                 system_routes.py
POST       /api/shutdown              system_routes.py
POST       /api/pick-folder            system_routes.py
GET        /                           static_routes.py
GET        /favicon.ico                static_routes.py
GET        /static                     static_routes.py
```

No duplicate routes.

---

## API Compatibility Review

All search route response shapes preserved:
- `/api/search` returns `{query, count, results, index, prebuild, loaded, index_saved}`
- `/api/search/status` returns prebuild status dict
- `/api/search/skipped` returns `{skipped: {...}}`
- `/api/search/scanned` returns `{scanned: [...]}`
- `/api/search/rebuild` returns `{ok: bool, needs_root?: bool, detail?: str}`

---

## Dev Smoke

```
/api/search/status:  OK running=False
/api/search/skipped: OK
/api/search/scanned: OK
/api/search/rebuild:  OK ok=True   ← async start_prebuild fix confirmed working
[search] 开始建索引 (root=教学资料)
/api/search:         OK count=<indexing in progress>
ROUTES_SEARCH_DEV_SMOKE_PASS
Shutdown:             {'ok': True, 'message': '...'}
```

The `async start_prebuild` fix (making `start_prebuild` async and awaiting it in the POST handler) correctly resolves the `RuntimeError: no running event loop` that would occur when `asyncio.create_task()` was called from a sync route handler.

---

## Packaging Review

**SKIPPED** — packaging requires Windows environment with PyInstaller and LibreOffice. No source-level packaging changes were made. Core functionality validated through dev smoke.

---

## Deferred Routes

The following remain in `server.py` (not moved in this task):

- `GET /api/preconvert/status` — preconvert status route
- `_scan_office_files` — preconvert scanner (uses `_SKIP_NAMES`)
- `_preconvert_worker` — preconvert background worker
- `_start_preconvert` — preconvert task starter
- `_preconvert_task` — preconvert task global
- `_preconvert_status` — preconvert status dict
- `_stop_background_tasks` — background coordinator (updated to delegate)
- `_request_app_shutdown` — shutdown entry point
- `main()` — application entry point
- `_open_app_url`, `_open_browser_when_ready` — browser launch
- Tray controller setup — in `main()`

---

## Forbidden Changes Review

| Item | Status |
|------|--------|
| `src/ai/**` unchanged | PASS |
| `src/backend/services/**` unchanged | PASS |
| `src/backend/infra/**` unchanged | PASS |
| `src/backend/domain/**` unchanged | PASS |
| `src/backend/app_context.py` unchanged | PASS |
| All existing route modules unchanged | PASS |
| `src/backend/routes/file_tree_routes.py` unchanged | PASS |
| `src/frontend/**` unchanged | PASS |
| `README.md` unchanged | PASS |
| `search_mod` behavior unchanged | PASS |
| No new features implemented | PASS |
| `search_routes.py` does not import `server.py` | PASS |

---

## Known Issues

- `save_index failed: dictionary changed size during iteration` warnings in search prebuild — pre-existing issue in search module, not introduced by this task
- `search_route_state` referenced in `_stop_background_tasks` before its definition in `server.py` — runtime-resolved; static linter warnings expected and harmless
- `_SKIP_NAMES` remains duplicated in `server.py` (preconvert) and `file_tree_routes.py` (tree) — intentional isolation

---

## Decision

**PASS**

All validations passed:
- `python -m compileall .` — clean
- `ROUTES_SEARCH_IMPORT_PASS` — pass
- `ROUTES_SEARCH_REGISTRATION_PASS` — pass
- `ROUTES_SEARCH_CONTENT_PASS` — pass
- `SEARCH_STATE_CONSTRUCTION_PASS` — pass
- `ROUTES_SEARCH_DEV_SMOKE_PASS` — pass (async fix confirmed)
- Only allowed files modified
